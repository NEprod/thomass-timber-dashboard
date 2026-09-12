# Thomas Timber Management — Legacy Recovery & Migration Audit

Audit date: 12 September 2026. **Audit only: no application changes, fixes, migration, tests, or deployment files created.**

## 1. Executive Summary

The supplied evidence supports retaining Flask as the eventual presentation architecture, but **neither current application is a complete, reliable source of truth for the whole job pipeline**.

The most important findings are:

1. **The known stair example is reproduced by the actual Tkinter source.** With the supplied dimensions and counts, plus 100 mm slats, 2440 mm board length and 3 mm kerf, it returns every reported dimension, mitre, classification and strip count. These additional material assumptions must accompany the future golden regression fixture.
2. **Current Tkinter totals are disconnected, not absent from the historical codebase.** `JobSheetWindow.on_change()` calls section calculators only. Neither material nor job totals update method is called. Its cut-list display is explicitly a placeholder. The older `SquarePanellingWindow` has actual cut aggregation, board purchasing, costing, job pricing and cut-list display; the intermediate backup also retains much of this logic.
3. **The refactor changed the data contract.** Older totals expect dictionaries in `self.measurements`, including a nested ledge group. Current calculators store MDF cuts on section object attributes, bead cuts inside `section.vars`, and ledges on a separate attribute. Merely reconnecting an old function would not recover complete totals.
4. **Flask has an integrated full-wall calculation → materials → job-price path**, but its browser event handling and data handling are incomplete. Its totals reconstruct placeholder strip arrays from displayed counts, use purchased stock length for linear meterage, and can retain stale results. This differs materially from older Tkinter's sum of packed `used` lengths.
5. **Half-wall and stair MDF calculations have not been migrated into Flask.** However, Flask contains an uncalled stair bead helper and half-wall branches in materials aggregation. It is incorrect to say no stair-related work reached Flask.
6. **Dado was implemented as a substantial UI/configuration skeleton.** All five named styles exist; Tkinter has straight and stair measurement components and output fields. No executable dado dimension/cut/price pipeline was found in current source, ignored backups, or the three available historical tags. No dado stock optimiser was found. The 3000 mm products exist in both catalogues, but selection of 3000 mm as normal stock and splitting long dado runs remain intended behaviour to implement.
7. **The 30 mm stair allowance is explicit workshop logic:** top upper landing +30 mm; top lower landing −30 mm, clamped to zero. Bottom landing lengths and slope lengths are unchanged. Preserve this behaviour pending physical verification; do not replace it with a speculative geometric correction.
8. **Save/load is unfinished in the supplied evidence.** SQLite databases contain product/pricing configuration, not jobs. Save/load buttons in Tkinter have no commands. There is no persisted `job_id`/wall-section relationship to migrate here.

Recovery should begin with characterization of the existing calculators and an explicit result/data contract. Recover geometry before modernising it. Resolve meterage, kerf and workshop conventions separately from framework extraction.

## 2. Repository / Evidence Overview

### Scope and source notation

Paths below use these exact roots. A reference such as `T/src/job_sheet_window.py:327` means that file beneath the Tkinter root, at the stated source line. Line numbers refer to the supplied working files, not future code.

| Alias | Evidence root/source |
|---|---|
| F | [old_evidence/flask-version](/Users/dalethomas/Desktop/Scripts/thomass-timber-dashboard/old_evidence/flask-version) |
| T | [old_evidence/tkinter-version](/Users/dalethomas/Desktop/Scripts/thomass-timber-dashboard/old_evidence/tkinter-version) |
| M | [T/src/square_panelling_measurments.py](/Users/dalethomas/Desktop/Scripts/thomass-timber-dashboard/old_evidence/tkinter-version/src/square_panelling_measurments.py) — older monolithic `SquarePanellingWindow` |
| B111 | `T/backups/1.1.1_backup/` |
| B112 | `T/backups/1.1.2 refactor attempt/` |

There are **239 evidence files**, including nested Git metadata, ignored backups, compiled caches and macOS metadata. Source inventory: Flask 8 Python files (including two version utilities), 15 JavaScript files, 13 HTML templates, one CSS file, 18 SQL files, four SQLite databases; Tkinter 40 Python files including backup copies and utilities. No applicable `AGENTS.md` was found in the evidence or project root.

The outer repository has no commits; initial status reported `.DS_Store` and `old_evidence/` as untracked. Both evidence folders contain nested `.git` directories. Flask's nested repository has no resolvable HEAD. Tkinter's nested repository has three reachable commits/tags:

| Tag | Commit | Evidence significance |
|---|---|---|
| 1.0.0 | `7acf2f4` | Initial arithmetic strip estimates; no detailed packing pipeline |
| 1.1.0 | `ae18732` | Detailed cut lists and board packing/material totals |
| 1.1.1 | `1da9e89` | Adds job pricing/configuration; current monolithic source matches this tag |

`T/VERSION.txt` still says 1.1.1. The modular working files and stair calculator go beyond that tagged tree. Thus version text/changelog cannot date every current feature. B111's monolithic source is identical to M and has the `material_prices.json` that M expects. B112 is an intermediate component refactor retaining monolithic calculation methods. Its label is historical evidence, not proof of a released version.

### Audit method and limits

Read source and traced callers, handlers, returned/stored data and consumers. Repeated whole-evidence searches with hidden/ignored files included; inspected backups, tag file trees and historical calculator code. Search concepts included stair spellings, wall sections, material totals, callbacks, cuts, kerf, dado, ledge, bead, slope, mitre, transition, persistence and job identifiers. Inspected SQLite with read-only immutable connections. Parsed all 48 Python sources successfully. Inspected Python 3.13 cache code-object/function inventories, especially source-orphaned, dado and stair modules; this was not a full bytecode decompilation or proof of equivalence to every historical cache.

Executed existing pure/calculator functions using in-memory section/variable adapters, with bytecode writing disabled. No GUI was launched and no Flask HTTP/browser end-to-end run was performed: Flask was absent from the inspected Python 3.9.6 and 3.13.5 environments; the historical editor-configured virtualenv path no longer exists. No dependencies were installed. Therefore “working” below means source-connected and/or reproduced for the stated case, not blanket production certification. Dangerous nonterminating edge cases were assessed from source, not run.

An evidence fingerprint was computed before report creation and checked again afterward. Method: sort all evidence file paths; concatenate `path:SHA256(file bytes)\n`; SHA256 that UTF-8 string. Fingerprint: `4e60e83c9f7fe4468c69487623463827a3ebfada10e5957039632860ab219838`. Existing compiled caches were retained; audit probes used `-B`. Negative findings apply to supplied evidence and reachable history, not to unknown copies outside it.

## 3. Flask Architecture

### Entry point and routes

[F/src/app.py](/Users/dalethomas/Desktop/Scripts/thomass-timber-dashboard/old_evidence/flask-version/src/app.py:9) creates a module-level `app = Flask(__name__)`. **No application factory, blueprints, ORM, form classes or service objects** are defined. The `__main__` block at line 451 runs the debug server on `0.0.0.0:2112`.

| Route(s) | Function/source | Behaviour |
|---|---|---|
| `/`, `/quote` | `dashboard`, `quote_form`, app.py:443–449 | Render dashboard shell and quote form |
| `/api/square_dado_options`, `/api/middle_dado_options` | app.py:11–43 | Read dado SQL/catalogue; return labels/categories only |
| `/api/mdf_thicknesses`, `/api/mouldings` | app.py:45–86 | Thickness list and thickness-filtered bead labels |
| `/api/board_length`, `/api/board_width`, `/api/board_price` | app.py:88–134, 204–226 | MDF dimensions/price by thickness |
| `/api/bead_length`, `/api/bead_price` | app.py:136–158, 180–202 | Moulding dimensions/price by label |
| `/api/get_kerf` | app.py:160–178 | Pricing configuration kerf |
| `/api/cut_price`, `/api/delivery_cost`, `/api/mastic_price`, `/api/mastic_coverage` | app.py:228–294 | Additional material/consumable settings |
| `/api/day_rate`, `/api/hourly_rate`, `/api/mdf_slat_per_m`, `/api/bead_per_m` | app.py:296–362 | Labour settings |
| POST `/api/calculate/full_wall` | `calculate_full_wall`, app.py:364–423 | Temporary section object → full MDF calculator → optional straight bead calculator → JSON |
| POST `/api/material_totals/full_wall` | `material_totals_full_wall`, app.py:425–432 | Pass JSON keyword arguments into `update_material_totals` |
| POST `/api/job_totals` | `api_job_totals`, app.py:434–441 | Pass JSON keyword arguments into `calculate_job_totals` |

Lookup functions open `sql/get_*.sql` and `databases/*.db` relative to **process working directory**, and return lists even for scalar values. SQL product filters use parameters. The default SQLite connection mode can create a missing database if started from the wrong directory; audit reads did not use that mode. No configuration-edit API, job save/retrieve API, half/stair calculation route, authentication or API input schema exists in source. Material/job handlers turn exceptions into JSON 500 responses; the full calculator route lacks that wrapper.

### Presentation and integration

`templates/base.html` provides navigation, sidebar toggle, search placeholder, Bootstrap 5.3.2 CDN assets and local CSS. Retrieve Quote, Calendar and Prices are text placeholders rather than implemented routes. The three calculation scripts are loaded by the base template, even on the dashboard.

`quote_form.html:6–28` includes status/customer/job/panelling selectors, square and dado option blocks, **only full-wall measurement/material blocks**, job totals and cut list. The form has no persistence submission handler. The thirteen templates are those two pages plus eleven components: customer details, cutlist, dado input, full-wall materials, full-wall measurements, full-wall section input, job status, job totals, job type, panelling type, square input.

All fifteen scripts have identifiable roles:

