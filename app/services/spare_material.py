"""Deterministic advisory spares; acceptance reuses room-owned Extra Material.

Central defaults are deliberately small. No percentage contingency and no
runtime model/API. All previews call the accepted dimensional-demand adapter.
"""
from collections import defaultdict
from hashlib import sha256

from ..calculations.pricing import aggregate, money
from .dimensional_extras import (room_inputs, with_dimensional_extras, extra_payloads,
                                strip_quantity, stock_counts)
from .room_procurement import family, compatible

STRAIGHT_STRIPS = 1
STAIR_STRIPS = 2
COMPLEX_LINEAR_LENGTHS = 1
TIGHT_LENGTH_RATIO = .9


def exact_plan(quote):
    rooms = room_inputs(quote)
    return aggregate([item['result'] for room in rooms for item in room['items']],
                     quote.snapshot['catalogue'], quote.snapshot['pricing'],
                     quote.full_days, quote.extra_hours, rooms=rooms)


def _identity(room_id, material_id, width):
    return sha256(f'{room_id}:{material_id}:{width}'.encode()).hexdigest()[:20]


def _signals(cuts, items):
    owners = {str(c.get('work_item_id')) for c in cuts if c.get('work_item_id') is not None}
    sources = [item for item in items if str(item.id) in owners and item.result.get('valid')]
    stair = any(item.type in ('PANELLING_STAIR_HALF', 'DADO_STAIR') for item in sources)
    transitions = any(item.result.get('geometry', {}).get('counts', {}).get('transition', 0) for item in sources)
    mitred = sum(any((cut.get('angle_information') or {}).get(key) for key in
                     ('start_joint_setting', 'end_joint_setting', 'slope_mitre')) for cut in cuts)
    site_fit = any(c.get('requirement_status') == 'PROVISIONAL' for c in cuts)
    joined = any(c.get('join_id') for c in cuts)
    external = any(item.type == 'COVING' and item.result.get('geometry', {}).get('external_allowance_mm', 0)
                   for item in sources)
    reasons = []
    if stair: reasons.append('Stair work with sloped and mitred members')
    if transitions: reasons.append('Transition work has multiple exact mitred cuts')
    if mitred > 1: reasons.append('Multiple mitred pieces')
    if site_fit: reasons.append('Valid site-fit components need fitting tolerance')
    if joined: reasons.append('Joined members use multiple prepared pieces')
    if external: reasons.append('External Coving corners require mitred cuts')
    return stair, bool(reasons), reasons


