# Run the local service

Copy `.env.example` to `.env`, replace every placeholder, and create a unique
device secret. The current service reads environment variables. The example YAML
file describes a future policy format; changing it does not affect a running
service yet.

```sh
docker compose config
docker compose up --build -d
docker compose ps
```

The default port is loopback-only. To connect a device, choose one trusted LAN
address, allow that subnet through the firewall, and set a reachable service
URL. Direct public internet exposure is not supported. Do not mount the Docker
socket, host root, or a broad home directory into the service.

The local defaults cover transcription, response generation, and speech output.
Models and voices stay local and are ignored by Git. Optional cloud fallback
stays off until credentials, TLS, retention policy, and a clear indication that
data may leave the LAN are configured.

Keep transcript logging off and audio retention short. Rotate a compromised
device token and pair the device again. Update the local service first when the
protocol is compatible, check its health, then update firmware by USB. Battery
OTA remains off until hardware evidence and rollback testing support it.
