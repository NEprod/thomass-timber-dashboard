"""Installation primitives emitted by calculators, never inferred by the SVG UI.

Coordinates are millimetres, x rightwards and y upwards from the low-end floor
reference. Stair transitions are reference regions, not finished polygons.
"""
import math


def _plan(width, height, summary, *, stair=False):
    return dict(width_mm=width, height_mm=height, stair=stair, elements=[],
                dimensions=[], summary=summary, notes=[])


def _shape(plan, kind, label, points, *, provisional=False):
    plan['elements'].append(dict(kind=kind, label=label, points=points,
                                 provisional=provisional))


def _rect(plan, kind, label, x, y, width, height):
    _shape(plan, kind, label, [[x, y], [x + width, y],
                             [x + width, y + height], [x, y + height]])


def _dimension(plan, start, end, label, axis='horizontal'):
    plan['dimensions'].append(dict(start=start, end=end, label=label, axis=axis))


def panelling_layout(kind, width, height, columns, rows, slat, geometry, *,
                     bead=False, lower=0, upper=0, slope=0):
    sw, sh = geometry['square_width'], geometry['square_height']
    stair = kind == 'PANELLING_STAIR_HALF'
    rise = math.sqrt(max(0, slope * slope - geometry['horizontal_run'] ** 2)) if stair else 0
    cosine = geometry['horizontal_run'] / slope if stair else 1
    extent = rise + height / cosine if stair else height
    plan = _plan(width, extent, [f'Wall width {width:g} mm', f'Panelling height {height:g} mm',
        f'{columns} × {rows} openings', f'Stile / rail {slat:g} mm',
        f'Left / right edge members {slat:g} mm'], stair=stair)
    if not stair:
        _rect(plan, 'wall', 'Calculated wall / panelling bounds', 0, 0, width, height)
        full = kind == 'PANELLING_FULL'
        for index in range(columns + 1):
            _rect(plan, 'mdf', f'Vertical {index + 1}', index * (sw + slat),
                  0 if full else slat, slat, height if full else height - 2 * slat)
        if full:
            for column in range(columns):
                for row in range(rows + 1):
                    _rect(plan, 'mdf', f'Horizontal {column + 1}.{row + 1}',
                          slat + column * (sw + slat), row * (sh + slat), sw, slat)
        else:
            for label, y in [('Bottom rail', 0), ('Top rail', height - slat)]:
                _rect(plan, 'mdf', label, 0, y, width, slat)
            for column in range(columns):
                for row in range(1, rows):
                    _rect(plan, 'mdf', f'Middle horizontal {column + 1}.{row}',
                          slat + column * (sw + slat), row * (sh + slat), sw, slat)
        for column in range(columns):
            for row in range(rows):
                x, y = slat + column * (sw + slat), slat + row * (sh + slat)
                _rect(plan, 'opening', f'Opening {column + 1}.{row + 1}', x, y, sw, sh)
                if bead:
                    _rect(plan, 'bead', f'Bead opening {column + 1}.{row + 1}', x, y, sw, sh)
        _dimension(plan, [0, 0], [width, 0], f'Wall {width:g} mm')
        _dimension(plan, [0, 0], [0, height], f'Panelling {height:g} mm', 'vertical')
        _dimension(plan, [slat, height], [slat + sw, height], f'Opening {sw:g} mm')
        plan['summary'].append(f'Opening {sw:g} × {sh:g} mm')
        return plan

    run = geometry['horizontal_run']
    def floor(x):
        return rise * min(1, max(0, (x - lower) / run))

    def polygon(x, y, span, tall, scale=1):
        xs = sorted({x, x + span, *(p for p in (lower, width - upper) if x < p < x + span)})
        return ([[p, floor(p) + y * scale] for p in xs] +
                [[p, floor(p) + (y + tall) * scale] for p in reversed(xs)])

    # Exact flat/angled regions use their recovered sizes. Transition references
    # use the nominal grid solely to locate the site-trim region, never the
    # conservative bead-cut allowances as an installation polygon.
    _shape(plan, 'wall', 'Measured lower landing / slope / upper landing',
           [[0, 0], [lower, 0], [width - upper, rise], [width, rise]], provisional=False)
    for index, column in enumerate(geometry['columns']):
        x = slat + index * (sw + slat)
        typ = column['type']
        scale = 1 if typ == 'flat' else 1 / cosine
        for row in range(rows):
            provisional = typ == 'transition'
            label = 'Trim to fit on site' if provisional else f'{typ.capitalize()} opening {index + 1}.{row + 1}'
            points = polygon(x, slat + row * (sh + slat), sw, sh, scale)
            _shape(plan, 'opening', label, points, provisional=provisional)
            if bead:
                _shape(plan, 'bead', 'Bead · ' + label, points, provisional=provisional)
        angled = typ == 'angled' or (typ == 'transition' and
                  (index == 0 or geometry['columns'][index - 1]['type'] == 'flat'))
        member_scale = 1 / cosine if angled else 1
        _shape(plan, 'mdf', f'Vertical {index + 2}',
               polygon(x + sw, slat, slat, height - 2 * slat, member_scale),
               provisional=typ == 'transition')
        for row in range(1, rows):
            _shape(plan, 'mdf', f'Middle horizontal {index + 1}.{row}',
                   polygon(x, row * (sh + slat), sw, slat, scale),
                   provisional=typ == 'transition')
    _shape(plan, 'mdf', 'Vertical 1', polygon(0, slat, slat, height - 2 * slat))
    transitions = [(slat + i * (sw + slat), slat + i * (sw + slat) + sw)
                   for i, c in enumerate(geometry['columns']) if c['type'] == 'transition']
    # Split rails at known bends and transition boundaries. Unknown connections
    # remain dashed; stock-cut +30/-30 allowances never move wall positions.
    breaks = sorted({0, lower, width - upper, width, *(p for pair in transitions for p in pair)})
    for start, end in zip(breaks, breaks[1:]):
        if end <= start:
            continue
        middle = (start + end) / 2
        scale = 1 / cosine if lower < middle < width - upper else 1
        provisional = any(a <= middle <= b for a, b in transitions)
        for label, y in [('Bottom rail', 0), ('Top rail', height - slat)]:
            _shape(plan, 'mdf', label, polygon(start, y, end - start, slat, scale),
                   provisional=provisional)
    _dimension(plan, [0, 0], [width, 0], f'Wall {width:g} mm')
    _dimension(plan, [0, extent], [lower, extent], f'{lower:g} mm')
    _dimension(plan, [lower, extent], [width - upper, extent], f'{run:g} mm')
    _dimension(plan, [width - upper, extent], [width, extent], f'{upper:g} mm')
    plan['summary'] += [f'Measured slope {slope:g} mm · angle {geometry["slope_angle"]:g}°',
                        f'Lower landing {lower:g} mm · horizontal run {run:g} mm · upper landing {upper:g} mm',
                        f'Flat reference opening {sw:g} × {sh:g} mm',
                        f'Angled opening {geometry["angled_square_width"]:g} × {geometry["angled_square_height"]:g} mm']
    if transitions:
        plan['notes'].append('Solid = calculated finished geometry. Dashed = trim to fit on site. Transition shapes have no finished dimensions; confirm the opening and rail connections on site.')
    plan['notes'].append('Landing positions use measured geometry; workshop cutting allowances and displayed saw settings remain unchanged.')
    return plan


