#include "audio_capture.h"

#include <array>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstring>

#include "audio_codec_if.h"
#include "board_profile.h"
#include "driver/gpio.h"
#include "driver/i2c_master.h"
#include "driver/i2s_std.h"
#include "esp_check.h"
#include "esp_codec_dev.h"
#include "esp_codec_dev_defaults.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "es8311_codec.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "gateway_client.h"

namespace {

#if CONFIG_INKMATE_BOARD_V2
constexpr char kTag[] = "inkmate.audio";
constexpr std::uint32_t kSampleRate = 16'000;
constexpr std::uint32_t kCaptureLimitMs = 10'000;
constexpr std::size_t kWavHeaderBytes = 44;
constexpr std::size_t kMaxPcmBytes = kSampleRate * 2 * kCaptureLimitMs / 1'000;
constexpr std::size_t kMaxWavBytes = kWavHeaderBytes + kMaxPcmBytes;
constexpr std::size_t kReadBytes = 1'024;
constexpr std::uint32_t kNotificationMs = 55;
constexpr std::size_t kNotificationFrames = kSampleRate * kNotificationMs / 1'000;
constexpr float kNotificationAmplitude = 0.015F;

std::atomic_bool capture_requested{false};
std::atomic_bool capture_active{false};

void write_le16(std::uint8_t* output, std::uint16_t value) {
    output[0] = static_cast<std::uint8_t>(value);
    output[1] = static_cast<std::uint8_t>(value >> 8);
}

void write_le32(std::uint8_t* output, std::uint32_t value) {
    output[0] = static_cast<std::uint8_t>(value);
    output[1] = static_cast<std::uint8_t>(value >> 8);
    output[2] = static_cast<std::uint8_t>(value >> 16);
    output[3] = static_cast<std::uint8_t>(value >> 24);
}

void write_wav_header(std::uint8_t* output, std::uint32_t pcm_bytes) {
    std::memcpy(output, "RIFF", 4);
    write_le32(output + 4, 36 + pcm_bytes);
    std::memcpy(output + 8, "WAVEfmt ", 8);
    write_le32(output + 16, 16);
    write_le16(output + 20, 1);
    write_le16(output + 22, 1);
    write_le32(output + 24, kSampleRate);
    write_le32(output + 28, kSampleRate * 2);
    write_le16(output + 32, 2);
    write_le16(output + 34, 16);
    std::memcpy(output + 36, "data", 4);
    write_le32(output + 40, pcm_bytes);
}

struct CaptureResources {
    i2c_master_bus_handle_t i2c{};
    i2s_chan_handle_t tx{};
    i2s_chan_handle_t rx{};
    const audio_codec_ctrl_if_t* control{};
    const audio_codec_data_if_t* data{};
    const audio_codec_gpio_if_t* gpio{};
    const audio_codec_if_t* codec{};
    esp_codec_dev_handle_t device{};
};

struct CaptureTaskContext {
    inkmate::AppState* state;
    inkmate::BootReport report;
};

void release(CaptureResources* resources) {
    if (resources->device != nullptr) {
        esp_codec_dev_close(resources->device);
        esp_codec_dev_delete(resources->device);
    }
    if (resources->codec != nullptr) audio_codec_delete_codec_if(resources->codec);
    if (resources->gpio != nullptr) audio_codec_delete_gpio_if(resources->gpio);
    if (resources->data != nullptr) audio_codec_delete_data_if(resources->data);
    if (resources->control != nullptr) audio_codec_delete_ctrl_if(resources->control);
    if (resources->rx != nullptr) {
        i2s_channel_disable(resources->rx);
        i2s_del_channel(resources->rx);
    }
    if (resources->tx != nullptr) {
        i2s_channel_disable(resources->tx);
        i2s_del_channel(resources->tx);
    }
    if (resources->i2c != nullptr) i2c_del_master_bus(resources->i2c);
}

esp_err_t initialize(CaptureResources* resources, const char** stage) {
    i2c_master_bus_config_t i2c{};
    i2c.i2c_port = I2C_NUM_0;
    i2c.sda_io_num = inkmate::board::kPins.i2c_sda;
    i2c.scl_io_num = inkmate::board::kPins.i2c_scl;
    i2c.clk_source = I2C_CLK_SRC_DEFAULT;
    *stage = "configure codec I2C";
    ESP_RETURN_ON_ERROR(i2c_new_master_bus(&i2c, &resources->i2c), kTag, "configure codec I2C");

    i2s_chan_config_t channel = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_AUTO, I2S_ROLE_MASTER);
    channel.auto_clear = true;
    *stage = "create I2S channels";
    ESP_RETURN_ON_ERROR(i2s_new_channel(&channel, &resources->tx, &resources->rx), kTag, "create I2S channels");
    i2s_std_config_t standard{
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(kSampleRate),
        .slot_cfg = I2S_STD_MSB_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_STEREO),
        .gpio_cfg = {
            .mclk = inkmate::board::kPins.i2s_mclk,
            .bclk = inkmate::board::kPins.i2s_bclk,
            .ws = inkmate::board::kPins.i2s_ws,
            .dout = inkmate::board::kPins.i2s_dout,
            .din = inkmate::board::kPins.i2s_din,
            .invert_flags = {},
        },
    };
    *stage = "configure I2S TX";
    ESP_RETURN_ON_ERROR(i2s_channel_init_std_mode(resources->tx, &standard), kTag, "configure I2S TX");
    *stage = "configure I2S RX";
    ESP_RETURN_ON_ERROR(i2s_channel_init_std_mode(resources->rx, &standard), kTag, "configure I2S RX");
    *stage = "enable I2S TX";
    ESP_RETURN_ON_ERROR(i2s_channel_enable(resources->tx), kTag, "enable I2S TX");
    *stage = "enable I2S RX";
    ESP_RETURN_ON_ERROR(i2s_channel_enable(resources->rx), kTag, "enable I2S RX");

    audio_codec_i2c_cfg_t codec_i2c{
        .port = I2C_NUM_0,
        .addr = inkmate::board::kEs8311CodecAddress,
        .bus_handle = resources->i2c,
        .clock_speed_hz = 100'000,
    };
    resources->control = audio_codec_new_i2c_ctrl(&codec_i2c);
    audio_codec_i2s_cfg_t codec_i2s{
        .port = I2S_NUM_0,
        .rx_handle = resources->rx,
        .tx_handle = resources->tx,
        .clk_src = 0,
    };
    resources->data = audio_codec_new_i2s_data(&codec_i2s);
    resources->gpio = audio_codec_new_gpio();
    if (resources->control == nullptr || resources->data == nullptr || resources->gpio == nullptr) {
        *stage = "create codec interfaces";
        return ESP_ERR_NO_MEM;
    }

    es8311_codec_cfg_t codec{
        .ctrl_if = resources->control,
        .gpio_if = resources->gpio,
        .codec_mode = ESP_CODEC_DEV_WORK_MODE_BOTH,
        .pa_pin = GPIO_NUM_NC,
        .pa_reverted = false,
        .master_mode = false,
        .use_mclk = true,
        .digital_mic = false,
        .invert_mclk = false,
        .invert_sclk = false,
        .hw_gain = {},
        .no_dac_ref = false,
        .mclk_div = 256,
    };
    resources->codec = es8311_codec_new(&codec);
    if (resources->codec == nullptr) {
        *stage = "create ES8311 codec";
        return ESP_ERR_NO_MEM;
    }
    esp_codec_dev_cfg_t device{
        .dev_type = ESP_CODEC_DEV_TYPE_IN_OUT,
        .codec_if = resources->codec,
        .data_if = resources->data,
    };
    resources->device = esp_codec_dev_new(&device);
    if (resources->device == nullptr) {
        *stage = "create codec device";
        return ESP_ERR_NO_MEM;
    }
    esp_codec_dev_sample_info_t format{
        .bits_per_sample = 16,
        .channel = 2,
        .channel_mask = 1,
        .sample_rate = kSampleRate,
        .mclk_multiple = 256,
    };
    if (esp_codec_dev_open(resources->device, &format) != ESP_CODEC_DEV_OK) {
        *stage = "open ES8311";
        return ESP_FAIL;
    }
    if (esp_codec_dev_set_in_gain(resources->device, 30.0F) != ESP_CODEC_DEV_OK) {
        *stage = "set microphone gain";
        return ESP_FAIL;
    }
    return ESP_OK;
}

