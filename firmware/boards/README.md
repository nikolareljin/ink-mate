# Board profiles

Build a profile with, for example:

```sh
idf.py -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;boards/v2/sdkconfig.defaults" build
```

`v1` and `v2` identify the silkscreen/PCB revision, not the sales option. Both profiles target the **non-touch, battery-equipped** product. The listing supplied with InkMate states 200 x 200 e-paper, ES8311 audio, PCF85063 RTC, SHTC3 environment sensor, TF/microSD, and integrated flash/PSRAM, but does not provide a trustworthy revision-specific GPIO table. Consequently all peripheral pins start as `GPIO_NUM_NC` in `main/include/board_profile.h`. Populate them only from the schematic matching the physical PCB.