def dado_layout(width, height, geometry, rail_width, *, frames=None, gap=0,
                stair=False, lower=0, upper=0, slope=0, square_profile_width=0):
    """Height is plain rail centreline, or the existing square clear-zone top."""
    if height is None:
        return None
    rise = math.sqrt(max(0, slope * slope - geometry['horizontal_run'] ** 2)) if stair else 0
    extent = height + rise + rail_width / 2
    plan = _plan(width, extent, [f'Wall / run {width:g} mm',
                 f'{"Clear zone below rail" if frames is not None else "Finished floor to dado centreline"} {height:g} mm'], stair=stair)
    route = [[0, 0], [lower, 0], [width - upper, rise], [width, rise]] if stair else [[0, 0], [width, 0]]
    _shape(plan, 'wall', 'Finished floor / measured route reference', route)
    _shape(plan, 'dado', 'Dado reference line' if frames is not None else 'Dado centreline',
           [[x, y + height] for x, y in route])
    if not stair:
        for index, frame in enumerate(frames or []):
            x = gap + index * (frame['width_mm'] + gap)
            _rect(plan, 'frame', f'Bottom square {index + 1}', x, gap, frame['width_mm'], frame['height_mm'])
        if frames:
            plan['summary'] += [f'{len(frames)} bottom squares · gap {gap:g} mm',
                f'Frame outside {frames[0]["width_mm"]:g} × {frames[0]["height_mm"]:g} mm',
                f'Square moulding {square_profile_width:g} mm']
    else:
        run = geometry['horizontal_run']
        _dimension(plan, [0, extent], [lower, extent], f'{lower:g} mm')
        _dimension(plan, [lower, extent], [width - upper, extent], f'{run:g} mm')
        _dimension(plan, [width - upper, extent], [width, extent], f'{upper:g} mm')
        plan['summary'] += [f'Measured slope {slope:g} mm · angle {geometry["slope_angle"]:g}°',
                           f'Lower landing {lower:g} mm · horizontal run {run:g} mm · upper landing {upper:g} mm']
        if frames is not None:
            # Reuse the existing stair-grid geometry exposure; there is no second
            # stair-opening formula or finished transition allowance conversion.
            grid = panelling_layout('PANELLING_STAIR_HALF', width, height,
                len(geometry['columns']), 1, gap, geometry, lower=lower, upper=upper, slope=slope)
            plan['height_mm'] = max(extent, grid['height_mm'])
            plan['elements'] += [dict(e, kind='frame') for e in grid['elements'] if e['kind'] == 'opening']
            plan['notes'] += grid['notes']
    _dimension(plan, [0, 0], [width, 0], f'Wall {width:g} mm')
    _dimension(plan, [0, 0], [0, height],
               f'{"Clear zone" if frames is not None else "Centreline"} {height:g} mm', 'vertical')
    return plan
