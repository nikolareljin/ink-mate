# Extension guide

## Providers

STT, LLM, and TTS adapters implement the gateway's typed provider interface and
return normalized results. New adapters must define health behavior, bounded
timeouts, cancellation, safe error mapping, and tests with network calls mocked.
Secrets are read indirectly from environment variables and never serialized to
device responses or normal logs.

## Local application adapters

The optional local adapter host connects the gateway to explicitly approved
applications on the same computer. It binds to `127.0.0.1` only and stores its
state under `~/.local/state/inkmate/adapters` by default. It is not a LAN API.

Start it in the foreground with `./dev run adapter-host`. The first start creates
an ignored `.env` with a random host token. For a user service, run
`./dev adapters install-service --start --yes`.

Adapters register either a loopback HTTP endpoint or a fixed absolute CLI argv.
Every registration includes a versioned manifest. The host fingerprints the
manifest and transport target together; any change returns the adapter to
`discovered` and blocks it until it is approved again.

```sh
./dev adapters list
./dev adapters approve workflow FINGERPRINT --yes
./dev adapters grant workflow DEVICE_ID --yes
```

Approval prints a per-adapter token. Store it in the adapter's local
configuration so its HTTP endpoint can verify the host request. Do not put it
in a manifest or commit it to a repository.

The gateway accepts only an explicit adapter request:

```text
adapter workflow work.next project=inbox
```

Parameters are checked against the operation schema before the adapter runs.
Read operations return one short card. Mutating operations produce a physical
device confirmation first. Accepted jobs are retained for seven days and can be
listed with `./dev jobs`.

Adapter commands receive one JSON invocation on standard input and must write
one JSON result on standard output. Shell parsing is never used. HTTP adapters
receive the same invocation at `POST /v1/invoke` with their per-adapter token.
Both transports must return `status`, `title`, `body`, `severity`, and, for an
accepted job, `job_id`.

An HTTP registration has this shape. The host rejects non-loopback endpoints
and unknown fields.

```json
{
  "manifest": {
    "schema_version": "1",
    "adapter_id": "workflow",
    "version": "1.0.0",
    "display_name": "Workflow",
    "transport": "http",
    "operations": [{
      "operation_id": "work.next",
      "display_name": "Next work item",
      "mode": "read",
      "timeout_seconds": 5,
      "job_allowed": false,
      "input_schema": {
        "properties": {"project": {"type": "enum", "values": ["inbox"]}},
        "required": ["project"]
      }
    }]
  },
  "endpoint": "http://127.0.0.1:9001"
}
```

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