| Scripts | Role and limitations |
|---|---|
| `panel_type_logic.js`, `update_panel_visibility.js` | Subtype lists and square/dado/moulding/ledge option visibility. They do not replace full-wall measurements with half/dado measurements. Programmatically replacing subtype options does not dispatch a panel change. |
| `populate_thickness.js`, `populate_moulding_options.js` | Catalogue lookups; initial thickness change is dispatched twice. Moulding selection dispatches change, but no calculator listener consumes it. |
| `populate_middle_dado.js`, `populate_square_dado.js` | Catalogue dropdowns only |
| `populate_ledge_options.js`, `slat_width_defaults.js` | Ledge dimensions from thickness; slat default 75 with bead, otherwise 100. Default assignment does not trigger slat input calculation. |
| `full_wall_section.js` | Clone template, index/add/remove sections, toggle bead fields |
| `full_wall_calc.js` | Watch wall dimensions/counts/slat width/panel/time; fetch settings; POST calculation; display outputs; cache results; trigger totals |
| `full_wall_materials_totals.js` | Reconstruct counts from DOM; fetch prices; POST aggregation; display material totals; trigger job totals |
| `job_totals.js` | Parse displayed costs/meterage, fetch labour rates, POST and display job pricing |
| `update_full_material_visibility.js` | Hide/clear bead-related total fields |
| `cutlist_display.js`, `cutlist_copy.js` | Format cached MDF/bead cuts and board layout; copy displayed text |

Local `styles.css` is presentation-only: dark shell, sidebar/mobile styling. There is no JS build system or packaged frontend dependency tree. Framework-independent pricing and board aggregation already exist under `core/logic/shared`; full-wall and bead logic still mutate simulated UI sections.

## 4. Tkinter Architecture

The current launcher is `T/src/main_gui.py:4,17–18,44–47`: `TimberPricingApp` opens `JobSheetWindow`. The job count is literal `ToDo`. It does **not** launch M.

`JobSheetWindow.__init__` loads four JSON catalogues/settings, builds a scrollable window and instantiates components. `JobTypeDropdownBlock` schedules selection callbacks with `after(10, ...)`. `PanellingTypeDropdownBlock` supplies subtype selection. `SquareInputBlock` owns thickness, slat, bead and ledge variables; `DadoInputBlock` owns middle/square profile and gap choices. Their callbacks reach `on_panelling_type_change`, which updates options/visibility and runs full/half calculation paths.

Measurement collections are explicit:

- `FullWallMeasurementsBlock.sections`: `FullWallSectionInputBlock` objects.
- `HalfWallMeasurementsBlock.sections` and `.stair_sections`: distinct straight and stair objects.
- `DadoWallMeasurementsBlock.sections` and `.stair_sections`: dado UI objects.

Each section mixes `StringVar`s, widgets and widget groups inside `.vars`. Full/half containers attach numeric `index`; stair and straight indexes are separate local sequences. Inputs use `trace_add('write', trigger_on_change)` → controller `on_change` → current job-type dispatcher. Full calculations are at controller line 233; straight/stair half calculations at 105 and 166. Shared calculators mutate read-only output variables and section attributes and print cuts.

`JobMaterialTotalsBlock`, `JobTotalsBlock` and `JobCutListBlock` are created at controller lines 473–481. Their existence does not mean integration: totals have setters but no caller in this controller; the cut-list button prints placeholder text.

M is a separate historical design. Its `measurements` list holds dictionaries with variables, widgets, cut dictionaries and job labels. `add_wall_section` attaches debounced input callbacks; `update_section_measurements:1074` dispatches full/half/bead/ledge, then calls `update_material_totals:1275`, then `update_job_totals:54`. `update_cut_list_display:182` reads real cuts. M's present location cannot initialize normally because it requests absent `T/json/material_prices.json`; B111 and Git 1.1.1 preserve that file and launcher relationship. Do not confuse this current-path problem with historical nonimplementation.

## 5. Feature Comparison Matrix

Classification key is the requested scheme: **A** working in Flask; **B** present in Flask but incomplete; **C** present in Flask but disconnected/not called; **D** present only in Tkinter; **E** different implementations in both; **F** UI exists but calculation/business logic does not; **G** business logic exists but UI/integration does not; **H** no implementation evidence found. Codes describe a specific feature or path, not a claim that an entire application is sound. Tkinter status is stated separately because A–C explicitly describe Flask.

| Feature | Classification / Flask status | Tkinter status | Best evidence | Eventual source of truth |
|---|---|---|---|---|
| Full square dimensions/cuts | A, with validation limitations | Connected; same core maths | F/T `core/logic/full_wall/calc_full_wall.py:4,31` | Shared characterized formula/cut generator |
| Full-wall lifecycle/display | B | Connected section display; current totals disconnected | F JS `full_wall_calc`, T controller:233 | Flask presentation with explicit result state |
| Straight half square | D; Flask selector only F | Connected dimensions/cuts | T `calc_half_wall.py:4,54` | Extract T modular calculator |
| Stair square geometry/MDF | D; no Flask calculator/route | Connected, regression reproduced | T `calc_half_stairs.py:4` | T formula and allowances, characterized |
| Straight bead | A core, B event lifecycle | Connected full/half; M also has inline copy | F/T `bead_calculations.py:3` | Shared existing straight bead algorithm |
| Stair bead | C/G in Flask | Called in T, transition/multirow caveats | F/T bead helper:47; T controller:209 | T call path plus shared helper after verification |
| MDF ledge | D; Flask selector F and aggregate branch C | T generates standalone ledge cuts; M integrates nested ledge | T `calc_half_ledge.py:3,26`; M:862 | T cuts plus explicit aggregation contract |
| Dado (all five variants) | F calculation; B overall UI/config feature | Straight/stair UI and config, no calculation | T dado section components; F dado template/API | Existing UI vocabulary/catalogue; new approved calculator |
| Preferred 3000 mm dado stock | H for selection/splitting policy | 3000 mm catalogue rows only | Both dado catalogues | User-specified business rule |
| Stair dado geometry sharing | H for sharing; Flask no dedicated UI | D/F stair inputs and outputs only | T `dado_wall_stair_section_input_block.py` | Reuse recovered T stair geometry later |
| Length packing | A/E family | Modular helper identical; older inline/estimated approaches | F/T `layout_strips.py`; Git 1.0.0 | Characterize then shared optimiser |
| Board width packing | A for valid inputs; edge failures | Present in M/B112, disconnected from current controller | F `materials_totals.py:91,117`; M:130,1234 | Existing algorithms with contract/invariant tests |
| Material totals | E/B Flask connected but different meterage basis | Current G/disconnected setters; M has implementation | F `materials_totals.py:3`; M:1275; T totals block:127 | Explicitly approved metric semantics + normalized cuts |
| Job totals/labour | A core, B frontend lifecycle; E wrappers | Current G; M/B112 connected historical paths | F `job_totals.py:3`; M:54 | F pure pricing function after policy confirmation |
| Cut-list display | A/B: real full cuts but stale cache risks | Current F placeholder; M real display | F `cutlist_display.js`; T block:32; M:182 | Flask display consuming canonical results |
| Customer/status fields | B/F persistence aspect | UI and getters | Both customer/status components | Preserve fields in future job model |
| Job save/load | H backend; no Flask save route | F buttons without commands | T controller:412–415; M:1436–1439 | New versioned persistence |
| Catalogue retrieval | E: SQLite lookup APIs | JSON lookups | F app.py; T controller:24 | One catalogue adapter/schema, preserve products |
| Dado labour rate | C configuration, no consumer | Loaded but unused in current/old pricing path | `dado_per_m_gbp` in DB/JSON | Future dado pricing policy |
| Tests / Docker | H | H | Entire inventory/tag trees | New later milestones |

## 6. Calculation Matrix

Notation: W = wall length, H = full/panel height, n = horizontal square count, r = vertical count, s = slat width, L = stock length, k = kerf. All dimensions are mm unless specified.

| Type | Input → event → calculation | Dimensions → cuts → packing | Quantities → costs → job → display / stopping point |
|---|---|---|---|
| Full Square Wall | T section traces → `on_change` → `calc_square_full`; F DOM input → POST full calculator | `(W−(n+1)s)/n`, `(H−(r+1)s)/r`; n+1 full-height verticals; n(r+1) square-width horizontals; each group packed | T current stops after section values/debug; M aggregates/prices/displays. F strip counts → board/material service → job service → readonly totals, subject to event/cache defects |
| Half Square Wall | T panel height/count traces → `update_half_wall_measurements` → `calc_square_half` | Same square formula with panel H; two full-width joined rails; n+1 verticals of H−2s; n(r−1) middle cuts; separate groups packed | T section values/debug only; M has straight-half totals. Flask has selection and uncalled half aggregation branch, no proper calculation chain |
| Stair Half Wall | T measured W/H/landings/slope/counts → traces → controller → `calc_stair_half` | acos geometry, classifications, adjusted landing/slope/vertical/middle cuts, labeled packing | T section values/debug only; optional bead/ledge functions follow; no job aggregation; Flask stops before geometry |
| Dado | T straight inputs/gap/profile → callbacks; F profile/gap selectors → option/visibility logic | No dado dimensions/cuts/packing found | Stops before calculation in both; totals labels/catalogue prices do not complete it |
| Stair Dado | T stair dado inputs → traces → `on_change` | Dispatcher has no dado branch, no geometry call | Stops at input/callback; no cuts, quantities, costs or job result |
| Bead | Existing square dimensions, counts and selected stock → conditional helper | Two widths + two heights per square; optional under-ledge run; packing | T helper updates section count only; M prices all straight bead groups; F connected straight bead totals; stair helper uncalled in F |
| Ledge | T subtype containing ledge → half/stair controller | Straight W or landing+slope+landing run → split → pack | T standalone `ledge_cut_list`, no consumer; M nested ledge has totals; F no MDF ledge generator |
| Cut Optimisation | Required lengths/groups or rip widths | Descending first-fit length packing; separate board-width simulation/layout | Produces stock containers, not a joint global cutting solution; no explicit waste result |
| Material Totals | M dictionaries or F DOM-rebuilt arrays | Sum strip counts → width packing → purchase quantities | M used-length basis vs F purchased-length basis; current T controller has no stage |
| Job Totals | Material costs, meterage, days/hours, rates | Material sum; labour by meterage; max(labour,time); upward £10 rounding | F pure function + API/UI; M method + historical UI; no current T call |

## 7. Full Wall Findings

Sources: F/T `src/core/logic/full_wall/calc_full_wall.py:4–54`; T controller:233–295; M:550–670; F `full_wall_calc.js:4–235`.

