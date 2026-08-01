# Protocol

The source of truth is the versioned schema under `protocol/`. This document
describes intended v1 behavior; implementations must reject incompatible major
versions and ignore documented optional fields they do not understand.

Every message carries `protocol_version`, `request_id`, `device_id`, and a UTC
timestamp. Request IDs are unique and confirmations are bound to both the
originating request and paired device.
## Request authentication

Device requests send `X-InkMate-Device`, `X-InkMate-Timestamp`, and
`X-InkMate-Signature`. The signature is hexadecimal HMAC-SHA256 over the
method, request path, Unix timestamp, and SHA-256 body digest separated by
newlines. The gateway rejects unknown devices, stale timestamps, identity
mismatches, and invalid signatures. See `protocol/README.md` for the canonical
form.


## Endpoints

### `POST /v1/interactions` (`Content-Type: audio/wav`)

An authenticated request whose body is bounded 16 kHz, mono, 16-bit PCM WAV.
Device identity comes from signed headers rather than multipart metadata. A
successful response contains the transcript, compact card,
optional short-lived speech URL, and optional pending action descriptor.

### `GET /v1/devices/{device_id}/snapshot`

Returns synchronized home/tool cards, gateway health, and server time. A device
may cache the last successful snapshot for offline display.

### `POST /v1/actions/{request_id}/confirm`

Consumes an unexpired action proposal after physical confirmation. Confirming
twice, using another device, changing parameters, or confirming after expiry is
an error. Execution results are represented as a new card.

### `POST /v1/actions/{request_id}/cancel`

Consumes and cancels a pending proposal. A cancelled proposal cannot execute.

### `GET /v1/audio/{response_id}`

Returns generated response audio using short-lived authorization. Audio expires
and is removed according to gateway retention configuration.

## Cards and errors

A card has a stable `kind`, title of at most 32 characters, body of at most 240
characters, optional footer, severity, update time, and a continuation
indicator when content is truncated. Firmware controls final
layout. Error responses include a stable machine-readable code and safe display
message; stack traces, credentials, provider payloads, and command output do not
cross the device boundary by default.

## Compatibility rules

- Additive optional fields are backward compatible within v1.
- Removing fields, changing meanings, or changing authentication requires a new
  major version.
- Schema changes update gateway tests, firmware parsing tests, fixtures, and
  this document in one pull request.
