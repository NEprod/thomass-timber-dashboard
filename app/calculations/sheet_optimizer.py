"""Deterministic guillotine packing of labelled rectangular sheet parts.

Every placement splits one free rectangle with full-width/height cuts.  The
resulting tree is retained so the workshop diagram and later cut sequencing
can use the same physically cuttable plan.
"""
from .packing import CalculationError, number


def _leaves(node, path=()):
    if node['kind'] == 'free':
        yield path, node
    elif node['kind'] == 'split':
        yield from _leaves(node['first'], path + ('first',))
        yield from _leaves(node['second'], path + ('second',))


def _node_at(tree, path):
    for step in path:
        tree = tree[step]
    return tree


def _replace(tree, path, replacement):
    if not path:
        tree.clear()
        tree.update(replacement)
    else:
        _node_at(tree, path[:-1])[path[-1]] = replacement


def _split(region, part, length, width, kerf, *, vertical_first):
    x, y, region_length, region_width = (region[key] for key in ('x', 'y', 'length_mm', 'width_mm'))
    placed = dict(part, x=x, y=y, length_mm=length, width_mm=width,
                  rotated=(length != part['cut_length_mm'] or width != part['cut_width_mm']))
    part_node = dict(kind='part', x=x, y=y, length_mm=length, width_mm=width, part=placed)

    def free(fx, fy, fl, fw):
        return dict(kind='free', x=fx, y=fy, length_mm=fl, width_mm=fw)

    remaining_length = region_length - length
    remaining_width = region_width - width
    side = free(x + length + kerf, y, max(0, remaining_length - kerf), region_width) if remaining_length > 0 and remaining_length + 1e-7 >= kerf else None
    below = free(x, y + width + kerf, length if vertical_first else region_length,
                 max(0, remaining_width - kerf)) if remaining_width > 0 and remaining_width + 1e-7 >= kerf else None
    if vertical_first:
        first = part_node if below is None else dict(kind='split', axis='horizontal', kerf_mm=kerf,
            x=x, y=y, length_mm=length, width_mm=region_width, first=part_node, second=below)
        return first if side is None else dict(kind='split', axis='vertical', kerf_mm=kerf,
            x=x, y=y, length_mm=region_length, width_mm=region_width, first=first, second=side), placed
    below = free(x, y + width + kerf, region_length, max(0, remaining_width - kerf)) if remaining_width > 0 and remaining_width + 1e-7 >= kerf else None
    right = free(x + length + kerf, y, max(0, remaining_length - kerf), width) if remaining_length > 0 and remaining_length + 1e-7 >= kerf else None
    first = part_node if right is None else dict(kind='split', axis='vertical', kerf_mm=kerf,
        x=x, y=y, length_mm=region_length, width_mm=width, first=part_node, second=right)
    return (first if below is None else dict(kind='split', axis='horizontal', kerf_mm=kerf,
        x=x, y=y, length_mm=region_length, width_mm=region_width, first=first, second=below)), placed


def _orientations(part):
    length, width = part['cut_length_mm'], part['cut_width_mm']
    yield length, width
    if part.get('rotation_allowed', True) and length != width:
        yield width, length


def _fits(length, width, region, kerf):
    gap_length = region['length_mm'] - length
    gap_width = region['width_mm'] - width
    return (gap_length >= -1e-7 and gap_width >= -1e-7 and
            (gap_length <= 1e-7 or gap_length + 1e-7 >= kerf) and
            (gap_width <= 1e-7 or gap_width + 1e-7 >= kerf))


def _expand(parts):
    expanded = []
    for part in parts:
        quantity = number(part.get('quantity', 1), 'Part quantity', maximum=500)
        if not quantity.is_integer():
            raise CalculationError('Part quantity must be a whole number.')
        length = number(part['cut_length_mm'], 'Part cut length')
        width = number(part['cut_width_mm'], 'Part cut width')
        for index in range(int(quantity)):
            copy = dict(part, cut_length_mm=length, cut_width_mm=width, quantity=1)
            copy['id'] = f"{part['id']}:{index + 1}" if quantity > 1 else str(part['id'])
            expanded.append(copy)
    if len(expanded) > 500:
        raise CalculationError('Limit each room to 500 rectangular sheet parts.')
    if len({part['id'] for part in expanded}) != len(expanded):
        raise CalculationError('Rectangular sheet part IDs must be unique.')
    return expanded