Required calculation inputs: W, H, n, r, s, board L, kerf k. Thickness selects board dimensions and prices rather than changing square geometry. Bead subtype additionally requires a selected bead profile/stock length. Counts must effectively be positive integers, square dimensions positive and stock usable; the functions do not enforce these constraints. Flask's browser unusually also requires positive full days or extra hours before calculation (`inputsAreFilled:13–15`), although geometry does not depend on labour.

Both current calculators round square width and height to two decimals **before generating cuts**. The verticals run full wall height; horizontal pieces fit between verticals. Vertical and horizontal pieces are packed independently. `horz_pieces_per_strip = floor(L / square_width)` ignores kerf; actual strip counts come from the packer. No vertical pieces-per-strip output is provided here. Full-height cuts and square-width cuts are not pre-split if longer than stock; the packer accepts them into oversized singleton strips.

Straight bead generates four pieces per square. No bead face-width subtraction or explicit mitre-length allowance is applied. Kerf is passed to the packer. Full-wall styles do not include an MDF ledge in the offered subtype list.

F and modular T are equivalent in core full-wall maths; the essential adaptation is assigning strings in `section.vars` versus `.set()` on Tk variables. M's 1.1.1 maths also agrees but embeds its own packer and hard-coded 3 mm kerf. Flask is more complete for **current connected material/job totals and web cut-list display**; T is not newer or better for full-wall formulas merely because it retains more files. Neither has save/load.

Read-only probe: W=3000, H=2400, n=4, r=2, s=100, L=2440, k=3 → square 625 × 1050; five vertical strips `[2400]`; four horizontal strips `[625,625,625]`, used 1881 each; horizontal pieces-per 3. Flask materials with 1220 board width, 9 mm MDF at £18, no beads and supplied pricing produce 9 strips, 1 board, 21.96 purchased linear metres, 3 mastic units, £18 board + £8.70 mastic + £20 cutting + £10 delivery = £56.70 materials. With one day, labour is £107.60, take-home £180, final £240. Packed `used` meterage is instead 19.524 m, which older Tkinter rounds to 19.52 for display/pricing. This is a reproducible semantic difference.

## 8. Half Wall Findings

Sources: T `calc_half_wall.py:4–106`, `calc_half_ledge.py`, controller:105–163; M:672–921.

Panel height is an explicit current T input; the monolith uses `wall_height_var` for this same role. Square dimensions subtract r+1 horizontal slat widths; physical vertical battens span H−2s across all rows, rather than just one opening height. Top and bottom rails are each W long. `split_into_joinable_pieces` divides each rail into up-to-L lengths without subtracting kerf from the required run. Middle pieces exist only for r>1, with n(r−1) pieces of square width.

Top/bottom, vertical and middle groups are separately packed. The horizontal strip output is the sum of top/bottom and middle stock counts, and horizontal pieces-per is deliberately 0 for one row. Vertical pieces-per is floor(L/(H−2s)), without kerf.

Ledge options derive 2× MDF thickness, or 3× with bead, in `SquareInputBlock.update_ledge_options_from_thickness:129`. Despite “thickness” wording in UI, the older board-ripping logic consumes this value as **strip width**. Clarify the physical interpretation before modelling it. The current ledge calculator receives only length/stock/kerf, generates cuts and stores `section.ledge_cut_list`; width does not affect this length packing. The old monolith stores ledges at `section['half_square_strip_cut_list']['ledge']` and does aggregate their width and cost.

Half-wall bead uses n×r rectangular openings. With ledge+bead it adds a separate under-ledge run of W, split to bead stock length. Current T generates and displays counts but does not update material/job totals. No half-wall dimension calculator, input template or API exists in Flask; its subtype list and half aggregation branch are incomplete migration remnants.

Probe W=3000, panel H=1000, n=4, r=1, s=100, L=2440, k=3: square 625×800; top/bottom `[2440]`, `[2440]`, `[560,560]` → 3 horizontal strips; vertical `[800,800,800]`, `[800,800]` → 2 strips; horizontal pieces-per 0, vertical 3. Ledge → `[2440]`, `[560]` (2 strips). At 2400 mm bead stock, four square perimeters → 6 strips plus 2 under-ledge strips. No inference that these values establish correctness for every workshop case.

## 9. Stair Geometry Findings

Primary evidence: [T calc_half_stairs.py](/Users/dalethomas/Desktop/Scripts/thomass-timber-dashboard/old_evidence/tkinter-version/src/core/logic/half_wall/calc_half_stairs.py:4), called by `JobSheetWindow.update_half_wall_measurements:166–228`. This is measured-slope geometry, not tread/riser geometry.

### Geometry and angle conventions

Let lower landing be a, upper landing b, measured slope S:

| Quantity | Actual expression / source | Meaning and confidence |
|---|---|---|
| Horizontal run R | W−a−b, line 24 | Horizontal projection between landings |
| Slope angle θ | `acos(R/S)`; radians retained, degrees rounded to 2 decimals, lines 26–27 | Angle of slope relative to horizontal, assuming positive valid run/slope |
| Slope mitre | `round(90−((180−rounded_theta)/2),2)`, line 29 | Algebraically θ/2; complement of half the landing/slope included angle 180−θ |
| Acute included angle | `round(90−rounded_theta,2)`, line 31 | Smaller intersection angle of vertical and slope |
| Top acute mitre | `round(90−acute_angle/2,2)`, line 32 | Complement of half acute included angle; displayed `(T)` |
| Obtuse included angle | `round(180−acute_angle,2)`, line 34 | Larger supplementary intersection angle |
| Bottom obtuse mitre | `round(90−obtuse_angle/2,2)`, line 35 | Complement of half obtuse included angle; displayed `(B)` |

The mitres are expressed **from a square crosscut**, consistent with a saw-setting convention where square is zero, rather than simply half the geometric included angle. The physical saw fence, face, handedness and whether a supplementary setup/jig is needed are not encoded. Do not assert that a particular saw can directly accept 61.78°. The source establishes top/bottom labels, not a complete cutting-orientation instruction. Mirrored/downward staircases are not explicitly modelled. Verify physically before using these as workshop instructions.

Flat width = `(W−(n+1)s)/n`; flat opening height = `(H−(r+1)s)/r`; full inter-rail vertical height = H−2s. All are rounded to 2 decimals. Angled opening width and height divide the corresponding flat dimension by `cos(angle_rad)`; angled vertical-piece height independently divides H−2s by that cosine. **Both width and height are scaled.** This unusual-looking historical rule is reproduced, not replaced with a conventional parallelogram assumption.

### Classification and cut generation

`calc_stair_half:47–91` walks horizontal openings using `used_length`, start at `used_length+s`, end at start+square_width. Slope boundaries are a and W−b. An opening entirely before/after the slope is flat; crossing either boundary is transition; otherwise angled. Exact boundary equality belongs to the fully flat/angled branch according to the comparisons. Counts are **horizontal columns**, not n×r cells. The layout stores index, centre and type, not explicit transition intersection dimensions.

`generate_stair_strip_cut_list_half:136` creates two slope runs plus four landing runs. `undercut_overcut_default = 30` at line 179 applies:

- Top upper landing = b+30.
- Top lower landing = max(0,a−30).
- Bottom upper = b; bottom lower = a.
- Each slope = S, used twice, unchanged.

This normally transfers 30 mm from one top landing cut to the other, preserving their combined length. With a<30 the clamp means it no longer preserves the sum; even a zero upper landing gets a 30 mm top piece. The comment calls it overhang/setback logic. No derivation from s, θ or thickness is provided. Preserve it as an explicit allowance awaiting workshop confirmation, including edge cases.

`split_labelled_cuts:160–176` uses a full board for the first sufficiently long segment, L−k for later oversized segments, and the remaining length for the final segment. It subtracts k from the **remaining required length** between segments. This is different from straight-half splitting. For a 3000 mm required segment with L=2440,k=3 it yields lengths 2440 and 557, a sum of 2997, not 3000. Reported dimensional loss is real arithmetic; whether this reflects intended measuring/joining practice must be settled before reuse for dado.

Vertical generator at line 274 always begins with one flat-height wall-edge batten. Each flat column adds a flat batten; each angled column adds an angled batten. A transition adds angled height when it is the first column or follows flat; otherwise flat height. This does not calculate an individual transition batten from an intersection. Always-flat initial batten and transitions spanning both boundaries deserve edge-case checks, not silent changes.

For r>1, middle pieces are square width for flat columns, angled width for angled/transition columns, repeated r−1 times. Top/bottom rails, verticals and middle pieces are packed as separate groups. Labels are reattached by slicing sorted input rather than tracking packing identity; this can mislabel mixed-length first-fit allocations (section 14).

### Stair bead and ledge

T controller:209–227 takes `angled_count + transition_count` as the angled bead count, and `n*r − that_count` as flat count. For one row this matches the classification tally; for multiple rows it does **not multiply angled columns by r**, allocating extra cells to flat geometry. Transition squares are treated as complete angled rectangles, without their own compound perimeter. Flag both for verification.

The stair bead helper packs flat and angled beads separately. Under-ledge bead is passed **W**, the horizontal stair-wall length, while MDF stair ledge receives **a+S+b**, the developed run (controller:205–207). Thus the regression geometry implies 1500 mm under-ledge bead versus 1700 mm MDF ledge. They are inconsistent unless a workshop reason explains it. Neither helper preserves separate landing/slope ledge joint labels or mitres.

No geometry validity check protects `acos`, zero divisions, negative/zero square sizes or stock length. Controller exceptions print to terminal and can leave prior results in fields. Landings are parsed with `int(string)` while W/H/S are floats, so decimal landing input such as `250.5` fails there even though the calculator can accept floats.

## 10. Known Stair Regression Case Analysis

**Actual source execution agrees with all supplied outputs.** Probe used in-memory `.set()`/`.get()` adapters; no Tk window or rewritten formula. Given inputs W=1500, H=1000, a=b=250, S=1200, n=4, r=1. Added explicit assumptions s=100, L=2440, k=3 (current default MDF/config values). The supplied expected square width itself implies s=100: `(1500−4×250)/5=100`.

