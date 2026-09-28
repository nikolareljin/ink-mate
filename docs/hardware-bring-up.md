# Bring up the hardware

## Start with the right board

The target is the **With Bat, No Touch** ESP32-S3 1.54-inch e-paper variant.
Touch variants have different pin maps and input behavior, so they are not part
of the current profile.

Do not infer the board revision from the listing title. Photograph the PCB and
record its silkscreen. Detect the chip package, flash, and PSRAM over USB. V2
uses the ESP32-S3-PICO-1-N8R8 with 8 MB flash and 8 MB PSRAM; detection wins if
the connected board differs.

## Inspect before flashing

To install the pinned ESP-IDF toolchain locally (if needed), activate it, and
inspect a connected board, run:

```sh
./scripts/inspect-connected-device.sh /dev/ttyACM0
```

The wrapper installs ESP-IDF 6.0.2 in `.tools/esp-idf`, which is ignored by
Git. To use an existing installation, set `INKMATE_ESP_IDF_DIR` to its path.
After the first installation, `./scripts/inspect-hardware.sh /dev/ttyACM0`
also works in a shell where that ESP-IDF installation's `export.sh` has been
sourced.

Save reports under the ignored `hardware-reports/` directory. Do not include
MAC addresses, pairing data, or serial logs containing credentials in issues.

After building and flashing a profile, confirm the device with:

```sh
./scripts/verify-connected-device.sh v2 /dev/ttyACM0
```

The helper reads the flashed bootloader, partition table, and application image
against the build manifest, then resets the board and saves a filtered boot
report. It does not compare OTA metadata because the bootloader changes it
when selecting the active image.

Verify V2 controls with:

```sh
./scripts/verify-controls.sh /dev/ttyACM0
```

During the capture, press BOOT briefly, then hold it for at least 700 ms and
release. The report must contain `next card`, `begin recording`, and `submit
recording`. Hold PWR for 2 seconds only when a powered-down board is safe: it
releases the battery latch and USB may keep the board running.

Before enabling peripherals, check them one at a time: e-paper, BOOT and PWR,
microphone and speaker, RTC, sensor, battery, Wi-Fi, and optional microSD. A
wrong V1 or V2 pin profile can damage or lock the board.

## Check battery resets

Some product reviews report failure to restart on battery after reset. Validate
each row on the exact hardware revision and firmware build. Record pass/fail,
boot logs, battery voltage, and whether a manual PWR cycle was required.

| Scenario | USB | Battery only |
| --- | --- | --- |
| Cold power-on | Required | Required |
| Hardware/reset button | Required | Required |
| Software restart | Required | Required |
| Watchdog restart | Required | Required |
| Brownout recovery | Required | Required |
| Deep-sleep wake | Required | Required |
| OTA reboot and rollback | Required | Required |

Assert the verified power-hold GPIO at the earliest safe startup point. Until
every relevant battery-only row passes, keep OTA and automatic deep sleep off,
avoid unattended reboots, and document that USB or a manual PWR cycle may be
necessary. If the failure is electrical, firmware must expose the limitation
rather than claim recovery.

## Check the display

Exercise repeated partial refreshes, then a full refresh. Confirm legibility,
ghosting limits, last-card persistence without power, and safe refresh timing at
low battery. Keep a configurable partial-refresh count; do not assume the same
threshold across panel lots.
