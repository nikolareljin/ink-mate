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

V2 BOOT holds capture up to 10 seconds of 16 kHz mono PCM into PSRAM. Release signs and sends the WAV to an enrolled gateway, then renders the returned card. The WAV buffer is released after the request and is never written to flash. Interaction card refreshes use one display worker, so e-paper refresh time does not block button polling.

V2 renders monochrome state illustrations for ready, recording, sending,
processing, confirmation, and cancellation. After a returned card it plays a
very quiet completion tone. Gateway failure cards and transport failures use a
lower, distinct tone. These cues require the V2 audio path and do not change
the persisted display card.

`firmware/assets/icons/*.svg` is the editable source for state artwork.
Run `./dev previews --write-header` after editing an SVG. That regenerates the
tracked firmware header and 200 x 200 black-and-white PNGs under ignored
`firmware/previews/`. `./dev previews --check` rejects a stale generated
header. The PNGs are layout previews, not e-paper waveform or ghosting
simulations.

## State artwork

The published previews are generated from the same SVG sources that produce
the firmware header. They contain only display artwork, no labels from a source
sheet or embedded text.

| Ready | Recording | Sending |
| --- | --- | --- |
| ![Ready state](../assets/device-states/ready.png) | ![Recording state](../assets/device-states/recording.png) | ![Sending state](../assets/device-states/sending.png) |

| Processing | Confirmation | Cancelled |
| --- | --- | --- |
| ![Processing state](../assets/device-states/processing.png) | ![Confirmation state](../assets/device-states/confirmation.png) | ![Cancelled state](../assets/device-states/cancelled.png) |

## Verified V2 state

The current V2 test image was built from the SVG-generated header and flashed
through the backup-first helper. The device reports the V2 profile, 8 MB flash,
8 MB PSRAM, working e-paper initialization, active controls, and a successful
Wi-Fi connection. The flash verifier matched the bootloader, partition table,
and application bytes after installation.

## Cards and refresh

Home shows time, environment, battery estimate, Wi-Fi, and gateway state. Answer shows concise wrapped output. Tools shows configured model/host/repository/agent status. Confirmation shows the exact normalized operation, target, expiry, and controls. Offline/error shows stable codes while retaining the last useful content where possible.

Layouts are bounded for 200 x 200 monochrome output. Partial refreshes are followed by configurable full refreshes to manage ghosting. A stale confirmation card must never remain actionable.

## Connectivity, audio, and power

Secure provisioning requires a privately configured per-device proof of possession and never logs it. Public builds fail closed when it is absent. Wi-Fi credentials use ESP-IDF NVS; NVS encryption remains gated until a hardware-specific key-protection scheme and eFuse slot are deliberately provisioned. Gateway and AI credentials stay off public firmware. Requests and audio are bounded and timed out. Offline sensor/time cards remain useful while reconnect attempts use backoff and jitter.

Gateway discovery uses authenticated UDP broadcast. Set
`INKMATE_GATEWAY_INTERFACE` in ignored `.env` to select one LAN on a multi-homed
host. `scripts/start-device-gateway.sh` derives the interface's current IPv4
address and subnet. HTTP binds to that address. UDP receives broadcasts on the
host socket but accepts and replies only to senders in that subnet, then signs
the nonce, URL, and UTC time with the enrolled device secret. Firmware and
tracked configuration never store a fixed LAN IP address.

## Enrolling a V2 device

Run the helper once from a trusted gateway host:

```sh
./scripts/enroll-v2-device.sh desk-v2
docker compose -f compose.device.yaml up --build
./scripts/build-firmware.sh v2
```

The helper creates ignored `firmware/sdkconfig.private` and `.env` files with a
unique device ID and secret. It refuses to overwrite either enrollment value.
If `.env` already contains the selected gateway enrollment, use
`./scripts/configure-v2-enrollment.sh [DEVICE_ID]` to create only the ignored
firmware overlay. The optional ID is required when more than one enrollment is
configured. An enrolled V2 build is written to ignored `firmware/build/v2-private`.
`scripts/start-device-gateway.sh` starts the same service and records an unused
local port in ignored `.env` if 8080 is already occupied.
`compose.device.yaml` uses host networking on Linux so UDP discovery receives
the selected LAN broadcast. Do not add a LAN IP to source, tracked
configuration, or firmware defaults.

When `INKMATE_STT_BACKEND=faster-whisper`, the device gateway stores the local
model in a Docker volume. The first start downloads the selected model; later
starts reuse it. No audio request is retained after the gateway returns a card.

Use `scripts/verify-audio-capture.sh /dev/ttyDEVICE` during bench verification. It records only filtered capture diagnostics under ignored `hardware-reports/`; it does not write audio to disk.

Docked mode favors responsiveness; battery mode limits radio/audio windows. Battery percentage is unavailable until calibrated. Automatic deep sleep and OTA reboot remain off until every applicable battery reset/wake/rollback scenario passes.

OTA eventually uses a validated image, inactive partition, health confirmation, and rollback. A successful download alone does not make a battery reboot safe. USB ROM-download recovery must remain possible if provisioning, NVS, or OTA state is corrupt.