R=1000; cos θ=1000/1200=5/6; θ≈33.55730976°, rounded to 33.56°. Slope mitre=16.78°. Acute included angle=56.44°, giving top setting 61.78°; obtuse included angle=123.56°, giving bottom setting 28.22°. Flat opening 250×800; dividing by 5/6 gives angled opening 300×960.

| Column | Opening horizontal interval | Type |
|---|---|---|
| 1 | 100–350 | Transition across slope start 250 |
| 2 | 450–700 | Angled |
| 3 | 800–1050 | Angled |
| 4 | 1150–1400 | Transition across slope end 1250 |

Counts: 0 flat, 2 angled, 2 transition. The actual packed cuts are:

| Group/strip | Cuts, mm | `used`, mm |
|---|---|---|
| Top/bottom 1 | 1200 slope, 1200 slope | 2403 |
| Top/bottom 2 | 280 top upper, 250 bottom upper, 250 bottom lower, 220 top lower | 1009 |
| Vertical 1 | 960 angled transition, 960 angled | 1923 |
| Vertical 2 | 960 angled, 800 flat | 1763 |
| Vertical 3 | 800 flat transition | 800 |

No middle pieces because r=1. Therefore horizontal strips=2, vertical=3. Horizontal pieces-per=0 is an explicit one-row rule, not inability to cut horizontal pieces. Vertical pieces-per=`floor(2440/960)=2`, ignoring kerf in this indicative field. Required vertical sequence before sorting is 800,960,960,960,800.

The candidate golden fixture should preserve **inputs, material selection/stock/kerf, rounded display strings, column classifications, actual cut lengths, allowances and packed groups**. Keep computed geometry assertions separate from stock-dependent counts. The given screen alone does not prove historical board length or kerf, but current configuration plus actual execution explains it exactly. A beaded subtype defaults to 75 mm slats unless overridden, so the fixture should explicitly select/set 100 mm rather than depend on UI defaults.

## 11. Dado Findings

Search covered current source, all ignored Python backups including `PanellingInputBlock`, all three reachable tag trees/calculators, SQL/JSON, templates/JS, and cache function inventories. No dado arithmetic or cuts consumer was found hidden inside the components. A square MDF subtraction formula exists, but no dado input flows into it as a dado calculation.

| Exact offered style | Existing T behaviour | Existing F behaviour | Calculation status |
|---|---|---|---|
| Dado | Middle profile plus wall/dado height; square groups hidden | Middle profile only; gap/square profile hidden | F: no run quantity/cuts |
| Dado Squares Top & Bottom | Shows separate top/bottom counts and outer dimensions/strips | Style choice plus generic dado options | F: no dimension/perimeter logic |
| Dado Double Squares Top & Bottom | Adds inner top and inner bottom dimension outputs and inner strips | Same generic selectors | F: no nested-square sizing/cuts |
| Dado Squares Bottom | Bottom count/dimensions and outer strips | Same generic selectors | F: no bottom-square calculator |
| Dado Double Squares Bottom | Adds inner bottom dimensions and inner strips | Same generic selectors | F: no nested bottom-square calculator |

Exact evidence: T controller:359–362; `DadoWallSectionInputBlock:12–26,159–192`; stair equivalent:183–216; F `panel_type_logic.js:14–20`. Here F in the final column is **classification F**, not the Flask path alias.

T `DadoInputBlock._get_dado_styles:45` populates “45mm Dado Rail”, “70mm Dado Rail” and astragal/decorative-cover labels. It does not select a stock-length variant or retrieve a price for calculation. `dado_wall_measurements_block.py` creates/removes straight/stair sections; section traces invoke the controller, whose `on_change:327–334` has no dado branch. Output variables remain unwritten. `get_data()` is not an integrated calculation service.

F has actual dado database lookup endpoints, SQL grouping and UI selection; it has no dedicated dado wall measurement template, dimension API, cut generator, quantities or cost calculator. Selecting a dado style does not create dado business logic. Full-wall UI remains included and its generic calculation handler is not gated by job type, so a displayed result under a dado selection can still be a **full-wall MDF result**; that is not evidence of dado implementation.

The intended `usable_length = W − gap*(n+1)` is **not connected to dado in the supplied code**. Existing square MDF geometry uses slat width in a similar expression, but that does not establish dado profile/edge-gap semantics. Source suggests top/bottom and inner/outer arrangements via field visibility only. It does not establish run multipliers, inner offsets, vertical opening heights, cut-end conventions or perimeter totals. Those must be specified before implementing each style; do not assume “double” means simply twice the material.

B111 includes a dado catalogue without a dado calculator. B112 and `backups/panelling_input_block.py` implement selection/layout, not cutting. The latter references an older `dado_moulds`/`mdf_boards` schema and hard-codes a “75mm” middle option, unlike the actual 70 mm catalogue. This is abandoned UI/config evidence, not a competing completed dado calculator.

## 12. Dado 3000 mm Stock Handling

Both current catalogues contain 45 mm and 70 mm profiles, 20 mm thick, with lengths 1500,1800,2100,2400,2700,3000,3600,4200,4500,4800. Their 3000 mm rows cost £7.20 and £10.50 respectively. F SQL returns profile categories, not a preferred stock variant. T likewise presents generic middle profiles. No default/max-3000 policy, long dado splitting or purchased-dado-length count exists.

**Classification H for implemented policy; intended business rule requiring implementation.** The user requirement is clear: normal stock for these products is 3000 mm, while required runs may exceed it and be joined. This does not mean rejecting W>3000 or silently picking 4800 mm stock from the historical catalogue. It also does not automatically change 2400 mm astragal/decorative-cover products.

Reusable precedents exist: straight-half rail splitting, ledge splitting and under-ledge bead splitting divide required runs before packing. The stair splitter differs by subtracting kerf from required run length. The common `layout_strips` itself never splits long cuts. Future dado work should preserve required installed length and represent joins/kerf explicitly after conventions are agreed, with 3000 mm stock invariants and purchased-length pricing. No such implementation was made here.

## 13. Stair Dado Findings

`T/src/components/dado_wall_stair_section_input_block.py` provides stair wall length, dado height, lower/upper landing, tread rise, tread depth, step count, measured slope, separate top/bottom square counts, dimension outputs and strip outputs. `DadoWallMeasurementsBlock.add_stair_section:55` is the UI integration entry point. This is real stair dado UI evidence (D/F), not H for the whole feature.

Tread rise/depth/count exist at lines 16–18, are displayed at 49–54 and traced at 176–178. Their only paths are UI variables, generic getters and callbacks; no calculation consumes them. The measured slope is similarly not consumed by dado calculations. The newer **square stair** component has no tread/riser variables and its controller passes measured geometry directly.

No shared geometry abstraction exists yet: square stair derives geometry inside `calc_stair_half`; dado never calls it. F's stair bead helper is not shared staircase geometry. Future stair dado should consume the same recovered landing → slope → landing representation, preserving the old raw inputs as legacy metadata until their migration meaning is settled. No removal is warranted during recovery.

## 14. Cut Optimisation Findings

### Complete optimiser family inventory

| Implementation | Inputs/result | State |
|---|---|---|
| F/T `core/logic/shared/layout_strips.py:1` | Lengths, stock length, kerf → named strips with `cuts`,`used` | Identical modular implementation |
| M nested `layout_strips` at 575,732,886,956 | Full MDF, half MDF, ledge, bead respectively; captured stock, hard-coded k=3 | Historical duplicates; B111 identical; B112 equivalents at 623,780,934,1004 |
| F `materials_totals.calc_boards_needed:91` / M:1234 / B112:1282 | Counts and rip widths → board count | Slats then ledges; sequential fill |
| F `generate_board_cut_layout:117` / M:130 / B112:179 | Same rip demand → board cut arrays, used width, total | Parallel representation algorithm |
| Git 1.0.0 M calculator methods:206–300 | Floor/ceil count estimates, separate bead directions | Pre-packing historical approach; not equivalent to detailed optimizer |
| T `calc_half_stairs.py:160`, `calc_half_wall.py:66`, `calc_half_ledge.py:11,34`, shared bead:20,78 | Pre-split long runs | Splitters, not additional packing optimisers |

### Algorithm behaviour and defects

Length packing is **first-fit decreasing**, not proof of a global minimum: sort descending, try existing strips in order, otherwise open a strip. Pieces are pooled within each passed group only. Full vertical/horizontal groups, half rail/vertical/middle groups, square/ledge bead groups, and separate sections are not globally repacked together. Board ripping combines counts across sections, not remnant lengths. There is no two-dimensional sheet optimisation, stock inventory or reusable-offcut ledger.

Placement checks `sum(existing)+k*len(existing)+cut+k <= L` (lines 17–18), while `used` reports `sum(cuts)+k*(count−1)`. This uses a stricter kerf budget for placement than reporting. Reproduced boundary: `[500,497]`, L=1000,k=3 yields two strips, although the reported between-piece convention would total 1000 on one. Do not silently change this during extraction; characterize it, then agree one convention.

Opening a new strip never checks that the cut fits. Reproduced `[3500]` at L=3000,k=3 → a strip with used=3500, not splitting/rejection. Thus “minimizing waste” in the docstring is not an enforced capacity invariant. `used` is available; waste is not returned explicitly and must be inferred as stock−used, which can be negative. No end-trim, blade/mitre orientation or profile-specific allowances exist in the common packer.

Stair labels are reattached by contiguous slices of the sorted input. First-fit packing may revisit an earlier strip for a shorter piece, breaking those slices. Example mechanism: lengths `[6,5,4,3,2]`, L=10,k=0 pack `[6,4]`, `[5,3,2]`, but slicing labels two-at-a-time gives labels for `[6,5]` on the first strip. Required cut identity must eventually travel with the cut; the golden stair case happens not to expose this.

Board-width functions greedily prioritise slats then fill remaining width with ledges. They agree on ordinary between-strip kerf geometry but are separate implementations that could drift. They do not sort widths to establish optimality. If any requested strip is wider than the board, a pass may remove nothing and their outer loops **never terminate**. This is especially serious for a future unrestricted API. The intended handling must be validation/error, not an endless loop.

