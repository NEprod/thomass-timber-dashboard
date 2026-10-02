# Calculation recovery and maintained extensions

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

Stair run = wall length minus lower and upper landings. Slope angle uses `acos(run / measured_slope_length)`. Historical angled-square width **and height** are divided by the cosine. Opening positions determine flat, angled and transition columns. These recovered fields remain calculation references; exact MDF and opening-profile cut demand comes from the canonical installed polygons described below.

Golden fixture: wall 1500, panel 1000, landings 250/250, slope 1200, grid 4×1, slat 100, stock 2440, kerf 3 mm:

- Run 1000; slope angle 33.56°; slope mitre 16.78°.
- Recovered reference fields: flat 250×800; angled 300×960 mm. These are not the exact installed opening dimensions.
- Top/bottom displayed settings 61.78° / 28.22°.
- Transition → angled → angled → transition; counts 0 flat, 2 angled, 2 transition.
- Two horizontal-group strips and two vertical-group strips under the exact base-cut policy; the room packer remains the authoritative combined purchase plan.

### Exact stair base cuts (v1.5.4)

Installed polygons are derived from the measured route, perpendicular material widths and shared mitre intersections. The minimum blank length is the polygon's axial long-point span, not its centreline, longest diagonal, historical cosine-expanded height or an arbitrary fitting allowance. The existing six-decimal cut/packing precision is retained.

For exact MDF landing/slope rails and vertical battens, this replaces the old +30/−30 landing rule and inflated batten demand. Exact straight intermediate members are clipped to their column endpoints. Intermediate members crossing a bend remain site-fit until separate member/joint endpoints are modelled. Existing automatic-join permissions are preserved; over-stock vertical/middle members are rejected.

A known stair Dado profile width is centred on the measured Dado route and offset to physical edges with shared mitre seams. Its long-point extent determines the base cut before the existing stock selection and splitting. Absolute installation height does not affect this length.

Opening bead and square Dado use the existing straight-frame convention: outside profile edge on the opening boundary, zero extra inset, catalogue width extending inward. Adjacent offset lines intersect at shared mitre seams. All six pieces of each representative transition have exact physical polygons and long-point base cuts. Old conservative provisions are retained only as audit comparison metadata, never as demand. The configured 9mm bead and 21mm square profile fit the representative acute transition. A 45mm square profile does not: the short segment's mitred inner edge collapses, so the calculator rejects that physical fit rather than fabricating a shape. The continuous centred 45mm Dado route remains valid.

The 4500mm wall / 1000mm panel / 4000mm slope / 2500mm run / 100mm rail fixture yields a 1048.038446mm lower top landing blank, 4048.038446mm slope blanks and 804.899960mm sloped vertical blanks. Room packing, charge and procurement use these requirements. No spare stock or hidden contingency is added. Recalculation uses the new policy; merely reopening a saved quote does not silently reprice it.

Acute and obtuse values are included angles; top/bottom and slope mitre retain historical displayed cut-setting terminology. Physical saw orientation still needs verification. Truly unmodelled members remain marked site-fit; exact profiles do not. The UI does not claim these are universal saw settings.

## Deliberate, tested corrections

- Kerf is charged **between pieces** in a stock strip: `sum(lengths) + kerf × (count − 1)`. The same rule controls placement and reported usage. Legacy incorrectly rejected the exact fit 500+497+3 in 1000 mm; maintained packing accepts it. Normal regression counts remain unchanged. Zero kerf is permitted; negative/nonfinite kerf or kerf above 50 mm is rejected.
- Pieces exceeding stock are rejected unless the calculator explicitly permits a joined run. Rails, ledges and stair runs split into pieces no longer than stock. Splitting conserves required length; legacy subtracted kerf from installed run demand. Square frame pieces and full-height verticals cannot silently overhang stock.
- Labels travel with their cut dictionaries during sorting. Historical stair label reassignment after sorting is removed.
- Positive finite dimensions, sheet-width bounds, count limits and piece limits prevent unsafe packing and historical nontermination. Limits are 100 squares per axis, 1000 squares per item, 100 items and 50 rooms per quote; pack capacity is 20,000 pieces per call.
- Empty quotations do not attract delivery, cutting, mastic or time charges. Invalid items replace their derived results with errors and empty cuts; a quote containing one has no final price.

## Materials and pricing

Each work-item group is length-packed independently, preserving historical grouping. The quote collects the **actual packed strip demands** and packs MDF rip widths into sheets, slats before ledges. Different widths/materials remain identifiable. This is deterministic first-fit, not a globally optimal cutting solver. MDF and bead retain this grouping. Milestone 3 pools identical dado stock across work items at quote level; its shared plan is shown in the quote summary.

