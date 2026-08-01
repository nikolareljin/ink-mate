# Extension guide

## Providers

STT, LLM, and TTS adapters implement the gateway's typed provider interface and
return normalized results. New adapters must define health behavior, bounded
timeouts, cancellation, safe error mapping, and tests with network calls mocked.
Secrets are read indirectly from environment variables and never serialized to
device responses or normal logs.

## Status sources

Status adapters are read-only. Keep payloads small and map them to card fields
rather than exposing arbitrary upstream JSON. Generic HTTP sources require an
explicit URL allowlist, authentication-by-environment, response size limits,
timeouts, and content-type validation.

## Actions

Actions are fixed executable plus argument templates, not command lines. Define
which arguments are constants, constrained values, or validated paths. Resolve
paths before checking workspace allowlists and reject symlink escapes. Mark all
state-changing actions as mutating so they require physical confirmation.

An adapter may propose an action but cannot execute it directly. The central
service binds the proposal to a paired device, gives it a short expiry, and
consumes it once. Add tests for denial, expiry, replay, target substitution,
path traversal, cancellation, and provider failure.

Codex and Claude job adapters remain disabled by default. Limit them to named
workspaces. Inspecting status may be read-only; starting or cancelling a job is
mutating and requires confirmation.

## Cards

Prefer a new stable card kind only when an existing kind cannot represent the
information. Design for 200 x 200 monochrome output, concise copy, predictable
wrapping, and stale/offline state. Update schema fixtures and firmware layout
tests with every new kind.
