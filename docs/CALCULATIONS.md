# Milestone 1 calculation recovery

The audit in `LEGACY_RECOVERY_AUDIT.md` remains the forensic reference. Historical files are untouched. Runtime source and seed data live entirely outside `old_evidence/`.

## Provenance and flow

`routes.py` → `services/quotes.py` → `calculations/sections.py` → `geometry.py` / `packing.py` → `pricing.py` → persisted JSON results and templates.

Recovered from `old_evidence/tkinter-version/src/core/logic/`:

| Maintained behaviour | Historical source |
| --- | --- |
| Full square opening dimensions, separate vertical/horizontal groups | `full_wall/calc_full_wall.py::calc_square_full` |
| Half square rails, verticals and middle pieces | `half_wall/calc_half_wall.py::calc_square_half` |
| Measured stair geometry, classification, vertical selection and 30 mm allowance | `half_wall/calc_half_stairs.py::calc_stair_half` |
| Straight perimeter bead, under-ledge bead, bounded stair bead support | `shared/bead_calculations.py` |
| Ledge run and ripping concepts | `half_wall/calc_half_ledge.py`, shared legacy material totals |
| Deterministic first-fit decreasing length packing | `shared/layout_strips.py` |
| Slat-first sheet ripping, material/pricing concepts | shared material totals and legacy job pricing described in audit §§15,17 |

Characterization tests execute selected historical functions from source in memory, with minimal variable adapters; they neither import GUI modules nor write bytecode into evidence. Maintained calculations accept ordinary values and return structured dictionaries. Each cut retains its originating work item, material, role, dimensions, label, allowance, angle metadata and join ID. Quantity is expanded to individual cuts (each quantity 1) before packing.

## Preserved formulas and golden case

Straight square width = `(wall_length − (horizontal_count + 1) × slat_width) / horizontal_count`. Height uses the equivalent vertical expression. Half-wall verticals span `panel_height − 2 × slat_width`; intermediate horizontals fill the square width. Full-wall verticals span the complete wall height. Historical two-decimal geometry rounding is retained.

Stair run = wall length minus lower and upper landings. Slope angle uses `acos(run / measured_slope_length)`. Historical angled-square width **and height** are divided by the cosine. Opening positions determine flat, angled and transition columns. Vertical-piece selection and middle-piece handling preserve the historical branch rules.

Golden fixture: wall 1500, panel 1000, landings 250/250, slope 1200, grid 4×1, slat 100, stock 2440, kerf 3 mm:

- Run 1000; slope angle 33.56°; slope mitre 16.78°.
- Flat opening 250×800; angled opening 300×960 mm.
- Top/bottom displayed settings 61.78° / 28.22°.
- Transition → angled → angled → transition; counts 0 flat, 2 angled, 2 transition.
- Two horizontal strips and three vertical strips.

Workshop allowance is explicit: top upper landing **+30 mm**, top lower landing **−30 mm clamped to zero**. Bottom landings and slope lengths are unchanged. Zero-length clamped pieces are not purchased. A split cut carries the allowance metadata once, on its first piece. These are preserved workshop instructions, not newly inferred geometry.

Acute and obtuse values are included angles; top/bottom and slope mitre retain historical displayed cut-setting terminology. Physical saw orientation and workshop allowance need later verification. The UI does not claim these are universal saw settings.

## Deliberate, tested corrections

- Kerf is charged **between pieces** in a stock strip: `sum(lengths) + kerf × (count − 1)`. The same rule controls placement and reported usage. Legacy incorrectly rejected the exact fit 500+497+3 in 1000 mm; maintained packing accepts it. Normal regression counts remain unchanged. Zero kerf is permitted; negative/nonfinite kerf or kerf above 50 mm is rejected.
- Pieces exceeding stock are rejected unless the calculator explicitly permits a joined run. Rails, ledges and stair runs split into pieces no longer than stock. Splitting conserves required length; legacy subtracted kerf from installed run demand. Square frame pieces and full-height verticals cannot silently overhang stock.
- Labels travel with their cut dictionaries during sorting. Historical stair label reassignment after sorting is removed.
- Positive finite dimensions, sheet-width bounds, count limits and piece limits prevent unsafe packing and historical nontermination. Limits are 100 squares per axis, 1000 squares per item, 100 items and 50 rooms per quote; pack capacity is 20,000 pieces per call.
- Empty quotations do not attract delivery, cutting, mastic or time charges. Invalid items replace their derived results with errors and empty cuts; a quote containing one has no final price.

## Materials and pricing

Each work-item group is length-packed independently, preserving historical grouping. The quote collects the **actual packed strip demands** and packs MDF rip widths into sheets, slats before ledges. Different widths/materials remain identifiable. This is deterministic first-fit, not a globally optimal cutting solver. It does not combine spare lengths across separate work-item groups.

Required material is the sum of actual cuts, including the documented workshop allowances. New purchase units are MDF sheets or bead stock lengths. Results separately retain allocated strip length, length kerf, length remainder, purchased MDF area and sheet rip remainder. No owned stock is allocated yet; `allocated_existing_mm` is explicitly zero. Material cost is purchase units × the saved unit price. Work-item pricing contains installed demand and labour; shared sheet purchasing is priced at quote level to avoid charging the same pooled sheet twice.

Historical pricing: panelling and finish labour use their respective per-metre rates; mastic is `ceil(required_total_m / coverage × 1.5)`; nonempty MDF cutting is `(strip_count + 1) × cutting_rate`; delivery applies when material exists. Take-home is the greater of per-metre labour and days/hours allowance. The total rounds upward to £10. Monetary components are rounded to pennies. No tax policy or additional invoicing behaviour is inferred.

Catalogue and pricing are JSON snapshots on each quote, independent of editable current database rows. Explicit refresh recalculates all items with the new snapshot. A quote revision counter prevents stale browser tabs overwriting newer saves. Generic string work-item types and JSON inputs/options/results permit later calculators without redesigning quote ownership.

## Supported boundaries

- Full and half straight bead preserve perimeter behaviour; half ledge with bead also includes the under-ledge run.
- Stair bead is supported only for single-row layouts without transitions and without ledge. Historical transition rectangles, multi-row bead counts and stair under-ledge geometry are not sufficiently established; these selections give an explicit unsupported error and no invented totals.
- Ledge uses an explicit confirmed rip width. Historical 2×/3× choices remain raw options; selecting one suggests a width but does not establish a physical interpretation. Stair ledge run is lower landing + measured slope + upper landing.
- Historic MDF, bead and dado catalogue data are seeded once. Dado style vocabulary and 45/70 mm preferred 3000 mm stock metadata are retained; no dado cuts are generated in this milestone.
- Customer edits update the reusable customer record. Quote price snapshots are implemented; immutable customer/address revisions are not.
- First-run administrator authentication is intentionally simple. No multi-user roles UI, account recovery or production deployment is included.
