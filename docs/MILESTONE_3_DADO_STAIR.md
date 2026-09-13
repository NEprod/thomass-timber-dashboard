# Milestone 3 — dado, stair finishes and workshop usability

## Rule provenance

- **RECOVERED RULE:** the five dado style names, distinct middle-rail and square-profile choices, gap inputs, independent top/bottom square counts, outer/inner frame fields, historical product dimensions/prices and £6.50/m dado labour rate exist in the evidence.
- **LIKELY RULE:** “double squares” means nested outer/inner frames, based on the historical field names. No complete layout formula or inset policy was found.
- **CONFIRMED BY USER:** gap width replaces slat width for dado layouts; finished bead requirements are not shortened by kerf; material charging uses whole required stock units. Landing/slope bends on the top and bottom of a transition opening occur at the same horizontal position. For transition bead the user permits larger-size material provisions rather than exact finished cuts, including six or more pieces where needed.
- **NEWLY IMPLEMENTED RULE:** explicit clear layout-zone heights and nested inset; configurable profile-use permissions; longest compatible continuous stock, safe joined runs, labelled frame cuts, quote-wide dado packing; segmented stair dado and conservative transition bead provisions.
- **UNRESOLVED RULE / NEEDS PHYSICAL TEST:** precise transition finished cuts and saw orientation; dado frame outside/long-point convention; nested inset choice; suitability of particular profiles for a specific installation. These are visible/documented assumptions, not recovered workshop certification.

Starting HEAD: `8ff780276686006d07ccbb7f36fe83766ddda7b7`. Working tree was clean. Existing baseline verification recorded 25 passing tests; the previous audit and milestone work were not repeated.

## Targeted historical evidence

Search covered dado-related source/configuration in both evidence applications and their backup copies. Useful sources:

| Source under `old_evidence/` | Actual evidence |
| --- | --- |
| `tkinter-version/src/components/dado_input_block.py::_get_dado_styles` | 45/70 mm middle rails; square profiles also include astragal/decorative cover; 75/100/125/150 mm gap choices, default 100; plain dado hides square controls |
| `tkinter-version/src/components/dado_wall_section_input_block.py::update_visible_fields` | Five styles, dado height, independent top/bottom counts and outer/inner outputs; no completed geometry/cut calculation |
| `tkinter-version/src/components/dado_wall_stair_section_input_block.py` | Landing/tread/rise/slope input UI, no completed stair-dado calculation |
| `tkinter-version/src/components/dado_wall_measurements_block.py`, `src/job_sheet_window.py` | Components and visibility/integration scaffolding, no working dado calculation dispatch |
| `flask-version/sql/get_middle_dado_options.sql`, `get_square_dado_options.sql` | Profile-category selection; no stock-length filter or finished cut generator |
| `tkinter-version/json/dado_prices.json` | 45/70 mm profiles, 20 mm thickness, lengths 1500–4800 mm; astragal/decorative cover at 2400 mm |
| `tkinter-version/json/pricing_config.json` | Dado labour pricing |

No complete historical dado optimiser, longest-stock selector, long-run joining implementation or shared stair-dado geometry was found. In particular, a historic 3000/2400-only square restriction was not enforced by the discovered SQL. The new conservative default permissions reflect the requested stock policy and known catalogue, rather than claiming recovery of a missing algorithm.

## Supported dado layouts

All five historical straight styles are selectable:

1. Dado — one continuous horizontal rail.
2. Dado Squares Top & Bottom — rail plus one frame per configured square in each zone.
3. Dado Double Squares Top & Bottom — rail plus outer/inner frames in each zone.
4. Dado Squares Bottom — rail plus bottom frames.
5. Dado Double Squares Bottom — rail plus bottom outer/inner frames.

Straight frame width is `(wall_length − gap × (horizontal_count + 1)) / horizontal_count`. Height is `clear_zone_height − 2 × gap`. Top/bottom counts and clear heights are independent. Enter clear zone heights excluding the rail, skirting and ceiling trim. No rail position is inferred from an unfinished historical dado-height field.

