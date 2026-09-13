import math
from core.logic.shared.layout_strips import layout_strips

def calc_square_half(section, wall_width, panel_height, horz_squares, vert_squares, slat_width, board_length, kerf=3):
    """
    Calculates square layout and MDF usage for half wall panelling.
    Stores all strip groups (horizontal, vertical, middle) in section.half_square_strip_cut_list.
    """

    # --- Square Dimensions ---
    square_width = round((wall_width - ((horz_squares + 1) * slat_width)) / horz_squares, 2)
    square_height = round((panel_height - ((vert_squares + 1) * slat_width)) / vert_squares, 2)

    # --- Strip Packing ---
    generate_square_strip_cut_list_half(
        section,
        wall_width,
        panel_height,
        horz_squares,
        vert_squares,
        square_width,
        slat_width,
        board_length,
        kerf
    )

    # --- GUI Output ---
    section.vars['square_width_var'].set(str(square_width))
    section.vars['square_height_var'].set(str(square_height))

    cut_data = section.half_square_strip_cut_list

    # Horizontal strips = top + bottom + middle
    h1 = len(cut_data.get("top_and_bottom_horizontal", {}))
    h2 = len(cut_data.get("middle_horizontal", {}))
    section.vars['horz_strips_var'].set(str(h1 + h2))

    # Vertical
    v_strips = len(cut_data.get("vertical", {}))
    section.vars['vert_strips_var'].set(str(v_strips))

    # Pieces per board
    vertical_piece_len = panel_height - (2 * slat_width)
    pieces_per_board = math.floor(board_length / vertical_piece_len) if vertical_piece_len > 0 else 0
    section.vars['vert_pieces_per_strip_var'].set(str(pieces_per_board))

    # Horizontal pieces per strip (middle slats only)
    if vert_squares > 1:
        horz_pieces = math.floor(board_length / square_width)
        section.vars['horz_pieces_per_strip_var'].set(str(horz_pieces))
    else:
        section.vars['horz_pieces_per_strip_var'].set("0")

def generate_square_strip_cut_list_half(section, wall_width, panel_height, horz_squares, vert_squares, square_width, slat_thickness, board_length, kerf):
    """
        Generates a detailed MDF strip cutting list for half-wall square panelling.
        Includes:
        - Top and bottom horizontal slats
        - Vertical slats (between squares)
        - Middle horizontal slats (optional, between rows)

        Results are stored in section.half_square_strip_cut_list
        """

    # --- Helper: Join long lengths into multiple segments ---
    def split_into_joinable_pieces(length):
        segments = []
        remaining = length
        while remaining > 0:
            piece = min(remaining, board_length)
            segments.append(piece)
            remaining -= piece
        return segments

    # --- Horizontal: top + bottom (full wall width) ---
    top_cuts = split_into_joinable_pieces(wall_width)
    bottom_cuts = split_into_joinable_pieces(wall_width)
    top_bottom_cuts = top_cuts + bottom_cuts

    # --- Vertical: one between each square (shorter than full height) ---
    vertical_height = panel_height - (2 * slat_thickness)
    vertical_cuts = [vertical_height] * (horz_squares + 1)

    # --- Middle Horizontal: only if >1 row ---
    middle_horizontal_cuts = []
    if vert_squares > 1:
        middle_horizontal_cuts = [square_width] * ((vert_squares - 1) * horz_squares)

    result = {
        "top_and_bottom_horizontal": layout_strips(top_bottom_cuts, board_length, kerf),
        "vertical": layout_strips(vertical_cuts, board_length, kerf),
        "middle_horizontal": layout_strips(middle_horizontal_cuts, board_length, kerf) if middle_horizontal_cuts else {}
    }

    section.half_square_strip_cut_list = result

    # Optional debug
    index = section.vars.get('index', '?')
    print(f"\n[MDF Strips Cut List] Wall Section {index} — Half Wall Panelling")
    for key, strips in result.items():
        label = key.replace("_", " ").title()
        print(f"  {label} ({len(strips)} strips):")
        for strip_name, data in strips.items():
            cuts = data["cuts"]
            used = data["used"]
            print(f"    {strip_name}: {cuts} | Used: {used:.1f}mm")