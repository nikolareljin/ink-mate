# Security and threat model

Assets include pairing/cloud credentials, voice and transcript content, host/workspace data, action authority, and firmware integrity. Physical device, LAN, gateway container, providers, host executor, and optional coding-agent workspaces are separate trust boundaries.

| Threat | Control |
| --- | --- |
| API impersonation | Unique device tokens, rotation, constant-time validation |
| Replay | Unique IDs, expiry, device binding, atomic single-use consumption |
| Prompt injection | Model output cannot invoke executors; policy is authoritative |
| Command injection | Fixed executable/argument vectors; no shell parsing |
| Path escape | Canonical paths, traversal/symlink rejection, workspace allowlist |
| Accidental mutation | Explicit classification and physical confirmation |
| Proposal substitution | Bind exact operation, arguments, target, device, and expiry |
| Secret/privacy leakage | Environment indirection, redacted logs, short audio retention |
| Malformed input | Schema, type, duration, body, field, and response limits |
| Public exposure | Loopback default, LAN firewall, optional correctly configured TLS proxy |

Confirmation is a security boundary: the display must show the exact normalized action and target. Confirmation expires quickly and is consumed even if execution fails.

Residual risks remain. Plain HTTP lacks confidentiality against a LAN attacker. A stolen paired device may authorize actions until revoked. Physical confirmation cannot rescue an overbroad template. Host compromise defeats gateway controls. E-paper retains visible data after power loss, so cards must avoid secrets.
