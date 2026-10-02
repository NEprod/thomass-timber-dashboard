"""Installation primitives emitted by calculators, never inferred by the SVG UI.

Coordinates are millimetres, x rightwards and y upwards from the low-end floor
reference. Opening/rail outlines are exact; unmodelled profile transitions remain site-fit.
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
                     bead=False, lower=0, upper=0, slope=0, groups=None):
    sw, sh = geometry['square_width'], geometry['square_height']
    stair = kind == 'PANELLING_STAIR_HALF'
    rise = math.sqrt(max(0, slope * slope - geometry['horizontal_run'] ** 2)) if stair else 0
    extent = rise + height if stair else height
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

    return _stair_panelling_plan(plan, width, height, columns, rows, slat,
                                geometry, lower, upper, slope, rise, bead, groups)


def _offset_stair_route(width, lower, upper, rise, run, offset, *, clip=True):
    """Parallel inner edge, with adjacent straight lines meeting at their mitre.

    Offset is real material width perpendicular to each route segment. The
    outside routes stay at the entered vertical envelope; no prepare sizes enter
    this construction.
    """
    gradient = rise / run
    lines = []
    if lower:
        lines.append((0, offset))
    lines.append((gradient, -gradient * lower + offset * math.hypot(1, gradient)))
    if upper:
        lines.append((0, rise + offset))
    knots = [(b2 - b1) / (m1 - m2) for (m1, b1), (m2, b2) in zip(lines, lines[1:])
             if not math.isclose(m1, m2)]
    if not knots:
        return [[0, lines[0][1]], [width, lines[0][0] * width + lines[0][1]]]
    if not clip:
        return ([[0, lines[0][1]]] +
                [[x, lines[i][0] * x + lines[i][1]] for i, x in enumerate(knots)] +
                [[width, lines[-1][0] * width + lines[-1][1]]])
    points = []
    for i, (m, b) in enumerate(lines):
        start = max(0, knots[i - 1] if i else 0)
        end = min(width, knots[i] if i < len(knots) else width)
        if end >= start:
            for x in (start, end):
                p = [x, m * x + b]
                if not points or p != points[-1]:
                    points.append(p)
    return points


def _route_y(route, x):
    for (a, ya), (b, yb) in zip(route, route[1:]):
        if a <= x <= b and b > a:
            return ya + (yb - ya) * (x - a) / (b - a)
    return route[0][1] if x <= route[0][0] else route[-1][1]


def _between_routes(bottom, top, start, end):
    xs = sorted({start, end, *(x for route in (bottom, top) for x, _ in route if start < x < end)})
    return ([[x, _route_y(bottom, x)] for x in xs] +
            [[x, _route_y(top, x)] for x in reversed(xs)])


def _clip_rail_to_wall(points, width):
    """Clip a mitred polygon at wall ends, including very short landings."""
    for bound, sign in ((0, 1), (width, -1)):
        output = []
        for a, b in zip(points, points[1:] + points[:1]):
            inside_a, inside_b = sign * (a[0] - bound) >= 0, sign * (b[0] - bound) >= 0
            if inside_a:
                output.append(a)
            if inside_a != inside_b:
                fraction = (bound - a[0]) / (b[0] - a[0])
                output.append([bound, a[1] + fraction * (b[1] - a[1])])
        points = output
    return points


def _mitred_rail_sections(width, lower, upper, rise, run, bottom_offset, top_offset, base):
    """Pair existing parallel-route vertices: adjacent rails share one seam.

    Keep the uncut bend intersections until polygons are clipped at wall ends;
    cutting both edges at one x would replace the mitre with a vertical butt.
    """
    bottom, top = ([[x, y + base] for x, y in _offset_stair_route(
        width, lower, upper, rise, run, offset, clip=False)]
        for offset in (bottom_offset, top_offset))
    names = (['Lower landing'] if lower else []) + ['Slope'] + (['Upper landing'] if upper else [])
    # With a level measured route there is no change of direction to mitre.
    if math.isclose(rise, 0):
        return {name: _between_routes(bottom, top, start, end)
                for name, start, end in [('Lower landing', 0, lower),
                    ('Slope', lower, width - upper), ('Upper landing', width - upper, width)] if end > start}
    return {name: _clip_rail_to_wall([bottom[i], bottom[i + 1], top[i + 1], top[i]], width)
            for i, name in enumerate(names)}


def _prepare_runs(groups, group):
    """Read existing demands, combining only cuts belonging to the same join."""
    runs = {}
    for cut in (groups or {}).get(group, {}).get('cuts', []):
        key = cut.get('join_id') or cut['id']
        run = runs.setdefault(key, dict(label=cut['role'], length_mm=0, cut_ids=[],
                                       angle_information=cut.get('angle_information') or {}))
        run['length_mm'] += cut['length_mm'] * cut.get('quantity', 1)
        run['cut_ids'].append(cut['id'])
    return list(runs.values())


def stair_profile_members(width, lower, upper, slope, run, profile_width):
    """Physical centred profile sections on the same measured/mitred route."""
    rise = math.sqrt(max(0, slope * slope - run * run))
    return _mitred_rail_sections(width, lower, upper, rise, run,
                                -profile_width / 2, profile_width / 2, 0)


def _group_wall_parts(parts):
    grouped = {}
    for part in parts:
        key = (part['component'], part['installed_length_mm'], part['prepare_length_mm'],
               tuple((part.get('installed_dimensions') or {}).items()),
               tuple((part.get('prepare_dimensions') or {}).items()),
               part['provisional'], tuple(part['notes']))
        if key not in grouped:
            grouped[key] = dict(part, labels=[part['label']], quantity=1,
                                cut_links={part['label']:list(part['cut_ids'])})
        else:
            grouped[key]['quantity'] += 1
            grouped[key]['labels'].append(part['label'])
            grouped[key]['cut_ids'] += part['cut_ids']
            grouped[key]['cut_links'][part['label']] = list(part['cut_ids'])
    return list(grouped.values())


def _stair_panelling_plan(plan, width, height, columns, rows, slat, geometry,
                          lower, upper, slope, rise, bead, groups):
    run = geometry['horizontal_run']
    sw = geometry['square_width']
    cosine = run / slope
    route = [[0, 0], [lower, 0], [width - upper, rise], [width, rise]]
    outer_top = [[x, y + height] for x, y in route]
    plan.update(installed_panel_height_mm=height, parts=[],profile_members=geometry.get('dado_profiles',{}),
                opening_profile_members=geometry.get('opening_profiles',[]),
                boundaries=dict(bottom_outer=route, top_outer=outer_top))
    _shape(plan, 'wall', 'Measured lower landing / slope / upper landing', route)

    # Each rail is 100mm (or the configured width) perpendicular to its run.
    # Intermediate rails divide the remaining installed openings evenly. The
    # offset-line intersections give continuous inner edges at landing bends.
    rails = []
    for index in range(rows + 1):
        base = height * index / rows
        bottom = [[x, y + base] for x, y in _offset_stair_route(width, lower, upper, rise, run, -slat * index / rows)]
        top = [[x, y + base] for x, y in _offset_stair_route(width, lower, upper, rise, run, slat * (1 - index / rows))]
        rails.append((bottom, top))
    plan['boundaries'].update(bottom_inner=rails[0][1], top_inner=rails[-1][0])
    parts = []

    def part(label, component, installed=None, prepare=None, *, provisional=False,
             installed_dimensions=None, prepare_dimensions=None, cut_ids=None, notes=None):
        parts.append(dict(label=label, component=component, installed_length_mm=installed,
            prepare_length_mm=prepare, installed_dimensions=installed_dimensions,
            prepare_dimensions=prepare_dimensions, quantity=1, provisional=provisional,
            trim_to_fit=provisional or (installed is not None and prepare is not None and not math.isclose(installed, prepare, abs_tol=.01)),
            cut_ids=list(cut_ids or []), notes=list(notes or [])))

    # All opening/batten vertices intersect the installed rail boundaries.
    bends = {lower, width - upper}
    bends.update(x for pair in rails for edge in pair for x, _ in edge[1:-1])
    def crosses_bend(start, end):
        return any(start < x < end for x in bends if 0 < x < width)

    for index, column in enumerate(geometry['columns']):
        start = slat + index * (sw + slat)
        typ = column['type']
        for row in range(rows):
            bottom, top = rails[row][1], rails[row + 1][0]
            profile_provisional = typ == 'transition' or crosses_bend(start, start + sw)
            provisional = False  # All opening vertices intersect exact inner rail boundaries.
            label = f'Opening {index + 1}.{row + 1} · {typ.capitalize()}'
            points = _between_routes(bottom, top, start, start + sw)
            _shape(plan, 'opening', label, points, provisional=provisional)
            plan['elements'][-1]['profile_provisional'] = profile_provisional
            if bead and not geometry.get('opening_profiles'):
                _shape(plan, 'bead', 'Bead · ' + label + (' · Trim to fit on site' if profile_provisional else ''),
                       points, provisional=profile_provisional)
            installed_height = _route_y(top, start + sw / 2) - _route_y(bottom, start + sw / 2)
            installed = None if provisional else dict(width_mm=sw, height_mm=round(installed_height, 2))
            part(f'Opening {index + 1}.{row + 1}', 'Panel opening', provisional=provisional,
                 installed_dimensions=installed,
                 notes=['Horizontal span × centre-sampled clear height; exact side/edge dimensions come from the polygon vertices.'])

    vertical_cuts = (groups or {}).get('vertical', {}).get('cuts', [])
    for index in range(columns + 1):
        start = index * (sw + slat)
        bottom, top = rails[0][1], rails[-1][0]
        provisional = False  # MDF endpoints, including bends, are deterministic intersections.
        _shape(plan, 'mdf', f'Vertical batten {index + 1}',
               _between_routes(bottom, top, start, start + slat), provisional=provisional)
        mid = start + slat / 2
        installed = _route_y(top, mid) - _route_y(bottom, mid)
        cut = vertical_cuts[index] if index < len(vertical_cuts) else None
        part(f'Vertical batten {index + 1}', 'Vertical batten',
             None if provisional else round(installed, 2), cut['length_mm'] if cut else None,
             provisional=provisional, cut_ids=[cut['id']] if cut else [],
             notes=['Installed length is the vertical intersection span between inner rail edges; prepare retains workshop tolerance.'])

    rail_runs = _prepare_runs(groups, 'top_and_bottom_horizontal')
    role_names = [('Lower landing', 0, lower), ('Slope', lower, width - upper),
                  ('Upper landing', width - upper, width)]
    for index, (bottom, top) in enumerate(rails):
        name = 'Bottom' if index == 0 else 'Top' if index == rows else f'Middle {index}'
        sections = _mitred_rail_sections(width, lower, upper, rise, run,
            -slat * index / rows, slat * (1 - index / rows), height * index / rows)
        for section, start, end in role_names:
            if end <= start:
                continue
            _shape(plan, 'mdf', f'{name} rail · {section}', sections[section])
            if index not in (0, rows):
                continue
            role = 'Slope' if section == 'Slope' else f'{name} ({section.title()})'
            matches = [p for p in rail_runs if p['label'] == role]
            if section == 'Slope' and len(matches) > 1:
                matches = [matches[0 if name == 'Top' else 1]]
            prepare = matches[0]['length_mm'] if matches else None
            cut_ids = matches[0]['cut_ids'] if matches else []
            installed = slope if section == 'Slope' else end - start
            part(f'{name} rail · {section}', 'Rail', installed, prepare, cut_ids=cut_ids,
                 notes=['Installed run follows the outside rail edge. Prepare retains existing landing adjustments and joins.'])

    # Intermediate cuts belong to individual columns, unlike the continuous
    # visual rail. Clip the same boundaries to those real member endpoints.
    plan['cut_members'] = []
    for index, prepared in enumerate(_prepare_runs(groups, 'middle_horizontal')):
        column_index = index // max(1, rows - 1)
        rail_index = index % max(1, rows - 1) + 1
        column = geometry['columns'][column_index]
        provisional = column['type'] == 'transition'
        installed = sw if column['type'] == 'flat' else sw / cosine
        start=slat + column_index * (sw + slat)
        bottom,top=rails[rail_index]
        vertices=_between_routes(bottom,top,start,start+sw)
        crossing=crosses_bend(start,start+sw)
        axis=(1,0) if column['type']=='flat' else (run/slope,rise/slope)
        plan['cut_members'].append(dict(label=f'Middle rail {column_index+1}.{rail_index}',vertices=vertices,axis=axis,
            cut_ids=prepared['cut_ids'],prepare_length_mm=prepared['length_mm'],
            cut_status='PROVISIONAL' if crossing else 'EXACT',
            reason='Intermediate rail crosses a bend; separate physical member/joint endpoints are not modelled.' if crossing else None))
        part(prepared['label'], 'Middle rail', None if provisional else round(installed, 2),
             prepared['length_mm'], provisional=provisional, cut_ids=prepared['cut_ids'])

    # Existing bead cutting dimensions stay separate from the installed opening.
    for prepared in _prepare_runs(groups, 'stair_opening_beads'):
        physical=next((p for p in plan['opening_profile_members'] if p['label']==prepared['label']),None)
        if physical:
            _shape(plan,'bead',physical['label'],physical['vertices'])
            part(prepared['label'],'Bead / moulding',physical['measurements']['member']['centreline_mm'],
                physical['base_cut_length_mm'],cut_ids=prepared['cut_ids'],
                notes=['Exact installed profile, mitred at shared offset intersections.'])
            continue
        info = prepared['angle_information']
        opening = next((p for p in parts if p['label'] == f'Opening {info.get("square")}.{info.get("row")}'), None)
        profile_site_fit = next((e.get('profile_provisional', False) for e in plan['elements']
            if e['kind'] == 'opening' and e['label'].startswith(f'Opening {info.get("square")}.{info.get("row")} · ')), True)
        provisional = not opening or profile_site_fit or bool(info.get('stock_allowance'))
        installed = None
        edge = info.get('edge', '')
        if not provisional:
            dims = opening['installed_dimensions']
            if 'vertical' in edge:
                installed = dims['height_mm']
            else:
                angled = geometry['columns'][info['square'] - 1]['type'] == 'angled'
                installed = round(dims['width_mm'] / (cosine if angled else 1), 2)
        part(prepared['label'], 'Bead vertical' if 'vertical' in edge else 'Bead horizontal',
             installed, prepared['length_mm'], provisional=provisional,
             cut_ids=prepared['cut_ids'], notes=['Existing bead preparation; fit to the installed opening on site.'])

    plan['parts'] = _group_wall_parts(parts)
    _dimension(plan, [0, 0], [width, 0], f'Wall {width:g} mm')
    _dimension(plan, [0, 0], [0, height], f'Installed height {height:g} mm', 'vertical')
    extent = plan['height_mm']
    for start, end in [(0, lower), (lower, width - upper), (width - upper, width)]:
        if end > start:
            _dimension(plan, [start, extent], [end, extent], f'{end-start:g} mm')
    plan['summary'] += [f'Measured slope {slope:g} mm · angle {geometry["slope_angle"]:g}°',
        f'Lower landing {lower:g} mm · horizontal run {run:g} mm · upper landing {upper:g} mm',
        f'Opening horizontal spacing {sw:g} mm; installed sides/edges shown below']
    plan['notes'] += ['Panel height is the installed vertical outside-to-outside height. Rail width is measured perpendicular to each run.',
        'Solid members use installed intersections. Only unmodelled components remain site-fit.',
        'Exact physical members use long-point Base cuts. Only unmodelled components remain site-fit; no spare material is added.']
    from .installed_geometry import annotate_installed_geometry
    annotate_installed_geometry(plan, groups or {})
    return plan

def dado_layout(width, height, geometry, rail_width, *, frames=None, gap=0,
                stair=False, lower=0, upper=0, slope=0, square_profile_width=0, groups=None):
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
            plan['elements'] += [dict(e, kind='frame', provisional=e['profile_provisional'],
                label='Trim to fit on site' if e['profile_provisional'] else e['label'])
                for e in grid['elements'] if e['kind'] == 'opening']
            plan['notes'] += grid['notes']
    _dimension(plan, [0, 0], [width, 0], f'Wall {width:g} mm')
    _dimension(plan, [0, 0], [0, height],
               f'{"Clear zone" if frames is not None else "Centreline"} {height:g} mm', 'vertical')
    if stair:
        plan['profile_members'] = geometry.get('dado_profiles',{})
        plan['opening_profile_members'] = geometry.get('opening_profiles',[])
        if plan['opening_profile_members']:
            plan['elements']=[e for e in plan['elements'] if e['kind']!='frame']
            for member in plan['opening_profile_members']:
                _shape(plan,'frame',member['label'],member['vertices'])
        from .installed_geometry import annotate_installed_geometry
        annotate_installed_geometry(plan, groups or {})
    return plan
