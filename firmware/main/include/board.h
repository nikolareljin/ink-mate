#pragma once

#include <cstdint>

#include "esp_err.h"
#include "inkmate_types.h"

namespace inkmate {

class Display {
public:
    virtual ~Display() = default;
    virtual esp_err_t initialize() = 0;
    virtual esp_err_t render(const Card& card, bool full_refresh) = 0;
    virtual esp_err_t sleep() = 0;
};

class Audio {
public:
    virtual ~Audio() = default;
    virtual esp_err_t initialize() = 0;
    virtual esp_err_t start_capture(std::uint32_t sample_rate_hz) = 0;
    virtual esp_err_t stop_capture() = 0;
};

class Sensors {
public:
    virtual ~Sensors() = default;
    virtual esp_err_t initialize() = 0;
    virtual esp_err_t read_environment(float* temperature_c, float* humidity_percent) = 0;
    virtual esp_err_t read_battery_mv(std::uint32_t* millivolts) = 0;
};

struct BootReport {
    std::uint32_t flash_bytes{0};
    std::uint32_t psram_bytes{0};
    bool pins_verified{false};
    bool rtc_detected{false};
    bool environment_sensor_detected{false};
};

BootReport initialize_board_safely();
bool automatic_deep_sleep_allowed();
bool ota_reboot_allowed();

}  // namespace inkmate