void play_notification(CaptureResources* resources, bool success) {
    if (resources->device == nullptr) return;
    std::array<std::int16_t, kNotificationFrames * 2> pcm{};
    const float frequency = success ? 1'176.0F : 392.0F;
    constexpr float kPi = 3.14159265358979323846F;
    for (std::size_t frame = 0; frame < kNotificationFrames; ++frame) {
        const float phase = 2.0F * kPi * frequency * static_cast<float>(frame) / static_cast<float>(kSampleRate);
        const auto sample = static_cast<std::int16_t>(std::sin(phase) * kNotificationAmplitude * 32767.0F);
        pcm[frame * 2] = sample;
        pcm[frame * 2 + 1] = sample;
    }
    if (!success) {
        for (std::size_t frame = kNotificationFrames / 2; frame < kNotificationFrames; ++frame) {
            pcm[frame * 2] = static_cast<std::int16_t>(pcm[frame * 2] / 2);
            pcm[frame * 2 + 1] = static_cast<std::int16_t>(pcm[frame * 2 + 1] / 2);
        }
    }
    if (esp_codec_dev_set_out_vol(resources->device, 8) != ESP_CODEC_DEV_OK ||
        esp_codec_dev_write(resources->device, pcm.data(), static_cast<int>(pcm.size() * sizeof(std::int16_t))) != ESP_CODEC_DEV_OK) {
        ESP_LOGW(kTag, "notification audio unavailable");
    }
}