Frame dimensions currently specify the **outside/long-point rectangle**. Each frame produces two horizontal and two vertical cuts. Double styles require an explicit outside-edge inset: inner width/height = outer width/height − twice the inset. Inset must exceed the chosen profile width to avoid overlapping nested frames. This explicit convention needs comparison with the user's real wall; it is not a claimed historical formula.

A panelling work item can also add a separate continuous dado rail. Existing bead remains in the MDF openings, and any ledge remains separate. This creates distinct material demands without changing the MDF grid. Actual rail placement must not overlap an existing finish physically; software does not infer placement from the old UI.

## Profile and stock policy

Material rows persist editable `uses` permissions, name/profile, dimensions, price and active state. Defaults:

| Family | Continuous / stair rail | Square frames |
| --- | --- | --- |
| 45 mm / 70 mm dado | Existing lengths permitted; select longest active identical family/width/thickness (currently 4800 mm) | 3000 mm rows only |
| Astragal / decorative cover | Not enabled | Existing 2400 mm rows |

The selector never swaps width or profile to gain length. The latest milestone's continuous-stock rule deliberately allows the longer catalogue lengths; the previous 3000 mm preference remains historical metadata and the default square-stock policy. Permission changes are explicit in Materials & pricing, not hardcoded inside geometry. Adding catalogue rows has no new UI in this milestone; the existing catalogue editor manages existing rows.

Migration `b31dado_compatible_uses` adds/backfills permissions while preserving edited prices, labels and quote snapshots. Old quote snapshots remain unchanged; enabling dado on a pre-M3 snapshot requires the existing explicit catalogue/price refresh, which also refreshes prices. No silent snapshot upgrade occurs.

Long runs split into labelled segments no longer than stock. Finished segment lengths sum to the original run. Fewer joins take priority over buying shorter stock: a 4800 mm run uses one matching 4800 mm length; 6000 mm splits into 4800 + 1200. Square edges may also have explicitly labelled joins if longer than permitted stock. Internal split joins use a displayed zero setting; frame external joints retain 45°. These describe provisional cutting information, not a certified saw orientation.

Packing is deterministic first-fit decreasing, with kerf between pieces, bounded piece counts and explicit remainders. It is not a proof of global optimum. Dado demands sharing the exact product ID pool across the quote, so remnants can serve another item within that quote. The shared quote plan is authoritative for purchased units; item plans are standalone previews. Different product IDs are never silently combined. Inventory/offcut allocation remains deferred.

## Stair dado

`dado.py::calculate_dado` and the optional panelling rail call the existing `geometry.py::stair_geometry`; there is no second angle system. Standalone stair dado accepts the measured stair inputs and gap-based grid for reference geometry. Only plain segmented stair rail is enabled, not unconfirmed stair dado-square layouts.

Lower landing, measured slope and upper landing remain separate labelled demands. Landing/slope joins retain the existing slope-mitre value and explicit start/end roles. Zero-length landings are omitted. Oversize slope/landing segments split safely; only the external segment ends retain the landing/slope setting. Neither the MDF 30 mm adjustment nor a speculative width-derived extension is added to dado.

The synthetic stair fixture still yields run 1000, slope 33.56°, mitre 16.78°, square 250×800, angled square 300×960, displayed top/bottom 61.78°/28.22°, transition→angled→angled→transition and MDF strips 2 horizontal / 3 vertical. Dado route lengths are 250 / 1200 / 250 mm. This verifies calculation consistency, not a real staircase or a physical cut.

## Stair bead and ledge

`stair_bead.py::bead_edges` consumes the same recovered geometry and classifications.

- Flat openings: two width and two height pieces using normal finished opening dimensions.
- Angled openings: recovered angled width/height, individually labelled by square, row and edge, with historical top/bottom display settings.
- Transition openings: **conservative trim-to-fit stock allowances**, authorized by the user's clarification. Both horizontal boundaries bend at the actual landing x positions. Each top/bottom span is scaled by `max(flat_width, angled_width) / flat_width`, rounded upward to 0.01 mm. Two vertical provisions use the larger recovered height. This supplies at least the larger recovered perimeter and accounts for every bend's extra cut/kerf. It does not claim to solve an exact physical polygon.

