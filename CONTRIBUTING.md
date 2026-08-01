# Contributing to InkMate

Thank you for helping improve InkMate.

## Before starting

- Open an issue for broad features, protocol changes, or new hardware variants.
- Keep pull requests focused and describe the hardware revision used for tests.
- Never commit credentials, recordings, model files, generated voices, device
  dumps, or local configuration.
- Do not copy vendor or upstream code without verifying its license and keeping
  required notices.

## Development workflow

1. Create a branch from the current default branch.
2. Copy example configuration to ignored local files.
3. Make the smallest coherent change and add negative-path tests.
4. Run `./scripts/check.sh`.
5. Document protocol, configuration, or hardware-behavior changes.

Python should be typed and PEP 8 compatible. C++ should follow the firmware's
ESP-IDF conventions. Shell scripts use `set -eu` and remain POSIX-compatible
unless Bash is genuinely required.

## Pull requests

Include the rationale, commands run, observed results, affected board profile,
and screenshots or display photographs for UI changes. Clearly label untested
hardware behavior. Protocol-breaking changes require a new protocol version
and compatibility notes.

Do not enable OTA or unattended battery reboots merely because USB-powered
testing succeeds; complete and report the hardware reset matrix first.
