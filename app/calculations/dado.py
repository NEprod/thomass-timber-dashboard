"""New dado calculation using recovered catalogue roles and user gap rules.

Frame dimensions describe the outside/long-point rectangle. Zone heights and
nested-frame inset are explicit measurements, not inferred legacy formulas.
"""
from dataclasses import asdict
from .packing import CalculationError, number, split_run, pack
from .geometry import stair_geometry, stair_route_geometry
from .stair_bead import bead_edges

SUPPORTED_DADO_STYLES = ('Dado', 'Dado Squares Bottom')

USES = {'continuous_dado': 'Continuous dado rail', 'square_dado': 'Square dado frames',
        'stair_dado': 'Stair dado rail'}


def rail_choices(catalogue):
    choices = {}
    for product in sorted(catalogue.values(), key=lambda p: (-p['length_mm'], p['price'], p['id'])):
        if product['category'] != 'dado' or not product.get('active', True):
            continue
        for use in ('continuous_dado', 'stair_dado'):
            if use in product.get('uses', []):
                key = (product['profile'], product['width_mm'], product['thickness_mm'], use)
                choices.setdefault(key, product)
    return list({product['id']: product for product in choices.values()}.values())


def product_for(catalogue, selected_id, use, *, longest=False):
    selected = catalogue.get(str(selected_id))
    if not selected or selected['category'] != 'dado' or use not in selected.get('uses', []):
        raise CalculationError(f'Select a configured profile approved for {USES[use].lower()}. Older quotes may need a catalogue refresh.')
    if not selected.get('active', True):
        raise CalculationError('The selected dado stock is inactive in this quote catalogue.')
    if not longest:
        return selected
    candidates = [p for p in catalogue.values() if p['category'] == 'dado'
                  and p.get('active', True) and use in p.get('uses', [])
                  and all(p[k] == selected[k] for k in ('profile', 'width_mm', 'thickness_mm'))]
    for product in candidates:
        number(product['length_mm'], 'Dado stock length')
    return sorted(candidates, key=lambda p: (-p['length_mm'], p['price'], p['id']))[0]


class DadoCuts:
    def __init__(self, work_item_id):
        self.work_item_id = str(work_item_id)
        self.groups = {}
        self.serial = 0

    def add(self, material, role, length, *, angles=None, stock_choices=None):
        from .sections import Cut
        pieces = split_run(length, material['length_mm'])
        if self.serial + len(pieces) > 20000:
            raise CalculationError('Too many dado cuts in one calculation.')
        run_id = f'{self.work_item_id}:dado:{self.serial + 1}'
        for index, piece in enumerate(pieces, 1):
            if stock_choices:
                material = min((p for p in stock_choices if p['length_mm'] >= piece),
                               key=lambda p: (p['length_mm'], p['price'], p['id']))
            group = self.groups.setdefault('dado_' + material['id'],
                                           {'material_id': material['id'], 'width_mm': material['width_mm'], 'cuts': []})
            self.serial += 1
            settings = dict(angles or {}, segment=index, segments=len(pieces))
            if 'start_joint_setting' in settings and index > 1:
                settings['start_joint_setting'] = 0
            if 'end_joint_setting' in settings and index < len(pieces):
                settings['end_joint_setting'] = 0
            cut = asdict(Cut(f'{self.work_item_id}:dado:{self.serial}', self.work_item_id,
                            material['id'], role, piece, material['width_mm'],
                            f'{role} · segment {index}/{len(pieces)}',
                            angle_information=settings,
                            join_id=run_id if len(pieces) > 1 else None))
            group['cuts'].append(cut)

    def finish(self, catalogue, kerf):
        # Omit zero-length landings rather than charging empty stock groups.
        self.groups = {name: group for name, group in self.groups.items() if group['cuts']}
        for group in self.groups.values():
            group['strips'] = pack(group['cuts'], catalogue[group['material_id']]['length_mm'], kerf)
        return self.groups


