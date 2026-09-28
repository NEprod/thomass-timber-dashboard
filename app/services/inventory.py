"""Physical owned-stock planning around the existing labelled cut demand.

Recommendations are advisory. Only explicit allocations affect procurement,
and neither path changes the normal customer charge calculation.
"""
from collections import Counter
from ..calculations.packing import CalculationError


def available_quantity(stock):
    return max(0, stock.quantity - stock.reserved_quantity - stock.consumed_quantity)


def stock_dimensions(stock, product):
    if stock.stock_type == 'full':
        return float(product['length_mm']), float(product['width_mm'])
    return float(stock.usable_length_mm or 0), float(stock.usable_width_mm or 0)


def stock_description(stock, product):
    length, width = stock_dimensions(stock, product)
    if product['category'] == 'mdf':
        return f"{length:g} × {width:g} mm {'full sheet' if stock.stock_type == 'full' else 'offcut'}"
    return f"{length:g} mm {'full stock' if stock.stock_type == 'full' else 'offcut'}"


class _ProposedAllocation:
    def __init__(self, stock, material_id, room_id=None):
        self.owned_stock = stock
        self.material_id = material_id
        self.room_id = room_id
        self.quantity = 1
        self.id = -stock.id
        self.stock_length_mm = None
        self.stock_width_mm = None


def stock_recommendations(quote, plan, stocks, allocations):
    from .room_procurement import (compatible, family, procurement_plan,
                                   stock_fits_room)

    def outstanding(simulated):
        needs, unused = procurement_plan(quote, allocations=simulated)
        extra_by_material = Counter()
        for row in quote.material_states:
            extra_by_material[row.material_id] += row.extra_quantity
        extras = sum(max(0, quantity - unused[material_id])
                     for material_id, quantity in extra_by_material.items())
        return sum(needs.values()) + extras

    suggestions = {}
    seen = set()
    simulated = list(allocations)
    before = outstanding(simulated)
    for row in plan:
        if row.get('is_calculated_consumable'):
            continue
        material_id = row['material_id']
        key = family(quote.snapshot['catalogue'], material_id)
        if key in seen:
            continue
        seen.add(key)
        candidates = [stock for stock in stocks if stock.active and available_quantity(stock)
                      and compatible(quote.snapshot['catalogue'], stock.material_id, material_id)]
        candidates.sort(key=lambda stock: stock_dimensions(
            stock, quote.snapshot['catalogue'][stock.material_id]))
        accepted = Counter()
        retained = None
        for stock in candidates:
            for _ in range(available_quantity(stock)):
                possible = []
                for room in quote.rooms:
                    if not stock_fits_room(quote, stock, room.id, row['extra_quantity']):
                        continue
                    proposal = _ProposedAllocation(stock, stock.material_id, room.id)
                    after = outstanding(simulated + [proposal])
                    possible.append((after, room.id, proposal))
                if possible and min(possible)[0] < before:
                    after, _, proposal = min(possible)
                    simulated.append(proposal)
                    accepted[stock.id] += 1
                    before = after
                elif possible:
                    retained = retained or 'Keep compatible stock — using it does not reduce the required purchase.'
                else:
                    retained = retained or 'Keep compatible stock — no current calculated cut fits.'
        if accepted:
            by_id = {stock.id: stock for stock in candidates}
            descriptions = [f'{quantity} × {stock_description(by_id[stock_id], quote.snapshot["catalogue"][by_id[stock_id].material_id])}'
                            for stock_id, quantity in accepted.items()]
            suggestions[material_id] = dict(stock=dict(accepted),
                text=f"Recommended: use {', '.join(descriptions)} — reduces purchase requirement.")
        elif retained:
            suggestions[material_id] = dict(stock={}, text=retained)
    return suggestions


def validate_stock_values(material, stock_type, usable_length, usable_width):
    if stock_type not in ('full', 'offcut'):
        raise CalculationError('Choose full stock or an offcut.')
    if stock_type == 'full':
        return None, None
    if not usable_length or usable_length <= 0:
        raise CalculationError('Enter the actual usable offcut length.')
    if usable_length > material.length_mm + 1e-7:
        raise CalculationError('Offcut length cannot exceed the configured full stock length.')
    if material.category == 'mdf':
        if not usable_width or usable_width <= 0:
            raise CalculationError('Enter the actual usable sheet offcut width.')
        if usable_width > material.width_mm + 1e-7:
            raise CalculationError('Offcut width cannot exceed the configured full sheet width.')
        return usable_length, usable_width
    return usable_length, None
