# Sources and evidence

## User-supplied

- Product listing: <https://www.aliexpress.us/item/3256810104401869.html>
- Saved PDF: `ESP32-S3 e-Paper AIoT Board with Touch.pdf`
- Saved text: `esp32_ink_mate.txt`

The files remain outside the repository and are not redistributed. The text is evidence for the selected `With Bat No Touch` option, four generic variants, listed features, and one customer's battery-reset report. Marketplace AI summaries, reviews, dimensions, and marketing are not authoritative engineering specifications.

## Upstream references

- Waveshare board repository: <https://github.com/waveshareteam/ESP32-S3-ePaper-1.54>
- Xiaozhi firmware: <https://github.com/78/xiaozhi-esp32>
- ESP-IDF documentation: <https://docs.espressif.com/projects/esp-idf/>

Record exact commits and licenses before copying code. A related-board example is not proof of shipped pins or components.

| Statement | Evidence status |
| --- | --- |
| Battery-equipped, non-touch selected option | Supplied listing capture |
| ESP32-S3, display, Wi-Fi/BLE, RTC, SHTC3, TF, audio | Vendor claim |
| PCF85063 RTC | Vendor claim in supplied text |
| ES8311 codec | Working assumption |
| V2 board | Working assumption |
| 4 MB flash / 2 MB PSRAM | Working assumption |
| Reset problem affects this exact unit | Unconfirmed risk from one review |
| Peripheral GPIO assignments | Unknown pending revision-specific evidence |
