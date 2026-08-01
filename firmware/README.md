# InkMate firmware

ESP-IDF firmware for the non-touch Waveshare/Spotpear ESP32-S3 1.54-inch e-paper board. Board listings are not a reliable pin-map source: select the PCB revision explicitly and verify every pin against the vendor schematic or a continuity check before enabling peripherals.

## Build

ESP-IDF 5.2 or newer is supported (6.0.2 is the intended CI toolchain).

```sh
idf.py set-target esp32s3
idf.py menuconfig                 # InkMate -> Board revision
idf.py build
idf.py -p /dev/ttyACM0 flash monitor
```

On first boot, the serial log reports chip, flash, PSRAM, reset reason, selected profile, and peripheral probe results. It does not enable GPIOs whose mapping is unverified. Copy the correct values from the vendor revision schematic into `main/include/board_profile.h`, then remove the associated `GPIO_NUM_NC` gate only after verification.

Deep sleep and OTA reboot default off because the supplied listing contains a report of battery restart failure. Enable each only after completing `docs/bring-up.md`'s reset matrix (kept in the repository documentation).

## Host tests

The state machine has no ESP-IDF dependency:

```sh
cmake -S components/inkmate_core/test -B build/host-tests
cmake --build build/host-tests
ctest --test-dir build/host-tests --output-on-failure
```

## Provisioning

If no Wi-Fi credentials exist, firmware starts ESP-IDF's Security 1 provisioning manager over BLE only when a private, per-device proof of possession of at least 16 characters is configured. Public builds leave it empty and fail closed; the firmware never prints it. Wi-Fi credentials use ESP-IDF NVS. NVS encryption remains disabled until a hardware-specific key-protection scheme and eFuse slot are deliberately provisioned and validated. Gateway and AI-provider credentials are not embedded in public firmware.
