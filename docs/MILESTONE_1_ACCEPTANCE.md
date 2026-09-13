# Milestone 1A — Workshop validation & acceptance review

Reviewed 13 September 2026 against **5b40f90**. **Outcome: C — requires user/workshop clarification before release.** Recovered numerical behaviour is consistent with the reviewed fixtures; physical cutting instructions and business prices are not yet workshop-approved. No application formulas, seed prices, UI or evidence were changed.

## Baseline and review limits

The starting working tree was clean and HEAD was `5b40f90`. This review used the existing calculation and integration tests, `CALCULATIONS.md`, `MILESTONE_1_VERIFICATION.md`, and the maintained calculation/service code. A single final full-suite run checks all existing tests plus stronger assertions in the existing quote-edit test; there was no separate repeated baseline suite.

This is numerical and code-path validation, not a physical installation trial. Fixture prices below use **the committed seed**, not a supplier-price lookup or an existing customer's quote snapshot. No working database prices were edited. Prior Milestone 1 browser observations were reused for light UI acceptance; no browser automation was needed.

## Reproducible calculation review

All lengths below are millimetres unless marked m. Common options: 9 mm MDF, sheet 2440×1220 at £18; slat width 100; kerf 3; no time allowance. Bead examples use `bead-glass_bead-9x9`, 2400 mm stock at £2.80. Ledge examples explicitly use an 18 mm rip width. Each row is a **standalone quote**; combined quotes share sheet purchases and charges, so their totals are not the sum of these prices.

### Full wall: inputs → dimensions → cuts → packing

Input 3000×2400, grid 4×2. Opening width `(3000−5×100)/4 = 625`; height `(2400−3×100)/2 = 1050`.

- Verticals: 5×2400; five separate 2440 mm strips.
- Horizontals: 12×625; four strips, each containing three pieces (1881 mm used including kerf).
- Nine 100 mm rips occupy 924 mm of sheet width including eight kerfs: **one MDF sheet**, £18. Required MDF 19.500 m; allocated strip stock 21.960 m; longitudinal kerf 0.024 m and remainder 2.436 m. Unused sheet-width area is separately recorded (0.72224 m²).
- Bead adds 16×625 and 16×1050: 26.800 m required. First-fit packs eight stocks with two 1050s, five with three 625s, and one with a single 625: **14 bead lengths**, 33.600 m purchased, £39.20, 6.746 m remainder after kerf.

Source: `app/calculations/sections.py::calculate` (full branch and `perimeter`), `packing.py::pack`, `pricing.py::aggregate`.

### Half wall: inputs → dimensions → cuts → packing

Input 3000×1000, grid 4×1. Opening 625×800.

- Top and bottom each require 3000, split as **2440+560** with join identity. Combined rails pack `[2440]`, `[2440]`, `[560,560]`: three strips.
- Verticals: 5×800, packed `[800,800,800]` and `[800,800]`: two strips. No middle pieces for one row.
- Five 100 mm rips purchase one MDF sheet. Required MDF 10.000 m; strip stock 12.200 m; remainder 2.188 m after 0.012 m kerf.
- Two-row variant: opening 625×350; the same rails and full-height 800 mm verticals, plus 4×625 middle pieces on two additional strips. Seven rips, one sheet; required MDF 12.500 m.
- Bead for the one-row case: 8×625 and 8×800, 11.400 m. Packing is four `[800,800,625]`, one `[625,625,625]`, one `[625]`: six bead lengths.
- Ledge: 3000 run becomes 2440+560, two **18 mm** rips. Together with the five slat rips these occupy 554 mm of sheet width including six kerfs, still one sheet. Ledge adds 3.000 m of finish labour/application demand.
- Ledge plus bead additionally includes a 3000 under-ledge bead run, split 2400+600 and packed separately from square beads. Eight bead lengths in total, 14.400 m bead demand.

Long-run splitting preserves required length; blade loss is charged during stock packing, not subtracted from the wall. Join positions are stock-driven, not a validated aesthetic or structural joint plan.

### Stair half wall: permanent golden case

