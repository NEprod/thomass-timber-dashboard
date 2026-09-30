"""Match room-assigned physical pieces to labelled room cuts before buying stock."""
from collections import Counter, defaultdict

from ..calculations.packing import pack
from ..calculations.room_stock import _dado_stocks, _dado_use
from ..calculations.room_stock import _coving_stocks
from ..calculations.materials import kerf_for
from ..calculations.sheet_optimizer import pack_sheet_parts, parts_on_owned_sheet
from ..models import db, OwnedStockAllocation
from .inventory import stock_dimensions


def assigned_room(quote, record):
    """Only a one-room legacy quote has an unambiguous missing room."""
    if record.room_id is not None:
        return record.room_id if any(room.id == record.room_id for room in quote.rooms) else None
    return quote.rooms[0].id if len(quote.rooms) == 1 else None


def compatible(catalogue, left_id, right_id):
    left, right = catalogue.get(left_id), catalogue.get(right_id)
    if not left or not right or left['category'] != right['category']:
        return False
    if left['category'] in ('dado', 'coving'):
        return all(left[key] == right[key] for key in ('profile', 'width_mm', 'thickness_mm'))
    return left_id == right_id


def family(catalogue, material_id):
    product = catalogue[material_id]
    if product['category'] in ('dado', 'coving'):
        return (product['category'], product['profile'], product['width_mm'], product['thickness_mm'])
    return ('product', material_id)


def stock_fits_room(quote, stock, room_id, extra_quantity=0):
    catalogue = quote.snapshot['catalogue']
    product = catalogue.get(stock.material_id)
    if product is None:
        return False
    length, width = stock_dimensions(stock, product)
    for planned in quote.result['room_stocks']:
        if planned['room_id'] != room_id or not compatible(
                catalogue, stock.material_id, planned['material_id']):
            continue
        for cut in planned['cuts']:
            if product['category'] == 'mdf':
                if planned.get('packing_kind') == 'sheet':
                    trim = quote.snapshot['pricing'].get('sheet_edge_trim', 10) if stock.stock_type == 'full' else 0
                    if any(part_length <= length - 2 * trim + 1e-7 and
                           part_width <= width - 2 * trim + 1e-7
                           for part_length, part_width in ((cut['cut_length_mm'], cut['cut_width_mm']),
                               (cut['cut_width_mm'], cut['cut_length_mm']))
                           if cut.get('rotation_allowed', True) or part_length == cut['cut_length_mm']):
                        return True
                elif cut['used_length_mm'] <= length + 1e-7 and cut['width_mm'] <= width + 1e-7:
                    return True
            elif cut['length_mm'] <= length + 1e-7 and (
                    product['category'] != 'dado' or _dado_use(cut) in product.get('uses', [])):
                return True
    return stock.stock_type == 'full' and extra_quantity > 0


def stock_fits_quote(quote, stock, extra_quantity=0):
    return any(stock_fits_room(quote, stock, room.id, extra_quantity)
               for room in quote.rooms)


def physical_pieces(quote, allocations=None):
    catalogue = quote.snapshot['catalogue']
    pieces = []
    for purchase in quote.purchases:
        room_id = assigned_room(quote, purchase)
        if room_id is None or purchase.material_id not in catalogue:
            continue
        product = catalogue[purchase.material_id]
        for index in range(purchase.quantity):
            pieces.append(dict(room_id=room_id, material_id=purchase.material_id,
                               length_mm=purchase.stock_length_mm or product['length_mm'],
                               width_mm=purchase.stock_width_mm or product['width_mm'],
                               uses=product.get('uses', []),
                               source=('purchase', purchase.id, index), full=True))
    if allocations is None:
        allocations = db.session.scalars(db.select(OwnedStockAllocation).where(
            OwnedStockAllocation.quote_id == quote.id)).all()
    for allocation in allocations:
        room_id = assigned_room(quote, allocation)
        if room_id is None or allocation.material_id not in catalogue:
            continue
        stock = allocation.owned_stock
        product = catalogue[allocation.material_id]
        length, width = stock_dimensions(stock, product)
        for index in range(allocation.quantity):
            pieces.append(dict(room_id=room_id, material_id=allocation.material_id,
                               length_mm=allocation.stock_length_mm or length,
                               width_mm=allocation.stock_width_mm or width,
                               uses=product.get('uses', []),
                               source=('reservation', allocation.id, index),
                               full=stock.stock_type == 'full'))
    return sorted(pieces, key=lambda piece: (piece['length_mm'], piece['width_mm'], piece['source']))


