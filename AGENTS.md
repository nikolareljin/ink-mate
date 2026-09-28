# InkMate Agent Guide

Read `README.md` and the relevant document under `docs/` before changing code.

## Public documentation

- Write `README.md` and `docs/` for people who use, operate, or extend InkMate.
- Keep contributor and agent operating instructions in this file, not public
  documentation.
- Do not add prompts, agent procedures, named-agent directions, or implementation
  guidance for automated contributors to public pages.
- Public pages may explain user-visible behavior, supported hardware, setup,
  safety limits, and local-service contracts.

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

## Branding assets

- Keep `docs/assets/inkmate-logo.png` as the master documentation logo.
- Keep `docs/assets/inkmate-app-icon-512.png` and
  `docs/assets/inkmate-app-icon-192.png` as application icons.
- Keep `docs/assets/favicon.ico` as the browser favicon and
  `docs/assets/inkmate-hero.png` as the README and documentation hero image.
- Preserve transparent logo proportions. Do not recolor individual elements.
- Use charcoal for the enclosure, warm cream for e-paper surfaces, and muted
  teal only as a status accent.
- Treat the hero as an illustration, not a mechanical rendering. Label hardware
  photographs separately.
- Keep README and documentation asset paths repository-relative.
