# InkMate Gateway

FastAPI gateway for authenticated device interactions, status snapshots, ephemeral speech, and physically confirmed allowlisted actions.

Install with `pip install -e '.[test]'`, run `uvicorn inkmate_gateway.app:app
--host 0.0.0.0 --port 8080`, and test with `pytest`. Copy `.env.example` to
`.env` and replace every development secret.

Device requests use the HMAC headers defined in `../protocol/README.md`.
`POST /v1/interactions` accepts a raw PCM WAV body; it is not multipart.
Install `.[audio]` and set `INKMATE_STT_BACKEND=faster-whisper` for local STT.
Set `INKMATE_TTS_URL` to a trusted Piper-compatible HTTP endpoint for speech
output. With neither option configured, the gateway fails closed for STT and

Actions are constructed as fixed argument vectors (`SafeCommand`) and cannot contain a shell command string. Coding-agent support is disabled unless explicitly enabled and constrained to canonical allowlisted workspaces.

## Desktop application adapters

The gateway maps fixed spoken requests, including `open VS Code for me`, to
approved JSON-defined adapters. It does not use the response provider to choose
an executable. Run `./dev run adapter-host`, then approve and grant each adapter
before use. Each app launch returns a device confirmation card; a brief BOOT
press runs the approved fixed command.

See [the extension guide](../docs/extensions.md) for adapter commands,
parameters, supported applications, browser URL examples, and links for
[installing host software](../docs/extensions.md#install-host-software).
