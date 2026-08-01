# Firmware design

Firmware owns audio capture/playback, cards, sensors, connectivity, power, and physical confirmation; it does not run AI or host commands.

## States and controls

The state machine covers boot diagnostics, provisioning, idle/home, recording, submitting, response playback, pending confirmation, offline, error, and safe sleep/shutdown. On boot it reports reset reason, selected profile, detected chip/flash/PSRAM, and safe peripheral probes without credentials.

| Context | BOOT gesture | Result |
| --- | --- | --- |
| Idle | Short press | Cycle cards |
| Idle | Hold then release | Record bounded audio and submit |
| Pending action | Short press | Confirm once |
| Pending action | Long press | Cancel |

PWR remains dedicated to the board power latch. Exact behavior must be measured. Buttons require debounce, duration thresholds, and protection against interpreting release as another event.

## Cards and refresh

Home shows time, environment, battery estimate, Wi-Fi, and gateway state. Answer shows concise wrapped output. Tools shows configured model/host/repository/agent status. Confirmation shows the exact normalized operation, target, expiry, and controls. Offline/error shows stable codes while retaining the last useful content where possible.

Layouts are bounded for 200 x 200 monochrome output. Partial refreshes are followed by configurable full refreshes to manage ghosting. A stale confirmation card must never remain actionable.

## Connectivity, audio, and power

Secure provisioning creates a per-device identity/proof of possession. Pairing data is stored in encrypted NVS; AI credentials stay on the gateway. Requests and audio are bounded and timed out. Offline sensor/time cards remain useful while reconnect attempts use backoff and jitter.

Docked mode favors responsiveness; battery mode limits radio/audio windows. Battery percentage is unavailable until calibrated. Automatic deep sleep and OTA reboot remain off until every applicable battery reset/wake/rollback scenario passes.

OTA eventually uses a validated image, inactive partition, health confirmation, and rollback. A successful download alone does not make a battery reboot safe. USB ROM-download recovery must remain possible if provisioning, NVS, or OTA state is corrupt.