void capture_task(void* argument) {
    auto* context = static_cast<CaptureTaskContext*>(argument);
    auto* state = context->state;
    const inkmate::BootReport report = context->report;
    heap_caps_free(context);
    CaptureResources resources{};
    const char* initialization_stage = "allocate WAV buffer";
    std::uint8_t* wav = static_cast<std::uint8_t*>(heap_caps_malloc(kMaxWavBytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
    ESP_LOGI(kTag, "audio heap: internal=%u psram=%u", static_cast<unsigned>(heap_caps_get_free_size(MALLOC_CAP_INTERNAL)),
             static_cast<unsigned>(heap_caps_get_free_size(MALLOC_CAP_SPIRAM)));
    const esp_err_t initialization_result = wav == nullptr ? ESP_ERR_NO_MEM : initialize(&resources, &initialization_stage);
    if (initialization_result != ESP_OK) {
        ESP_LOGE(kTag, "microphone initialization failed at %s: %s", initialization_stage,
                 esp_err_to_name(initialization_result));
        if (wav != nullptr) heap_caps_free(wav);
        release(&resources);
        state->interaction_complete();
        capture_active.store(false);
        vTaskDelete(nullptr);
        return;
    }

    std::array<std::uint8_t, kReadBytes> chunk{};
    std::size_t pcm_bytes = 0;
    const TickType_t started = xTaskGetTickCount();
    while (capture_requested.load() && pcm_bytes + chunk.size() <= kMaxPcmBytes &&
           xTaskGetTickCount() - started < pdMS_TO_TICKS(kCaptureLimitMs)) {
        if (esp_codec_dev_read(resources.device, chunk.data(), chunk.size()) != ESP_CODEC_DEV_OK) {
            ESP_LOGW(kTag, "microphone read failed");
            break;
        }
        std::memcpy(wav + kWavHeaderBytes + pcm_bytes, chunk.data(), chunk.size());
        pcm_bytes += chunk.size();
    }
    write_wav_header(wav, static_cast<std::uint32_t>(pcm_bytes));
    ESP_LOGI(kTag, "capture complete: pcm_bytes=%u wav_bytes=%u duration_ms=%u", static_cast<unsigned>(pcm_bytes),
             static_cast<unsigned>(pcm_bytes + kWavHeaderBytes),
             static_cast<unsigned>(pcm_bytes * 1'000 / (kSampleRate * 2)));
    if (pcm_bytes != 0) {
        inkmate::GatewayCard card{};
        const esp_err_t submit_result = inkmate::submit_wav_to_gateway(wav, pcm_bytes + kWavHeaderBytes, &card);
        if (submit_result == ESP_OK) {
            const esp_err_t display_result = inkmate::queue_response_card(card.title, card.body, report);
            if (display_result != ESP_OK) ESP_LOGW(kTag, "cannot queue gateway card: %s", esp_err_to_name(display_result));
            play_notification(&resources, !card.is_error);
        } else {
            ESP_LOGW(kTag, "gateway submission failed: %s", esp_err_to_name(submit_result));
            inkmate::queue_response_card("Gateway unavailable", "Audio was not retained. Check Wi-Fi and enrollment.", report);
            play_notification(&resources, false);
        }
    }
    heap_caps_free(wav);
    release(&resources);
    state->interaction_complete();
    capture_active.store(false);
    vTaskDelete(nullptr);
}
#endif

}  // namespace

namespace inkmate {

esp_err_t start_audio_capture(AppState* state, const BootReport& report) {
#if !CONFIG_INKMATE_BOARD_V2
    (void)state;
    (void)report;
    return ESP_ERR_NOT_SUPPORTED;
#else
    if (state == nullptr || !report.pins_verified) return ESP_ERR_INVALID_STATE;
    bool expected = false;
    if (!capture_active.compare_exchange_strong(expected, true)) return ESP_ERR_INVALID_STATE;
    capture_requested.store(true);
    auto* context = static_cast<CaptureTaskContext*>(heap_caps_malloc(sizeof(CaptureTaskContext), MALLOC_CAP_8BIT));
    if (context == nullptr) {
        capture_requested.store(false);
        capture_active.store(false);
        return ESP_ERR_NO_MEM;
    }
    *context = {.state = state, .report = report};
    if (xTaskCreate(capture_task, "inkmate_audio", 8 * 1024, context, 5, nullptr) != pdPASS) {
        heap_caps_free(context);
        capture_requested.store(false);
        capture_active.store(false);
        return ESP_ERR_NO_MEM;
    }
    ESP_LOGI(kTag, "microphone capture started: 16kHz mono PCM, maximum %u ms", kCaptureLimitMs);
    return ESP_OK;
#endif
}

void stop_audio_capture() {
#if CONFIG_INKMATE_BOARD_V2
    capture_requested.store(false);
#endif
}

}  // namespace inkmate