def _plan(parts, stock_length, stock_width, trim, kerf, order, vertical_first, *, one_sheet=False):
    def sheet():
        return dict(stock_length_mm=stock_length, stock_width_mm=stock_width, trim_mm=trim,
                    tree=dict(kind='free', x=trim, y=trim,
                              length_mm=stock_length - 2 * trim, width_mm=stock_width - 2 * trim),
                    placements=[])

    sheets = [sheet()] if one_sheet else []
    leftover = []
    for part in order:
        choices = []
        for sheet_index, board in enumerate(sheets):
            for path, leaf in _leaves(board['tree']):
                for length, width in _orientations(part):
                    if _fits(length, width, leaf, kerf):
                        choices.append((sheet_index, leaf['length_mm'] * leaf['width_mm'] - length * width,
                                        len(path), length != part['cut_length_mm'], path, length, width))
        if not choices and one_sheet:
            leftover.append(part)
            continue
        if not choices:
            sheets.append(sheet())
            for length, width in _orientations(part):
                leaf = sheets[-1]['tree']
                if _fits(length, width, leaf, kerf):
                    choices.append((len(sheets) - 1, leaf['length_mm'] * leaf['width_mm'] - length * width,
                                    0, length != part['cut_length_mm'], (), length, width))
        if not choices:
            raise CalculationError(f"{part.get('label', 'Part')}: part exceeds available sheet size.")
        _, _, _, _, path, length, width = min(choices)
        sheet_index = min(choices)[0]
        board = sheets[sheet_index]
        replacement, placed = _split(_node_at(board['tree'], path), part, length, width, kerf,
                                     vertical_first=vertical_first)
        _replace(board['tree'], path, replacement)
        board['placements'].append(placed)
    return sheets, leftover


def _orders(parts):
    return [sorted(parts, key=lambda p: (-p['cut_length_mm'] * p['cut_width_mm'], -max(p['cut_length_mm'], p['cut_width_mm']), p['id'])),
            sorted(parts, key=lambda p: (-max(p['cut_length_mm'], p['cut_width_mm']), -p['cut_length_mm'] * p['cut_width_mm'], p['id'])),
            sorted(parts, key=lambda p: (-p['cut_length_mm'], -p['cut_width_mm'], p['id'])),
            sorted(parts, key=lambda p: (-p['cut_width_mm'], -p['cut_length_mm'], p['id']))]


def _cut_lines(node):
    if node['kind'] != 'split':
        return []
    first = node['first']
    if node['axis'] == 'vertical':
        position = first['x'] + first['length_mm'] + node['kerf_mm'] / 2
        line = dict(x1=position, y1=node['y'], x2=position,
                    y2=node['y'] + node['width_mm'])
    else:
        position = first['y'] + first['width_mm'] + node['kerf_mm'] / 2
        line = dict(x1=node['x'], y1=position,
                    x2=node['x'] + node['length_mm'], y2=position)
    return [line] + _cut_lines(node['first']) + _cut_lines(node['second'])


def _tree_stats(node):
    if node['kind'] != 'split':
        area = node['length_mm'] * node['width_mm'] if node['kind'] == 'free' else 0
        return 0, 0, area
    left = _tree_stats(node['first'])
    right = _tree_stats(node['second'])
    span = node['width_mm'] if node['axis'] == 'vertical' else node['length_mm']
    return (1 + left[0] + right[0], node['kerf_mm'] * span + left[1] + right[1],
            max(left[2], right[2]))


def pack_sheet_parts(parts, stock_length, stock_width, *, trim=10, kerf=3):
    """Return guillotine-valid sheets, using bounded deterministic heuristics."""
    stock_length = number(stock_length, 'Sheet length')
    stock_width = number(stock_width, 'Sheet width')
    trim = number(trim, 'Sheet edge trim', allow_zero=True, maximum=100)
    kerf = number(kerf, 'Sheet kerf', allow_zero=True, maximum=50)
    if stock_length <= 2 * trim or stock_width <= 2 * trim:
        raise CalculationError('Sheet edge trim leaves no usable area.')
    expanded = _expand(parts)
    for part in expanded:
        if not any(length <= stock_length - 2 * trim + 1e-7 and
                   width <= stock_width - 2 * trim + 1e-7 for length, width in _orientations(part)):
            raise CalculationError(f"{part.get('label', 'Part')}: part exceeds available sheet size.")
    if not expanded:
        return []
    candidates = []
    for order in _orders(expanded):
        for vertical_first in (True, False):
            sheets, _ = _plan(expanded, stock_length, stock_width, trim, kerf, order, vertical_first)
            stats = [_tree_stats(sheet['tree']) for sheet in sheets]
            score = (len(sheets), sum(stat[0] for stat in stats),
                     sum(stat[1] for stat in stats), -sum(stat[2] for stat in stats),
                     tuple(tuple(p['id'] for p in s['placements']) for s in sheets))
            candidates.append((score, sheets))
    result = min(candidates, key=lambda entry: entry[0])[1]
    for index, board in enumerate(result, 1):
        board['index'] = index
        board['cut_lines'] = _cut_lines(board['tree'])
        board['offcuts'] = [dict(leaf, reusable=min(leaf['length_mm'], leaf['width_mm']) >= 100)
                            for _, leaf in _leaves(board['tree'])]
    return result


def parts_on_owned_sheet(parts, length, width, *, kerf=3):
    """Select a guillotine-cuttable subset for one known usable physical sheet."""
    expanded = _expand(parts)
    candidates = []
    for order in _orders(expanded):
        for vertical_first in (True, False):
            sheets, leftover = _plan(expanded, length, width, 0, kerf, order, vertical_first, one_sheet=True)
            placed = sheets[0]['placements']
            score = (-sum(p['length_mm'] * p['width_mm'] for p in placed), -len(placed),
                     tuple(p['id'] for p in placed))
            candidates.append((score, placed, leftover))
    _, placed, leftover = min(candidates, key=lambda entry: entry[0])
    return placed, leftover