Inputs: wall 1500, panel 1000, lower/upper landings 250/250, measured slope 1200, grid 4×1, slat 100, stock 2440, kerf 3.

| Derived value | Result |
| --- | --- |
| Horizontal run | 1000 |
| Slope angle / slope mitre | 33.56° / 16.78° |
| Square / angled square | 250×800 / 300×960 |
| Acute / obtuse included angles | 56.44° / 123.56° |
| Top / bottom displayed settings | 61.78° / 28.22° |
| Column classification | Transition → Angled → Angled → Transition |
| Counts | 0 flat, 2 angled, 2 transition |

Cuts and labels stay attached during sorting:

- Top upper 280 (+30 allowance); top lower 220 (−30); bottom upper/lower 250 each; slopes 1200 each.
- Horizontal stocks `[1200,1200]` (2403 used) and `[280,250,250,220]` (1009 used): **2 strips**.
- Verticals are two 800s and three 960s. Packing `[960,960]`, `[960,800]`, `[800]`: **3 strips**. No middle pieces for one row.
- Five 100 mm rips purchase one sheet; required MDF **7.880 m**, strip stock 12.200 m, remainder 4.302 m after 0.018 m kerf.
- Stair ledge adds a **single 1700 mm demand** (`250+1200+250`), one 18 mm rip, still one sheet. It is a material-length provision, **not an approved segmented landing/slope mitre plan**.
- Golden-case bead is explicitly unsupported because of transitions: it does not silently generate rectangular substitute demand. Single-row, no-transition stair bead remains supported; multiple rows or bead plus ledge are also explicitly blocked.

Source: `geometry.py::stair_geometry`, stair branch of `sections.py::calculate`. Both width and height cosine scaling, transition classification and vertical-selection branches remain unchanged.

### Purchasing and price reconciliation

“Strip m” is full-length stock allocated to MDF rips, **not all the material area in purchased sheets**. MDF required includes ledge where selected. Bead lengths are 2.4 m each. Material subtotal includes stock, mastic, cutting and £10 delivery.

| Standalone case | MDF required / strip m | Sheets | Bead required / purchased m (lengths) | Stock £ | Mastic tubes | Cutting £ | Material subtotal £ | Labour / take-home £ | Rounded total £ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Full plain | 19.500 / 21.960 | 1 | — | 18.00 | 3 | 20 | 56.70 | 95.55 | 160 |
| Full bead | 19.500 / 21.960 | 1 | 26.800 / 33.600 (14) | 57.20 | 7 | 20 | 107.50 | 202.75 | 320 |
| Half plain | 10.000 / 12.200 | 1 | — | 18.00 | 2 | 12 | 45.80 | 49.00 | 100 |
| Half, two rows | 12.500 / 17.080 | 1 | — | 18.00 | 2 | 16 | 49.80 | 61.25 | 120 |
| Half bead | 10.000 / 12.200 | 1 | 11.400 / 14.400 (6) | 34.80 | 3 | 12 | 65.50 | 94.60 | 170 |
| Half ledge | 13.000 / 17.080 | 1 | — | 18.00 | 2 | 16 | 49.80 | 61.00 | 120 |
| Half ledge + bead | 13.000 / 17.080 | 1 | 14.400 / 19.200 (8) | 40.40 | 4 | 16 | 78.00 | 118.60 | 200 |
| Stair plain | 7.880 / 12.200 | 1 | — | 18.00 | 2 | 12 | 45.80 | 38.61 | 90 |
| Stair ledge | 9.580 / 14.640 | 1 | — | 18.00 | 2 | 14 | 47.80 | 45.41 | 100 |

These values were obtained from the maintained calculators and reconciled with their cuts. Deterministic first-fit is preserved; it is not a guarantee of minimum possible stock. Packing stays separate by item/group, with MDF rip widths then pooled by product at quote level.

## Physical questions requiring workshop confirmation

