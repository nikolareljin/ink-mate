# Troubleshooting and recovery

## USB or flashing

Use a known data cable and direct port. Check enumeration/permissions, then hold BOOT while connecting or resetting to enter the ROM downloader. Do not guess the port or publish MAC addresses. If flash/PSRAM differs from expectations, stop and adopt the detected layout; never flash a 4 MB partition table to a smaller chip.

## USB boots but battery does not

Keep OTA/deep sleep disabled. Record revision, battery voltage, reset scenario, boot log, and whether PWR or USB was required. Inspect power-hold timing and circuitry before changing GPIOs. A confirmed electrical limitation must be documented rather than hidden by retry loops.

## Peripheral failures

For blank/mirrored display output, verify revision, controller, pins, busy polarity, reset timing, and LUT; use full refresh during bring-up. For audio/sensor/RTC/SD failures, probe shared buses individually and check addresses, clocks, enables, chip selects, formatting, and pin conflicts. An apparent ES8311 I2C address does not prove all routing.

## Gateway or AI failures

Ensure the gateway is bound to a LAN address (not device-local `localhost`), firewall allows the subnet, time is reasonable, and ID/token match. Test gateway health before STT, LLM, and TTS individually. Confirm models/voices are installed and provider URLs work inside the container.

Rejected actions should remain rejected until the template is enabled, normalized target and arguments match policy, canonical workspace is allowlisted, and an unexpired proposal belongs to this device. Modified or replayed proposals must never succeed.

Recovery order is: preserve safe logs, return to USB, enter ROM download mode, flash a known-good verified profile/partition table, erase only the minimum corrupt state, then re-provision. A full erase destroys pairing data and should not be the first step.
