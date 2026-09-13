# Thomas Timber Management

Editable quotations for full-square, half-square and measured stair panelling. Flask presentation, pure Python calculations, SQLite persistence and database migrations. Default port **2112**.

## Local startup

Python **3.13** is the supported development, CI and production runtime.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock -r requirements-dev.txt
flask --app app init-db
python run.py
```

Open http://127.0.0.1:2112 and create the first administrator. No default credentials exist. Subsequent visits require sign-in. `init-db` upgrades the schema and inserts missing catalogue records; it preserves edited prices and existing quotes.

By default, the database and generated session key are stored in `.local-data/` (ignored by Git). Set `TIMBER_DATA_DIR` to an absolute writable directory to use another location. Keep its `timber.db` and `session.key` together when backing up or restoring. `SECRET_KEY` can override the generated key. Use `TIMBER_SECURE_COOKIES=1` when serving over HTTPS. Do not expose an installation before completing administrator setup. The bundled server is for local development only; use the Docker/Gunicorn deployment below for permanent service.

## Working with quotations

1. Create a customer, then a quotation.
2. Add rooms or areas; add named work items within them.
3. Enter measurements in millimetres and select a finish. Save each changed section to recalculate.
4. Review labeled cuts, material purchases and the quote price. Reopen and edit the same quote at any time.

Prices and stock dimensions are snapshotted when a quote is created. Editing **Materials & pricing** does not change existing quotes. **Use current catalogue & recalculate** explicitly replaces a quote's snapshot. Incomplete items have no stale cuts; the final price remains pending until all items are valid. Labour and mastic use required material, while material costs use purchased stock. Quote dates and appointments are entered in local time; saved/updated timestamps use UTC.

## Tests

```sh
pytest -q
```

The suite includes read-only legacy characterization, maintained calculator regression, authentication, migrations, persistence and snapshot tests. Historical characterization requires the preserved `old_evidence/` tree; maintained runtime code never imports it. No Tkinter GUI is required.

## Project layout

- `app/calculations/`: recovered geometry, explicit cuts, bounded first-fit packing and pricing.
- `app/services/`: work-item recalculation and quotation aggregation.
- `app/models.py`, `migrations/`: customers, quotes, rooms, work items, accounts and configuration.
- `app/templates/`, `app/static/`: server-rendered responsive application.
- `app/data/catalogue.json`: historical catalogue seed copied into the maintained application.
- `old_evidence/`: immutable historical source/configuration preserved for characterization tests; nested Git metadata and caches stay local.

See [calculation provenance and limitations](docs/CALCULATIONS.md) and the [original recovery audit](docs/LEGACY_RECOVERY_AUDIT.md).

Milestone 3 adds straight dado styles, segmented stair dado, stair bead provisions and preserved recalculation context. See [workshop rules and validation limits](docs/MILESTONE_3_DADO_STAIR.md).

Deferred: inventory/offcuts, attachments, quote PDF/revisions UI, calendar/iCal, job workflow, alcove calculators, dashboard analytics.

## Docker deployment

The production image uses digest-pinned Python 3.13.15 / Debian Bookworm slim, pinned production dependencies in `requirements.lock`, and Gunicorn 26.2.0 (one worker, two threads). Supported release platform: **linux/amd64**, suitable for Unraid. Local ARM machines can build/run with `--platform linux/amd64` for the same release image.

```sh
docker build --platform linux/amd64 -t neprod/thomass-timber-dashboard:local .
docker volume create timber-data
docker volume create timber-uploads
docker run -d --name timber --restart unless-stopped --stop-timeout 40 \
  --platform linux/amd64 -p 2112:2112 \
  -v timber-data:/data -v timber-uploads:/uploads \
  neprod/thomass-timber-dashboard:local
```

Alternatively, `docker compose up -d --build` uses the included minimal Compose file and named volumes. For a published image, use `docker compose pull` followed by `docker compose up -d --no-build`. Never use `docker compose down -v` when retaining data.

Open `http://SERVER:2112/` and create the first administrator before allowing other users to access the installation. There are no default credentials. Startup checks writable paths, runs the existing migrations and inserts only missing seed records, then replaces the startup process with Gunicorn. Migration/permission/configuration failures stop startup visibly; no database is deleted or recreated. Use one application container per SQLite data directory; do not run concurrent migration/startup processes against the same installation.

| Setting | Container default / meaning |
| --- | --- |
| `APP_PORT` | `2112`, bound to `0.0.0.0`; changing it also requires changing the container side of the port mapping |
| `DATA_DIR` | `/data`; SQLite `timber.db`, generated `session.key`, future application-owned state |
| `TIMBER_DATA_DIR` | Optional existing setting; takes precedence over `DATA_DIR` |
| `UPLOAD_DIR` | `/uploads`; writable persistent directory prepared for future uploads, no attachment feature or public file serving |
| `SECRET_KEY` | Optional: leave empty to generate a random 64-character key in `/data/session.key` with mode 0600; retained across replacement |
| `TIMBER_SECURE_COOKIES` | `0` for LAN HTTP; set `1` when using HTTPS |
| `TIMBER_ENV` / `FLASK_DEBUG` | Startup enforces `production` / `0`; Flask debug is disabled |

An explicitly supplied production `SECRET_KEY` must contain at least 32 characters; use a cryptographically random stable value. Do not put it in Git, screenshots or shell command arguments. Keep its private deployment configuration backed up if overriding the generated key. Changing/removing the effective key invalidates existing sessions. The default generated/persisted key needs no manually copied secret.

