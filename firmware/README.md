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

On first boot, the serial log reports chip, flash, PSRAM, reset reason, selected profile, and peripheral probe results. V2 enables the confirmed display, BOOT, PWR, and power-latch GPIOs. For a new board revision, keep unverified GPIOs as `GPIO_NUM_NC`, copy values from the matching vendor schematic into `main/include/board_profile.h`, and remove each gate only after verification.

Deep sleep and OTA reboot default off because the supplied listing contains a report of battery restart failure. Enable each only after completing `docs/hardware-bring-up.md`'s reset matrix.

## V2 microphone capture

V2 uses the vendor-confirmed ES8311 path: I2C GPIO47/48, I2S
MCLK/BCLK/WS/DIN GPIO14/15/38/16, and speaker PA GPIO46. No audio rail-enable
GPIO is configured because the vendor V2 board profile does not specify one. A BOOT hold of at least 700 ms
captures at most 10 seconds of 16 kHz mono PCM in PSRAM and validates a WAV
header. An enrolled gateway receives the buffer only after release, returns a
bounded card, and the firmware releases the buffer. It does not retain
recordings.

Enroll a device on the gateway host before flashing the private image:

```sh
./scripts/enroll-v2-device.sh desk-v2
./scripts/build-firmware.sh v2
```

The helper creates ignored private configuration and refuses to replace an
existing enrollment. `compose.device.yaml` starts the gateway with Linux host
networking, allowing the gateway to determine its reachable address without a
tracked local IP.

After flashing a verified V2 image, run:

```sh
./scripts/verify-audio-capture.sh /dev/ttyACM0
```

Hold BOOT, speak, then release it. A successful capture logs `capture complete`
with nonzero PCM and WAV byte counts. New board profiles must leave the audio
pins as `GPIO_NUM_NC` until the matching revision schematic and physical probe
confirm them.

## Host tests

The state machine has no ESP-IDF dependency:

```sh
cmake -S components/inkmate_core/test -B build/host-tests
cmake --build build/host-tests
ctest --test-dir build/host-tests --output-on-failure
```

## Provisioning

If no Wi-Fi credentials exist, firmware starts ESP-IDF's Security 1 provisioning manager over BLE only when a private, per-device proof of possession of at least 16 characters is configured. Public builds leave it empty and fail closed; the firmware never prints it. Wi-Fi credentials use ESP-IDF NVS. NVS encryption remains disabled until a hardware-specific key-protection scheme and eFuse slot are deliberately provisioned and validated. Gateway and AI-provider credentials are not embedded in public firmware.