def _consume(cuts, piece, category, kerf, *, mode='linear', sheet_trim=10, sheet_kerf=3):
    length, width = piece['length_mm'], piece['width_mm']
    if mode == 'sheet':
        trim = sheet_trim if piece['full'] else 0
        usable_length, usable_width = length - 2 * trim, width - 2 * trim
        if usable_length <= 0 or usable_width <= 0:
            return cuts
        selected, _ = parts_on_owned_sheet(cuts, usable_length, usable_width, kerf=sheet_kerf)
    elif category == 'mdf':
        eligible = [cut for cut in cuts if cut['used_length_mm'] <= length + 1e-7
                    and cut['width_mm'] <= width + 1e-7]
        if not eligible:
            return cuts
        selected = pack([dict(cut, length_mm=cut['width_mm']) for cut in eligible], width, kerf)[0]['cuts']
    else:
        eligible = [cut for cut in cuts if cut['length_mm'] <= length + 1e-7
                    and (category != 'dado' or _dado_use(cut) in piece['uses'])]
        if not eligible:
            return cuts
        selected = pack(eligible, length, kerf)[0]['cuts']
    ids = {cut['id'] for cut in selected}
    return [cut for cut in cuts if cut['id'] not in ids]


def procurement_plan(quote, result=None, allocations=None):
    """Return remaining room/SKU units and unused full pieces for quote extras.

    Normal customer charging is deliberately absent from this calculation.
    """
    result = result or quote.result
    catalogue = quote.snapshot['catalogue']
    pricing = quote.snapshot['pricing']
    demands = defaultdict(list)
    for stock in result['room_stocks']:
        key = (stock['room_id'], family(catalogue, stock['material_id']),
               stock.get('packing_kind', 'linear'))
        demands[key].extend(dict(cut, material_id=stock['material_id']) for cut in stock['cuts'])
    unused_full = Counter()
    def sheet_units(cuts, product, mode):
        if not cuts:
            return 0
        if mode == 'sheet':
            return len(pack_sheet_parts(cuts, product['length_mm'], product['width_mm'],
                trim=pricing.get('sheet_edge_trim', 10), kerf=pricing.get('sheet_kerf', 3)))
        return len(pack([dict(cut, length_mm=cut['width_mm']) for cut in cuts],
                        product['width_mm'], kerf_for(product, pricing)))

    for piece in physical_pieces(quote, allocations):
        product = catalogue[piece['material_id']]
        kerf = kerf_for(product, pricing)
        family_key = family(catalogue, piece['material_id'])
        possibilities = []
        for mode in ('sheet', 'linear'):
            key = (piece['room_id'], family_key, mode)
            cuts = demands.get(key, [])
            if not cuts:
                continue
            remaining = _consume(cuts, piece, product['category'], kerf,
                mode=mode, sheet_trim=pricing.get('sheet_edge_trim', 10),
                sheet_kerf=pricing.get('sheet_kerf', 3))
            if len(remaining) < len(cuts):
                saved = (sheet_units(cuts, product, mode) - sheet_units(remaining, product, mode)
                         if product['category'] == 'mdf' else len(cuts) - len(remaining))
                possibilities.append((saved, len(cuts) - len(remaining), mode, key, remaining))
        if not possibilities and piece['full']:
            unused_full[piece['material_id']] += 1
        if possibilities:
            _, _, _, key, remaining = max(possibilities)
            demands[key] = remaining
    needs = Counter()
    for (room_id, _, mode), cuts in demands.items():
        if not cuts:
            continue
        product = catalogue[cuts[0]['material_id']]
        kerf = kerf_for(product, pricing)
        if mode == 'sheet':
            needs[(room_id, product['id'])] += len(pack_sheet_parts(cuts,
                product['length_mm'], product['width_mm'],
                trim=pricing.get('sheet_edge_trim', 10), kerf=pricing.get('sheet_kerf', 3)))
        elif product['category'] == 'dado':
            stocks = _dado_stocks(cuts, catalogue, kerf, {cut['material_id'] for cut in cuts})
            for stock in stocks:
                needs[(room_id, stock['material_id'])] += 1
        elif product['category'] == 'mdf':
            for cut in cuts:
                if cut['used_length_mm'] > product['length_mm'] + 1e-7:
                    raise ValueError('MDF rip exceeds its stock sheet length.')
            needs[(room_id, product['id'])] += len(pack(
                [dict(cut, length_mm=cut['width_mm']) for cut in cuts],
                product['width_mm'], kerf))
        elif product['category'] == 'coving':
            stocks = _coving_stocks(cuts, catalogue, kerf, {cut['material_id'] for cut in cuts})
            for stock in stocks:
                needs[(room_id, stock['material_id'])] += 1
        else:
            needs[(room_id, product['id'])] += len(pack(cuts, product['length_mm'], kerf))
    return needs, unused_full
