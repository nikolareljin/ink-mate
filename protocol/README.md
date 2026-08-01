# InkMate protocol

The files in this directory are the source of truth for messages exchanged by
the device and gateway. Protocol version `1` uses JSON for metadata and 16 kHz,
16-bit, mono PCM WAV for recorded speech.

All device requests carry `X-InkMate-Device`, `X-InkMate-Timestamp`, and
`X-InkMate-Signature` headers. The signature is lower-case hexadecimal
HMAC-SHA256 over:

```text
METHOD\nPATH\nTIMESTAMP\nSHA256_BODY
```

The gateway rejects stale timestamps and invalid signatures. Device secrets are
created during pairing and must never be committed.

Schema compatibility follows these rules:

- Readers ignore unknown object properties.
- New required fields require a new `protocol_version`.
- Error codes are stable machine identifiers; human messages may change.
- Action confirmations are single-use and expire at `expires_at`.
