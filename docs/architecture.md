# Architecture

InkMate keeps the device simple and puts the heavier work on a service you run
on your local network. That split keeps the e-paper companion responsive while
keeping credentials and local integrations off the board.

```text
BOOT / microphone -> ESP32-S3 -> authenticated HTTPS/HTTP-on-trusted-LAN
                                      |
                         local interaction service
                           /          |          \
                    transcription  response   speech
                                      |
                               action proposals
                                      |
                    physical confirmation -> executor
```

## Device responsibilities

The firmware captures and plays audio, renders persistent cards, reads the RTC,
SHTC3 and battery ADC, manages Wi-Fi and pairing, and preserves the last useful
screen during sleep or failure. It stores a device identity and pairing token,
but not service credentials. V1 and V2 are explicit compile-time profiles.

## Gateway responsibilities

The local service authenticates devices, validates versioned messages, handles
speech and response providers, creates compact display cards, reports service
status, and stores short-lived response audio. If a provider is unavailable,
the device receives a clear error card and keeps its last useful state.

The action service is the only execution boundary. Integrations can propose a
typed action, but the service checks its fixed template, target allowlist,
expiry, device binding, and single-use confirmation before it runs. Read-only
health checks need no physical confirmation; state-changing work does.

## Data flow

1. The device records bounded audio while BOOT is held.
2. It submits audio, device metadata, protocol version, and a unique request ID.
3. The local service transcribes the request, prepares a response card, and can
   create a short spoken reply.
4. The device displays the card and streams or downloads the short-lived audio.
5. A requested mutation returns a proposal instead of executing. BOOT confirms
   it; expired, replayed, mismatched, or cancelled proposals are rejected.

## Response model use

After speech-to-text, ordinary questions are sent to the configured response
provider and its answer becomes the card and optional speech. The default
provider is the local Ollama endpoint configured by `INKMATE_OLLAMA_URL` and
`INKMATE_OLLAMA_MODEL`. See the [host software installation guide](extensions.md#install-host-software)
for the official Ollama installation and model-library links.

The response model is not used to select or execute adapters. Fixed adapter
requests and the desktop application phrases are parsed locally into typed,
allowlisted operations before any response-provider call. Voice captures use
the provider only to produce a short summary before the device confirms saving
it.

## Deployment boundary

Compose binds to loopback by default. LAN use needs an explicit bind address,
firewall restrictions, and a service URL that the device can reach. A reverse
proxy may add TLS, but public internet exposure is outside the initial design.
