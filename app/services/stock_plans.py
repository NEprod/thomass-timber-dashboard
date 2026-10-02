"""Display-only adapters and SVGs for authoritative room stock assignments.

No packing is performed here. Kerf spacing is recovered from recorded losses,
and every sheet/strip/cut retains its original assignment and source ID.
"""
from collections import Counter
from html import escape
from ..calculations.preparation import stock_mode, prepared_strip_count


def _segments(cuts, kerf_loss, dimension='length_mm'):
    gap = kerf_loss / (len(cuts) - 1) if len(cuts) > 1 else 0
    position = 0
    segments, kerfs = [], []
    for index, cut in enumerate(cuts):
        if index:
            kerfs.append(dict(position_mm=position, size_mm=gap))
            position += gap
        segments.append(dict(source=cut, position_mm=position, size_mm=cut[dimension]))
        position += cut[dimension]
    return segments, kerfs


def prepare_stock_views(stocks, rooms=()):
    """Return ephemeral display data; never mutate saved results or room stock."""
    installed = {}
    for room in rooms:
        for item in room.items:
            for part in (item.result.get('geometry', {}).get('wall_layout') or {}).get('parts', []):
                # Joined Prepare pieces cannot inherit a whole-run Installed size.
                ids = part['cut_ids']
                if len(ids) == part['quantity'] and part['installed_length_mm'] is not None:
                    for cut_id in ids:
                        installed[cut_id] = part['installed_length_mm']
    def stock_key(stock):
        mode = stock_mode(stock)
        # Preserve the accepted Cabinet numbering across all nested materials.
        return (None if mode == 'sheet' else stock['material_id'], mode)

    totals = Counter(stock_key(s) for s in stocks)
    numbers, strip_numbers = Counter(), Counter()
    views = []
    for stock in stocks:
        mode = stock_mode(stock)
        key = stock_key(stock)
        numbers[key] += 1
        view = dict(source=stock, mode=mode, number=numbers[key], total=totals[key], strips=[],
                    prepared_strip_count=prepared_strip_count([stock]))
        if mode == 'sheet':
            views.append(view)
            continue
        view['segments'], view['kerfs'] = _segments(stock['cuts'], stock['kerf_loss_mm'])
        if mode == 'rip':
            for segment in view['segments']:
                rip = segment['source']
                strip_numbers[stock['material_id']] += 1
                number = strip_numbers[stock['material_id']]
                segment['number'] = number
                cuts = rip['finished_cuts']
                loss = round(rip['used_length_mm'] - sum(c['length_mm'] for c in cuts), 6)
                pieces, kerfs = _segments(cuts, loss)
                view['strips'].append(dict(number=number, segments=pieces, kerfs=kerfs,
                    stock_length_mm=stock['stock_length_mm'], width_mm=rip['width_mm'],
                    used_mm=rip['used_length_mm'], kerf_loss_mm=loss,
                    remainder_mm=round(stock['stock_length_mm'] - rip['used_length_mm'], 6)))
        else:
            view['stock_length_mm'] = stock['stock_length_mm']
            view['remainder_mm'] = stock['remainder_mm']
        for plan in view['strips'] or [view]:
            for segment in plan['segments']:
                segment['installed_length_mm'] = installed.get(segment['source']['id'])
                segment['installed_reference'] = 'Installed centreline' if segment['source'].get('requirement_status')=='EXACT' or stock['category']!='bead' else 'Installed opening-boundary path'
        views.append(view)
    return views


def _svg(title, width, height):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" class="stock-plan-svg" role="img" '
            f'aria-label="{escape(title, quote=True)}" viewBox="0 0 {width:g} {height:g}" '
            f'preserveAspectRatio="xMidYMid meet"><title>{escape(title)}</title>'
            '<desc>Green: required stock or cuts. Orange: kerf. Grey: theoretical remainder; confirm actual retained stock separately.</desc>']


