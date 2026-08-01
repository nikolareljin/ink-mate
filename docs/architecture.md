# Architecture

InkMate separates the resource-constrained, physically trusted device from a
LAN gateway that performs expensive and privileged work.

```text
BOOT / microphone -> ESP32-S3 -> authenticated HTTPS/HTTP-on-trusted-LAN
                                      |
                         FastAPI interaction service
                           /          |          \
                         STT         LLM         TTS
                                      |
                               action proposals
                                      |
                    physical confirmation -> executor
```

## Device responsibilities

The firmware captures and plays audio, renders persistent cards, reads the RTC,
SHTC3 and battery ADC, manages Wi-Fi and pairing, and preserves the last useful
screen during sleep or failure. It stores a device identity and pairing token,
but no AI-provider credentials. V1 and V2 are explicit compile-time profiles.

## Gateway responsibilities

The gateway authenticates devices, validates versioned messages, coordinates
STT/LLM/TTS providers, creates compact display cards, reports configured host
status, and stores short-lived response audio. Provider failures degrade to a
machine-readable error card without discarding the last useful device state.

The action service is the only execution boundary. Adapters propose typed
actions; the service validates a fixed template, target allowlists, expiry,
device binding, and single-use confirmation before execution. Read-only health
queries need no physical confirmation; state-changing jobs do.

## Data flow

1. The device records bounded audio while BOOT is held.
2. It submits audio, device metadata, protocol version, and a unique request ID.
3. The gateway transcribes, queries the configured model, creates a card, and
   optionally synthesizes response audio.
4. The device displays the card and streams or downloads the short-lived audio.
5. A requested mutation returns a proposal instead of executing. BOOT confirms
   it; expired, replayed, mismatched, or cancelled proposals are rejected.

## Deployment boundary

Compose binds to loopback by default. LAN use requires an explicit bind address,
firewall restrictions, and a gateway URL reachable by the device. A reverse
proxy may add TLS, but public internet exposure is outside the initial design.
