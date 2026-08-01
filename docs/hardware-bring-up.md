# Hardware bring-up

## Target

The initial target is the **With Bat, No Touch** ESP32-S3 1.54-inch e-paper
variant. The product family also contains touch variants; their pin maps and
input behavior are out of scope for the initial profile.

Do not infer the board revision from the listing title. Photograph the PCB and
record its silkscreen. Detect the chip package, flash, and PSRAM over USB. The
working expectation is V2, 4 MB flash, and 2 MB PSRAM, but detection wins over
that expectation.

## Inspection

With ESP-IDF active, run:

```sh
./scripts/inspect-hardware.sh /dev/ttyACM0
```

Save reports under the ignored `hardware-reports/` directory. Do not include
MAC addresses, pairing data, or serial logs containing credentials in issues.

Before enabling peripherals, verify one at a time: e-paper, BOOT and PWR logic,
ES8311 microphone/speaker, PCF85063 RTC, SHTC3, battery ADC/charger, Wi-Fi, and
optional FAT32 microSD. A wrong V1/V2 pin profile can damage or lock the board.

## Battery reset matrix

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

## Display acceptance

Exercise repeated partial refreshes, then a full refresh. Confirm legibility,
ghosting limits, last-card persistence without power, and safe refresh timing at
low battery. Keep a configurable partial-refresh count; do not assume the same
threshold across panel lots.
