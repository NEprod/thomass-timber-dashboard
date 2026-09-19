"""Physical owned-stock planning around the existing labelled cut demand.

Recommendations are advisory. Only explicit allocations affect procurement,
and neither path changes the normal customer charge calculation.
"""
from collections import Counter
from ..calculations.packing import CalculationError, pack


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


def material_demands(quote, material_id):
    """Return existing physical demand without changing calculator geometry."""
    product = quote.snapshot['catalogue'][material_id]
    demands = []
    serial = 0
    for room in quote.rooms:
        for item in room.items:
            if not item.result.get('valid'):
                continue
            for group in item.result.get('groups', {}).values():
                if group.get('material_id') != material_id:
                    continue
                if product['category'] == 'mdf':
                    for strip in group.get('strips', []):
                        serial += 1
                        demands.append({'id': f'rip-{item.id}-{serial}',
                                        'length_mm': float(strip['used_mm']),
                                        'width_mm': float(group['width_mm']),
                                        'label': strip['cuts'][0].get('label', 'MDF rip')})
                else:
                    for cut in group.get('cuts', []):
                        serial += 1
                        demand = dict(cut)
                        demand['_inventory_id'] = f'cut-{item.id}-{serial}'
                        demands.append(demand)
    return demands


def _take_linear_piece(demands, length, kerf):
    eligible = [d for d in demands if d['length_mm'] <= length + 1e-7]
    if not eligible:
        return demands, False
    chosen = pack(eligible, length, kerf)[0]['cuts']
    chosen_ids = {d['_inventory_id'] for d in chosen}
    return [d for d in demands if d['_inventory_id'] not in chosen_ids], True


def _take_sheet_piece(demands, length, width, kerf):
    eligible = [d for d in demands
                if d['length_mm'] <= length + 1e-7 and d['width_mm'] <= width + 1e-7]
    if not eligible:
        return demands, False
    widths = [dict(d, length_mm=d['width_mm'], _sheet_id=d['id']) for d in eligible]
    chosen = pack(widths, width, kerf)[0]['cuts']
    chosen_ids = {d['_sheet_id'] for d in chosen}
    return [d for d in demands if d['id'] not in chosen_ids], True


def _normal_units(demands, product, kerf):
    if not demands:
        return 0
    if product['category'] == 'mdf':
        widths = [dict(d, length_mm=d['width_mm']) for d in demands]
        return len(pack(widths, product['width_mm'], kerf))
    return len(pack(demands, product['length_mm'], kerf))


def _expanded_stock(allocations):
    pieces = []
    for allocation in allocations:
        pieces.extend([allocation.owned_stock] * allocation.quantity)
    return pieces


def procurement_units(quote, calculated, extra_quantity, allocations):
    """Calculate gross units still needed after explicit physical reservations."""
    material_id = calculated['material_id']
    product = quote.snapshot['catalogue'][material_id]
    if not allocations:
        return int(calculated['new_purchase_units']) + extra_quantity
    kerf = quote.snapshot['pricing']['kerf']
    demands = material_demands(quote, material_id)
    unused_full = 0
    pieces = sorted(_expanded_stock(allocations),
                    key=lambda s: stock_dimensions(s, product))
    for stock in pieces:
        length, width = stock_dimensions(stock, product)
        if product['category'] == 'mdf':
            demands, used = _take_sheet_piece(demands, length, width, kerf)
        else:
            demands, used = _take_linear_piece(demands, length, kerf)
        if not used and stock.stock_type == 'full':
            unused_full += 1
    return _normal_units(demands, product, kerf) + max(0, extra_quantity - unused_full)


def stock_can_satisfy(quote, stock, extra_quantity=0):
    product = quote.snapshot['catalogue'].get(stock.material_id)
    if not product:
        return False
    demands = material_demands(quote, stock.material_id)
    length, width = stock_dimensions(stock, product)
    if product['category'] == 'mdf':
        fits = any(d['length_mm'] <= length + 1e-7 and
                   d['width_mm'] <= width + 1e-7 for d in demands)
    else:
        fits = any(d['length_mm'] <= length + 1e-7 for d in demands)
    return fits or (stock.stock_type == 'full' and extra_quantity > 0)


def stock_recommendations(quote, plan, stocks, allocations):
    """Greedily retain stock unless one physical piece reduces purchases."""
    by_material = {}
    existing = {}
    for allocation in allocations:
        existing.setdefault(allocation.material_id, []).append(allocation)
    for row in plan:
        if row.get('is_calculated_consumable'):
            continue
        material_id = row['material_id']
        product = quote.snapshot['catalogue'][material_id]
        candidates = [s for s in stocks if s.active and s.material_id == material_id
                      and available_quantity(s)]
        candidates.sort(key=lambda s: stock_dimensions(s, product))
        simulated = list(existing.get(material_id, []))
        purchased = row.get('purchased_quantity', 0)
        before = max(0, procurement_units(quote, row, row['extra_quantity'], simulated) - purchased)
        accepted = Counter()
        retained = None
        for stock in candidates:
            for _ in range(available_quantity(stock)):
                if not stock_can_satisfy(quote, stock, row['extra_quantity']):
                    retained = retained or f"Keep {stock_description(stock, product)} — no current calculated cut fits."
                    continue
                proposed = simulated + [_ProposedAllocation(stock, material_id)]
                after = max(0, procurement_units(quote, row, row['extra_quantity'], proposed) - purchased)
                if after < before:
                    simulated = proposed
                    accepted[stock.id] += 1
                    before = after
                else:
                    purchase = (f"{product['length_mm']:g} × {product['width_mm']:g} mm sheet"
                                if product['category'] == 'mdf' else
                                f"{product['length_mm']:g} mm length")
                    retained = retained or f"Keep {stock_description(stock, product)} — using it does not reduce the required {before} × {purchase} purchase."
        if accepted:
            descriptions = []
            for stock_id, quantity in accepted.items():
                stock = next(s for s in candidates if s.id == stock_id)
                descriptions.append(f"{quantity} × {stock_description(stock, product)}")
            original = row['need_to_purchase_quantity']
            by_material[material_id] = {'stock': dict(accepted),
                                        'text': f"Recommended: use {', '.join(descriptions)} — reduces purchase requirement from {original} to {before}."}
        elif retained:
            by_material[material_id] = {'stock': {}, 'text': retained}
    return by_material


class _ProposedAllocation:
    def __init__(self, stock, material_id):
        self.owned_stock = stock
        self.material_id = material_id
        self.quantity = 1


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
