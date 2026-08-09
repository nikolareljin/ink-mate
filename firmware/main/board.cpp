#include "board.h"

#include "board_profile.h"
#include "driver/i2c_master.h"
#include "esp_chip_info.h"
#include "esp_flash.h"
#include "esp_log.h"
#include "esp_psram.h"
#include "esp_system.h"
#include "sdkconfig.h"

namespace {
constexpr char kTag[] = "inkmate.board";

bool required_pins_verified() {
    const auto& p = inkmate::board::kPins;
    return p.power_hold != GPIO_NUM_NC && p.boot_button != GPIO_NUM_NC &&
           p.i2c_sda != GPIO_NUM_NC && p.i2c_scl != GPIO_NUM_NC &&
           p.epaper_busy != GPIO_NUM_NC && p.epaper_reset != GPIO_NUM_NC &&
           p.epaper_dc != GPIO_NUM_NC && p.epaper_cs != GPIO_NUM_NC &&
           p.epaper_sclk != GPIO_NUM_NC && p.epaper_mosi != GPIO_NUM_NC;
}
void probe_i2c_devices(inkmate::BootReport* report) {
    const auto& pins = inkmate::board::kPins;
    if (pins.i2c_sda == GPIO_NUM_NC || pins.i2c_scl == GPIO_NUM_NC) return;

    i2c_master_bus_config_t config{};
    config.i2c_port = I2C_NUM_0;
    config.sda_io_num = pins.i2c_sda;
    config.scl_io_num = pins.i2c_scl;
    config.clk_source = I2C_CLK_SRC_DEFAULT;
    config.glitch_ignore_cnt = 7;

    i2c_master_bus_handle_t bus{};
    const esp_err_t bus_result = i2c_new_master_bus(&config, &bus);
    if (bus_result != ESP_OK) {
        ESP_LOGW(kTag, "I2C bring-up skipped: %s", esp_err_to_name(bus_result));
        return;
    }

    report->rtc_detected =
        i2c_master_probe(bus, inkmate::board::kPcf85063Address, 50) == ESP_OK;
    report->environment_sensor_detected =
        i2c_master_probe(bus, inkmate::board::kShtc3Address, 50) == ESP_OK;
    ESP_LOGI(kTag, "I2C probe RTC=%s SHTC3=%s",
             report->rtc_detected ? "present" : "absent",
             report->environment_sensor_detected ? "present" : "absent");
    i2c_del_master_bus(bus);
}
}  // namespace

namespace inkmate {

BootReport initialize_board_safely() {
    esp_chip_info_t chip{};
    esp_chip_info(&chip);
    BootReport report{};
    if (esp_flash_get_size(nullptr, &report.flash_bytes) != ESP_OK) report.flash_bytes = 0;
#if CONFIG_SPIRAM
    report.psram_bytes = static_cast<std::uint32_t>(esp_psram_get_size());
#else
    report.psram_bytes = 0;
#endif
    report.pins_verified = required_pins_verified();

    ESP_LOGI(kTag, "profile=%s cores=%u revision=%u flash=%lu psram=%lu reset_reason=%d",
             board::kRevision, chip.cores, chip.revision,
             static_cast<unsigned long>(report.flash_bytes),
             static_cast<unsigned long>(report.psram_bytes),
             static_cast<int>(esp_reset_reason()));
    // This only emits address probes on the verified shared peripheral bus. It does
    // not power, configure, or drive the display, microphone, amplifier, or codec.
    probe_i2c_devices(&report);
    if (!report.pins_verified) {
        ESP_LOGW(kTag, "GPIO map is unverified; display/audio/sensors/power-hold remain disabled");
    }
    // Never drive power_hold here unless the selected profile has a verified value.
    // Once populated, this is the earliest application-level place to assert it; a
    // board-specific bootloader hook is preferable if battery testing requires earlier.
    return report;
}

bool automatic_deep_sleep_allowed() {
#if CONFIG_INKMATE_ENABLE_DEEP_SLEEP
    return required_pins_verified();
#else
    return false;
#endif
}

bool ota_reboot_allowed() {
#if CONFIG_INKMATE_ENABLE_OTA_REBOOT
    return required_pins_verified();
#else
    return false;
#endif
}

}  // namespace inkmate