The image runs as UID/GID **1000:1000**. Named volumes inherit prepared ownership. Bind-mounted directories must be writable by the selected runtime UID/GID; no privileged container or automatic recursive host ownership changes are used. Only HTTP port 2112 is exposed. Gunicorn access/error and migration logs go to `docker logs timber`; secrets, forms and URL query strings are not logged by the configured access format. SIGTERM allows up to 30 seconds for graceful worker shutdown; give Docker 40 seconds.

`GET /health` returns `{"status":"ok"}` without authentication, including before admin setup. Docker probes it every 30 seconds. This is process liveness, not database readiness or a monitoring system; migration failure prevents WSGI startup. All business pages retain existing authentication/CSRF protection and hashed passwords. `/data` and `/uploads` are not static web roots. Use LAN/VPN access or an HTTPS reverse proxy for remote use; HTTPS-only cookies require HTTPS access.

## Unraid

Template: [unraid/thomass-timber-dashboard.xml](unraid/thomass-timber-dashboard.xml). Image: `neprod/thomass-timber-dashboard:latest` (or pin `:1.0.0`). WebUI: `http://[IP]:[PORT:2112]/`; bridge network, host/container port 2112 by default.

Prepare these **new application directories** on Unraid before starting:

```sh
mkdir -p /mnt/user/appdata/thomass-timber-dashboard/data /mnt/user/appdata/thomass-timber-dashboard/uploads
chown 99:100 /mnt/user/appdata/thomass-timber-dashboard/data /mnt/user/appdata/thomass-timber-dashboard/uploads
chmod 700 /mnt/user/appdata/thomass-timber-dashboard/data /mnt/user/appdata/thomass-timber-dashboard/uploads
```

Map `.../data/` to `/data` and `.../uploads/` to `/uploads` read/write. The template selects non-root `--user=99:100`, matching Unraid's nobody/users ownership. If restoring existing data, ensure the restored files and session key also belong to the selected UID/GID. Leave the optional masked `SECRET_KEY` field empty to use the generated persistent key. Set HTTPS-only cookies only when appropriate.

Copy the XML into `/boot/config/plugins/dockerMan/templates-user/` on Unraid, then select it from **Docker → Add Container → Template**. This is a Community Applications-style user template, not a claim of Community Applications store registration. Start and complete administrator setup; subsequent container updates must retain both mappings. No stable icon URL exists yet; adding an icon is a small future follow-up. No live Unraid host was accessed by the local acceptance tests.

## CI and releases

Repository: [NEprod/thomass-timber-dashboard](https://github.com/NEprod/thomass-timber-dashboard). Images: [Docker Hub](https://hub.docker.com/r/neprod/thomass-timber-dashboard).

- `.github/workflows/test.yml`: pull requests and pushes to `main` run Python 3.13 tests, build the production image, then run the fresh-install/replacement-container smoke test. It is also reusable by releases.
- `.github/workflows/release.yml`: pushing a stable `vMAJOR.MINOR.PATCH` tag runs that validation before publishing the image. Pull requests and ordinary branch pushes **never publish**. Pre-release/non-semantic tags are rejected before publishing.
- Required repository secrets: `DOCKERHUB_USERNAME` (`neprod`) and `DOCKERHUB_TOKEN` (a Docker Hub PAT with image write permission). Configure through GitHub's private repository-secret settings; no credential is stored in the repository. Actions are pinned to immutable commits with read-only repository permissions.
- `v1.0.0` publishes `neprod/thomass-timber-dashboard:1.0.0`, `:1.0`, `:1`, and `:latest`. Publish releases in increasing version order; floating aliases follow the latest published release. Do not move an existing release tag. No separate development image tag is used.

After reviewing a clean, validated `main` commit:

```sh
git push origin main
git tag -a v1.0.0 -m "Thomas Timber Management 1.0.0"
git push origin v1.0.0
```

GitHub Actions performs the release build/push. Check its result and Docker Hub tags before updating Unraid. Future work uses small feature branches/PRs; `main` remains releasable, without GitFlow or history rewriting.

## Updating and backup

Back up **all of `/data`** and `/uploads` before pulling an update; stop the application during a simple filesystem copy so SQLite and any journal files are consistent. Include `/data/session.key`, or separately retain an overridden secret. Protect backups because they contain customer, account and quote information. The database includes users, customers, quotes, rooms, work items, calculation/price snapshots and edited material/pricing configuration; the image's JSON catalogue is only an initial/missing-row seed.

Update model: pull new image → stop/remove old container → recreate with the **same persistent mappings** → migrations → existing application data. Do not delete volumes or run database resets. If migration fails, inspect logs and retain the data for diagnosis; do not run an old image against a newer schema without checking compatibility. For rollback, restore the pre-update backup with its matching image version. No automated backup subsystem is included.

For repeatable deployment acceptance only: `python tests/container_smoke.py IMAGE [HOST_PORT]`. It creates disposable volumes, uses HTTP with real CSRF/session handling, exercises UID 99:100, compares persisted tables before/after replacement, and cleans up only its own resources. It does not touch a real installation.

Production configuration references: [Gunicorn settings](https://gunicorn.org/reference/settings/) and [Docker GitHub Actions](https://docs.docker.com/build/ci/github-actions/).