Shared infrastructure is justified, but first preserve packing grouping, quantities, label identity and kerf semantics in characterization. Splitting, length packing and board-width ripping should have distinct contracts; consolidating names alone will not reconcile them.

## 15. Material Totals / Job Totals Data Flow

### Exact cause in current Tkinter

The code supports the reported symptom directly:

1. Input trace reaches `JobSheetWindow.on_change:327`.
2. Full/half/stair functions generate and store detailed cuts and print them. Section variables receive counts/dimensions.
3. `on_change` returns after the full/half update. There is **no section collection/aggregation stage**, no import of a material-total service and no call to `job_material_totals_block.update_totals` or `job_totals.update_totals` anywhere in the current controller.
4. `JobMaterialTotalsBlock.update_totals:127` is only a renderer. It expects keys such as `boards_needed_var`, not bare `boards_needed`; it clears keys absent from supplied data. Its stored `on_change` callback is not an aggregation implementation.
5. `JobTotalsBlock.update_totals:30` similarly only formats four numeric arguments. `JobCutListBlock.generate_cut_list:32` explicitly says TEMP placeholder and consumes no sections.

This is a **confirmed missing connection in the supplied current source**, not evidence of a mathematical failure in the successful debug cut list. Refactor incompleteness is the likely historical cause: M and B112 retain aggregation/pricing while the current launcher selects the newer component controller. No commit history of the uncommitted refactor establishes exactly when or why the connection was dropped.

Customer time updates are also disconnected: `CustomerDetailsBlock.__init__:20` references `self._attach_traces` without parentheses, so traces are never installed; current controller constructs it without an `on_change` argument. Both connections would matter after totals recovery.

### Data mismatches that reconnection must address

| Data | Older M / F service expects | Current T generates |
|---|---|---|
| Section collection | M `self.measurements` dictionaries; F list of dictionaries | Full/half/dado containers, separate straight/stair object lists |
| Full cuts | `section['square_strip_cut_list']` | `section.square_strip_cut_list` |
| Half/stair cuts | `section['half_square_strip_cut_list']` | `section.half_square_strip_cut_list` |
| Ledge | Nested half cut-list `ledge` | Separate `section.ledge_cut_list` |
| Bead | Top-level `section['bead_cut_list']` | `section.vars['bead_cut_list']` |
| Stair bead groups | Old aggregators count `square_beads`,`ledge_beads` | `flat_square_beads`,`angled_square_beads`,`ledge_beads` |
| Output keys | F bare `board_cost`, etc. | Tk totals setter expects `board_cost_var`, etc. |

An adapter must explicitly collect active sections, distinguish material/profile/thickness, and include all groups. Reusing the Flask aggregate unchanged would omit stair square beads and standalone ledges even after converting objects to dictionaries. Current calculators also do not consistently clear obsolete results when inputs/styles become invalid; that must not become persisted stale demand.

### Flask's connected but incomplete path

`full_wall_calc.js:142–155` stores real returned cuts in `window.allWallCutData` and invokes totals. `full_wall_materials_totals.js:11–26` **does not use that cache**: it reads count fields and builds arrays of `{used:1000}`. Python only calls `len` on these groups, so the fake 1000 does not currently drive costs; nevertheless detailed geometry, cut identity and actual used length are lost in this path. Board quantities then come from total rip-strip count and board width.

`materials_totals.py:20,35,42` sets meterage to purchased count × stock length, whereas M:1295–1317 sums each strip's packed `used`. Flask's ledge branch increments ledge count but sets bead/ledge meterage from **bead count × bead length**, never adding MDF ledge length. It only consumes straight bead keys. `slat_thickness` is accepted but unused; grouping assumes one common stock/price selection for all sections.

Material formulas: board count×board price; bead strips×bead price; mastic=`ceil((panelling_lm+bead_ledge_lm)/coverage*1.5)`; cut cost=`(combined_MDF_strips+1)*cut_price`; delivery once. The extra cut charge and 1.5 mastic factor are historical policy, not inferred improvements. At zero demand, cutting still charges one cut and delivery still applies. The broad board exception sets count=0 without ensuring `board_cut_summary` exists, so an earlier exception can cause an unbound-local error at return.

Job formula in F `job_totals.py:20–39` and M:54: labour=`round(panelling_lm*slat_rate+bead_ledge_lm*bead_rate,2)`; time allowance=`round(days*day_rate+hours*hourly_rate,2)`; take-home=max(labour,time); materials=sum(board,bead,mastic,cut,delivery); final=`ceil((materials+take_home)/10)*10`. The comment says nearest £10, but code rounds **up**. Dado costs/rate are absent. “Take home” here is a pricing allowance, not net profit accounting with tax/overheads.

### Frontend conditions affecting correctness

- Calculation requires positive time entry; geometry can stay blank despite complete wall inputs.
- Thickness and moulding changes populate dropdowns but do not directly recalculate wall/material results. A later wall edit may finally use the new settings.
- Panel listeners run in registration order; slat default change can occur before/alongside async requests without a canonical recalculation transaction.
- Job type switching changes options but leaves full-wall measurement/material sections; full-wall handler does not validate active job type. Half/dado selections can therefore operate on full-wall inputs.
- Clearing incomplete wall/time fields clears many displayed results, but not `allWallCutData`/`latestMaterialTotals`; some clear lists omit `beads_needed`.
- Removing a section recomputes DOM-based totals but does not remove its cached cut data. The cut-list display can show deleted sections while totals exclude them.
- Independent fetches have no cancellation/revision checks. Older responses may overwrite newer values; an in-flight removed section can repopulate cache.
- Material results do not check HTTP status or `data.error` before updating display; optional chaining can turn an error into plausible zero costs. Job totals check `data.error`, but consume existing DOM values.

These are separate from the confirmed current Tkinter missing calls. They explain why “Flask has totals” is insufficient to declare migration complete.

## 16. Persistence / Data Model

No job tables, quote tables, saved measurement files, serializer, deserializer, `job_id` domain field, foreign-key section relationship or ORM model was found in the supplied source/tag trees. `wall_section` appears in names/comments and UI components, not as a persisted entity. F's `section_id` is a browser index used in debug/result bookkeeping; the route constructs a temporary object and discards it after JSON response. No stable job association exists.

Tk file buttons at controller:412–415 and M:1436–1439 have no Save/Load commands. M's Clear Form button only calls `clear_customer_details`, not a complete job reset. Its clear helpers are not persistence. Imports of `filedialog`/JSON and “No file loaded” labels do not establish saved sessions. `json/data` in B111/Git is a moulding catalogue schema, not job data. Version utilities write version/changelog text, not quotes; none was run.

Four F databases were inspected directly:

| Database/table | Columns and rows |
|---|---|
| `mdf_options.db / mdf_options` | code TEXT, label TEXT, price REAL, width_mm INTEGER, length_mm INTEGER, thickness_mm INTEGER; 3 rows |
| `moulding_options.db / moulding_options` | type TEXT, size TEXT, label TEXT, price REAL, width_mm INTEGER, thickness_mm INTEGER, length_mm INTEGER; 5 rows |
| `dado_options.db / dado_options` | type TEXT, category TEXT, code TEXT, label TEXT, price REAL, width_mm INTEGER, thickness_mm INTEGER, length_mm INTEGER; 23 rows |
| `price_config.db / pricing_config` | id INTEGER PRIMARY KEY; kerf, mastic_unit_price, mastic_linear_coverage, cut_cost_per_strip, delivery_cost, day_rate, hourly_rate, mdf_slat_per_m_gbp, bead_per_m_gbp, dado_per_m_gbp all REAL; 1 row |

No declared catalogue primary keys except pricing `id`, no relationships or migrations. T JSON encodes nested categories, string thickness keys, profiles/variants and dimensions; F flattens these into rows. These are compatible in content but not interchangeable schemas.

Future canonical model should preserve customer/address/date/status, labour inputs, stable job and section IDs/order, section type/subtype, all raw measurements (including legacy stair fields where present), profile/thickness/slat/ledge choices, units, price/config snapshot, calculator version, allowance conventions, derived geometry, labeled cut demand, join identity, packed stock, quantities and cost breakdown. Separate user input from derived/cache/UI state. Preserve both purchased meterage and installed/cut meterage with explicit names. Mixed section types/materials need explicit grouping rather than one global thickness assumption. This is a recommendation, not a schema implementation or claim that saved jobs already exist.

The component `get_data()` methods are unsafe as generic serializers: `.vars` also contains lists/widgets and, for full/half, integer `index`; `{key:var.get() for ...}` will fail. Customer/status getters are simpler scalar-variable collections but are not called by a save service.

## 17. Pricing / Configuration

Current T JSON and F SQLite contain the same principal products/prices. All amounts below are historical stored values, not verified current supplier prices.

| Setting/product | Historical value | Consumption |
|---|---|---|
| MDF sheets | 2440×1220; 6/9/12 mm at £15/£18/£22 | T board-length selection; F dimensions/pricing; M uses matching historical material file |
| Glass bead | 9×9 £2.80; 12×9 £3; 15×9 £3.20; all 2400 long, 9 thick | Filtered by selected MDF thickness; length/cuts in T/F, connected cost in F/M |
| Barrel | 21×9 £4; 34×12 £5.20; 2400 long | Same |
| 45/70 dado | 20 thick, 1500–4800 stock variants; 3000 at £7.20/£10.50 | Profile choices only; stock/price rows unused by dado calculation |
| External square mouldings | Astragal 21×8 £4, 34×12 £6; decorative cover 34×12 £6.20; 2400 long | Dado square profile choices; no cuts/pricing consumer |
| Kerf | 3 mm | T modular/F calculation; M ignores config and hard-codes 3 |
| Mastic | £2.90/unit, 11.5 m coverage | F/M material totals, with hard-coded 1.5 multiplier |
| Cutting / delivery | £2 per strip, £10 delivery | F/M; cutting uses strips+1 |
| Day / hour | £180 / £22.50 | F/M job totals; current T customer inputs disconnected |
| Slat / bead / dado labour per m | £4.90 / £4 / £6.50 | F/M slat+bead; dado rate unused |

