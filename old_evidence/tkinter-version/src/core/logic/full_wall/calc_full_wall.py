import math
from core.logic.shared.layout_strips import layout_strips

def generate_square_strip_cut_list_full(section, square_width, wall_height, horz_squares, vert_squares, board_length, kerf):
    """
    Generates vertical and horizontal slat cut lists for full wall square panelling.
    """

    vertical_slats = horz_squares + 1
    vertical_cuts = [wall_height] * vertical_slats

    horizontal_slats = horz_squares * (vert_squares + 1)
    horizontal_cuts = [square_width] * horizontal_slats

    result = {
        "vertical": layout_strips(vertical_cuts, board_length, kerf),
        "horizontal": layout_strips(horizontal_cuts, board_length, kerf)
    }

    section.square_strip_cut_list = result

    # Optional debug
    index = section.vars.get('index', '?')
    print(f"\n[MDF Strips Cut List] Wall Section {index} — Full Wall Panelling")
    for direction, strips in result.items():
        print(f"  {direction.capitalize()} Strips ({len(strips)} total):")
        for strip_name, data in strips.items():
            print(f"    {strip_name}: {data['cuts']} | Used: {data['used']:.1f}mm")


def calc_square_full(section, wall_width, wall_height, horz_squares, vert_squares, slat_width, board_length, kerf):
    """
    Calculates square layout and MDF usage for full wall panelling.
    """
    square_width = round((wall_width - ((horz_squares + 1) * slat_width)) / horz_squares, 2)
    square_height = round((wall_height - ((vert_squares + 1) * slat_width)) / vert_squares, 2)

    horz_pieces_per = math.floor(board_length / square_width)

    generate_square_strip_cut_list_full(
        section,
        square_width,
        wall_height,
        horz_squares,
        vert_squares,
        board_length,
        kerf
    )

    section.vars['square_width_var'].set(str(square_width))
    section.vars['square_height_var'].set(str(square_height))
    section.vars['horz_pieces_per_strip_var'].set(str(horz_pieces_per))
    section.vars['vert_strips_var'].set(str(len(section.square_strip_cut_list['vertical'])))
    section.vars['horz_strips_var'].set(str(len(section.square_strip_cut_list['horizontal'])))