def _rect(kind, x, y, width, height, label):
    fill = {'stock': '#e9e6dc', 'prepared': '#dbe6b7', 'cut': '#dbe6b7',
            'kerf': '#bd7524', 'remainder': '#eee9e3'}[kind]
    return (f'<rect data-kind="{kind}" x="{x:g}" y="{y:g}" width="{width:g}" height="{height:g}" '
            f'fill="{fill}" stroke="#4b513f" stroke-width=".6" vector-effect="non-scaling-stroke">'
            f'<title>{escape(label)}</title></rect>')


def render_sheet_rip_plan(view, material):
    stock = view['source']
    length, width = stock['stock_length_mm'], stock['stock_width_mm']
    title = f"Workshop Preparation — {material['label']} — Sheet {view['number']} of {view['total']}"
    out = _svg(title, length, width)
    out.append(_rect('stock', 0, 0, length, width, f'{length:g} × {width:g} mm raw sheet'))
    for segment in view['segments']:
        y, size, number = segment['position_mm'], segment['size_mm'], segment['number']
        label = f'Strip {number} — {size:g} × {length:g} mm'
        out.append(_rect('prepared', 0, y, length, size, label))
        if size >= length / 55:
            out.append(f'<text x="20" y="{y + size / 2:g}" dominant-baseline="middle" font-family="sans-serif" font-size="{length / 55:g}" fill="#253128">{escape(label)}</text>')
    for gap in view['kerfs']:
        out.append(_rect('kerf', 0, gap['position_mm'], length, gap['size_mm'], f"Rip kerf {gap['size_mm']:g} mm"))
    out.append(_rect('remainder', 0, stock['used_mm'], length, stock['remainder_mm'], f"Remainder {stock['remainder_mm']:g} × {length:g} mm"))
    if stock['remainder_mm'] >= 50:
        out.append(f'<text x="20" y="{stock["used_mm"] + stock["remainder_mm"] / 2:g}" dominant-baseline="middle" font-family="sans-serif" font-size="{length / 55:g}">Remainder {stock["remainder_mm"]:g} mm</text>')
    return ''.join(out) + '</svg>'


def render_linear_stock_plan(plan, title):
    length = plan['stock_length_mm']
    # Only longitudinal dimensions are represented by this schematic stock bar.
    bar_height, text_size = length / 20, length / 50
    out = _svg(title, length, bar_height * 1.8)
    out.append(_rect('stock', 0, 0, length, bar_height, f'{length:g} mm stock'))
    for index, segment in enumerate(plan['segments'], 1):
        x, size, cut = segment['position_mm'], segment['size_mm'], segment['source']
        term='Base cut' if cut.get('requirement_status')=='EXACT' else 'Site-fit Prepare' if cut.get('requirement_status')=='PROVISIONAL' else 'Prepare'
        out.append(_rect('cut', x, 0, size, bar_height, f"{cut.get('wall_name', '')} / {cut['label']} — {term} {size:g} mm"))
        if size > text_size * 3:
            out.append(f'<text x="{x + size / 2:g}" y="{bar_height / 2:g}" dominant-baseline="middle" text-anchor="middle" font-family="sans-serif" font-size="{text_size:g}">{index} · {size:g}</text>')
    for gap in plan['kerfs']:
        out.append(_rect('kerf', gap['position_mm'], 0, gap['size_mm'], bar_height, f"Kerf {gap['size_mm']:g} mm"))
    used = length - plan['remainder_mm']
    out.append(_rect('remainder', used, 0, plan['remainder_mm'], bar_height, f"Remainder {plan['remainder_mm']:g} mm"))
    out.append(f'<text x="0" y="{bar_height * 1.5:g}" font-family="sans-serif" font-size="{text_size:g}">{length:g} mm stock · remainder {plan["remainder_mm"]:g} mm</text>')
    return ''.join(out) + '</svg>'
