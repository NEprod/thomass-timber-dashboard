"""Cabinet construction: finished rectangular parts, never raw-sheet placement."""
from .packing import CalculationError, number

PRESETS = {
    'alcove': 'Alcove / Base Cabinet',
    'window_seat': 'Window Seat',
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
    material = _material(catalogue, options.get('carcass_material_id'), 'carcass')
    thickness = number(material['thickness_mm'], 'Carcass thickness')
    unit_width = number(inputs.get('unit_width'), 'Finished unit width')
    unit_height = number(inputs.get('unit_height'), 'Finished unit height')
    unit_depth = number(inputs.get('unit_depth'), 'Finished unit depth')
    opening_width = number(inputs.get('opening_width'), 'Opening width') if preset == 'alcove' else None
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

    if preset != 'custom' or options.get('sides_enabled', True):
        add('Left side', unit_height, unit_depth)
        add('Right side', unit_height, unit_depth)
    if preset != 'custom' or options.get('bottom_enabled', True):
        add('Bottom', internal, unit_depth)
    if preset == 'window_seat' or options.get('full_top'):
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
        divider_height = number(inputs.get('divider_height'), 'Divider cut height')
        for index in range(dividers):
            add(f'Divider {index + 1}', divider_height, unit_depth, component='divider')

    back = bool(options.get('back_enabled'))
    shelf_depth = unit_depth - shelf_setback - (back_inset if back else 0)
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

    if options.get('face_frame', preset == 'alcove'):
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

    if options.get('worktop', preset == 'alcove'):
        if opening_width is None:
            raise CalculationError('Enter opening width for the scribed worktop.')
        front_overhang = number(inputs.get('front_overhang', 0), 'Front overhang', allow_zero=True)
        worktop = _material(catalogue, options.get('worktop_material_id') or material['id'], 'worktop')
        add('Worktop cut blank', opening_width + 2 * scribe,
            unit_depth + worktop_rear + front_overhang, material_id=worktop['id'],
            component='worktop', finished=(opening_width, unit_depth + front_overhang),
            notes=f'{scribe:g}mm scribe each side; {worktop_rear:g}mm rear fitting allowance')

    doors = _count(inputs, 'door_count', 'Door count')
    if doors:
        if dividers and doors != dividers + 1:
            raise CalculationError('With equal bays, use one door per bay.')
        door_material = _material(catalogue, options.get('door_material_id') or material['id'], 'doors')
        finished_width = (unit_width - 2 * door_gap - (doors - 1) * door_gap) / doors
        finished_height = unit_height - 2 * door_gap
        edge_band = band if options.get('door_banding', 'all') == 'all' else 0
        if options.get('door_banding', 'all') not in ('all', 'none'):
            raise CalculationError('Choose no door banding or all four edges.')
        for index in range(doors):
            add(f'Door {index + 1}', finished_height - 2 * edge_band,
                finished_width - 2 * edge_band, material_id=door_material['id'],
                component='door', finished=(finished_height, finished_width),
                notes='All four edges banded' if edge_band else 'No edge banding')

    base = options.get('base_type', 'none')
    if base not in ('none', 'legs', 'plinth'):
        raise CalculationError('Choose no base, legs, or a plinth / box base.')
    if base == 'plinth':
        plinth_height = number(inputs.get('plinth_height') or config.get('cabinet_plinth_height', 100), 'Plinth height')
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

    hours = number(inputs.get('workshop_hours', 0), 'Workshop hours', allow_zero=True, maximum=10000)
    days = number(inputs.get('installation_days', 0), 'Installation days', allow_zero=True, maximum=365)
    if not parts:
        raise CalculationError('Choose at least one Cabinet component.')
    return dict(valid=True, errors=[], groups={}, sheet_parts=parts, warnings=[],
                geometry=dict(preset=preset, opening_width=opening_width,
                              opening_height=opening_height, opening_depth=opening_depth,
                              unit_width=unit_width,
                              unit_height=unit_height, unit_depth=unit_depth, internal_width=internal,
                              bay_width=round(bay_width, 6), bay_count=dividers + 1,
                              shelf_depth=round(shelf_depth, 6), back_position=back_position,
                              workshop_hours=hours, installation_days=days))
