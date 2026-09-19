# v1.1.2: Dado stock and quote workflow

## Preserved calculations

Full walls, half walls, measured stair half walls, bead, ledge and existing
dado geometry continue to use their existing calculator paths. Kerf remains a
stock-packing allowance: it does not reduce finished bead or dado dimensions.

The stair values remain calculation regressions, not physically validated saw
instructions. The 30 mm MDF stair allowance has not been applied to dado.

## Straight and stair dado stock

Straight continuous dado still preserves a finished long run and splits it
only when its chosen profile stock requires a joint. A stair dado preserves
the lower landing, measured slope and upper landing as individually labelled
finished cuts. Their compatible raw stock is now packed as one route:

- 450 / 1200 / 450 mm can use one 2400 mm length when that compatible product
  exists;
- where 1500 mm and 3000 mm are available, the same route uses one 3000 mm
  length rather than three 1500 mm lengths;
- kerf is included between cuts on a raw stock length.

The cut labels and landing/slope joint settings remain attached. “Need to
purchase” is deliberately used until a user records an actual purchase.

## Stair result review

Stair result cards show slope angle, slope mitre, normal square dimensions,
angled-square dimensions, top/bottom settings and the flat/angled/transition
sequence together. Repetitive straight Dado Squares Bottom frame rows are
kept in the result data but collapsed under **Square layout details**.

## Quote financial and material semantics

The material plan keeps these distinct:

1. calculated stock requirement;
2. explicit extra job material;
3. total customer-chargeable material;
4. explicitly allocated owned stock;
5. material still needed for purchase; and
6. recorded purchase events.

Customer material charges use calculated stock plus extra material. Allocating
owned stock never reduces the customer material charge or the deposit. A
purchase records its saved product price and date and removes that quantity
from **Materials to buy**. Purchased job material is not automatically made
owned stock.

The application has a lightweight **Owned stock** register. It only accepts a
configured compatible product for allocation and never creates an offcut from
a theoretical remainder. On a completed quote, the workshop records the
actual usable leftover length and quantity after inspection.

## Quote extras, deposit and payments

Materials & pricing now contains configurable quote consumables. Added quote
consumables save the label, unit and price at the time they are added. Quotes
also support multiple editable additional charges and payment entries.

Deposit Required is the sum of chargeable materials, quote consumables and
additional charges, rounded up to the next £10 with decimal-safe arithmetic.
Normal labour/time allowance is excluded from the deposit. The quote total,
paid amount, balance and payment state are visible together. Physical quote
status remains separate from payment state.

## Workshop validation still needed

- Confirm real-stair saw orientation and long-point/short-point conventions
  for the recovered stair settings.
- Confirm the historical MDF 30 mm allowance across varied slat widths and
  angles; the current fixed rule is retained.
- Trim-to-fit transition bead/dado allowances remain conservative material
  provisions, not verified finished cuts.
- Validate finished stair-dado joints and any profile-specific workshop
  restrictions on a real wall.