def rail(cuts, inputs, options, catalogue, *, geometry=None):
    product = product_for(catalogue, options.get('dado_rail_id'),
                          'stair_dado' if geometry else 'continuous_dado', longest=True)
    use = 'stair_dado' if geometry else 'continuous_dado'
    choices = [p for p in catalogue.values() if p['category']=='dado' and p.get('active',True)
               and use in p.get('uses',[]) and all(p[k]==product[k] for k in ('profile','width_mm','thickness_mm'))]
    if geometry is None:
        cuts.add(product, 'Continuous dado rail', number(inputs.get('wall_length'), 'Wall length'),
                 angles={'dado_role':'rail'}, stock_choices=choices)
    else:
        angle = geometry['slope_mitre']
        convention = geometry['angle_convention']
        lower_joint = angle if float(inputs['lower_landing']) > 0 else None
        upper_joint = angle if float(inputs['upper_landing']) > 0 else None
        for role, key, start, end in [('Lower landing dado', 'lower_landing', None, angle),
                                       ('Slope dado', 'slope_length', lower_joint, upper_joint),
                                       ('Upper landing dado', 'upper_landing', angle, None)]:
            cuts.add(product, role, number(inputs.get(key), key.replace('_', ' ').capitalize(), allow_zero=key!='slope_length'),
                     stock_choices=choices, angles={'dado_role':'rail', 'start_joint_setting': start, 'end_joint_setting': end,
                             'slope_angle': geometry['slope_angle'], 'convention': convention,
                             'measurement': 'Developed route; no speculative long-point allowance. Split interiors are butt joins.'})
    return product['id']


def count(value, label):
    result = number(value, label, maximum=100)
    if not result.is_integer():
        raise CalculationError(f'{label} must be a whole number.')
    return int(result)


def calculate_dado(kind, style, inputs, options, catalogue, kerf, work_item_id):
    from .sections import DADO_STYLES
    if style not in SUPPORTED_DADO_STYLES:
        raise CalculationError('This dado style is coming later. Saved historical results are not converted to another style.')
    w = number(inputs.get('wall_length'), 'Wall length')
    number(kerf, 'Kerf', allow_zero=True, maximum=50)
    cuts = DadoCuts(work_item_id)
    geometry = {'square_width': None, 'square_height': None, 'frames': []}
    warnings = ['Dado is a new calculation. Frame sizes use outside/long-point dimensions; kerf only consumes stock. Verify joint orientation on a real wall.']
    stair = kind == 'DADO_STAIR'
    if stair:
        lower = number(inputs.get('lower_landing'), 'Lower landing', allow_zero=True)
        upper = number(inputs.get('upper_landing'), 'Upper landing', allow_zero=True)
        slope = number(inputs.get('slope_length'), 'Measured slope')
        geometry.update(stair_route_geometry(w, lower, upper, slope))
        if style == 'Dado Squares Bottom':
            gap = number(inputs.get('gap_width'), 'Gap width', maximum=1000)
            n = count(inputs.get('bottom_squares'), 'Bottom horizontal squares')
            zone_height = number(inputs.get('bottom_zone_height'), 'Clear layout height below rail')
            geometry = stair_geometry(w, zone_height, lower, upper, slope, n, 1, gap)
        warnings.append('Synthetic/recovered stair geometry is not physically verified. Landing/slope boundaries are preserved; the MDF 30 mm allowance is not applied to dado.')
    geometry['rail_stock_id'] = rail(cuts, inputs, options, catalogue, geometry=geometry if stair else None)
    if stair and style == 'Dado Squares Bottom':
        profile = product_for(catalogue, options.get('dado_square_id'), 'square_dado')
        for edge in bead_edges(geometry, w, lower, upper, gap, 1):
            information = dict(edge['information'], dado_role='square')
            cuts.add(profile, edge['role'].replace('Bead ', 'Bottom dado ', 1), edge['length_mm'], angles=information)
        if geometry['counts']['transition']:
            warnings.append('Transition square dado pieces are conservative trim-to-fit provisions, not verified finished cuts. Labour and mastic use that provisional requirement.')
    elif style != 'Dado':
        gap = number(inputs.get('gap_width'), 'Gap width', maximum=1000)
        profile = product_for(catalogue, options.get('dado_square_id'), 'square_dado')
        zones = ['bottom', 'top'] if 'Top & Bottom' in style else ['bottom']
        double = 'Double' in style
        inset = number(inputs.get('inner_inset'), 'Nested frame outer-edge inset') if double else None
        if double and inset <= profile['width_mm']:
            raise CalculationError('Nested frame inset must exceed the profile width so the two frames do not overlap.')
        for zone in zones:
            n = count(inputs.get(zone + '_squares'), zone.capitalize() + ' squares')
            zone_height = number(inputs.get(zone + '_zone_height'), zone.capitalize() + ' clear layout-zone height')
            width = number(round((w - gap * (n + 1)) / n, 6), zone.capitalize() + ' frame width')
            height = number(round(zone_height - 2 * gap, 6), zone.capitalize() + ' frame height')
            for square in range(1, n + 1):
                frames = [('Outer', width, height)]
                if double:
                    frames.append(('Inner', number(width - 2 * inset, 'Inner width'), number(height - 2 * inset, 'Inner height')))
                for layer, fw, fh in frames:
                    frame = {'zone': zone, 'square': square, 'layer': layer.lower(), 'width_mm': fw, 'height_mm': fh}
                    geometry['frames'].append(frame)
                    for edge, length in [('top', fw), ('bottom', fw), ('left vertical', fh), ('right vertical', fh)]:
                        cuts.add(profile, f'{zone.capitalize()} square {square} · {layer.lower()} · {edge}', length,
                                 angles={'dado_role':'square', 'edge':edge, 'corner_included_angle': 90, 'start_joint_setting': 45, 'end_joint_setting': 45,
                                         'measurement': 'Outside/long-point rectangle; split interiors are butt joins.'})
        first = geometry['frames'][0]
        geometry.update(square_width=first['width_mm'], square_height=first['height_mm'])
    groups = cuts.finish(catalogue, kerf)
    return {'valid': True, 'version': '1.1-dado-follow-up', 'geometry': geometry, 'groups': groups, 'warnings': warnings,
            'horizontal_strips': sum(len(g['strips']) for g in groups.values()), 'vertical_strips': 0}