Dado price variant details worth preserving: for lengths 4800/4500/4200/3600/3000/2700/2400/2100/1800/1500, 45 mm prices are £11/10.40/9.70/8.60/7.20/6.50/5.60/4.80/5.60/3.40; 70 mm prices £16.40/15.30/14.30/12.60/10.50/9.50/8.20/7.20/6.20/5.10. The 45 mm 1800 price equals the 2400 price and exceeds 2100; suspicious catalogue data, not changed or assumed erroneous.

Hard-coded duplication/fallbacks:

- T full kerf fallback **5000**, half **3**. T board fallback 5000 despite docstring claiming 2440; bead missing-label and exception fallbacks also 5000.
- F full calculation JS defaults board/bead to **5440**, kerf to **30**. Totals JS repeats these and defaults board width to **5440**, board price 50, bead/mastic/cut prices 40, delivery 50, coverage 60. These disagree with supplied configuration. `||` treats a legitimate zero as absent; this affects zero kerf/charges if later permitted.
- F totals submits ledge width as `slatWidth*2`, while the UI offers `thickness*2` or `thickness*3`. No actual ledge demand reaches the current F page, so this is a latent integration discrepancy.
- M uses kerf=3 across inline packers/aggregation, and price-error fallbacks £100. Original board-length fallback is 2440, unlike current controller's 5000.
- Slat default: 100 plain / 75 bead. T editable choices 75/100; F fixed list 70–100 by 5. Dado gaps T 75/100/125/150 (editable), F 70–100 by 5. UI option migration narrowed some choices.
- 30 mm stair allowance, 1.5 mastic factor, +1 cut and upward £10 rounding live in code, not config. Their business meaning should be recorded rather than silently parameterised or removed.

No environment-variable configuration is read by application code. No product/config editor exists. T current loads pricing beyond kerf but has no totals consumer for those values. F `dado_per_m_gbp` has no lookup route/JS pricing use. B112 retains obsolete material-file/schema references; orphaned `json/data` has an earlier internal/external moulding hierarchy with no current loader.

## 18. Flask vs Tkinter Differences

| Concern | Flask | Current Tkinter / historical differences |
|---|---|---|
| Architecture | Single Flask module, JSON calls, browser DOM/cache | Component controller plus separate historical monolith |
| Supported current geometry | Full wall, straight bead | Full, half, measured stairs, bead, ledge |
| Calculator return contract | Mutates temporary section with plain strings | Mutates section attributes and Tk variables |
| Aggregation | Connected counts-only browser reconstruction | Absent current connection; historical real cuts |
| Meterage | Purchased strips × stock | M sum of packed used length including kerf |
| Stair migration | Uncalled stair bead; half aggregate branches | Actual stair MDF/angles/classification/controller |
| Ledge | Selector/latent aggregate handling | Generates physical run cuts; representation changed from nested to standalone |
| Dado | Products and style/input options | More extensive straight/stair measurement UI, still no calculation |
| Persistence | Catalogue SQLite only | Catalogue JSON only; file UI unfinished |
| Job price | Pure shared function and API | Same policy in M/B112; setters only current |
| Errors | Async console errors, API failures, stale caches | Broad controller catches, console errors, stale values |

“Newer” can only be assigned confidently to architecture relationships: current T launcher/component files supersede the tagged monolith; Flask adapts that logic and includes web totals. No F commit/release provenance proves individual formulas newer. Select sources per feature, not per folder age.

## 19. Dead / Duplicate / Disconnected Code

- M is uncalled by current `main_gui.py` and requests an absent material file in its current location; identical B111/tag source remains valuable, not disposable.
- B112 preserves job-total setter integration and almost all M calculators/aggregation. AST comparison shows its changed methods mainly adapt UI names; full/half strip generation, board packing and material aggregation remain equivalent. It still requests `material_prices.json` while its folder contains `mdf_prices.json`, and retains references to old top-level variables. It is an incomplete refactor, not an alternative verified application.
- `backups/panelling_input_block.py` and its B112 copy contain earlier combined square/dado option UI and obsolete catalogue schema references.
- F stair bead helper is defined but never imported/called by `app.py`; F half-wall aggregation branches have no matching browser calculator producer.
- T current totals setters have no controller caller; job cut-list display is placeholder. Customer `_attach_traces` is not called. Stored callbacks in material totals are not an aggregator.
- All M inline length packers and B112/B111 copies duplicate the modular packer family. T `calc_ledge_half` and `calc_ledge_stair` are effectively the same length-splitting algorithm with different debug labels; geometry difference lives in caller arguments.
- Historical 1.0.0 uses floor/ceil estimates rather than detailed packing; 1.1.0 replaces those paths; commented-out estimates remain in M. Do not restore them over detailed cut-list counts.
- Unused locals/comments include bead helper `bead_data`, board `cut_count`/`board_index` bookkeeping, F unused `slat_thickness` aggregate argument, M stale “wall_sections” wording, and misleading nearest-£10/docstring fallback comments.
- Existing caches include orphaned `panelling_input_block`, `customer_details`, `job_totals`, `calc_ledge_half` and a backup monolith cache. They were inventoried, not executed, removed or treated as current source. Their existence supports previous module names, not a hidden completed dado service.
- Version/changelog scripts exist in both folders; Flask's `.gitignore` ignores these scripts, and both ignore backups/caches. Ordinary tracked-file search alone misses recovery evidence. No version utility was run.

## 20. Known Bugs / Suspicious Code

| Priority for later work | Evidence / finding | Confidence and consequence |
|---|---|---|
| Critical recovery | T controller:327–334,473–481: no totals calls | Confirmed current cut → totals disconnection |
| Critical migration | Object/dict/ledge/bead-key mismatches, section 15 | Confirmed incompatibility; partial totals if naively ported |
| High | T controller:258 `pricing_data.get('kerf',5000)` vs line 112 default 3 | Confirmed erroneous-looking kerf fallback, not stock-length purpose. Dormant with supplied `kerf:3`; reachable if key absent; not unreachable code. It prevents normal multi-piece packing when used. |
| High | `layout_strips:22–23` accepts oversized cut | Reproduced invalid stock allocation |
| High | Board packer outer loops | Source-confirmed lack of progress for unfit widths; potential nontermination |
| High | F DOM/event/cache lifecycle defects | Source-confirmed connections absent; browser outcomes not end-to-end exercised |
| High | F/M meterage policy difference | Reproduced numeric difference; business policy unresolved |
| High | Stair bead controller:213–214 | Multirow angled-cell counts not scaled; transition perimeters approximated |
| High | Stair under-ledge bead W vs ledge a+S+b | Confirmed different input lengths; physical intent unresolved |
| Medium | Stair splitter subtracts kerf from required run | Confirmed arithmetic shortening; workshop convention unresolved |
| Medium | Stair label reattachment by sorted slices | Confirmed algorithmic mismatch mechanism for first-fit backfilling |
| Medium | Common packer placement/report kerf mismatch | Reproduced exact-fit rejection |
| Medium | Missing validations throughout | Divide-by-zero/domain/negative lengths; stale results after controller catch |
| Medium | F `materials_totals:69–70,88` exception path | May return unassigned `board_cut_summary`; masks initial failure |
| Medium | T `CustomerDetailsBlock:20`, controller:437 | Traces not invoked; callback not supplied |
| Medium | Section `get_data` mixes objects | Not a viable serializer without explicit field selection |
| Verify workshop | Stair 30 mm rule, both dimensions scaled, first vertical always flat, `(T)/(B)` mitres | Preserve pending physical validation; not declared incorrect |
| Verify pricing | +1 cutting fee, 1.5 mastic, ceil £10, 45 mm 1800 price | Existing policy/data; do not silently correct |

Also note current T `SquareInputBlock` writes option/default variables from callbacks that themselves invoke `on_panelling_type_change`. This can produce nested callbacks and repeated recalculation. Tk trace semantics and actual UI order should be characterized; a recursion failure was not demonstrated, so it is not asserted here.

## 21. Test Coverage Assessment

No test files, test runner configuration, CI workflow or dependency manifest was found in current evidence, ignored backups or reachable tag trees. Changelog assertions are not automated coverage. The audit's in-memory execution probes are not a committed test suite.

Observed probes: Python source syntax/AST parse; stair golden case; full-wall geometry + F materials/job pricing; straight half/bead/ledge cuts; exact-fit kerf case; oversized-stock acceptance. Full Flask route/browser and Tk GUI behaviours remain source-traced rather than runtime-certified.

Proposed future regression suite:

| Area | Required fixtures/assertions |
|---|---|
| Full square | 3000×2400, 4×2, s100 fixture from section 7; multiple walls; bead on/off; unchanged formulas/rounding |
| Half square | Section 8 fixture; r=1 vs r>1; split rails; physical full-height verticals vs opening heights |
| Stair half | Exact section 10 golden case; extra rows; flat/angled/transition boundaries; one/no landing; a<30; long slope; mirrored direction decision |
| Angles | Stored θ and included angles distinct from displayed settings; two-stage rounding; physical signed/handed convention once confirmed |
| Kerf | k0 and k3; exact fit; one cut; mixed cuts; conservation and agreed end-cut convention |
| Packing | Deterministic first-fit legacy output; oversized input; invalid stock; board width too small terminates; label-to-length identity; separate material groups |
| Bead | n×r perimeters; profile thickness/length; multirow stair classification and transition treatment; stale cuts cleared on style change |
| Ledge | 2×/3× thickness selection; long runs; straight vs developed stair run; aggregation and bead-run agreement |
| Straight dado | Each of five styles with approved geometry; W−gap(n+1); negative usable length; independent top/bottom counts and inner offsets |
| Dado >3000 | 3000, 3001, multi-stock runs and multiple walls; no cut exceeds stock; installed-run conservation; kerf/joins; profile-specific purchased count |
| Stair dado | Same input geometry yields same stair run/θ as stair square; landing/slope joins; legacy tread values do not silently override measured slope |
| Material aggregation | Real full/half/stair cuts; all bead/ledge groups; mixed materials; purchase vs installed/used meterage; no omitted/double-counted sections |
| Job totals | Labour/time branches, rounding upward, zero demand policy, consumables/cutting/delivery, config missing/zero/invalid cases |
| API/UI/persistence | Input schema errors; option changes; invalidation; deletion; out-of-order responses; save/load round trip; config/calculator version preservation |

