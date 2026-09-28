#include "board.h"
#include "state_icons.generated.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <initializer_list>
#include <string_view>

#include "board_profile.h"
#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "esp_check.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
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

void draw_line(std::array<std::uint8_t, kFrameBytes>* frame, int x0, int y0, int x1, int y1, int width = 2) {
    const int dx = std::abs(x1 - x0);
    const int sx = x0 < x1 ? 1 : -1;
    const int dy = -std::abs(y1 - y0);
    const int sy = y0 < y1 ? 1 : -1;
    int error = dx + dy;
    for (;;) {
        fill_rect(frame, x0 - width / 2, y0 - width / 2, width, width);
        if (x0 == x1 && y0 == y1) break;
        const int doubled = 2 * error;
        if (doubled >= dy) { error += dy; x0 += sx; }
        if (doubled <= dx) { error += dx; y0 += sy; }
    }
}

void draw_circle(std::array<std::uint8_t, kFrameBytes>* frame, int center_x, int center_y, int radius, int width = 2) {
    int x = radius;
    int y = 0;
    int error = 1 - radius;
    while (x >= y) {
        fill_rect(frame, center_x + x - width / 2, center_y + y - width / 2, width, width);
        fill_rect(frame, center_x + y - width / 2, center_y + x - width / 2, width, width);
        fill_rect(frame, center_x - y - width / 2, center_y + x - width / 2, width, width);
        fill_rect(frame, center_x - x - width / 2, center_y + y - width / 2, width, width);
        fill_rect(frame, center_x - x - width / 2, center_y - y - width / 2, width, width);
        fill_rect(frame, center_x - y - width / 2, center_y - x - width / 2, width, width);
        fill_rect(frame, center_x + y - width / 2, center_y - x - width / 2, width, width);
        fill_rect(frame, center_x + x - width / 2, center_y - y - width / 2, width, width);
        ++y;
        if (error < 0) error += 2 * y + 1;
        else { --x; error += 2 * (y - x + 1); }
    }
}

template <std::size_t Count>
void draw_icon(std::array<std::uint8_t, kFrameBytes>* frame,
               const std::array<inkmate::assets::IconCommand, Count>& commands) {
    for (const auto& command : commands) {
        switch (command.primitive) {
            case inkmate::assets::IconPrimitive::Line:
                draw_line(frame, command.a, command.b, command.c, command.d, command.width);
                break;
            case inkmate::assets::IconPrimitive::Circle:
                draw_circle(frame, command.a, command.b, command.c, command.width);
                break;
            case inkmate::assets::IconPrimitive::Rect:
                fill_rect(frame, command.a, command.b, command.c, command.d);
                break;
            case inkmate::assets::IconPrimitive::Box:
                draw_line(frame, command.a, command.b, command.a + command.c, command.b, command.width);
                draw_line(frame, command.a + command.c, command.b, command.a + command.c, command.b + command.d, command.width);
                draw_line(frame, command.a + command.c, command.b + command.d, command.a, command.b + command.d, command.width);
                draw_line(frame, command.a, command.b + command.d, command.a, command.b, command.width);
                break;
        }
    }
}

void draw_state_icon(std::array<std::uint8_t, kFrameBytes>* frame, inkmate::Intent intent) {
    switch (intent) {
        case inkmate::Intent::BeginRecording: draw_icon(frame, inkmate::assets::kRecording); break;
        case inkmate::Intent::SubmitRecording: draw_icon(frame, inkmate::assets::kSending); break;
        case inkmate::Intent::NextCard: draw_icon(frame, inkmate::assets::kProcessing); break;
        case inkmate::Intent::ConfirmAction: draw_icon(frame, inkmate::assets::kConfirmation); break;
        case inkmate::Intent::CancelAction: draw_icon(frame, inkmate::assets::kCancelled); break;
        case inkmate::Intent::None: draw_icon(frame, inkmate::assets::kReady); break;
    }
}

std::uint16_t glyph(char value) {
    if (value >= 'a' && value <= 'z') value = static_cast<char>(value - 'a' + 'A');
    switch (value) {
        case 'A': return 0b010101111101101; case 'B': return 0b110101110101110;
        case 'C': return 0b011100100100011; case 'D': return 0b110101101101110;
        case 'E': return 0b111100110100111; case 'F': return 0b111100110100100;
        case 'G': return 0b011100101101011; case 'H': return 0b101101111101101;
        case 'I': return 0b111010010010111; case 'J': return 0b001001001101010;
        case 'K': return 0b101101110101101; case 'L': return 0b100100100100111;
        case 'M': return 0b101111111101101; case 'N': return 0b101111111111101;
        case 'O': return 0b010101101101010; case 'P': return 0b110101110100100;
        case 'Q': return 0b010101101111011; case 'R': return 0b110101110101101;
        case 'S': return 0b011100010001110; case 'T': return 0b111010010010010;
        case 'U': return 0b101101101101111; case 'V': return 0b101101101101010;
        case 'W': return 0b101101111111101; case 'X': return 0b101101010101101;
        case 'Y': return 0b101101010010010; case 'Z': return 0b111001010100111;
        case '0': return 0b111101101101111; case '1': return 0b010110010010111;
        case '2': return 0b110001111100111; case '3': return 0b110001110001110;
        case '4': return 0b101101111001001; case '5': return 0b111100110001110;
        case '6': return 0b011100111101111; case '7': return 0b111001010010010;
        case '8': return 0b111101111101111; case '9': return 0b111101111001110;
        case '.': return 0b000000000000010; case ',': return 0b000000000010100;
        case ':': return 0b000010000010000; case '-': return 0b000000111000000;
        case '?': return 0b110001010000010; case '!': return 0b010010010000010;
        case '/': return 0b001001010100100; default: return 0;
    }
}

