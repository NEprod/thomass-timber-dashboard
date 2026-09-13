import math
from core.logic.shared.layout_strips import layout_strips

def calc_stair_half(
    section,
    wall_width,
    panel_height,
    lower_landing_length,
    upper_landing_length,
    slope_length,
    horz_squares,
    vert_squares,
    slat_width,
    board_length,
    kerf
):
    """
    Main controller for stair panelling calculations.
    Derives all square counts and dimensions from physical inputs.
    Updates GUI fields and builds MDF strip layout.
    """

    # --- Calculate slope geometry ---
    run = wall_width - lower_landing_length - upper_landing_length

    angle_rad = math.acos(run / slope_length)
    angle_deg = round(math.degrees(angle_rad), 2)

    slope_mitre = round(90 - ((180 - angle_deg) / 2), 2)

    acute_angle = round(90 - angle_deg, 2) # eg 50
    acute_mitre = round(90 - (acute_angle / 2), 2) # eg 65

    obtuse_angle = round(180 - acute_angle, 2) # eg 130
    obtuse_mitre = round(90 - (obtuse_angle / 2), 2) # eg 25

    # --- Determine usable square count ---
    square_width = round((wall_width - ((horz_squares + 1) * slat_width)) / horz_squares, 2)
    flat_square_height = round((panel_height - ((vert_squares + 1) * slat_width)) / vert_squares, 2)
    vert_pieces_height = round((panel_height - (slat_width * 2)), 2)

    # --- Calculate angled height using slope angle ---
    angled_height = round(flat_square_height / math.cos(angle_rad), 2)
    vert_angled_height = round(vert_pieces_height / math.cos(angle_rad), 2)
    angled_width = round(square_width / math.cos(angle_rad), 2)

    # --- Classify squares based on position using both landings ---
    squares = []
    used_length = 0
    slope_start = lower_landing_length
    slope_end = wall_width - upper_landing_length

    for i in range(horz_squares):
        x_start = used_length + slat_width
        x_center = x_start + (square_width / 2)
        x_left = x_center - (square_width / 2)
        x_right = x_center + (square_width / 2)

        if x_right <= slope_start:
            square_type = "flat"
        elif x_left >= slope_end:
            square_type = "flat"
        elif x_left < slope_start or x_right > slope_end:
            square_type = "transition"
        else:
            square_type = "angled"

        squares.append({
            "index": i + 1,
            "center_x": x_center,
            "type": square_type
        })

        used_length += slat_width + square_width

    # --- Tally up square types ---
    total_squares = len(squares)
    flat_squares = len([s for s in squares if s["type"] == "flat"])
    angled_squares = len([s for s in squares if s["type"] == "angled"])
    transition_squares = len([s for s in squares if s["type"] == "transition"])

    section.square_layout = squares  # This will allow vertical logic to access detailed layout

    # Optional: store diagnostic
    section.square_layout_summary = {
        "total": total_squares,
        "flat": flat_squares,
        "angled": angled_squares,
        "transition": transition_squares,
        "squares": squares
    }

    # --- Calculate cut list ---
    generate_stair_strip_cut_list_half(
        section,
        upper_landing_length,
        lower_landing_length,
        slope_length,
        angled_width,
        square_width,
        vert_angled_height,
        vert_pieces_height,
        slat_width,
        board_length,
        kerf,
        vert_squares,
    )

    # --- GUI field updates ---
    section.vars['square_width_var'].set(str(square_width))
    section.vars['square_height_var'].set(str(flat_square_height))
    section.vars['angled_square_height_var'].set(str(angled_height))
    section.vars['angled_square_width_var'].set(str(angled_width))

    section.vars['slope_mitre_var'].set(f"{slope_mitre}°")
    section.vars['angled_square_mitres_var'].set(f"{acute_mitre}° (T) / {obtuse_mitre}° (B)")
    section.vars['angled_square_count_var'].set(str(angled_squares))
    section.vars['transition_square_count_var'].set(str(transition_squares))

    cut_data = section.half_square_strip_cut_list
    section.vars['horz_strips_var'].set(str(len(cut_data.get("top_and_bottom_horizontal", {})) + len(cut_data.get("middle_horizontal", {}))))
    section.vars['vert_strips_var'].set(str(len(cut_data.get("vertical", {}))))

    # Pieces per strip
    vertical_piece_len = angled_height
    pieces_per_board_vert = math.floor(board_length / vertical_piece_len) if vertical_piece_len > 0 else 0
    section.vars['vert_pieces_per_strip_var'].set(str(pieces_per_board_vert))

    # Only calculate horizontal middle pieces if multiple rows
    if vert_squares > 1:
        horz_pieces = math.floor(board_length / square_width) if square_width > 0 else 0
        section.vars['horz_pieces_per_strip_var'].set(str(horz_pieces))
    else:
        section.vars['horz_pieces_per_strip_var'].set("0")