def dado_summary(result, catalogue):
    """Read structured cuts, including older saved results, without recalculation."""
    from collections import Counter
    rail_counts, square_counts = Counter(), Counter()
    purchases = []
    horizontal = vertical = 0
    for group in result.get('groups', {}).values():
        product = catalogue[group['material_id']]
        if product['category'] != 'dado':
            continue
        uses = set()
        for cut in group['cuts']:
            info = cut.get('angle_information') or {}
            square = info.get('dado_role') == 'square' or 'square' in cut['role'].lower()
            if square:
                uses.add('Square dado')
                orientation = 'Vertical' if 'vertical' in info.get('edge', cut['role']) else 'Horizontal'
                provision = info.get('stock_allowance', False)
                kind = 'Transition — trim to fit' if provision else ('Angled' if 'angled' in cut['role'].lower() else 'Flat')
                square_counts[(orientation,kind,cut['length_mm'],product['label'])] += 1
                horizontal += orientation == 'Horizontal'
                vertical += orientation == 'Vertical'
            else:
                uses.add('Main dado rail')
                rail_counts[(cut['role'],cut['length_mm'])] += 1
        required = sum(c['length_mm'] for c in group['cuts'])
        units = len(group['strips'])
        kerf = sum(s['kerf_loss_mm'] for s in group['strips'])
        purchases.append(dict(label=product['label'],use=' + '.join(sorted(uses)),units=units,
                              stock_mm=product['length_mm'],required_mm=required,purchased_mm=units*product['length_mm'],
                              kerf_mm=kerf,cost=round(units*product['price'],2),remainder_mm=round(units*product['length_mm']-required-kerf,6)))
    return dict(rail=[dict(role=k[0],length_mm=k[1],count=v) for k,v in rail_counts.items()],
                rail_count=sum(rail_counts.values()),rail_required_mm=round(sum(k[1]*v for k,v in rail_counts.items()),6),horizontal=horizontal,vertical=vertical,
                square_count=horizontal+vertical,
                square=[dict(orientation=k[0],kind=k[1],length_mm=k[2],profile=k[3],count=v) for k,v in square_counts.items()],
                purchases=purchases)
