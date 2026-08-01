# InkMate Agent Guide

Read `README.md` and the relevant document under `docs/` before changing code.

- Keep the ESP32 a thin client; inference, secrets, and tool execution belong in
  the gateway.
- Support V1 and V2 through explicit build profiles. Never silently guess pins.
- Assume 4 MB flash and 2 MB PSRAM only until physical detection confirms them.
- Keep OTA and automatic deep sleep off until the battery reset matrix passes.
- Never execute free-form shell strings. Mutations require a physical,
  unexpired, replay-resistant confirmation.
- Version wire changes and update schemas, both implementations, tests, and
  `docs/protocol.md` together.
- Do not commit `.env`, local YAML, recordings, models, build output, device
  dumps, or generated credentials.
- Run `./scripts/check.sh`; report precisely what ran and what was unavailable.
