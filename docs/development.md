# Development, testing, and CI

## Clone and shared tooling

Clone recursively, or initialize the helper after an ordinary clone:

```sh
git submodule update --init --recursive
```

`scripts/script-helpers` is pinned as a Git submodule and used by local scripts
for consistent logging, Docker Compose discovery, and static-site preview.
GitHub Actions delegates general Python/build orchestration and secret scanning
to reusable workflows in `nikolareljin/ci-helpers@production`. Firmware builds
remain explicit because their ESP-IDF matrix is hardware-specific.

## Local command suite

Run `./update` after cloning to initialize `scripts/script-helpers` and any
nested submodules at the revisions pinned by the checkout. `./update --remote`
is an explicit opt-in to moving submodules to their configured tracking branch;
review any resulting gitlink changes before committing.

`./install` prepares project-local dependencies: ESP-IDF 6.0.2 under
`.tools/esp-idf`, `gateway/.venv` with test dependencies, and `.venv-docs` for
the documentation site. Use `--esp-idf-dir DIR` for a pre-existing toolchain,
`--with-audio` for optional local STT dependencies, or `--with-docker` to opt
in to Docker installation through the shared helpers. `--skip-esp-idf`,
`--skip-gateway`, and `--skip-docs` omit individual groups.

`./build` builds every component by default. Select `--firmware`, `--gateway`,
or `--docs` to narrow it; `--profile v1|v2|both` controls the firmware matrix
and `--esp-idf-dir DIR` selects its toolchain.

`./test` runs gateway tests and Compose validation, both selected firmware
builds plus host tests, and a strict documentation build by default. It accepts
the same component flags, `--profile`, and `--esp-idf-dir` as `./build`.

`./deploy --profile v1|v2 --port /dev/ttyDEVICE --hardware-verified` builds and
flashes one USB-connected board, then opens the serial monitor. The profile,
port, and acknowledgement are mandatory. Use `--skip-build` only for an
already-built matching profile. Never pass `--hardware-verified` until the PCB
revision and memory inspection have been recorded.

## Documentation site

Install the documentation dependencies and build with warnings treated as
errors:

```sh
python3 -m venv .venv-docs
. .venv-docs/bin/activate
python -m pip install -r requirements-docs.txt
mkdocs build --strict
scripts/script-helpers/bin/serve-pages site 8000
```

Pull requests validate the site. A successful build on `main` uploads and
deploys the Pages artifact through GitHub.

## Private firmware provisioning

Public firmware builds deliberately leave `CONFIG_INKMATE_PROVISIONING_POP`
empty and therefore refuse to open BLE provisioning. Create an ignored
`sdkconfig.private` overlay containing a unique random value for each physical
device; never put it in the tracked V1 or V2 profiles. Include that overlay in
`SDKCONFIG_DEFAULTS` only for the device being enrolled. The firmware never
prints the PoP to logs.

## Security checks

The `Secrets Scan` workflow fetches full history and runs gitleaks through
`ci-helpers`. Production configuration belongs only in ignored `.env`,
`sdkconfig`, or `config/secrets/` files.

`./scripts/check.sh` runs locally available checks and reports skipped categories. A skipped check is not a pass. Release evidence must record commands, tool versions, board revision, power source, and observed results.

Gateway tests cover authentication, schemas, mocked providers, timeouts, redaction, allowlists, canonical paths, expiry, cancellation, and replay. Integration tests cover audio to transcript to model to card to speech without public network access.

Firmware host tests cover buttons, recording bounds, layout, protocol parsing, confirmation expiry, refresh scheduling, and offline recovery. CI compiles explicit V1 and V2 profiles and must track flash/partition budgets. Compilation does not validate pins, battery resets, audio, RF, or ghosting.

Release candidates require gateway tests, both firmware builds, schema/example validation, complete peripheral and USB/battery reset results for every claimed board, provisioning and credential rotation, allowed/denied/expired/replayed actions, network recovery, display/audio/low-battery checks, and OTA rollback evidence only if OTA is advertised. Simulated, bench, and physical-device results must be labeled separately.
