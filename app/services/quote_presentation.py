"""Read-only quote display adapters. Calculators and saved plans stay authoritative."""
from collections import defaultdict
import math
import re

from ..calculations.preparation import stock_mode
from ..calculations.pricing import money
from .spare_material import exact_plan
from .stock_plans import prepare_stock_views


def quote_presentation(quote):
    exact = exact_plan(quote)
    catalogue = quote.snapshot['catalogue']
    saved = quote.result.get('room_stocks', [])
    calculated = exact['room_stocks']
    requirements = {}
    workshop, cutting = [], []
    rate = quote.result.get('strip_cut_rate', quote.snapshot['pricing']['cut_cost_per_strip'])
    for room in quote.rooms:
        room_exact = [s for s in calculated if s['room_id'] == room.id]
        room_saved = [s for s in saved if s['room_id'] == room.id]
        # A stock unit can serve several walls; report that shared unit honestly.
        for item in room.items:
            rows = {}
            for stock in room_exact:
                mode = stock_mode(stock)
                units = stock['cuts'] if mode == 'rip' else [stock]
                for unit in units:
                    cuts = unit['finished_cuts'] if mode == 'rip' else stock['cuts']
                    owners = {str(c.get('work_item_id')) for c in cuts}
                    if str(item.id) not in owners:
                        continue
                    width = unit['width_mm'] if mode == 'rip' else stock['stock_width_mm']
                    key = (stock['material_id'], mode, width, stock['stock_length_mm'])
                    row = rows.setdefault(key, dict(material_id=stock['material_id'], mode=mode,
                        width_mm=width, length_mm=stock['stock_length_mm'], quantity=0, shared=False))
                    row['quantity'] += 1
                    row['shared'] |= len(owners) > 1
            requirements[item.id] = list(rows.values())
        views = prepare_stock_views(room_saved, quote.rooms)
        groups = defaultdict(list)
        for view in views:
            groups[(view['source']['material_id'], view['mode'])].append(view)
        for (material_id, mode), grouped in groups.items():
            product = catalogue[material_id]
            stocks = [v['source'] for v in grouped]
            base = [s for s in room_exact if s['material_id'] == material_id and stock_mode(s) == mode]
            if mode == 'rip':
                widths = sorted({r['width_mm'] for s in stocks for r in s['cuts']})
                rows = []
                for width in widths:
                    original = sum(r['width_mm'] == width for s in base for r in s['cuts'])
                    total = sum(r['width_mm'] == width for s in stocks for r in s['cuts'])
                    rows.append(dict(width_mm=width, length_mm=product['length_mm'], calculated=original,
                        extra=total-original, total=total, cut_charge=money(total*rate)))
                workshop.append(dict(room=room, material_id=material_id, mode=mode, views=grouped,
                    rows=rows, sheets=len(stocks), additional_sheets=len(stocks)-len(base), rate=rate))
                plans = [p for v in grouped for p in v['strips']]
                for plan in plans:
                    plan['total'] = len(plans)
                    plan['spare'] = all(s['source'].get('is_dimensional_extra') for s in plan['segments'])
                cutting.append(dict(room=room, material_id=material_id, category=product['category'],
                    mode=mode, plans=plans, extra_lengths=0))
            elif mode == 'sheet':
                workshop.append(dict(room=room, material_id=material_id, mode=mode, views=grouped,
                    operations=sum(v['sheet_cut_operations'] for v in grouped), rate=rate,
                    cut_charge=money(sum(v['sheet_cut_operations'] for v in grouped)*rate)))
            else:
                extra = sum(s.extra_quantity for s in quote.material_states
                            if s.room_id == room.id and s.material_id == material_id)
                cutting.append(dict(room=room, material_id=material_id, category=product['category'],
                    mode=mode, plans=grouped, extra_lengths=extra))
    return dict(requirements=requirements, workshop=workshop, cutting=cutting,
        deposit_paid=money(sum(p.amount for p in quote.payments if p.kind == 'Deposit')))


def opening_examples(layout):
    """Representative installed dimensions from canonical polygons, not form fields."""
    examples, seen = [], set()
    for element in layout.get('elements', []):
        if element['kind'] != 'opening':
            continue
        identity = element['label'].split(' · ')[0]
        family = element['label'].split(' · ')[-1] if ' · ' in element['label'] else 'Standard'
        if family != 'Transition' and family in seen:
            continue
        seen.add(family)
        points = element['points']
        # Polygon winding follows the lower boundary left→right, the right
        # vertical, then the upper boundary right→left. Transition bends can
        # contribute unequal vertex counts to the two boundary chains.
        right_x = max(x for x, _ in points)
        right_indices = [i for i, (x, _) in enumerate(points) if x == right_x]
        lower_end, upper_start = right_indices[0], right_indices[-1]
        lower, upper = points[:lower_end+1], points[upper_start:]
        examples.append(dict(id=identity, family=family,
            width=right_x-min(x for x, _ in points), left=math.dist(points[0],points[-1]),
            right=math.dist(points[lower_end],points[upper_start]),
            upper=[math.dist(a,b) for a,b in zip(upper,upper[1:])],
            lower=[math.dist(a,b) for a,b in zip(lower,lower[1:])]))
    # Straight Dado frame identities originate in its canonical frame labels.
    if not examples:
        for element in layout.get('elements', []):
            if element['kind']=='frame' and re.fullmatch(r'Bottom square \d+', element['label']):
                xs,ys=zip(*element['points'])
                examples.append(dict(id=element['label'], family='Frame outside', width=max(xs)-min(xs),
                    left=max(ys)-min(ys),right=max(ys)-min(ys),upper=[max(xs)-min(xs)],lower=[max(xs)-min(xs)]))
                break
    return examples


def cut_display_label(cut):
    info = cut.get('angle_information') or {}
    if info.get('square') is not None:
        label = f"Square {info['square']}"
        if info.get('row') is not None: label += f".{info['row']}"
        if 'transition' in cut.get('role','').lower(): label = 'Transition ' + label
        label += ' · ' + info.get('edge', cut.get('role',cut['label']))
        if 'transition' in cut.get('role','').lower() and info.get('profile_segment') is not None: label += f" segment {info['profile_segment']}"
        return label
    return cut['label']
