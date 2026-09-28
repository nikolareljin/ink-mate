# Sources and evidence

## Public product reference

- Product listing: <https://www.aliexpress.us/item/3256810104401869.html>

The repository records the public listing URL and engineering conclusions that
still require hardware validation. It does not store or redistribute listing
exports, downloaded pages, vendor PDFs, screenshots, review captures, or other
source artifacts. Marketplace summaries, reviews, dimensions, and marketing are
not authoritative engineering specifications.

## Upstream references

- Waveshare board repository: <https://github.com/waveshareteam/ESP32-S3-ePaper-1.54>
- V2 audio board profile: <https://github.com/waveshareteam/ESP32-S3-ePaper-1.54/blob/main/02_Example/ESP-IDF/V2/08_Audio_Test/components/codec_board/board_cfg.txt>
- Vendor schematic: <https://github.com/waveshareteam/ESP32-S3-ePaper-1.54/blob/main/04_Hardware/Schematics/ESP32-S3-Touch-ePaper-1.54-Schematic.pdf>
- Xiaozhi firmware: <https://github.com/78/xiaozhi-esp32>
- ESP-IDF documentation: <https://docs.espressif.com/projects/esp-idf/>

Record exact commits and licenses before copying code. A related-board example
is not proof of shipped pins or components.

| Statement | Evidence status |
| --- | --- |
| Battery-equipped, non-touch selected option | Linked public listing |
| ESP32-S3, display, Wi-Fi/BLE, RTC, SHTC3, TF, audio | Vendor claim |
| PCF85063 RTC | Vendor claim in linked public listing |
| ES8311 codec and V2 I2C/I2S/PA assignments | Vendor V2 audio board profile; microphone capture confirmed on this unit |
| V2 board | PCB marking and USB chip probe |
| V2 8 MB flash / 8 MB PSRAM | USB flash probe and ESP-IDF boot diagnostics |
| Reset problem affects this exact unit | Unconfirmed risk from one review |
| V2 display, power, and button GPIO assignments | V2 vendor ESP-IDF example, display output, and input configuration |
| GPIO42 audio rail enable | Rejected. The V2 audio board profile specifies no audio rail-enable GPIO; driving GPIO42 prevents ES8311 I2C access on this unit. |