| Question | Current representation / acceptance boundary |
| --- | --- |
| Saw orientation and reference face | `slope_angle` and `*_included_angle` are geometric values; `slope_mitre`, `top_angle_setting`, `bottom_angle_setting` are historical displayed values. Cuts have role labels and angle metadata, but no approved face-up/face-down, left/right, blade tilt, fence or end-specific orientation. Confirm these against an actual fitted sample; do not read every numeric field as a universal saw setting. |
| Stair measurement convention | Confirm how wall/panel height and angled opening dimensions are measured, especially the height cosine scaling and transition verticals. The supplied golden values are preserved, not independently physically certified. |
| 30 mm allowance | Top upper = upper+30; top lower = max(0,lower−30); bottom landings and slopes unchanged. Confirm purpose and applicability to short/zero landings. At lower<30 the net demand increases; zero-length pieces are omitted. |
| Ledge construction | `ledge_width` means rip width in mm on the selected MDF sheet, not thickness, lamination count or number of layers. 2×/3× is stored raw; selecting it in the UI suggests 2 or 3 times current sheet thickness, while the explicit width drives calculation. Later MDF changes do not automatically redefine that confirmed width. Confirm physical projection, layers and dimensions. |
| Stair ledge joints | The current 1700 total is one cut demand; confirm how actual landing/slope junctions should be segmented and mitred before treating this as a workshop cutting schedule. No geometry was invented here. |
| Bead dimensions and adhesive | Straight beads use two widths and two heights per opening, without a separately approved inside/long-point measurement or extra mitre allowance. Confirm that dimension convention and whether all bead/ledge length needs mastic. No compatible bead is seeded for 6 mm MDF; incompatible profiles fail validation. |
| Kerf and joining | Between-piece kerf is the explicit contract, including sheet ripping. It does not separately reserve end trimming, the cut separating a final piece from remainder, defects, or scarf/mitre overlap. Confirm the workshop needs before changing this contract. |

The current angle/role data is sufficient for this recovery stage; no large model refactor is justified. These questions require user or physical evidence, not speculative formula changes.

## Quantity and pricing semantics

`required_m` is the sum of **cut-demand lengths**, including documented allowances. It excludes purchased remainder and saw loss; it is not surface area or independently measured net installed length. Panelling labour uses slat demand; finish labour includes bead **and ledge** demand. Mastic uses their sum. Thus “required” and “installed” are only equivalent insofar as cut demand represents applied work; allowances and overlapping trim must be business-approved.

Purchase cost uses `new_purchase_units × snapshot unit price`: sheets for MDF, lengths for bead. `allocated_existing_mm` is zero; no inventory allocation is implied. Longitudinal remainder and kerf are separate; unused MDF sheet width is represented as area. Different-width MDF rips have additive length totals but not interchangeable material area.

Mastic tubes = `ceil((panelling_m + finish_m) / 11.5 × 1.5)`; the 1.5 factor effectively reduces coverage to about 7.667 m/tube. Cutting = `(total MDF rips + 1) × £2` for nonempty MDF demand, including ledge rips; no separate bead cutting charge. Delivery is once per nonempty quote. Labour is rounded to pennies, as are monetary components. Take-home = max(per-metre labour, days×180 + hours×22.50); final = ceil((materials + take-home)/10)×10. Exactly divisible totals stay at that £10 boundary. No tax interpretation is assumed.

### Committed seed prices — require commercial confirmation

| Product | Stock | Unit £ |
| --- | --- | --- |
| MDF 6 / 9 / 12 mm | 2440×1220 sheet | 15 / 18 / 22 |
| Pine glass bead 9×9 / 12×9 / 15×9 | 2400 mm length; compatible 9 mm MDF | 2.80 / 3.00 / 3.20 |
| Pine barrel 21×9 / 34×12 | 2400 mm length; compatible 9 / 12 mm MDF | 4.00 / 5.20 |
| Pine astragal 21×8 / 34×12 (deferred dado catalogue) | 2400 mm | 4.00 / 6.00 |
| Pine decorative cover 34×12 (deferred dado catalogue) | 2400 mm | 6.20 |

Other retained dado prices remain in `app/data/catalogue.json`, outside the active calculator review. One conspicuous seed value to confirm later: 45 mm dado 1.8 m is £5.60 while 2.1 m is £4.80. No seed was corrected on an assumption.

