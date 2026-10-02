# v1.5.6 quote display audit

Baseline: v1.5.5 plus approved pricing commits d0cf982 and 6bf5aec.
No geometry, packing, recommendation, pricing, procurement or schema changes.

| Work family | Authoritative normal display | Useful derived display | Collapsed engineering detail | Removed competing display |
| --- | --- | --- | --- | --- |
| Full / Half / Stair panelling, all enabled finishes | Room-packed prepared MDF strips and linear stock; installed wall geometry; base-cut summary | Canonical opening IDs / representative polygon dimensions; stair pattern and mitre settings | Installed polygons / members, measurement conventions and warnings | Per-item horizontal/vertical stock estimates, inflated angled square dimensions, duplicate finish metres / labour |
| Plain Dado / Dado Squares Bottom, straight and stair | Room-packed linear stock; installed layout; grouped profile cuts | Square dimensions and installed mitres where available | Frame geometry / provenance / site-fit warnings | Repeated verbose Dado workshop summary, early labour / finish totals |
| Coving | Packed purchased stock lengths and final cuts | Wall length, corner types | External-end allowance / labour | Legacy per-item stock estimate |
| Cabinet / Built-in: Alcove, Window Seat, Bench, Custom | Room-packed raw sheets and PSE lengths; unchanged guillotine sheet plan | Cabinet/bay/shelf/door dimensions | Finished part dimensions vs cut blanks, workshop / installation time | Early labour duplication, verbose individual linear-cut table |
| Quote-wide commercial / administration | Saved financial totals / payments, raw material rows, explicit Extra Material and procurement state | Strip count × saved rate breakdown; recorded sheet cuts × saved rate | Draft purchasing / receipts collapsed; saved snapshot | Mixed sheet/strip units in a single extra-quantity cell; purchase counts summed across unlike units |

Calculated Requirements uses the existing exact-plan adapter and room packer,
excluding accepted extras. A prepared strip, stock length or sheet can support
several work items: each participating work item explicitly identifies shared
stock rather than claiming invented exclusive allocation. These shared totals
are not additive. Workshop Preparation and Quoted Materials carry room totals.

Canonical opening metadata supplies IDs; cut labels use square/row/edge metadata
only where present. Other cuts retain their existing authoritative labels. No
new identities are inferred from packing order. The SVG adds identity labels
only; every installed vertex, dimension endpoint and mirrored coordinate rule
is unchanged.

Equivalent top/bottom profile cuts group only within the same material, width,
component family, base length, allowance, status and cutting settings. Transition
segment metadata remains distinct. All original cuts remain in the detailed plan.

Decisions precede preparation. Sheet ripping and direct Cabinet sheet nesting
precede final strip/linear component cutting. Extra Material edit forms, payment,
receipt and procurement actions preserve their existing POST payloads and tokens.
Both cut-charge fixes are consumed unchanged; border allowance remains uncharged.
