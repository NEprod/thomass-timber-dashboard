"""Match room-assigned physical pieces to labelled room cuts before buying stock."""
from collections import Counter, defaultdict

from ..calculations.packing import pack
from ..calculations.room_stock import _dado_stocks, _dado_use
from ..models import db, OwnedStockAllocation
from .inventory import stock_dimensions, stock_can_satisfy


def assigned_room(quote, record):
    """Only a one-room legacy quote has an unambiguous missing room."""
    if record.room_id is not None:
        return record.room_id if any(room.id == record.room_id for room in quote.rooms) else None
    return quote.rooms[0].id if len(quote.rooms) == 1 else None


def compatible(catalogue, left_id, right_id):
    left, right = catalogue.get(left_id), catalogue.get(right_id)
    if not left or not right or left['category'] != right['category']:
        return False
    if left['category'] == 'dado':
        return all(left[key] == right[key] for key in ('profile', 'width_mm', 'thickness_mm'))
    return left_id == right_id


def family(catalogue, material_id):
    product = catalogue[material_id]
    if product['category'] == 'dado':
        return ('dado', product['profile'], product['width_mm'], product['thickness_mm'])
    return ('product', material_id)


def stock_fits_room(quote, stock, room_id, extra_quantity=0):
    catalogue = quote.snapshot['catalogue']
    product = catalogue.get(stock.material_id)
    if product is None:
        return False
    if 'room_stocks' not in quote.result and len(quote.rooms) == 1:
        return stock_can_satisfy(quote, stock, extra_quantity)
    length, width = stock_dimensions(stock, product)
    for planned in quote.result.get('room_stocks', []):
        if planned['room_id'] != room_id or not compatible(
                catalogue, stock.material_id, planned['material_id']):
            continue
        for cut in planned['cuts']:
            if product['category'] == 'mdf':
                if cut['used_length_mm'] <= length + 1e-7 and cut['width_mm'] <= width + 1e-7:
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


def _consume(cuts, piece, category, kerf):
    length, width = piece['length_mm'], piece['width_mm']
    if category == 'mdf':
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
    result = result or quote.result or {}
    if 'room_stocks' not in result:
        return None
    catalogue = quote.snapshot['catalogue']
    kerf = quote.snapshot['pricing']['kerf']
    demands = defaultdict(list)
    for stock in result['room_stocks']:
        key = (stock['room_id'], family(catalogue, stock['material_id']))
        demands[key].extend(dict(cut, material_id=stock['material_id']) for cut in stock['cuts'])
    unused_full = Counter()
    for piece in physical_pieces(quote, allocations):
        key = (piece['room_id'], family(catalogue, piece['material_id']))
        cuts = demands.get(key, [])
        remaining = _consume(cuts, piece, catalogue[piece['material_id']]['category'], kerf)
        if len(remaining) == len(cuts) and piece['full']:
            unused_full[piece['material_id']] += 1
        demands[key] = remaining
    needs = Counter()
    for (room_id, _), cuts in demands.items():
        if not cuts:
            continue
        product = catalogue[cuts[0]['material_id']]
        if product['category'] == 'dado':
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
        else:
            needs[(room_id, product['id'])] += len(pack(cuts, product['length_mm'], kerf))
    return needs, unused_full