| Rule | Seed |
| --- | --- |
| Kerf | 3 mm; zero supported, negative/nonfinite or >50 rejected |
| Mastic price / nominal coverage | £2.90/tube / 11.5 m, with additional ×1.5 factor |
| Cutting / delivery | £2 per (MDF rip count+1) / £10 per nonempty quote |
| Day / hour | £180 / £22.50 |
| Panelling labour | £4.90/m required slat |
| Finish labour | £4/m bead and ledge |
| Dado labour | £6.50/m, retained configuration, unused by supported types |

Confirm supplier currency/tax basis and current prices, coverage factor, extra cutting unit, delivery policy, ledge-at-bead labour rate and whether whole/fractional days are intended (the form/service currently permits fractions). These are commercial questions; this review does not assert prices are current market rates.

## Editable quotes and failure states

`services/quotes.py::recalculate_item` replaces results; `reaggregate` consumes only current item results. `routes.py::quote_edit` saves stable Room/WorkItem identities, uses the saved quote catalogue, and reaggregates after changes/removals. SQLAlchemy sessions in the existing integration test are closed and reopened between actions, testing persisted state rather than only in-memory objects.

The existing mixed-quote test was strengthened to assert: the edited full wall becomes a 3500 mm half wall with 750 mm openings; required quote panelling becomes 28.880 m and final price changes; both unrelated half-wall result data and stair result data remain unchanged; saved inputs and IDs survive reload; invalidating the edited wall clears groups/pricing and blocks final price; explicit price refresh replaces the snapshot; deleting the other room leaves only 7.880 m of stair demand. Current-price edits alone do not affect the quote snapshot.

Existing validation tests cover zero/fractional counts, negative/nonfinite/incomplete dimensions, slope shorter than run, stock length zero or too short, excessive slat/ledge width, invalid kerf and overlong cuts. Packing has bounded counts and no historical width-subtraction loop. Empty quotes have zero material, delivery, cutting, mastic and time charge. Invalid quotes may display explicitly provisional totals for valid siblings, but no final price. Deleted items are removed from subsequent aggregation.

## Light UI acceptance

The unchanged baseline sufficiently follows the supplied design direction for this stage: charcoal navigation, warm cream backgrounds, restrained yellow accents, rounded panels, compact tables, named rooms and collapsible work items. Dashboard values come from saved quotes; quote list supports reopen; editor separates measurements/results and marks unsaved totals pending; materials page states snapshot behaviour. Prior desktop/mobile smoke results are recorded in `MILESTONE_1_VERIFICATION.md`; no fresh browser session or visual redesign was performed.

Future polish only: clearer pricing units/labels, singular/plural copy, shorter stock selector labels, clearer distinction between aggregate material demand and workshop-ready joint instructions. No placeholder feature buttons were added.

## Changes, tests and next milestone

Application code/configuration: **none**. Existing integration test assertions strengthened; this acceptance document added. No new workshop rule was invented or approved by the agent. Full-suite result and evidence comparison are recorded below after the single completion run.

Next milestone should obtain a physical sign-off on the golden stair sample, ledge section/joints, bead measurement convention and pricing checklist. Record the user's decisions as focused fixtures; implement only any resulting agreed corrections. Do not start deployment or Milestone 2 automatically. No release tag is appropriate yet.

### Completion evidence

- Single full run: `/private/tmp/timber-verify-venv/bin/pytest -q` — **23 passed, 4 warnings in 32.24 seconds**. The four warnings are the previously recorded generated migration `get_engine()` deprecation; no new failure. No test was removed or rerun separately.
- `git diff --check` passed for the tracked changes.
- Read-only per-file SHA256 comparison against the saved Milestone 1 final manifest: **239 evidence files, zero changed/missing, zero added**. This confirms no evidence drift since that baseline, including historical source. The older audit-to-Milestone-1 `.DS_Store` discrepancy remains separately documented; it was not repaired or hidden.
- Only this document and 11 added assertions/setup lines in the existing integration test changed. Application source, seed values, database schema, UI and evidence remain at the accepted implementation baseline.
