# Milestone 1 verification

Completed 12–13 September 2026. Existing successful tests were retained when work resumed; the full suite was not repeated unnecessarily.

## Automated results

- Legacy characterization: **3 passed** before maintained extraction checks.
- Maintained calculation development checks: **15 passed**.
- Application route development checks: **4 passed** (migration checked in final suite).
- Complete relevant suite: **23 passed in 8.93 seconds**. Four deprecation warnings come from Flask-Migrate's generated `get_engine()` compatibility adapter; schema creation and repeated initialization both pass.
- Browser-discovered correction: starting a quote from a customer-linked URL used an undefined Jinja `int` callable. Changed to the Jinja integer filter; added the parameterized URL to the existing page integration test. **That focused test passed in 10.85 seconds**. No calculator changed afterward.

Tests cover legacy and maintained full/half/stair fixtures, bead/ledge boundaries, exact stair geometry and separate packing assertions, kerf, overlong cuts, impossible widths/slope, invalid inputs, deterministic labels, splitting, real-demand aggregation, purchased/required semantics, pricing and empty quotes, authentication/CSRF, persisted edits, unchanged sibling items, price snapshots/explicit refresh, stale revisions, cross-quote ownership, migrations and idempotent seeds.

## Browser smoke test

Used a separate temporary database at `/private/tmp/timber-milestone1-smoke`; no test customers or administrator were added to `.local-data/timber.db`.

- First-run administrator setup, logout and subsequent login succeeded.
- Created a customer and quote `TT-000001`.
- Created Living room and Hall & stairs areas.
- Added TV wall (full 3000×2400, 4×2), Window wall (half 3000×1000, 4×1) and the exact measured stair golden case.
- Combined saved quote: **£290**, required panelling **37.380 m**.
- Reopened from the quote list. Changed only the full wall length to 4000 mm; unsaved state showed pending totals, and saving updated the quote to **£310**, required panelling **40.380 m**.
- Half and stair items remained present. Stair retained 250×800 / 300×960 dimensions, 33.56° slope, 16.78° mitre, 61.78°/28.22° settings, 2 angled/2 transition columns and 2 horizontal/3 vertical strips.
- Inspected setup, dashboard, customers, quote list/editor, materials/pricing and settings.
- Mobile inspection exposed grid/table min-content overflow. Added `min-width: 0` to grid children; subsequent dashboard and quote checks showed document width equal to viewport width, with tables contained in their scroll panels. This was CSS-only and required no calculator test rerun.

## Scope boundaries

Stair saw orientation, the 30 mm workshop allowance and ledge interpretation still require physical confirmation. Ambiguous stair bead configurations fail explicitly. The full deferred scope is listed in README; no deployment, tagging or publishing was performed.

Verification used `/private/tmp/timber-verify-venv` with the same pinned requirements after workspace virtual-environment imports stalled on local file reads. The clean working database contains 31 materials and no users, customers or quotes. The development server was started on port 2112 against that clean database. Automatic browser approval later rejected the final attempt to display its setup page, citing the usage limit; the earlier setup/login and complete smoke checks above had already succeeded. No browser workaround was attempted.

## Evidence integrity observation

No historical application source was edited, moved or removed by this milestone. The final inventory still contains 239 files, but the whole-tree fingerprint is `663854c6156d2ff6993d443da81d30e5212b5a800a8d9495b41c13e3fb0569f9`, differing from the audit's `4e60e83c9f7fe4468c69487623463827a3ebfada10e5957039632860ab219838`.

String and Path sorting produce identical order here. The only evidence file with a modification timestamp after 2026-09-12 19:00 UTC is `old_evidence/.DS_Store` (2026-09-12 23:34:34 UTC), consistent with external macOS folder-metadata activity. There is no saved pre-milestone per-file hash manifest, so that observation cannot conclusively attribute every byte of the aggregate drift. The metadata was left untouched; the report does not claim a byte-identical whole evidence tree.
