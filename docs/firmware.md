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

V2 configures BOOT on GPIO0 and PWR on GPIO18 as active-low inputs with internal pull-ups. It polls at 10 ms and accepts a state change only after 30 ms. A BOOT hold reaches the recording intent at 700 ms; its release submits the intent. A short BOOT press renders the next diagnostic card. A 2 second PWR hold releases GPIO17, the battery power latch. PWR must be released once after boot before it can request shutdown, preventing the power-on hold from immediately cutting power. USB can keep the board powered after that action.

Audio capture and gateway submission are not connected yet. The current firmware renders the gesture-specific diagnostic card and logs the requested intent. It does not claim to record or submit audio.

## Cards and refresh

Home shows time, environment, battery estimate, Wi-Fi, and gateway state. Answer shows concise wrapped output. Tools shows configured model/host/repository/agent status. Confirmation shows the exact normalized operation, target, expiry, and controls. Offline/error shows stable codes while retaining the last useful content where possible.

Layouts are bounded for 200 x 200 monochrome output. Partial refreshes are followed by configurable full refreshes to manage ghosting. A stale confirmation card must never remain actionable.

## Connectivity, audio, and power

Secure provisioning requires a privately configured per-device proof of possession and never logs it. Public builds fail closed when it is absent. Wi-Fi credentials use ESP-IDF NVS; NVS encryption remains gated until a hardware-specific key-protection scheme and eFuse slot are deliberately provisioned. Gateway and AI credentials stay off public firmware. Requests and audio are bounded and timed out. Offline sensor/time cards remain useful while reconnect attempts use backoff and jitter.

Docked mode favors responsiveness; battery mode limits radio/audio windows. Battery percentage is unavailable until calibrated. Automatic deep sleep and OTA reboot remain off until every applicable battery reset/wake/rollback scenario passes.

OTA eventually uses a validated image, inactive partition, health confirmation, and rollback. A successful download alone does not make a battery reboot safe. USB ROM-download recovery must remain possible if provisioning, NVS, or OTA state is corrupt.