For the golden fixture each transition has six pieces: 180, 120, 180, 120, 960, 960 mm. A panel crossing both bends has eight. Multiple rows retain separate labels/provisions. No fake four-piece rectangular transition is presented as finished geometry. Kerf changes packing only; it does not shrink any of these requirements.

Stair bead with ledge also provides under-ledge bead along separate lower/slope/upper runs. Existing MDF ledge developed length and 2×/3× thickness-derived rip-width rules remain unchanged.

The transition stock allowance contributes to required finish length, labour and mastic as a **provisional work allowance**, not purchased remainder. A future exact measured polygon could refine that quantity; the current warning makes this limitation explicit.

## Pricing and editable quotes

Dado material cost = required purchased product units × quote-snapshot price. Dado labour = required dado metres × saved dado rate (seed £6.50/m). Mastic includes required dado/bead/panelling work, including disclosed transition provisions, and excludes stock remainder. Existing MDF ripping, bead stock grouping, charges and quote rounding are retained. Required length, stock kerf, purchased length/units and remainder remain separate.

Saving one item retains the quote/room/item hierarchy, other items' results and existing price snapshot. Invalid input clears the affected result and prevents a stale final total. Explicit price refresh remains the only action updating the quote catalogue/pricing snapshot.

## Workshop UI and Save & Recalculate

Four compact stair result cards promote slope angle, slope mitre, angled square dimensions, and top/bottom displayed settings. Classification counts/sequence and physical-verification wording remain nearby. Cut labels show roles and readable joint metadata instead of raw dictionaries.

Normal server POST/recalculation remains. The response anchors to the active item. `app.js` stores only tab-local UI state in sessionStorage: open details IDs, active item, viewport offset and last focused field name. After reload it restores open item/Cut Plan/notes, keeps the item's viewport position (accounting for flash-message height changes), and restores visible field focus. It expires after ten minutes and contains no measurement values. If storage is unavailable, the redirect anchor still opens the active item. Unsaved results still hide immediately.

## Validation

Focused calculation and integration tests cover five styles, gap geometry, explicit nested inset, compatibility, longest same-profile stock, splitting, cut labels, kerf/remainders, pooled purchasing/labour, stair geometry reuse, endpoint settings, flat/angled/transition bead provisions, multiple bends, ledge interaction, editable snapshots, invalidation and migration preservation. Existing legacy characterization tests and golden MDF expectations remain intact; only the obsolete “transition bead unsupported” expectation is replaced.

Browser smoke used an isolated temporary database, not production data: half-wall with dado, synthetic stair bead/dado, prominent results, stale-result hiding, recalculation from 4→5→4 columns, both items and Cut Plan staying open, focus restoration and stable item viewport offset (within 0.3 px despite a changed flash-message height). The unrelated half wall retained 625×800 mm and 3/2 strips. A saved shorter-profile dropdown omission found here was corrected and covered by integration testing.

Final full automated suite: **37 passed**, run once at milestone completion. Eight warnings are the existing Alembic `get_engine` deprecation, now exercised by two migration tests. The final focused dado/stair-finish suite passed all 12 tests. Original catalogue/pricing values were compared against the starting commit and are unchanged; only use permissions were added. Browser JavaScript executed successfully during the smoke test (standalone Node syntax checking was unavailable because Node is not on PATH).

## Real-wall validation next

Ready for controlled comparison against the user's existing panelling after software checks complete. Confirm actual long/short-point convention and saw orientation, exact angled bead dimensions, transition trim lengths, rail/ledge meeting joints, selected profile suitability, outside-frame/gap convention and explicit nested inset. The historical MDF 30 mm rule remains unchanged; width × tan(mitre) remains an unapproved hypothesis, not an implemented replacement.

Do not treat synthetic fixture success as physical validation. No PDFs, inventory, other calculator family, deployment or Milestone 4 work is included.
