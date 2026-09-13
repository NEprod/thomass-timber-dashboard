# Milestone 2 — deployment verification

Starting HEAD: `a728116`, with a clean working tree and Milestone 1 acceptance **B**. No calculator, golden expectation, existing regression test, schema or historical evidence content was changed. The synthetic stair fixture remains calculation characterization, not physical saw verification.

## Deployment delivered

- Digest-pinned Python 3.13.15 Bookworm slim, pinned production dependencies, Gunicorn 26.2.0, Linux amd64.
- Production binds `0.0.0.0:2112`, debug disabled; one WSGI worker/two threads, stdout/stderr logging, SIGTERM shutdown. The unnecessary Gunicorn administrative socket is disabled for non-root operation.
- `/data` holds SQLite and a generated persistent session key; `/uploads` is prepared without implementing attachments. Existing `TIMBER_DATA_DIR` remains supported alongside `DATA_DIR`.
- Startup checks directory access, applies existing Alembic migrations and missing-row seeding, then execs Gunicorn. Failures terminate startup; no reset/recreation path was introduced.
- Default image user `1000:1000`; Unraid template selects `99:100` with documented host ownership. No privileged runtime or recursive host ownership changes.
- Public `/health` returns only `{"status":"ok"}`; Docker health check probes it. Business authentication, CSRF and password hashing remain intact. Data/upload paths are not publicly served.
- Unraid XML and minimal Compose configuration; README covers setup, variables, permissions, persistent mappings, updates, backups, CI and release policy. No icon URL was invented and no actual Unraid host was accessed.

## Local acceptance evidence

- Two focused deployment tests passed: health without database/admin; persistent generated key/path handling, debug disabled and rejection of short production secrets.
- Production image built successfully. Image inspection confirmed `linux/amd64`, non-root default user and only exposed port `2112/tcp`.
- `python tests/container_smoke.py timber-m2:validation 12112` passed. Host 2112 was occupied by the existing development server, which was left running; the container still used 2112.
- Fresh empty volumes initialized and supported first administrator creation, authenticated CSRF-protected customer/quote/room/work-item creation and calculation, plus recognizable material/pricing edits.
- Stop/remove/recreate used the same two volumes. All rows in user/customer/quote/room/work-item/material/pricing/migration tables matched, including snapshots; generated key and signed session persisted. Fresh login succeeded, setup stayed closed, uploads persisted, health returned 200 and SIGTERM exited cleanly. Tested runtime UID/GID: `99:100`.
- The smoke harness was corrected for Docker's empty-volume ownership copy-up and Flask-Login's normal `next` query parameter. Earlier port-2112 requests reached the old development server; the final run used 12112. These were harness/environment corrections, not calculation changes.
- Full completion suite: **25 passed, 4 warnings in 4.29 seconds**, under production Python 3.13.15. The four warnings are the existing migration `get_engine()` deprecation; calculation expectations were unchanged. An earlier read-only Docker bind-mount attempt failed during collection with host file-sharing `EIO`; no tests executed in that attempt. The completion run uses an exact staged Git archive copied inside the production container.
- Unraid XML parsed and expected WebUI/path mappings checked. Workflow YAML parsed and release gating, destinations, secret references and tag patterns reviewed. Compose validation and deployment diff checks passed.

## Evidence and credential handling

The original 239-file manifest matched at baseline and completion: **239 files unchanged, none added or removed**. The tracked-file credential-pattern scan and runtime-secret exclusion check passed. Historical source/configuration was previously ignored by Git, so 116 existing files are now preserved as ordinary Git files, with their existing bytes and executable modes. This supplies characterization evidence to CI. Nested historical `.git`, caches, editor/OS metadata stay local; the entire evidence tree is excluded from the production image. No evidence was moved, rewritten or deleted.

GitHub identity `NEprod`, origin `https://github.com/NEprod/thomass-timber-dashboard.git` and Docker Hub identity `neprod` were verified. The initially empty remote was fetched before publication. Docker Hub login succeeded; `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` were configured as GitHub repository secrets following explicit user authorization after the initial approval-review rejection. No credential values were printed or written to project files.

## Release gate

The `Tests` workflow validates pushes/PRs and is reused by `Release image`. Only stable semantic tag pushes publish, after tests, Docker build and persistence smoke checks pass. `v1.0.0` produces `neprod/thomass-timber-dashboard:{1.0.0,1.0,1,latest}`; ordinary branch/PR builds do not publish. Actions use immutable commit pins and read-only repository permissions. Remote commit/tag, workflow result and registry digests must be verified before declaring the milestone complete.

Actual Unraid installation, configuring the host mappings/ownership, initial administrator creation on that installation and routine backups remain operator steps. Physical stair saw/allowance validation remains non-blocking as recorded in Milestone 1. No Milestone 3 feature work is included.
