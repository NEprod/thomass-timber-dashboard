"""Measured stair geometry recovered from calc_half_stairs.py:23–91.
Rounding, cosine scaling and column classification deliberately preserved.
"""
import math
from .packing import CalculationError, number

WORKSHOP_ALLOWANCE_MM = 30

def stair_geometry(wall_length, panel_height, lower_landing, upper_landing,
                   slope_length, horizontal_squares, vertical_squares, slat_width):
    run = wall_length - lower_landing - upper_landing
    if run <= 0 or slope_length < run:
        raise CalculationError('Slope must be at least the positive horizontal run (wall minus both landings).')
    rad = math.acos(run / slope_length)
    degrees = round(math.degrees(rad), 2)
    acute = round(90-degrees, 2)
    obtuse = round(180-acute, 2)
    sw = round((wall_length-(horizontal_squares+1)*slat_width)/horizontal_squares,2)
    sh = round((panel_height-(vertical_squares+1)*slat_width)/vertical_squares,2)
    number(sw, 'Square width'); number(sh, 'Square height')
    vertical = round(panel_height-2*slat_width,2)
    aw, ah = round(sw/math.cos(rad),2), round(sh/math.cos(rad),2)
    layout, used = [], 0
    for i in range(horizontal_squares):
        left = used+slat_width
        center = left+sw/2
        right = center+sw/2
        if right <= lower_landing or left >= wall_length-upper_landing:
            kind = 'flat'
        elif left < lower_landing or right > wall_length-upper_landing:
            kind = 'transition'
        else:
            kind = 'angled'
        layout.append({'index':i+1,'center_x':center,'type':kind})
        used += slat_width+sw
    return dict(horizontal_run=run,slope_angle=degrees,slope_mitre=round(90-(180-degrees)/2,2),
                acute_included_angle=acute,obtuse_included_angle=obtuse,
                top_angle_setting=round(90-acute/2,2),bottom_angle_setting=round(90-obtuse/2,2),
                angle_convention='Historical displayed cut settings; physical saw orientation unverified',
                square_width=sw,square_height=sh,angled_square_width=aw,angled_square_height=ah,
                vertical_height=vertical,angled_vertical_height=round(vertical/math.cos(rad),2),
                columns=layout,counts={k:sum(c['type']==k for c in layout) for k in ('flat','angled','transition')})