Required material is the sum of actual cuts, including the documented workshop allowances. New purchase units are MDF sheets or bead stock lengths. Results separately retain allocated strip length, length kerf, length remainder, purchased MDF area and sheet rip remainder. No owned stock is allocated yet; `allocated_existing_mm` is explicitly zero. Material cost is purchase units × the saved unit price. Work-item pricing contains installed demand and labour; shared sheet purchasing is priced at quote level to avoid charging the same pooled sheet twice.

Historical pricing: panelling and finish labour use their respective per-metre rates; mastic is `ceil(required_total_m / coverage × 1.5)`; MDF strip cutting is `total prepared full-length MDF strips × saved cutting_rate`, using the packed rip-sheet records also rendered by Workshop Preparation (including accepted dimensional strips; excluding directly nested Cabinet parts and whole-product extras); delivery applies when material exists. Take-home is the greater of per-metre labour and days/hours allowance. The total rounds upward to £10. Monetary components are rounded to pennies. No tax policy or additional invoicing behaviour is inferred.

Catalogue and pricing are JSON snapshots on each quote, independent of editable current database rows. Explicit refresh recalculates all items with the new snapshot. A quote revision counter prevents stale browser tabs overwriting newer saves. Generic string work-item types and JSON inputs/options/results permit later calculators without redesigning quote ownership.

## Supported boundaries

- Full and half straight bead preserve perimeter behaviour; half ledge with bead also includes the under-ledge run.
- Stair opening bead now uses exact catalogue-width mitred polygons under the v1.5.4 policy above, replacing Milestone 3's conservative transition allowances. Straight bead and under-ledge behaviour remain unchanged.
- Ledge uses an explicit confirmed rip width. Historical 2×/3× choices remain raw options; selecting one suggests a width but does not establish a physical interpretation. Stair ledge run is lower landing + measured slope + upper landing.
- Historic MDF, bead and dado catalogue data are seeded once. Dado style vocabulary and 45/70 mm preferred 3000 mm stock metadata are retained; Milestone 3 now generates dado cuts using explicit product-use permissions and new documented layout rules.
- Customer edits update the reusable customer record. Quote price snapshots are implemented; immutable customer/address revisions are not.
- First-run administrator authentication is intentionally simple. No multi-user roles UI, account recovery or production deployment is included.

## Optional Recommended Spare Material (v1.5.5)

Exact Work Item cuts remain unchanged. Deterministic advisory recommendations use
room-owned stock/remainders, structured stair/transition/mitre/site-fit/join and
external-corner metadata. Defaults: up to two full-length MDF strips for stairs;
one strip for straight work lacking recovery capacity; one purchasable linear
length for complex or tight work without practical recovery. Useful straight
linear remainder produces no recommendation. Complex work with recovery is lower
priority. Cabinet sheets have no default spare merely because a Cabinet exists.
PSE uses the linear policy. Invalid components never generate recommendations.

Accepted MDF strips live in the optional `JobMaterialState.dimensional_extras`
JSON list (kind, width_mm, length_mm, quantity); existing `extra_quantity` still
means whole catalogue products. Only full-length MDF strips are supported here.
One record can contain different strip widths. Set quantity to zero to remove an
entry. Migration `h31_dimensional_extra_material` adds the nullable column and
does not reinterpret existing records.

Preview and acceptance use the same side-effect-free room-demand adapter and
unchanged room packing algorithms. Extra demand is not a Work Item and never
adds labour, mastic or installed components. Accepted dimensional strips do increase strip-cut charges because they are physically prepared. Raw stock cost changes
only when repacking changes sheet count. Whole-product extras retain their
existing per-product charging. Owned stock still affects actual procurement
only. Spare strips fitting current sheets consume theoretical remainder:
"No additional sheet required" does not mean material is free. Each quantity's
preview is incremental to current accepted extras; combined selections are
repacked together. Accepted quantities offset the recommendation target so they
cannot be repeatedly offered as missing. No automatic contingency is added.

## Cabinet sheet-cut pricing

Sheet-nesting cutting is the number of recorded guillotine split operations
(`sheet_cut_lines`) multiplied by the saved `cut_cost_per_strip` rate. Each
split appears once, including a cut shared by multiple parts. This is added
to prepared MDF strip cutting; nested parts themselves are never charged as
strips. Linear stock, assembly and installation are excluded. Labour and
raw-stock packing/prices remain separate. The optimiser's edge-trim border is
only a planning/squaring allowance, not a chargeable cut; no border operations
are added. Dimensional-extra repacking retains the recorded sheet-cut charge.
