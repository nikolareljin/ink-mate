# Configuration and deployment

Copy `.env.example` to `.env`, replace every placeholder, and generate a unique
high-entropy HMAC secret per device. Gateway v0.1 reads environment variables.
`config/gateway.example.yaml` documents the planned typed policy format but is
not consumed yet; do not assume changes there affect a running gateway.

```sh
docker compose config
docker compose up --build -d
docker compose ps
```

The default port is loopback-only. A device requires a specific trusted-LAN bind address, a reachable public base URL, and firewall access limited to the device subnet. Direct public internet exposure is unsupported. Do not mount the Docker socket, host root, or a broad home directory. Mount configuration read-only and coding-agent workspaces narrowly.

The planned local defaults are faster-whisper STT, Ollama/`ai-runner` chat, and Piper-compatible TTS. Models and voices are local, ignored artifacts. Optional cloud fallback stays disabled until credentials, TLS, retention/privacy policy, and an explicit indication that data may leave the LAN are configured.

Keep transcript logging off and audio retention short. Rotate a compromised device token and re-pair. Update the gateway first when protocol-compatible, validate health, then update firmware by USB. Battery OTA remains gated by hardware evidence and rollback testing.
