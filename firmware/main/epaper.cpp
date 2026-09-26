#include "board.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <initializer_list>

#include "board_profile.h"
#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "esp_check.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

namespace {

constexpr char kTag[] = "inkmate.epaper";
constexpr int kSpiClockHz = 4 * 1000 * 1000;
constexpr std::size_t kFrameBytes = inkmate::board::kDisplayWidth *
                                    inkmate::board::kDisplayHeight / 8;
constexpr TickType_t kBusyTimeout = pdMS_TO_TICKS(10'000);

constexpr std::array<std::uint8_t, 159> kFullRefreshLut{
    0x80, 0x48, 0x40, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x40, 0x48, 0x80, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x80, 0x48, 0x40, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x40, 0x48, 0x80, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x0A, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x08, 0x01, 0x00, 0x08, 0x01,
    0x00, 0x02, 0x0A, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x22, 0x22, 0x22, 0x22, 0x22, 0x22, 0x00, 0x00, 0x00, 0x22, 0x17, 0x41,
    0x00, 0x32, 0x20,
};

#if CONFIG_INKMATE_BOARD_V2
class Epaper {
public:
    esp_err_t initialize() {
        const auto& pins = inkmate::board::kPins;
        gpio_config_t output{};
        output.mode = GPIO_MODE_OUTPUT;
        output.pin_bit_mask = (1ULL << pins.epaper_power) | (1ULL << pins.epaper_reset) |
                              (1ULL << pins.epaper_dc) | (1ULL << pins.epaper_cs);
        ESP_RETURN_ON_ERROR(gpio_config(&output), kTag, "configure output pins");
        gpio_set_level(pins.epaper_power, 1);
        gpio_set_level(pins.epaper_cs, 1);
        gpio_set_level(pins.epaper_reset, 1);
        gpio_set_level(pins.epaper_power, 0);

        gpio_config_t input{};
        input.mode = GPIO_MODE_INPUT;
        input.pin_bit_mask = 1ULL << pins.epaper_busy;
        input.pull_up_en = GPIO_PULLUP_ENABLE;
        ESP_RETURN_ON_ERROR(gpio_config(&input), kTag, "configure busy pin");

        spi_bus_config_t bus{};
        bus.mosi_io_num = pins.epaper_mosi;
        bus.miso_io_num = GPIO_NUM_NC;
        bus.sclk_io_num = pins.epaper_sclk;
        bus.quadwp_io_num = GPIO_NUM_NC;
        bus.quadhd_io_num = GPIO_NUM_NC;
        bus.max_transfer_sz = kFrameBytes;
        ESP_RETURN_ON_ERROR(spi_bus_initialize(SPI2_HOST, &bus, SPI_DMA_CH_AUTO), kTag,
                            "initialize SPI bus");

        spi_device_interface_config_t device{};
        device.clock_speed_hz = kSpiClockHz;
        device.mode = 0;
        device.spics_io_num = GPIO_NUM_NC;
        device.queue_size = 1;
        ESP_RETURN_ON_ERROR(spi_bus_add_device(SPI2_HOST, &device, &spi_), kTag,
                            "attach e-paper SPI device");

        vTaskDelay(pdMS_TO_TICKS(50));
        gpio_set_level(pins.epaper_reset, 0);
        vTaskDelay(pdMS_TO_TICKS(20));
        gpio_set_level(pins.epaper_reset, 1);
        vTaskDelay(pdMS_TO_TICKS(50));

        ESP_RETURN_ON_ERROR(wait_until_idle(), kTag, "wait for panel");
        ESP_RETURN_ON_ERROR(command(0x12), kTag, "reset panel");
        ESP_RETURN_ON_ERROR(wait_until_idle(), kTag, "wait after reset");

        ESP_RETURN_ON_ERROR(command(0x01), kTag, "set driver output");
        ESP_RETURN_ON_ERROR(data({0xC7, 0x00, 0x01}), kTag, "write driver output");
        ESP_RETURN_ON_ERROR(command(0x11), kTag, "set data entry mode");
        ESP_RETURN_ON_ERROR(data({0x01}), kTag, "write data entry mode");
        ESP_RETURN_ON_ERROR(command(0x44), kTag, "set X window");
        ESP_RETURN_ON_ERROR(data({0x00, 0x18}), kTag, "write X window");
        ESP_RETURN_ON_ERROR(command(0x45), kTag, "set Y window");
        ESP_RETURN_ON_ERROR(data({0xC7, 0x00, 0x00, 0x00}), kTag, "write Y window");
        ESP_RETURN_ON_ERROR(command(0x3C), kTag, "set border waveform");
        ESP_RETURN_ON_ERROR(data({0x01}), kTag, "write border waveform");
        ESP_RETURN_ON_ERROR(command(0x18), kTag, "set temperature sensor");
        ESP_RETURN_ON_ERROR(data({0x80}), kTag, "write temperature sensor");
        ESP_RETURN_ON_ERROR(command(0x22), kTag, "load waveform");
        ESP_RETURN_ON_ERROR(data({0xB1}), kTag, "write waveform load");
        ESP_RETURN_ON_ERROR(command(0x20), kTag, "apply waveform");
        ESP_RETURN_ON_ERROR(command(0x4E), kTag, "set X cursor");
        ESP_RETURN_ON_ERROR(data({0x00}), kTag, "write X cursor");
        ESP_RETURN_ON_ERROR(command(0x4F), kTag, "set Y cursor");
        ESP_RETURN_ON_ERROR(data({0xC7, 0x00}), kTag, "write Y cursor");
        ESP_RETURN_ON_ERROR(wait_until_idle(), kTag, "wait before LUT");
        ESP_RETURN_ON_ERROR(command(0x32), kTag, "set LUT");
        ESP_RETURN_ON_ERROR(data(kFullRefreshLut.data(), 153), kTag, "write LUT");
        ESP_RETURN_ON_ERROR(wait_until_idle(), kTag, "wait after LUT");
        ESP_RETURN_ON_ERROR(command(0x3F), kTag, "set LUT option");
        ESP_RETURN_ON_ERROR(data({kFullRefreshLut[153]}), kTag, "write LUT option");
        ESP_RETURN_ON_ERROR(command(0x03), kTag, "set LUT timing");
        ESP_RETURN_ON_ERROR(data({kFullRefreshLut[154]}), kTag, "write LUT timing");
        ESP_RETURN_ON_ERROR(command(0x04), kTag, "set LUT voltage");
        ESP_RETURN_ON_ERROR(data(kFullRefreshLut.data() + 155, 3), kTag, "write LUT voltage");
        ESP_RETURN_ON_ERROR(command(0x2C), kTag, "set LUT VCOM");
        return data({kFullRefreshLut[158]});
    }

    esp_err_t display(const std::array<std::uint8_t, kFrameBytes>& frame) {
        ESP_RETURN_ON_ERROR(command(0x24), kTag, "start frame transfer");
        ESP_RETURN_ON_ERROR(data(frame.data(), frame.size()), kTag, "transfer frame");
        ESP_RETURN_ON_ERROR(command(0x22), kTag, "start refresh");
        ESP_RETURN_ON_ERROR(data({0xC7}), kTag, "write refresh command");
        ESP_RETURN_ON_ERROR(command(0x20), kTag, "refresh panel");
        return wait_until_idle();
    }

    ~Epaper() {
        if (spi_ != nullptr) spi_bus_remove_device(spi_);
        spi_bus_free(SPI2_HOST);
    }

private:
    esp_err_t wait_until_idle() const {
        const TickType_t deadline = xTaskGetTickCount() + kBusyTimeout;
        while (gpio_get_level(inkmate::board::kPins.epaper_busy) != 0) {
            if (xTaskGetTickCount() >= deadline) return ESP_ERR_TIMEOUT;
            vTaskDelay(pdMS_TO_TICKS(5));
        }
        return ESP_OK;
    }

    esp_err_t command(std::uint8_t value) const {
        gpio_set_level(inkmate::board::kPins.epaper_dc, 0);
        return transmit(&value, 1);
    }

    esp_err_t data(std::initializer_list<std::uint8_t> values) const {
        return data(values.begin(), values.size());
    }

    esp_err_t data(const std::uint8_t* values, std::size_t size) const {
        gpio_set_level(inkmate::board::kPins.epaper_dc, 1);
        return transmit(values, size);
    }

    esp_err_t transmit(const std::uint8_t* values, std::size_t size) const {
        gpio_set_level(inkmate::board::kPins.epaper_cs, 0);
        spi_transaction_t transaction{};
        transaction.length = size * 8;
        transaction.tx_buffer = values;
        const esp_err_t result = spi_device_polling_transmit(spi_, &transaction);
        gpio_set_level(inkmate::board::kPins.epaper_cs, 1);
        return result;
    }

    spi_device_handle_t spi_{};
};

[[maybe_unused]] void set_pixel(std::array<std::uint8_t, kFrameBytes>* frame, int x, int y,
                                bool black) {
    if (x < 0 || x >= inkmate::board::kDisplayWidth || y < 0 || y >= inkmate::board::kDisplayHeight) return;
    const std::size_t offset = static_cast<std::size_t>(y) * inkmate::board::kDisplayWidth / 8 + x / 8;
    const std::uint8_t bit = 1U << (7 - (x % 8));
    if (black) (*frame)[offset] &= ~bit;
    else (*frame)[offset] |= bit;
}

[[maybe_unused]] void fill_rect(std::array<std::uint8_t, kFrameBytes>* frame, int x, int y,
                                 int width, int height) {
    for (int row = y; row < y + height; ++row) {
        for (int column = x; column < x + width; ++column) set_pixel(frame, column, row, true);
    }
}
#endif

}  // namespace

namespace inkmate {

namespace {

esp_err_t render_card(Intent intent, const BootReport& report) {
#if !CONFIG_INKMATE_BOARD_V2
    (void)intent;
    (void)report;
    return ESP_ERR_NOT_SUPPORTED;
#else
    static std::array<std::uint8_t, kFrameBytes> frame{};
    frame.fill(0xFF);
    fill_rect(&frame, 8, 8, 184, 8);
    fill_rect(&frame, 8, 184, 184, 8);
    fill_rect(&frame, 8, 8, 8, 184);
    fill_rect(&frame, 184, 8, 8, 184);
    fill_rect(&frame, 48, 42, 104, 18);
    fill_rect(&frame, 80, 80, 40, 40);
    fill_rect(&frame, 36, 144, 128, 12);
    if (report.rtc_detected) fill_rect(&frame, 36, 164, 52, 8);
    if (report.environment_sensor_detected) fill_rect(&frame, 112, 164, 52, 8);
    switch (intent) {
        case Intent::NextCard: fill_rect(&frame, 24, 96, 32, 32); break;
        case Intent::BeginRecording: fill_rect(&frame, 72, 88, 56, 56); break;
        case Intent::SubmitRecording: fill_rect(&frame, 144, 96, 32, 32); break;
        case Intent::ConfirmAction: fill_rect(&frame, 72, 144, 56, 16); break;
        case Intent::CancelAction: fill_rect(&frame, 72, 144, 56, 16); fill_rect(&frame, 88, 128, 24, 48); break;
        case Intent::None: break;
    }

    Epaper panel;
    ESP_RETURN_ON_ERROR(panel.initialize(), kTag, "initialize V2 panel");
    ESP_RETURN_ON_ERROR(panel.display(frame), kTag, "render V2 boot card");
    ESP_LOGI(kTag, "rendered V2 boot card");
    return ESP_OK;
#endif
}

}  // namespace

esp_err_t render_boot_card(const BootReport& report) { return render_card(Intent::None, report); }

esp_err_t render_interaction_card(Intent intent, const BootReport& report) {
    return render_card(intent, report);
}

}  // namespace inkmate
