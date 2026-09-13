"""Stair bead edges and user-approved conservative transition provisions.

Landing bends align horizontally (user clarification). Transition pieces are
stock allowances using the larger recovered square sizes, not certified cuts.
"""
import math


def bead_edges(geometry, wall_length, lower, upper, slat_width, rows):
    sw, sh = geometry['square_width'], geometry['square_height']
    aw, ah = geometry['angled_square_width'], geometry['angled_square_height']
    boundary_points = (lower, wall_length - upper)
    edges = []
    for column in geometry['columns']:
        index, kind = column['index'], column['type']
        left = (index - 1) * (slat_width + sw) + slat_width
        right = left + sw
        points = sorted({left, right, *(p for p in boundary_points if left < p < right)})
        for row in range(1, rows + 1):
            base = f'Bead {kind} square {index} row {row}'
            if kind == 'transition':
                # Split each conservative horizontal provision at actual bend x.
                # Scaling every span by max width/sw preserves the user-approved
                # larger-size provision while representing every physical piece.
                scale = max(sw, aw) / sw
                for edge in ('top', 'bottom'):
                    for segment, (start, end) in enumerate(zip(points, points[1:]), 1):
                        sloped = lower <= (start + end) / 2 <= wall_length - upper
                        length = math.ceil((end - start) * scale * 100) / 100
                        edges.append({'role': f'{base} · {edge} segment {segment} · trim-to-fit allowance',
                                      'length_mm': length, 'information': {'square': index, 'row': row,
                                      'edge': edge, 'segment': segment, 'route': 'slope' if sloped else 'landing',
                                      'x_start': start, 'x_end': end, 'stock_allowance': True,
                                      'slope_mitre': geometry['slope_mitre'],
                                      'measurement': 'Conservative larger-size provision; measure finished opening before cutting.'}})
                height = max(sh, ah)
            else:
                width, height = (sw, sh) if kind == 'flat' else (aw, ah)
                for edge in ('top', 'bottom'):
                    edges.append({'role': f'{base} · {edge}', 'length_mm': width,
                                  'information': {'square': index, 'row': row, 'edge': edge,
                                  'top_angle_setting': geometry['top_angle_setting'] if kind=='angled' else 45,
                                  'bottom_angle_setting': geometry['bottom_angle_setting'] if kind=='angled' else 45,
                                  'measurement': 'Recovered finished opening edge; saw orientation unverified.'}})
            for edge in ('left vertical', 'right vertical'):
                edges.append({'role': f'{base} · {edge}' + (' · trim-to-fit allowance' if kind=='transition' else ''),
                              'length_mm': height, 'information': {'square': index, 'row': row, 'edge': edge,
                              'stock_allowance': kind=='transition',
                              'top_angle_setting': geometry['top_angle_setting'] if kind!='flat' else 45,
                              'bottom_angle_setting': geometry['bottom_angle_setting'] if kind!='flat' else 45,
                              'measurement': 'Larger recovered height provision; trim to opening.' if kind=='transition' else 'Recovered opening edge.'}})
    return edges
