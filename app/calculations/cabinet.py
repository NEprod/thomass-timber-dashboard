"""Cabinet construction: finished rectangular parts, never raw-sheet placement."""
import math
from .packing import CalculationError, number

PRESETS = {
    'alcove': 'Alcove / Base Cabinet',
    'window_seat': 'Window Seat',
    'bench': 'Free-standing Bench',
    'custom': 'Custom Cabinet',
}


def _count(inputs, key, label, maximum=50):
    value = number(inputs.get(key, 0), label, allow_zero=True, maximum=maximum)
    if not value.is_integer():
        raise CalculationError(f'{label} must be a whole number.')
    return int(value)


def _material(catalogue, material_id, label):
    material = catalogue.get(str(material_id))
    if not material or material['category'] != 'mdf':
        raise CalculationError(f'Select a sheet material for {label}.')
    return material


def calculate_cabinet(inputs, options, catalogue, config, work_item_id='preview', room_id=None):
    preset = options.get('cabinet_preset', 'alcove')
    if preset not in PRESETS:
        raise CalculationError('Choose a Cabinet / Built-in preset.')
    mode = ('top' if preset in ('window_seat', 'bench') else
            (options.get('construction_mode') or 'front') if preset == 'custom' else 'front')
    if mode not in ('front', 'top'):
        raise CalculationError('Choose front-opening or top-opening construction.')
    top_opening = mode == 'top'
    material = _material(catalogue, options.get('carcass_material_id'), 'carcass')
    thickness = number(material['thickness_mm'], 'Carcass thickness')
    unit_width = number(inputs.get('unit_width'), 'Finished unit width')
    unit_height = number(inputs.get('unit_height'), 'Finished unit height')
    unit_depth = number(inputs.get('unit_depth'), 'Finished unit depth')
    opening_width = (number(inputs.get('opening_width'), 'Opening width')
                     if not top_opening and (preset == 'alcove' or inputs.get('opening_width')) else None)
    opening_height = number(inputs['opening_height'], 'Opening height') if inputs.get('opening_height') else None
    opening_depth = number(inputs['opening_depth'], 'Opening depth') if inputs.get('opening_depth') else None
    if opening_width is not None and opening_width < unit_width:
        raise CalculationError('Opening width must be at least the finished unit width.')
    internal = unit_width - 2 * thickness
    if internal <= 0:
        raise CalculationError('Unit width must exceed two carcass thicknesses.')
    rail_depth = number(config.get('cabinet_top_rail_depth', 100), 'Cabinet top rail depth')
    shelf_setback = number(config.get('cabinet_shelf_setback', 18), 'Cabinet shelf setback')
    back_inset = number(config.get('cabinet_back_inset', 50), 'Cabinet back inset')
    worktop_rear = number(config.get('cabinet_worktop_rear_allowance', 50), 'Worktop rear allowance', allow_zero=True)
    scribe = number(config.get('cabinet_scribe_allowance', 50), 'Cabinet scribe allowance', allow_zero=True)
    face_rail_height = number(config.get('cabinet_face_rail_height', 100), 'Cabinet face rail height')
    door_gap = number(config.get('cabinet_door_gap', 2), 'Door reveal', allow_zero=True)
    band = number(config.get('cabinet_edge_band', 1), 'Door edge band', allow_zero=True)
    parts = []
    groups = {}
    door_results = []
    serial = 0
    rotation_allowed = options.get('sheet_rotation_allowed', True)

    def add(label, length, width, *, material_id=None, quantity=1, component=None,
            finished=None, rotation=True, notes=''):
        nonlocal serial
        product = _material(catalogue, material_id or material['id'], label)
        length = number(length, f'{label} length')
        width = number(width, f'{label} width')
        serial += 1
        part = dict(id=f'{work_item_id}:sheet:{serial}', label=label,
                    work_item_id=str(work_item_id), room_id=room_id,
                    material_id=product['id'], thickness_mm=product['thickness_mm'],
                    finished_length_mm=finished[0] if finished else length,
                    finished_width_mm=finished[1] if finished else width,
                    cut_length_mm=length, cut_width_mm=width, quantity=quantity,
                    rotation_allowed=rotation and rotation_allowed,
                    grain_constraint='none' if rotation and rotation_allowed else 'fixed',
                    component=component or label, notes=notes)
        parts.append(part)

    def linear(label, length, product, *, width=None, role):
        nonlocal serial
        length = number(length, f'{label} length')
        if length > product['length_mm']:
            raise CalculationError(f'{label}: {length:g} mm exceeds {product["length_mm"]:g} mm stock. This piece cannot be joined automatically.')
        serial += 1
        group = groups.setdefault(role + '_' + product['id'],
                                  dict(material_id=product['id'], width_mm=product['width_mm'], cuts=[]))
        group['cuts'].append(dict(id=f'{work_item_id}:linear:{serial}', label=label,
            work_item_id=str(work_item_id), room_id=room_id, material_id=product['id'],
            length_mm=length, width_mm=product['width_mm'] if width is None else width,
            thickness_mm=product['thickness_mm'], continuous=True, no_join=True))

    upright_height = unit_height - thickness if top_opening else unit_height
    upright_depth = unit_depth - 2 * thickness if top_opening else unit_depth
    if top_opening:
        add('Bottom', unit_width, unit_depth)
        add('Front panel', unit_width, upright_height)
        add('Back panel', unit_width, upright_height)
        add('Left side', upright_height, upright_depth)
        add('Right side', upright_height, upright_depth)
    elif preset != 'custom' or options.get('sides_enabled', True):
        add('Left side', unit_height, unit_depth)
        add('Right side', unit_height, unit_depth)
    if not top_opening and (preset != 'custom' or options.get('bottom_enabled', True)):
        add('Bottom', internal, unit_depth)
    has_lid = top_opening or bool(options.get('full_top'))
    if has_lid:
        add('Full top / lid', unit_width, unit_depth, component='lid',
            notes='Hinged lid' if options.get('hinged_lid') else 'Fixed top')
    elif options.get('top_rails', preset != 'custom'):
        add('Front top rail', internal, rail_depth, component='top_rail')
        add('Rear top rail', internal, rail_depth, component='top_rail')

    dividers = _count(inputs, 'divider_count', 'Divider count')
    bay_width = (internal - dividers * thickness) / (dividers + 1)
    if bay_width <= 0:
        raise CalculationError('Dividers leave no clear bay width.')
    if dividers:
        divider_height = upright_height if top_opening else number(inputs.get('divider_height'), 'Divider cut height')
        for index in range(dividers):
            add(f'Divider {index + 1}', divider_height, upright_depth, component='divider')

    back = bool(options.get('back_enabled')) and not top_opening
    shelf_depth = (upright_depth - shelf_setback if top_opening else
                   unit_depth - shelf_setback - (back_inset if back else 0))
    shelves = _count(inputs, 'shelves_per_bay', 'Shelves per bay')
    if shelves and shelf_depth <= 0:
        raise CalculationError('The shelf depth is not positive after its setbacks.')
    for bay in range(dividers + 1):
        for shelf in range(shelves):
            add(f'Bay {bay + 1} shelf {shelf + 1}', bay_width, shelf_depth, component='shelf')

    back_position = None
    if back:
        back_material = _material(catalogue, options.get('back_material_id') or 'mdf-9mm', 'back panel')
        add('Inset back', internal + 10, unit_height - 2 * thickness,
            material_id=back_material['id'], component='back',
            notes='5mm engagement in each side groove')
        back_position = dict(front_face_from_rear_mm=back_inset,
                             rear_face_from_rear_mm=back_inset - back_material['thickness_mm'])
        if back_position['rear_face_from_rear_mm'] < 0:
            raise CalculationError('Back panel thickness exceeds the configured inset.')

    if not top_opening and options.get('face_frame', preset == 'alcove'):
        if opening_width is None:
            raise CalculationError('Enter opening width for face-frame scribes.')
        side_width = (opening_width - unit_width) / 2 + scribe
        frame_material = _material(catalogue, options.get('face_frame_material_id') or material['id'], 'face frame')
        add('Left side stile / scribe', unit_height + face_rail_height, side_width,
            material_id=frame_material['id'], quantity=2, component='face_frame')
        add('Right side stile / scribe', unit_height + face_rail_height, side_width,
            material_id=frame_material['id'], quantity=2, component='face_frame')
        add('Bottom face-frame rail', unit_width, face_rail_height,
            material_id=frame_material['id'], quantity=2, component='face_frame')

    worktop_type = options.get('worktop_type') or ('sheet' if options.get('worktop', preset == 'alcove') else 'none')
    if worktop_type not in ('none', 'sheet', 'pse'):
        raise CalculationError('Choose no worktop, sheet material, or glue-up PSE timber.')
    if not top_opening and worktop_type != 'none':
        if opening_width is None:
            raise CalculationError('Enter opening width for the scribed worktop.')
        front_overhang = number(inputs.get('front_overhang', 0), 'Front overhang', allow_zero=True)
        cut_length = opening_width + 2 * scribe
        cut_depth = unit_depth + worktop_rear + front_overhang
        if worktop_type == 'sheet':
            worktop = _material(catalogue, options.get('worktop_material_id') or material['id'], 'worktop')
            add('Worktop cut blank', cut_length, cut_depth, material_id=worktop['id'],
                component='worktop', finished=(opening_width, unit_depth + front_overhang),
                notes=f'{scribe:g}mm scribe each side; {worktop_rear:g}mm rear fitting allowance')
        else:
            timber = catalogue.get(options.get('pse_material_id'))
            if not timber or timber['category'] != 'pse':
                raise CalculationError('Select PSE timber for the glue-up worktop.')
            board_width = number(timber['width_mm'], 'PSE board width')
            count = math.ceil(cut_depth / board_width)
            if count > 500:
                raise CalculationError('Limit a glue-up worktop to 500 strips.')
            for index in range(count):
                linear(f'Worktop strip {index + 1}', cut_length, timber,
                       width=min(board_width, cut_depth - index * board_width), role='worktop')

    doors = 0 if top_opening else _count(inputs, 'door_count', 'Door count')
    if doors:
        if dividers and doors != dividers + 1:
            raise CalculationError('With equal bays, use one door per bay.')
        door_material = _material(catalogue, options.get('door_material_id') or material['id'], 'doors')
        finished_width = (unit_width - 2 * door_gap - (doors - 1) * door_gap) / doors
        finished_height = unit_height - 2 * door_gap
        edge_band = band if options.get('door_banding', 'all') == 'all' else 0
        if options.get('door_banding', 'all') not in ('all', 'none'):
            raise CalculationError('Choose no door banding or all four edges.')
        style = options.get('door_style') or 'flat'
        if style not in ('flat', 'shaker'):
            raise CalculationError('Choose Flat or Shaker doors.')
        bead = catalogue.get(options.get('door_bead_id')) if options.get('door_bead_id') else None
        if options.get('door_bead_id') and (not bead or bead['category'] != 'bead'):
            raise CalculationError('Choose an existing bead / moulding product.')
        for index in range(doors):
            prefix = f'Door {index + 1}'
            blank_height, blank_width = finished_height - 2 * edge_band, finished_width - 2 * edge_band
            number(blank_height, 'Door blank height'); number(blank_width, 'Door blank width')
            door_result = dict(label=prefix, style=style, finished_width_mm=finished_width,
                finished_height_mm=finished_height, blank_width_mm=blank_width, blank_height_mm=blank_height)
            if style == 'flat':
                add(prefix, blank_height, blank_width, material_id=door_material['id'],
                    component='door', finished=(finished_height, finished_width),
                    notes='All four edges banded' if edge_band else 'No edge banding')
                inset_value = inputs.get('door_bead_inset')
                inset = number(config.get('cabinet_flat_bead_inset', 100)
                               if inset_value in (None, '') else inset_value,
                               'Flat-door bead inset', allow_zero=True)
                bead_width, bead_height = finished_width - 2 * inset, finished_height - 2 * inset
            else:
                stile = number(config.get('cabinet_shaker_stile_width', 100), 'Shaker stile width')
                rail = number(config.get('cabinet_shaker_rail_width', 100), 'Shaker rail width')
                engagement = number(config.get('cabinet_shaker_panel_engagement', 5), 'Shaker panel engagement', allow_zero=True)
                bead_width = number(finished_width - 2 * stile, 'Shaker opening width')
                bead_height = number(finished_height - 2 * rail, 'Shaker opening height')
                panel = _material(catalogue, options.get('shaker_panel_material_id') or 'mdf-9mm', 'Shaker centre panel')
                if engagement > min(stile - edge_band, rail - edge_band):
                    raise CalculationError('Shaker panel engagement exceeds its frame width.')
                # Outside band contributes once to each outside edge. Internal
                # rail ends and the visible opening receive no band deduction.
                add(prefix + ' stile', blank_height, stile - edge_band, quantity=2,
                    material_id=door_material['id'], component='door_stile',
                    finished=(finished_height, stile), notes='Full-height stile; band on outside edges only')
                add(prefix + ' rail', bead_width, rail - edge_band, quantity=2,
                    material_id=door_material['id'], component='door_rail',
                    finished=(bead_width, rail), notes='Fits between stiles; band on outside edge only')
                add(prefix + ' Shaker centre panel', bead_width + 2 * engagement,
                    bead_height + 2 * engagement, material_id=panel['id'], component='door_panel',
                    notes=f'{engagement:g}mm engagement on each of four edges')
                door_result.update(opening_width_mm=bead_width, opening_height_mm=bead_height)
            door_results.append(door_result)
            if bead:
                for label, length in [('left', bead_height), ('right', bead_height),
                                      ('top', bead_width), ('bottom', bead_width)]:
                    linear(f'{prefix} bead {label}', length, bead, role='door_bead')

    base = options.get('base_type', 'none')
    if base not in ('none', 'legs', 'plinth'):
        raise CalculationError('Choose no base, legs, or a plinth / box base.')
    base_height = number(inputs.get('feet_height', 0), 'Feet height', allow_zero=True) if base == 'legs' else 0
    if base == 'plinth':
        plinth_height = number(inputs.get('plinth_height') or config.get('cabinet_plinth_height', 100), 'Plinth height')
        base_height = plinth_height
        plinth_recess = number(inputs.get('plinth_front_recess') or config.get('cabinet_plinth_front_recess', 50),
                              'Plinth front recess', allow_zero=True)
        if plinth_recess >= unit_depth:
            raise CalculationError('Plinth front recess must be less than unit depth.')
        front_back = number(inputs.get('plinth_front_back_length'), 'Plinth front/back cut length')
        side_length = number(inputs.get('plinth_side_length'), 'Plinth side cut length')
        plinth_material = _material(catalogue, options.get('plinth_material_id') or material['id'], 'plinth')
        add('Plinth front', front_back, plinth_height, material_id=plinth_material['id'], component='plinth',
            notes=f'Front recessed {plinth_recess:g}mm from carcass')
        add('Plinth back', front_back, plinth_height, material_id=plinth_material['id'], component='plinth')
        add('Plinth left side', side_length, plinth_height, material_id=plinth_material['id'], component='plinth')
        add('Plinth right side', side_length, plinth_height, material_id=plinth_material['id'], component='plinth')
        for index in range(_count(inputs, 'plinth_support_count', 'Plinth support count')):
            add(f'Plinth support {index + 1}', side_length, plinth_height,
                material_id=plinth_material['id'], component='plinth')

    assembly_height = unit_height + base_height + (thickness if has_lid else 0)
    scribed_sides = options.get('scribed_sides') or 'none'
    if scribed_sides not in ('none', 'left', 'right', 'both'):
        raise CalculationError('Choose None, Left, Right, or Both scribed sides.')
    if top_opening:
        allowance = number(config.get('cabinet_bench_scribe_allowance', 50), 'Bench scribe allowance', allow_zero=True)
        for side in ('left', 'right'):
            if scribed_sides in (side, 'both'):
                add(f'{side.title()} end scribe', assembly_height + allowance, unit_depth + allowance,
                    component='end_scribe', finished=(assembly_height, unit_depth),
                    notes='Full assembly including overlay lid and base; trim during fitting')

    hours = number(inputs.get('workshop_hours', 0), 'Workshop hours', allow_zero=True, maximum=10000)
    days = number(inputs.get('installation_days', 0), 'Installation days', allow_zero=True, maximum=365)
    if not parts and not groups:
        raise CalculationError('Choose at least one Cabinet component.')
    return dict(valid=True, errors=[], groups=groups, sheet_parts=parts, warnings=[],
                geometry=dict(preset=preset, construction_mode=mode, opening_width=opening_width,
                              opening_height=opening_height, opening_depth=opening_depth,
                              unit_width=unit_width,
                              unit_height=unit_height, unit_depth=unit_depth, internal_width=internal,
                              bay_width=round(bay_width, 6), bay_count=dividers + 1,
                              shelf_depth=round(shelf_depth, 6), back_position=back_position,
                              upright_height=upright_height, upright_depth=upright_depth,
                              assembly_height=assembly_height, doors=door_results,
                              workshop_hours=hours, installation_days=days))