Separate characterization of current suspicious results from acceptance tests for later approved corrections. A golden case must not force unrelated formulas or mask known faults.

## 22. Docker Readiness

No Dockerfile, Compose file, `.dockerignore`, production WSGI configuration, dependency lock/requirements file, migration scripts or container health checks exist. Dockerisation is future work in the **same maintained repository**, not a separate repository. No Docker build/run was attempted.

| Concern | Evidence-based requirement |
|---|---|
| Python | Python 3 source; cached modules indicate historical CPython 3.13 use. Exact supported version is undeclared. Audit pure functions ran under 3.9.6; cache inspection used 3.13.5. Pin a supported version only after compatibility tests. |
| Dependencies | F imports Flask plus stdlib math/sqlite3/os; templates require Jinja through Flask. No Tk dependency should be needed by final framework-neutral engine. T uses stdlib Tkinter/JSON/math plus platform Tk. |
| Working directory/imports | Current launch must resolve `sql/` and `databases/` from F root, with `src` on import path; `src/app.py` owns Flask template/static locations. Final paths should be explicit/configured. |
| Server | Current `app.run(debug=True)` is development-only. Add a production WSGI server and non-debug configuration later; select/test worker model once persistence is specified. |
| Port | Existing application default is 2112; no env-driven port setting in code. Preserve or explicitly configure container mapping. |
| Database | Four embedded SQLite catalogue files; no external DB service required by present implementation. Future job persistence requires its own design/migrations. |
| Read-only assets | Application source, templates, static files and SQL can be image assets. Current catalogues are read-only in intended route behaviour; no config UI writes them. |
| Persistent writable paths | Future job DB/data directory; SQLite journal/WAL sidecars require directory write permission when used. Exports/backups only if those future features are introduced. No current job-write path exists. |
| Config mounts | No hard-coded host-mounted materials directory. Choose either versioned seed catalogue files or an explicitly configured persistent catalogue location if user-editable; do not bake mutable job data into the image. |
| Environment | No existing application env-var contract. Future data/config paths, production settings and any security settings need explicit definitions rather than undocumented fallback values. |
| Static/network | Local JS/CSS are direct files; Bootstrap CSS/JS currently rely on jsDelivr. No frontend compilation required. Decide offline/bundled assets later. |
| Repository packaging | Exclude evidence backups, nested Git metadata and bytecode from runtime image; preserve them as evidence. Do not copy the whole historical tree into the maintained app. |

Production readiness depends first on bounded validation, correct totals state, persistence and reproducible dependencies. Container packaging alone would not repair these failures.

## 23. Recommended Target Architecture

Retain the useful `core/logic` direction already present in Flask. Introduce a calculation/service boundary that accepts numeric, unit-explicit data and returns structured results instead of mutating Flask surrogate sections or Tk variables.

```text
Flask templates / browser presentation
                 ↓
Validated API / job service / persistence adapter
                 ↓
Specific full / half / stair / dado calculators
                 ↓
Shared measured stair geometry + explicit workshop allowances
                 ↓
Labeled cut demand → join/split policy → stock packing / sheet ripping
                 ↓
Material quantities (purchased and installed/used, separately)
                 ↓
Pricing and job totals → one result snapshot → UI / cut list / saved job
```

Responsibilities similar to `stair_geometry`, `cut_optimisation`, `material_totals` and `pricing` are justified. Exact filenames are provisional. F already has `layout_strips`, `materials_totals` and `job_totals`; extend/extract coherently rather than creating competing parallel services. Specific calculators should share geometry and packing while retaining different full/half joinery layouts and material-specific splitting rules.

Preserve historical source under evidence. The maintained app should use recovered formulas with provenance and characterization, not runtime imports from the Tk UI. Model cuts with material/profile, section, role, length, allowance, end-angle convention and join identity before packing; keep labels attached throughout. Aggregate homogeneous stock/profile/thickness groups. Persist raw inputs and versioned result/config snapshots; UI should render the same result used for pricing and export. Do not calculate prices by parsing formatted currency fields or reconstructing fake cut objects.

Business decisions remain explicit: used vs purchased metre rates, exact kerf convention, transition bead geometry, 30 mm allowances, mitre orientation and zero-job charges. Recovery and correction should be separate commits where practical.

## 24. Recovery / Migration Roadmap

These are proposed later milestones, **not work performed by this audit**. Paths refer to future maintained files outside `old_evidence`; source modules are listed as extraction references. Dependencies are explicit and each milestone has a narrow acceptance boundary.

### M1 — Freeze calculation contracts and golden fixtures

**Purpose:** Establish a reproducible basis for lossless recovery. No calculator redesign.

**Existing behaviour to preserve:** Full/half cuts, stair case, two-stage angle rounding, group-specific packing, allowances and current price formula.

**New/recovered behaviour:** Future characterization fixtures, documented result units and recorded unresolved policies; distinguish historical output from approved correctness.

**Likely files/modules affected:** Future `tests/legacy_characterization/`, fixture data and calculation contract documentation; references F/T core logic and M. Evidence remains unchanged.

**Tests required:** Full/half/stair probes in sections 7–10; kerf exact-fit, oversize and label-identity characterization; no GUI dependency.

**Risks:** Golden fixture omitting slat/stock settings; legitimising suspicious outputs as permanent policy.

**Acceptance criteria:** All supplied stair values reproduced with explicit material assumptions; every changed result later attributable to a named contract/policy decision. Depends on no implementation milestone.

### M2 — Establish maintained Flask package and pure full-wall adapter

**Purpose:** Give the recovered engine a maintained home and validate the smallest complete calculator path.

**Existing behaviour to preserve:** Full-square dimensions/cut groups and current quote-page output vocabulary.

**New/recovered behaviour:** Framework-neutral input/result objects; explicit configuration paths; bounded input validation; pinned/testable dependencies; Flask presentation adapter.

**Likely files/modules affected:** Future application entry/package, full-wall module, API adapter and dependency manifest; reference F `app.py` and `calc_full_wall.py`.

**Tests required:** Full-wall parity; invalid counts/dimensions; API response contract; startup from documented directory.

**Risks:** Mixing packaging changes with formula changes; importing Tk dependencies accidentally.

**Acceptance criteria:** Valid full-wall fixture matches M1 without Tk/Flask request objects inside calculation code; invalid data has explicit errors. Depends on M1.

### M3 — Introduce labeled stock demand and bounded shared packing

**Purpose:** Make cut identity and capacity reliable before adding recovered section types.

**Existing behaviour to preserve:** First-fit descending ordering/grouping for ordinary characterized inputs and existing board-rip quantities.

**New/recovered behaviour:** Stable labels; explicit long-piece policy; agreed kerf accounting; invalid/unfit requests terminate with a result/error rather than hang.

**Likely files/modules affected:** Future shared cut/stock model and `layout_strips`/board-rip helpers; references both modular packers and M board methods.

**Tests required:** Identity after backfilling, exact fit, one piece, oversized stock, zero/negative stock, unfit width, deterministic layout and installed-length conservation.

**Risks:** Different kerf policy changes purchased counts; pooling unlike profiles; silently removing stair split allowance.

**Acceptance criteria:** No oversized assigned cuts or unbounded loops; labels match actual lengths; any intentional output changes documented separately from extraction. Depends on M2 and confirmed kerf/join policy from M1.

### M4 — Make full-wall material and job totals consume real results

**Purpose:** Establish one auditable path from cuts to displayed job price.

**Existing behaviour to preserve:** Historical board/bead price multiplication, mastic factor, cut/delivery rules and max(labour,time)/£10 ceiling unless explicitly changed.

**New/recovered behaviour:** Real cut aggregation; distinct purchased/used metrics; approved pricing basis; consistent result snapshot; clear invalidation on edit/removal; latest-response handling.

**Likely files/modules affected:** Future material totals/job service, F-derived `materials_totals`, `job_totals`, full-wall/material/job JS and cut-list renderer.

**Tests required:** Section 7 material/job fixture, multiple/deleted sections, blank/zero time policy, prices/profiles changing, errors and out-of-order responses.

**Risks:** Choosing meterage basis implicitly; old cache still feeding exports; hidden defaults replacing missing prices.

**Acceptance criteria:** UI, cut list and totals use the same active-section result; no deleted/stale demand; policy-specific numeric reconciliation documented. Depends on M3 and meterage/zero-charge decisions.

### M5 — Recover straight bead into the maintained full-wall path

**Purpose:** Complete the full-wall bead subtype before broader layout migration.

**Existing behaviour to preserve:** Four pieces per opening, selected profile dimensions/stock and established packing groups.

**New/recovered behaviour:** Profile identity through pricing; option changes recalculate; stale bead cuts removed on subtype change.

**Likely files/modules affected:** Future bead module, catalogue adapter, full-wall service/API/UI; reference shared `bead_calculations:3`.

**Tests required:** Profile selection/length, 6 mm MDF with no matching bead, bead toggle, aggregate/cost reconciliation, overlong bead policy.

**Risks:** Treating missing profile as invented 5000/5440 stock; changing mitre measuring conventions.

**Acceptance criteria:** Full-wall bead counts/costs agree with characterized cuts and chosen product; missing profile yields explicit state. Depends on M4.

### M6 — Recover straight half-wall MDF

**Purpose:** Port the actual half-wall construction instead of routing half selections through full-wall formulas.

**Existing behaviour to preserve:** Panel-height role, continuous joined rails, H−2s verticals, middle rows and one-row pieces-per display.

**New/recovered behaviour:** Half-wall input/API/service path, material/job aggregation and full cut-list rendering.

**Likely files/modules affected:** Future half-wall calculator, section schema, routes and templates; reference T `calc_half_wall.py` and input components.

**Tests required:** Section 8 MDF case, multirow/long rails, mixed straight sections, quantities/job price.

**Risks:** Mistaking opening height for batten height; reusing full-wall horizontal construction.

**Acceptance criteria:** Half selection invokes half calculator; every generated MDF group reaches material/job totals. Depends on M5.

### M7 — Recover straight-half ledge and bead integration