void draw_text(std::array<std::uint8_t, kFrameBytes>* frame, int x, int y, std::string_view text,
               int scale, int columns, int rows) {
    int column = 0;
    int row = 0;
    for (char character : text) {
        if (character == '\n' || column >= columns) {
            column = 0;
            ++row;
            if (character == '\n') continue;
        }
        if (row >= rows) return;
        const std::uint16_t pixels = glyph(character);
        for (int glyph_row = 0; glyph_row < 5; ++glyph_row) {
            for (int glyph_column = 0; glyph_column < 3; ++glyph_column) {
                if ((pixels & (1U << (14 - glyph_row * 3 - glyph_column))) == 0) continue;
                fill_rect(frame, x + (column * 4 + glyph_column) * scale,
                          y + (row * 6 + glyph_row) * scale, scale, scale);
            }
        }
        ++column;
    }
}
#endif

}  // namespace

namespace inkmate {

namespace {

struct RenderRequest {
    Intent intent;
    BootReport report;
    char title[33];
    char body[241];
    bool response;
};

QueueHandle_t interaction_queue{};

esp_err_t render_card(Intent intent, const BootReport& report, const char* title = nullptr, const char* body = nullptr) {
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
    if (title != nullptr && body != nullptr) {
        draw_text(&frame, 22, 24, title, 2, 21, 2);
        draw_text(&frame, 22, 64, body, 2, 21, 9);
    } else {
        draw_state_icon(&frame, intent);
        if (report.rtc_detected) draw_circle(&frame, 44, 166, 8, 2);
        if (report.environment_sensor_detected) {
            draw_circle(&frame, 156, 162, 6, 2);
            draw_line(&frame, 156, 168, 156, 176, 2);
        }
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

namespace {

[[maybe_unused]] void interaction_renderer_task(void*) {
    RenderRequest request{};
    for (;;) {
        if (xQueueReceive(interaction_queue, &request, portMAX_DELAY) == pdPASS) {
            const esp_err_t result = render_card(request.intent, request.report,
                                                 request.response ? request.title : nullptr,
                                                 request.response ? request.body : nullptr);
            if (result != ESP_OK) ESP_LOGW(kTag, "cannot render interaction card: %s", esp_err_to_name(result));
        }
    }
}

}  // namespace

esp_err_t start_interaction_renderer() {
#if !CONFIG_INKMATE_BOARD_V2
    return ESP_ERR_NOT_SUPPORTED;
#else
    if (interaction_queue != nullptr) return ESP_ERR_INVALID_STATE;
    interaction_queue = xQueueCreate(4, sizeof(RenderRequest));
    if (interaction_queue == nullptr) return ESP_ERR_NO_MEM;
    if (xTaskCreate(interaction_renderer_task, "inkmate_display", 5 * 1024, nullptr, 4, nullptr) != pdPASS) {
        vQueueDelete(interaction_queue);
        interaction_queue = nullptr;
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
#endif
}

esp_err_t queue_interaction_card(Intent intent, const BootReport& report) {
#if !CONFIG_INKMATE_BOARD_V2
    (void)intent;
    (void)report;
    return ESP_ERR_NOT_SUPPORTED;
#else
    if (interaction_queue == nullptr) return ESP_ERR_INVALID_STATE;
    const RenderRequest request{intent, report, {}, {}, false};
    return xQueueSend(interaction_queue, &request, 0) == pdPASS ? ESP_OK : ESP_ERR_TIMEOUT;
#endif
}

esp_err_t queue_response_card(const char* title, const char* body, const BootReport& report) {
#if !CONFIG_INKMATE_BOARD_V2
    (void)title;
    (void)body;
    (void)report;
    return ESP_ERR_NOT_SUPPORTED;
#else
    if (interaction_queue == nullptr || title == nullptr || body == nullptr) return ESP_ERR_INVALID_ARG;
    RenderRequest request{Intent::None, report, {}, {}, true};
    std::strncpy(request.title, title, sizeof(request.title) - 1);
    std::strncpy(request.body, body, sizeof(request.body) - 1);
    return xQueueSend(interaction_queue, &request, 0) == pdPASS ? ESP_OK : ESP_ERR_TIMEOUT;
#endif
}

}  // namespace inkmate
