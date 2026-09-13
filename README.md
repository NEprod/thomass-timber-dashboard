# Thomas Timber Management

Editable quotations for full-square, half-square and measured stair panelling. Flask presentation, pure Python calculations, SQLite persistence and database migrations. Default port **2112**.

## Local startup

Python 3.11 or newer is required (developed with Python 3.13).

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
flask --app app init-db
python run.py
```

Open http://127.0.0.1:2112 and create the first administrator. No default credentials exist. Subsequent visits require sign-in. `init-db` upgrades the schema and inserts missing catalogue records; it preserves edited prices and existing quotes.

By default, the database and generated session key are stored in `.local-data/` (ignored by Git). Set `TIMBER_DATA_DIR` to an absolute writable directory to use another location. Keep its `timber.db` and `session.key` together when backing up or restoring. `SECRET_KEY` can override the generated key. Use `TIMBER_SECURE_COOKIES=1` when serving over HTTPS. Do not expose an installation before completing administrator setup. The bundled server is for local development; production serving and Docker are a later milestone.

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
- `old_evidence/`: immutable historical applications and metadata; excluded from new application commits.

See [calculation provenance and limitations](docs/CALCULATIONS.md) and the [original recovery audit](docs/LEGACY_RECOVERY_AUDIT.md).

Deferred: dado/stair-dado calculations, inventory/offcuts, attachments, quote PDF/revisions UI, calendar/iCal, job workflow, alcove calculators, dashboard analytics, Docker/Unraid, GitHub Actions and Docker Hub publishing.