**Purpose:** Recover optional finishes with their actual lengths and ripping dimensions.

**Existing behaviour to preserve:** Existing ledge run splitting and square/under-ledge bead demand; 2×/3× option intent.

**New/recovered behaviour:** Explicit ledge width semantics, unified result storage, consumption by board totals and pricing.

**Likely files/modules affected:** Future half service, ledge/bead modules, stock grouping/UI; references T `calc_half_ledge`, `SquareInputBlock` and M nested ledge contract.

**Tests required:** Section 8 finish case, all four half subtypes, ledge widths, selected bead stock, no double counting.

**Risks:** Width/thickness confusion; copying F's slat-width×2 fallback; omitted standalone ledges.

**Acceptance criteria:** Each finish's cuts, strips, boards and costs reconcile and disappear when deselected. Depends on M6 and physical ledge dimension confirmation.

### M8 — Extract measured stair geometry and MDF calculator

**Purpose:** Preserve the most valuable stair logic independently of UI.

**Existing behaviour to preserve:** Actual acos/scaling/classification/vertical selection, 30 mm rule and displayed angle convention.

**New/recovered behaviour:** Shared geometry result, explicit allowance metadata, measured stair API/UI and total consumption.

**Likely files/modules affected:** Future stair geometry/calculator, input schema and stair section template; reference T `calc_half_stairs.py` and controller:166.

**Tests required:** Golden case, boundaries, multirow, long runs, a<30, invalid geometry, label identity and totals.

**Risks:** Replacing unusual formulas; loss of physical handedness; kerf shortening copied without decision.

**Acceptance criteria:** Golden outputs match exactly; all deviations on other cases are separately explained/approved; stair MDF flows to totals. Depends on M7 and angle/allowance/join decisions.

### M9 — Resolve and recover stair bead/ledge finishes

**Purpose:** Complete stair material demand without silently preserving known omissions.

**Existing behaviour to preserve:** Existing one-row flat/angled demand and selected product handling as characterized.

**New/recovered behaviour:** Confirmed transition/multirow treatment, correct chosen under-ledge path convention, labeled landing/slope finish demand and complete aggregation.

**Likely files/modules affected:** Future stair finish service and shared bead/ledge functions; references T controller:209 and shared stair bead helper.

**Tests required:** One/multirow stair finishes, transition perimeters, W versus developed run, all bead group keys and ledge widths.

**Risks:** Assuming transition equals angled rectangle; multiplying counts incorrectly; missing saw orientation.

**Acceptance criteria:** Physically confirmed fixtures; each stair finish accounted for once in cuts/quantities/costs. Depends on M8 and workshop confirmation.

### M10 — Implement plain straight dado and 3000 mm purchasing

**Purpose:** Add the smallest previously unfinished dado business path.

**Existing behaviour to preserve:** 45/70 mm product identities and catalogue records; long wall runs remain allowed.

**New/recovered behaviour:** Plain dado run demand, 3000 mm preferred stock, joins, packing, purchased lengths and pricing integration.

**Likely files/modules affected:** Future dado calculator/catalogue policy, section inputs, shared splitter/packer and material/job service.

**Tests required:** Short/exact 3000/3001/multi-stock runs, multiple walls, both profiles, kerf conservation and purchased cost.

**Risks:** Accidentally choosing historic 4800 stock; treating 3000 as maximum wall length; applying policy to 2400 moulding products.

**Acceptance criteria:** Runs over 3000 split with traceable joins and agreed length conservation; purchased count/cost reconciles. Depends on M9 (shared stack stable); requires no invented square arrangement.

### M11 — Implement single-square straight dado arrangements

**Purpose:** Complete Bottom and Top & Bottom variants using approved gap/perimeter definitions.

**Existing behaviour to preserve:** Separate top/bottom counts, gap options, middle versus square profile selection.

**New/recovered behaviour:** W−gap(n+1) usable-length logic, approved opening heights and labeled perimeter cuts.

**Likely files/modules affected:** Future dado geometry/service/template; reference T straight dado UI fields.

**Tests required:** Both single-square styles, unequal top/bottom counts, material profiles, invalid usable dimensions, stock splitting and totals.

**Risks:** Insufficient top height/wall-height inputs; ambiguity of measured face/centre/outer dimensions.

**Acceptance criteria:** Approved drawings map to exact cuts, required inputs are explicit and totals match purchased profiles. Depends on M10 and arrangement specification.

### M12 — Implement double-square straight dado arrangements

**Purpose:** Add nested inner geometry without guessing a material multiplier.

**Existing behaviour to preserve:** Inner/outer output vocabulary and separate top/bottom arrangements.

**New/recovered behaviour:** Confirmed inner offset/profile rules and separate demand for both Double styles.

**Likely files/modules affected:** Future dado nested-layout calculator, inputs and cut labels.

**Tests required:** Double Bottom and Double Top & Bottom, inner-fit limits, two profile choices, material reconciliation.

**Risks:** Treating nested frames as identical doubled perimeters; undefined clearances.

**Acceptance criteria:** Each inner/outer frame is physically specified and independently traceable through stock/pricing. Depends on M11 and inner-offset decisions.

### M13 — Implement stair dado using recovered geometry

**Purpose:** Extend approved dado styles across landing/slope/landing without a second staircase interpretation.

**Existing behaviour to preserve:** Measured stair geometry and legacy raw tread fields as historical input metadata.

**New/recovered behaviour:** Stair dado cuts, joint angles/allowances, 3000 mm packing and full pricing; implement plain rail first, then square styles as separate commits if needed.

**Likely files/modules affected:** Future stair dado calculator/service/UI consuming shared stair geometry and dado profiles.

**Tests required:** Same geometry as M8; landing/slope cuts; long runs; profile/joint orientation; intended effect or non-effect of legacy tread inputs.

**Risks:** Applying MDF-specific 30 mm allowance indiscriminately to dado; inventing transition geometry.

**Acceptance criteria:** One measured staircase definition; workshop-approved dado fixtures; complete costs and cut list. Depends on M12 and M8/M9 physical conventions.

### M14 — Add versioned job save/load

**Purpose:** Persist all recovered inputs and reproducible results in one canonical model.

**Existing behaviour to preserve:** Customer/status/time fields and all supported section inputs, product identities and allowances.

**New/recovered behaviour:** Stable job/section IDs, relationships, versioned save/load and config snapshots; import only actual user-supplied saved data formats if later discovered.

**Likely files/modules affected:** Future persistence models/repository/migrations, job API, quote retrieval UI and storage configuration.

**Tests required:** All-type round trips, mixed materials, missing/old schema handling, config price changes and reproducibility, interrupted-save behaviour.

**Risks:** Persisting Tk widgets or browser caches; claiming a migration format without sample files.

**Acceptance criteria:** Reloaded job preserves raw dimensions/types/prices and reproduces selected calculation version; no dependency on evidence paths. Depends on M13; result contracts should already have been established in M1/M2.

### M15 — Package and verify production Docker deployment

**Purpose:** Deliver one maintained Flask repository with reproducible runtime and durable data.

**Existing behaviour to preserve:** Verified calculator/API/UI/persistence fixtures and port choice unless explicitly changed.

**New/recovered behaviour:** Dockerfile/Compose in the same repository, pinned dependencies, production WSGI startup, data mounts, health check and deployment instructions.

**Likely files/modules affected:** Future root deployment files, dependency lock, production config and operational documentation; no separate Git repository.

**Tests required:** Image build/start, calculation smoke, save/restart/load with volume, permissions, clean startup and static assets.

**Risks:** Baking mutable DB into image, wrong working directory, debug server exposure, accidentally including evidence/nested Git in image.

**Acceptance criteria:** Clean checkout builds and runs the maintained Flask app; persisted jobs survive container replacement; no Tk GUI/evidence dependency. Depends on M14.

## 25. Open Questions Requiring User Confirmation

These questions are for later implementation decisions; they do not block this completed audit.

1. For labour and mastic, should meterage be purchased stock length, cut/installed length, or the older packed `used` length including kerf? Should each purpose have its own metric?
2. Confirm the golden case's actual historical material selection. Current 100 mm slats/2440 mm MDF/3 mm kerf reproduce it; was that the screen configuration?
3. What physical measurement does stair panel height represent? Confirm the existing cosine scaling of both opening dimensions, initial flat vertical and transition handling against a built example.
4. Confirm the 30 mm top landing transfer, its behaviour for landings below 30 mm, and whether it applies only to this MDF layout. Is it measured to long point, short point or another reference?
5. Confirm saw settings/face/handedness for 16.78°, 61.78° `(T)` and 28.22° `(B)`, including mirrored staircases and angles beyond ordinary saw range.
6. Should kerf be between pieces only, per actual saw cut, include end trims, or reflect a supplier cutting convention? Is the stair splitter's reduction of joined installed length deliberate?
7. How should transition-square bead be cut, especially over multiple rows? Should under-ledge bead follow the developed 1700 mm run in the golden geometry, rather than horizontal 1500?
8. Are ledge “2×/3× thickness” values the rip width/depth intended by the old board packing, and are landing/slope mitred ledge joints required?
9. For each square dado style, what defines top/bottom heights, gap measurement, profile reference edges and double-square inner offset? Are different top/bottom counts intentional?
10. The 3000 mm normal stock rule for 45/70 dado is already specified. Clarify allowed join positions/orientation and whether shorter remnants can be pooled across sections; no need to reconfirm the rule itself.
11. Preserve +1 cutting charge, 1.5 mastic allowance and upward £10 job rounding? What should an empty job charge? Are historical stored prices still the desired starting catalogue?
12. Must a job combine full, half, stair and dado sections/materials, or retain one global job type? A canonical model should avoid losing the separate current collections either way.
13. Are there saved job files or other historical copies outside this repository? No functioning save/load format was found here, so any later import work needs representative evidence.
14. Which Python/runtime and deployment host constraints should the final Docker milestone target? Existing code provides port 2112 but no production configuration contract.

**Audit outcome:** Working historical calculations have been identified and traced without changing them. The recovery plan can retain Flask while preserving Tkinter's stair/half-wall logic and recovering the totals functionality lost from the current Tkinter controller.
