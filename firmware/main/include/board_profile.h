#pragma once

#include <cstdint>

#include "driver/gpio.h"
#include "sdkconfig.h"

namespace inkmate::board {

// GPIO_NUM_NC is intentional. Populate only from the schematic matching the PCB.
struct Pins {
    gpio_num_t power_hold;
    gpio_num_t boot_button;
    gpio_num_t battery_adc;
    gpio_num_t i2c_sda;
    gpio_num_t i2c_scl;
    gpio_num_t epaper_busy;
    gpio_num_t epaper_reset;
    gpio_num_t epaper_dc;
    gpio_num_t epaper_cs;
    gpio_num_t epaper_sclk;
    gpio_num_t epaper_mosi;
};

#if CONFIG_INKMATE_BOARD_V1
inline constexpr char kRevision[] = "v1-non-touch";
inline constexpr Pins kPins{GPIO_NUM_NC, GPIO_NUM_NC, GPIO_NUM_NC,
                            GPIO_NUM_NC, GPIO_NUM_NC, GPIO_NUM_NC,
                            GPIO_NUM_NC, GPIO_NUM_NC, GPIO_NUM_NC,
                            GPIO_NUM_NC, GPIO_NUM_NC};
#elif CONFIG_INKMATE_BOARD_V2
inline constexpr char kRevision[] = "v2-non-touch";
inline constexpr Pins kPins{
    GPIO_NUM_17,  // BAT_Control: keep the battery power latch asserted.
    GPIO_NUM_0,   // BOOT0 button.
    GPIO_NUM_4,   // BAT_ADC (VBAT divider).
    GPIO_NUM_47,  // shared RTC/SHTC3/ES8311 I2C SDA.
    GPIO_NUM_48,  // shared RTC/SHTC3/ES8311 I2C SCL.
    GPIO_NUM_8,   // e-paper BUSY.
    GPIO_NUM_9,   // e-paper reset.
    GPIO_NUM_10,  // e-paper D/C.
    GPIO_NUM_11,  // e-paper chip select.
    GPIO_NUM_12,  // e-paper SPI clock.
    GPIO_NUM_13,  // e-paper SPI MOSI.
};
#else
#error "Select exactly one InkMate board revision"
#endif

inline constexpr int kDisplayWidth = 200;
inline constexpr int kDisplayHeight = 200;
inline constexpr std::uint8_t kShtc3Address = 0x70;
inline constexpr std::uint8_t kPcf85063Address = 0x51;
inline constexpr std::uint8_t kEs8311Address = 0x18;

}  // namespace inkmate::board
