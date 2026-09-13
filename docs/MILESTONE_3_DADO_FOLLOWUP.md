# Milestone 3 follow-up — dado workshop corrections

Starting commit: `fceeda2ce0da35a67162713e1c4c61bfb02f9db9` (released v1.1.0). This is a focused correction for user review; no release/tag/push is part of this pass.

## Continuous rail stock and pricing

The calculator still splits long installed runs at the longest compatible active stock length to limit joins. For **each resulting piece**, it now chooses the smallest compatible stock capable of supplying that piece. Ties use price then product ID for determinism. Compatibility requires identical profile/family, width and thickness, plus the correct explicit continuous/stair use permission. It does not swap to a different moulding just to find a short length.

Given compatible 1000/2400/3000/4800 mm stock:

| Required rail | Finished pieces | Purchased stock | Remainder |
| --- | --- | --- | --- |
| 5743 mm | 4800 + 943 | 4800 + 1000 | 57 mm |
| 4800 mm | 4800 | 4800 | 0 mm |
| 4900 mm | 4800 + 100 | 4800 + 1000 | 900 mm |
| 12001 mm | 4800 + 4800 + 2401 | 4800 + 4800 + 3000 | 599 mm |

The former 5743 mm behavior purchased 2×4800 (9600 mm). It now buys 5800 mm with those configured options, charging `price(4800) + price(1000)`, not `2 × price(4800)`. The regression fixture uses £9.60/4800 and £2.00/1000, so the material charge is £11.60 instead of £19.20. These are test prices, not changes to customer configuration.

**Catalogue-dependent:** the unchanged historical seed has a shortest 45/70 mm stock of 1500 mm, not 1000. With that seed, 5743 mm purchases 4800 + 1500, costing £11.00 + £3.40 for the 45 mm family, with 557 mm remainder. No fictional 1000 mm product was added. A 1000 mm compatible option is used when present in the quote's configured catalogue snapshot.

Kerf remains between cuts sharing stock; it never shortens the 943 mm finished piece. A single piece on each of the two example lengths has no between-piece kerf. Labels, segment IDs, installed lengths and stock-source product IDs survive packing. Identical products still pool at quote level. This is a bounded deterministic method, not a new global optimiser; it does not search cross-length purchasing combinations after the per-piece selection.

## Piece and purchasing summaries

Above Cut Plan, work items show:

- Main dado rail: installed piece count, role, grouped finished lengths and total requirement.
- Square dado: horizontal/vertical/total piece counts, grouped lengths and flat/angled/transition roles.
- Purchased stock: product/use, quantity × stock length, required length, purchased length, kerf, remainder and stock cost.

These summaries read structured cuts, not rendered text. The item purchase plan is clearly labelled standalone; the quote summary remains authoritative where products pool across items. If a product is explicitly compatible with both main and square dado, the item purchase row identifies both uses rather than inventing separate purchases. Otherwise their products/demands remain separate.

Straight bottom example: wall 3000, gap 100, bottom count 4, clear height 1000 yields the unchanged **625×800 mm** frames. It has one 3000 mm main rail, **8 horizontal + 8 vertical = 16** square pieces, using actual calculator counts rather than the illustrative 7/5 numbers in the request. With seeded 21×8 mm astragal, the standalone square plan buys **6×2400**, required 11400, kerf 30, remainder 2970 mm; the main rail buys one 3000 mm length.

## Dado-specific stair model

Plain stair Dado requires wall length, lower landing, upper landing, measured slope and rail profile only. It neither displays nor consumes gap, MDF panel height, MDF grid counts, square profile or clear layout height. It retains lower/slope/upper rail labels and angle metadata.

Stair Dado Squares Bottom uses the **straight dado bottom layout model**: gap width, square profile, Bottom horizontal squares and Clear layout height below rail, plus the measured stair route and main rail profile. MDF `height`, `horizontal_squares`, `vertical_squares` and `slat_width` do not drive it; a regression test supplies deliberately invalid values in those old fields and the dado-specific calculation remains valid.

The existing stair-angle expressions were extracted verbatim to `_stair_angles` in `geometry.py`, shared by `stair_route_geometry` and the existing `stair_geometry`. No second slope/mitre interpretation was introduced. The bottom layout passes clear zone height, gap and bottom count to the existing grid transform with one row. Existing MDF golden values, rounding, classifications, top/bottom settings and 30 mm allowance are unchanged.

For the synthetic 1500/250/250/1200 route with gap 100, bottom count 4 and clear height 1000: the rail segments remain 250/1200/250; openings are 250×800, angled dimensions 300×960; sequence is transition/angled/angled/transition. Square dado has **12 horizontal + 8 vertical = 20** provisions. The existing bead-edge generator is reused, without modifying bead implementation, to supply individually labelled flat/angled edges and conservative transition spans.

**Transition provisions are trim-to-fit stock allowances, not verified finished cuts.** Their allowance also enters provisional required-work labour/mastic, excluding purchased waste. Saw orientation, long-/short-point convention and exact real transition cuts remain physical verification items. No dado-specific 30 mm extension has been guessed.

## Supported styles and saved data

Selectable, both straight and stair: **Dado**, **Dado Squares Bottom**.

Visible but disabled with “Coming later”: **Dado Squares Top & Bottom**, **Dado Double Squares Bottom**, **Dado Double Squares Top & Bottom**. Historical formula code and saved data have not been deleted or silently converted.

Server-side calculation rejects the disabled styles. The edit route rejects a submitted disabled style **before changing the saved item**; it leaves name, inputs and results intact and explains why. A quote containing such a historical style can still be viewed. The original selection remains selected, even though disabled; JavaScript does not silently replace it with plain Dado. Explicitly selecting a supported style is required to replace it. Price refresh is blocked before snapshot replacement if any such item remains, preventing a partial or destructive refresh.

No schema migration is required: existing JSON inputs/results and material permissions support the corrections. No database reset or automatic repricing occurs. Existing quote snapshots, prices/profile choices, customers/rooms/items are preserved. The existing migration-upgrade and saved-snapshot tests remain part of validation.

## Validation

- Focused existing MDF/legacy characterization: **18 passed**.
- Focused dado correction, existing finishes, snapshots and migration: **22 passed**, four existing Alembic deprecation warnings.
- One isolated browser smoke: straight Dado Squares Bottom, plain stair Dado and stair bottom squares rendered/calculated correctly; only two styles enabled; irrelevant MDF and square fields hidden appropriately; profile selections preserved.
- Browser recalculation from 4 to 5 bottom squares produced 180×800 mm and 14 horizontal / 10 vertical provisions; unrelated straight result stayed 625×800. Active item, other expanded items and Cut Plan stayed open; exact item viewport offset remained −252.17 px; focus returned to `bottom_squares`; stale results hid before saving.
- Evidence checksum comparison: **239 files unchanged**, no additions or changes.
- Full suite run **once at completion: 47 passed**, eight existing Alembic `get_engine` deprecation warnings. No application code changed after that run.

Ready for user testing after final software validation. Next is real-wall/profile comparison, not the remaining styles, PDFs, inventory, Milestone 4 or an automatic release.
