# Security Policy

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability. Use GitHub's private
security advisory feature for this repository. Include affected versions,
reproduction steps, impact, and any suggested mitigation. Maintainers will
acknowledge the report and coordinate disclosure after a fix is available.

## Security model

InkMate is intended for a trusted LAN. The gateway must not be exposed directly
to the public internet. Device requests are authenticated; cloud credentials
remain on the gateway; logs redact secrets and transcripts by default.

Tool actions use named, fixed executable/argument templates. Free-form shell
commands are prohibited. Mutating actions require an unexpired, single-use
proposal and physical confirmation on the paired device. Workspace-based tools
must resolve paths and reject targets outside configured allowlists.

Users are responsible for securing the host, network, Ollama and optional cloud
providers, rotating pairing credentials, and reviewing configuration examples
before use. Example secrets are placeholders and are never production defaults.

Only supported releases receive security fixes. Until the first tagged release,
use the latest commit and review changes before deploying.
