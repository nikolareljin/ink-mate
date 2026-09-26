# Hardware overview

InkMate initially targets the battery-equipped, non-touch variant. The selected product option was identified as `With Bat No Touch`; the generic “Touch Options” title covers multiple variants and does not establish that this unit has touch input. The public marketplace listing is not a revision-specific schematic.

## Evidence labels

- **Listing fact:** directly present in the linked public product listing.
- **Vendor claim:** described by the seller/vendor but still requires validation.
- **Working assumption:** useful for development, not yet confirmed on the unit.
- **Unknown:** must remain disabled or unspecified until reliable evidence exists.

## Described capabilities

The listing describes an ESP32-S3 dual-core LX7 MCU (up to 240 MHz), 2.4 GHz Wi-Fi, Bluetooth LE 5, a 1.54-inch 200 x 200 e-paper panel, audio capture/playback, PCF85063 RTC, SHTC3 temperature/humidity sensor, TF/microSD slot, lithium battery charging, PWR and BOOT buttons, and USB/UART/I2C/GPIO expansion through a 2 x 6 header. Each peripheral still needs a physical probe.

The ES8311 codec is a working assumption based on related board materials, not a fact established by the linked marketplace listing. Battery capacity, charging limits, battery ADC circuit, panel driver, and expansion pinout are unknown.

## Revision, memory, and pinout

Related vendor material distinguishes V1 and V2 non-touch boards. A store SKU does not establish the PCB revision, so InkMate uses explicit build profiles. V2 uses the ESP32-S3-PICO-1-N8R8 with 8 MB flash and 8 MB PSRAM. PCB silkscreen, package markings, `esptool flash-id`, and ESP-IDF boot diagnostics take precedence.

The V2 vendor ESP-IDF example confirms GPIO 6 for the e-paper power rail, GPIOs
8-13 for panel control and SPI, GPIO 17 for battery power hold, GPIO 0 for
BOOT, GPIO 18 for PWR, and GPIOs 47-48 for the shared I2C bus. Both buttons
are active-low. InkMate uses these only in the
explicit V2 profile. Add a new profile for another board revision, leave its
unverified fields as `GPIO_NUM_NC`, and do not inherit V1 or V2 pins. Never
copy a touch-model pinout or assume board revisions match.

## Known limitations and risks

- E-paper is slow, monochrome, susceptible to ghosting, and unsuitable for animation, though it retains an image without power.
- Audio and Wi-Fi can dominate battery use despite low display standby power.
- One customer review reports that a no-touch battery unit could not restart on battery after reset and first needed USB. This is unverified and may not affect every unit, but it requires the reset matrix before OTA or unattended sleep/reboot.
- Battery state-of-charge must stay “unknown” until ADC calibration and a cell discharge curve exist.
- Touch support is outside the initial target.