def generate_stair_strip_cut_list_half(
    section,
    top_landing_length,
    bottom_landing_length,
    slope_length,
    angled_width,
    square_width,
    angled_height,
    flat_square_height,
    slat_thickness,
    board_length,
    kerf,
    rows
):
    """
    Generates MDF strip cut list for half-wall stair panelling.
    Separately cuts:
    - Top landing
    - Bottom landing
    - Slope run
    - Vertical slats (angled height)
    - Middle horizontal slats (if rows > 1)
    """

    def split_labelled_cuts(label, total_length):
        cuts = []
        remaining = total_length
        first = True
        while remaining > 0:
            if first and remaining >= board_length:
                cut = board_length  # allow full board for first large piece
            elif remaining > board_length:
                cut = board_length - kerf  # greedy cut with room for more
            else:
                cut = remaining  # final cut
            cuts.append(round(cut, 2))
            remaining -= cut
            if remaining > 0:
                remaining -= kerf
            first = False
        return [(label, cut) for cut in cuts]

    # --- Adjusted lengths for overhang/setback logic ---
    undercut_overcut_default = 30
    true_top_upper = top_landing_length + undercut_overcut_default
    true_top_lower = max(0, bottom_landing_length - undercut_overcut_default)  # avoid negative
    true_bottom_upper = top_landing_length
    true_bottom_lower = bottom_landing_length

    # --- Labelled cuts for each segment ---
    top_upper_cuts = split_labelled_cuts("Top (Upper Landing)", true_top_upper)
    top_lower_cuts = split_labelled_cuts("Top (Lower Landing)", true_top_lower)
    bottom_upper_cuts = split_labelled_cuts("Bottom (Upper Landing)", true_bottom_upper)
    bottom_lower_cuts = split_labelled_cuts("Bottom (Lower Landing)", true_bottom_lower)

    # --- Slope cuts (used twice: top and bottom horizontal) ---
    slope_cuts = split_labelled_cuts("Slope", slope_length)
    slope_cuts_twice = slope_cuts * 2

    # --- Combine all horizontal runs ---
    all_horz_cuts = (
        top_upper_cuts +
        top_lower_cuts +
        bottom_upper_cuts +
        bottom_lower_cuts +
        slope_cuts_twice
    )
    all_horz_cuts = sorted(all_horz_cuts, key=lambda x: -x[1])

    # Extract just lengths for layout
    horz_lengths = [length for label, length in all_horz_cuts]
    horz_result = layout_strips(horz_lengths, board_length, kerf)

    # Attach labels back to each cut in each strip
    i = 0
    for strip_data in horz_result.values():
        count = len(strip_data["cuts"])
        strip_data["cut_labels"] = all_horz_cuts[i:i + count]
        i += count

    # --- Vertical angled cuts between battens ---
    vertical_result = generate_vertical_cuts_half_wall_stair(
        section,
        flat_square_height,
        angled_height,
        board_length,
        kerf
        )

    # --- Middle horizontal slats (if needed) ---
    middle_result = {}
    if rows > 1:
        middle_cuts = []
        for square in section.square_layout:
            square_type = square["type"]
            if square_type == "flat":
                length = square_width
                label = "Middle (Flat)"
            else:
                length = angled_width
                label = "Middle (Angled/Trans)"
            for _ in range(rows - 1):
                middle_cuts.append((label, length))

        # Sort longest first
        middle_cuts = sorted(middle_cuts, key=lambda x: -x[1])
        middle_lengths = [length for label, length in middle_cuts]

        middle_result = layout_strips(middle_lengths, board_length, kerf)

        # Attach labels back
        i = 0
        for strip_data in middle_result.values():
            count = len(strip_data["cuts"])
            strip_data["cut_labels"] = middle_cuts[i:i + count]
            i += count

    # --- Store all results ---
    result = {
        "top_and_bottom_horizontal": horz_result,
        "vertical": vertical_result,
        "middle_horizontal": middle_result
    }
    section.half_square_strip_cut_list = result

    # --- Optional: log breakdown ---
    index = section.vars.get('index', '?')
    print(f"\n[MDF Strips Cut List] Stair Section {index} — Half Wall Panelling")
    for key, strips in result.items():
        label = key.replace("_", " ").title()
        print(f"  {label} ({len(strips)} strips):")
        for strip_name, data in strips.items():
            used = data.get("used", 0)
            labels = data.get("cut_labels", [])
            desc = " | ".join([f"{cut:.2f}mm ({label})" for label, cut in labels])
            print(f"    {strip_name}: {desc} | Used: {used:.1f}mm")


def generate_vertical_cuts_half_wall_stair(
    section,
    flat_height,
    angled_height,
    board_length,
    kerf
):
    """
    Generates vertical batten cut list for half-wall stair section.
    Includes logic for flat, angled, and transition squares.
    """

    square_summary = section.square_layout_summary
    total_squares = square_summary["total"]

    vertical_cuts = []

    # Start at the wall edge
    vertical_cuts.append(("Flat", flat_height))

    for i in range(total_squares):
        square_type = section.square_layout[i]["type"]

        if square_type == "flat":
            vertical_cuts.append(("Flat", flat_height))
        elif square_type == "angled":
            vertical_cuts.append(("Angled", angled_height))
        elif square_type == "transition":
            # Decide if this is a top or bottom transition
            if i == 0 or section.square_layout[i - 1]["type"] == "flat":
                vertical_cuts.append(("Angled (Trans)", angled_height))
            else:
                vertical_cuts.append(("Flat (Trans)", flat_height))

    # Extract lengths for layout
    vertical_cuts = sorted(vertical_cuts, key=lambda x: -x[1])  # sort by length DESC
    vertical_lengths = [length for label, length in vertical_cuts]

    # Create layout
    vertical_result = layout_strips(vertical_lengths, board_length, kerf)

    # Attach labels
    i = 0
    for strip_data in vertical_result.values():
        count = len(strip_data["cuts"])
        strip_data["cut_labels"] = vertical_cuts[i:i + count]
        i += count

    return vertical_result