def recommendations(quote):
    """No writes, and no mutation of saved cuts, snapshots or totals."""
    catalogue, pricing = quote.snapshot['catalogue'], quote.snapshot['pricing']
    exact = exact_plan(quote)
    current = with_dimensional_extras(quote, exact)
    current_counts = stock_counts(current['room_stocks'])
    items = []
    for room in quote.rooms:
        stocks = [s for s in exact['room_stocks'] if s['room_id'] == room.id]
        rip_groups, linear_groups = defaultdict(list), defaultdict(list)
        for stock in stocks:
            if stock['category'] == 'mdf':
                if stock.get('packing_kind') != 'sheet':
                    for rip in stock['cuts']:
                        rip_groups[(stock['material_id'], rip['width_mm'])].append((stock, rip))
                # Cabinet sheets have no default spare: a Cabinet alone is not risk evidence.
            else:
                linear_groups[family(catalogue, stock['material_id'])].append(stock)
        for (material_id, width), prepared in sorted(rip_groups.items()):
            product = catalogue[material_id]
            cuts = [cut for _, rip in prepared for cut in rip['finished_cuts']]
            critical = max(cut['length_mm'] for cut in cuts)
            stair, complex_work, reasons = _signals(cuts, room.items)
            recovery = any(stock['remainder_mm'] >= width + pricing['kerf'] or
                           product['length_mm'] - rip['used_length_mm'] >= critical + pricing['kerf']
                           for stock, rip in prepared)
            target = STAIR_STRIPS if stair else STRAIGHT_STRIPS if not recovery else 0
            accepted = strip_quantity(quote, room.id, material_id, width)
            # Explicit whole sheets already provide reserve strip capacity too.
            whole = sum(state.extra_quantity for state in quote.material_states
                        if state.room_id == room.id and state.material_id == material_id)
            accepted += whole * int((product['width_mm'] + pricing['kerf']) / (width + pricing['kerf']))
            remaining = max(0, target - accepted)
            if not remaining: continue
            reasons.append('Current sheet/remainders can provide recovery material' if recovery else
                           'Current remainders cannot reproduce the longest critical piece')
            if not complex_work: reasons.insert(0, 'Straight strip work with limited recovery capacity')
            previews = []
            payloads = extra_payloads(quote).get((room.id, material_id), [])
            for quantity in range(1, remaining + 1):
                proposed = payloads + [dict(kind='rectangular_strip', width_mm=width,
                    length_mm=product['length_mm'], quantity=quantity)]
                simulated = with_dimensional_extras(quote, exact, {(room.id, material_id): proposed})
                count = stock_counts(simulated['room_stocks'])[(room.id, material_id)]
                previews.append(dict(quantity=quantity, stock_count=count,
                    additional_stock=count-current_counts[(room.id, material_id)],
                    incremental_cost=money(simulated['stock_material_cost']-current['stock_material_cost']),
                    used_widths=[s['used_mm'] for s in simulated['room_stocks']
                                 if s['room_id']==room.id and s['material_id']==material_id and s.get('packing_kind')!='sheet'],
                    remainders=[s['remainder_mm'] for s in simulated['room_stocks']
                                if s['room_id']==room.id and s['material_id']==material_id and s.get('packing_kind')!='sheet']))
            items.append(dict(id=_identity(room.id, material_id, width), room_id=room.id, room_name=room.name,
                material_id=material_id, label=product['label'], kind='rectangular_strip', width_mm=width,
                length_mm=product['length_mm'], quantity=remaining, accepted_quantity=accepted,
                priority='MEDIUM' if recovery else 'HIGH', reasons=reasons,
                current_requirement=len(prepared), current_stock_count=current_counts[(room.id, material_id)],
                critical_length_mm=critical, previews=previews))
        for _, packed in sorted(linear_groups.items(), key=lambda pair: str(pair[0])):
            cuts = [cut for stock in packed for cut in stock['cuts']]
            critical = max(c['length_mm'] for c in cuts)
            # Recommend a currently used purchasable SKU that can remake the critical cut.
            stock = min((s for s in packed if s['stock_length_mm'] >= critical),
                        key=lambda s: (s['stock_length_mm'], catalogue[s['material_id']]['price'], s['material_id']))
            product = catalogue[stock['material_id']]
            recovery = any(s['remainder_mm'] >= critical for s in packed)
            _, complex_work, reasons = _signals(cuts, room.items)
            tight = critical >= stock['stock_length_mm'] * TIGHT_LENGTH_RATIO
            if not complex_work and (recovery or not tight) and not (product['category']=='pse' and not recovery):
                continue
            accepted = sum(state.extra_quantity for state in quote.material_states
                if state.room_id==room.id and compatible(catalogue, state.material_id, product['id'])
                and catalogue[state.material_id]['length_mm']>=critical)
            quantity = max(0, COMPLEX_LINEAR_LENGTHS-accepted)
            if not quantity: continue
            reasons.append('Existing remainder can reproduce the critical piece' if recovery else
                           'Current remainders cannot reproduce the longest critical piece')
            if tight: reasons.append(f'Longest critical cut uses {critical / stock["stock_length_mm"]:.0%} of stock length')
            if product['category']=='pse': reasons.append('PSE worktop stock has limited recovery capacity')
            items.append(dict(id=_identity(room.id, product['id'], None), room_id=room.id, room_name=room.name,
                material_id=product['id'], label=product['label'], kind='stock_length', width_mm=product['width_mm'],
                length_mm=product['length_mm'], quantity=quantity, accepted_quantity=accepted,
                priority='LOW' if recovery else 'HIGH' if tight else 'MEDIUM', reasons=reasons,
                current_requirement=len(cuts), current_stock_count=current_counts[(room.id, product['id'])],
                critical_length_mm=critical, previews=[dict(quantity=quantity,
                    stock_count=current_counts[(room.id, product['id'])]+accepted+quantity,
                    additional_stock=quantity, incremental_cost=money(quantity*product['price']))]))
    return items
