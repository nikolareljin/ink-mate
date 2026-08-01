# Sources and evidence

## Public product reference

- Product listing: <https://www.aliexpress.us/item/3256810104401869.html>

The repository records only the public listing URL and engineering conclusions
that still require hardware validation. It does not store or redistribute
listing exports, downloaded pages, vendor PDFs, screenshots, review captures,
or other source artifacts. Marketplace AI summaries, reviews, dimensions, and
marketing are not authoritative engineering specifications.

## Upstream references

- Waveshare board repository: <https://github.com/waveshareteam/ESP32-S3-ePaper-1.54>
- Xiaozhi firmware: <https://github.com/78/xiaozhi-esp32>
- ESP-IDF documentation: <https://docs.espressif.com/projects/esp-idf/>

Record exact commits and licenses before copying code. A related-board example is not proof of shipped pins or components.

| Statement | Evidence status |
| --- | --- |
| Battery-equipped, non-touch selected option | Linked public listing |
| ESP32-S3, display, Wi-Fi/BLE, RTC, SHTC3, TF, audio | Vendor claim |
| PCF85063 RTC | Vendor claim in linked public listing |
| ES8311 codec | Working assumption |
| V2 board | Working assumption |
| 4 MB flash / 2 MB PSRAM | Working assumption |
| Reset problem affects this exact unit | Unconfirmed risk from one review |
| Peripheral GPIO assignments | Unknown pending revision-specific evidence |
