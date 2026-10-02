"""Room-owned full-length strip extras, adapted to the existing room packer.

No Work Items are created. Exact results and labour/mastic remain unchanged.
The same side-effect-free adapter serves saved additions and preview simulations.
"""
from collections import Counter
from copy import deepcopy

from ..calculations.packing import CalculationError, number
from ..calculations.pricing import money
from ..calculations.room_stock import pack_rooms
from ..calculations.preparation import prepared_strip_count


def strip_payload(product, width, length, quantity):
    if product.get('category') != 'mdf':
        raise CalculationError('Dimensional strip extras require an MDF sheet.')
    width = number(width, 'Extra strip width', maximum=product['width_mm'])
    length = number(length, 'Extra strip length', maximum=product['length_mm'])
    quantity = number(quantity, 'Extra strip quantity', allow_zero=True, maximum=100)
    if quantity != int(quantity):
        raise CalculationError('Extra strip quantity must be a whole number.')
    if abs(length - product['length_mm']) > 1e-7:
        raise CalculationError('Dimensional extras currently support full-length prepared strips only.')
    return dict(kind='rectangular_strip', width_mm=width, length_mm=length, quantity=int(quantity))


def room_inputs(quote):
    return [dict(id=room.id, name=room.name,
                 items=[dict(id=item.id, name=item.name, result=item.result) for item in room.items])
            for room in quote.rooms]


def extra_payloads(quote):
    return {(state.room_id, state.material_id): deepcopy(state.dimensional_extras or [])
            for state in quote.material_states if state.dimensional_extras}


def strip_quantity(quote, room_id, material_id, width):
    return sum(p['quantity'] for p in extra_payloads(quote).get((room_id, material_id), [])
               if p['width_mm'] == width)


def stock_counts(stocks):
    return Counter((stock['room_id'], stock['material_id']) for stock in stocks)


def with_dimensional_extras(quote, exact, overrides=None):
    payloads = extra_payloads(quote)
    if overrides:
        payloads.update(deepcopy(overrides))
    result = deepcopy(exact)
    if not any(payloads.values()):
        return result
    rooms = room_inputs(quote)
    by_id = {room['id']: room for room in rooms}
    catalogue, pricing = quote.snapshot['catalogue'], quote.snapshot['pricing']
    for (room_id, material_id), entries in sorted(payloads.items()):
        if room_id not in by_id or material_id not in catalogue:
            raise CalculationError('Dimensional Extra Material must belong to a current room and saved material.')
        if not isinstance(entries, list) or len(entries) > 50:
            raise CalculationError('Invalid dimensional Extra Material payload.')
        for index, entry in enumerate(entries):
            if entry.get('kind') != 'rectangular_strip':
                raise CalculationError('Unsupported dimensional Extra Material kind.')
            p = strip_payload(catalogue[material_id], entry.get('width_mm'), entry.get('length_mm'), entry.get('quantity'))
            if not p['quantity']:
                continue
            cuts = [dict(id=f'extra:{room_id}:{material_id}:{index}:{n}', material_id=material_id,
                         length_mm=p['length_mm'], width_mm=p['width_mm'], work_item_id=None,
                         label='Extra spare strip', role='Extra spare strip', allowance_mm=0,
                         is_dimensional_extra=True)
                    for n in range(p['quantity'])]
            by_id[room_id].setdefault('extra_groups', []).append(dict(
                material_id=material_id, width_mm=p['width_mm'], cuts=cuts))
    materials, stocks = pack_rooms(rooms, catalogue, pricing['kerf'],
        coving_kerf=pricing.get('coving_kerf', 10), sheet_trim=pricing.get('sheet_edge_trim', 10),
        sheet_kerf=pricing.get('sheet_kerf', 3))
    cost = money(sum(row['cost'] for row in materials))
    delta = money(cost - exact['stock_material_cost'])
    strips = prepared_strip_count(stocks)
    cut_cost = money(strips * pricing['cut_cost_per_strip'])
    cut_delta = money(cut_cost - exact['cut_cost'])
    counts = stock_counts(exact['room_stocks'])
    result.update(materials=materials, room_stocks=stocks, stock_material_cost=cost,
                  material_cost=money(exact['material_cost'] + delta + cut_delta), dimensional_extra_cost=delta,
                  total_prepared_strips=strips, strip_cut_rate=pricing['cut_cost_per_strip'], cut_cost=cut_cost,
                  exact_stock_counts=[dict(room_id=r, material_id=m, quantity=q)
                                      for (r, m), q in sorted(counts.items())])
    return result
