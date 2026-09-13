from core.logic.shared.layout_strips import layout_strips

def calc_ledge_half(section, wall_width, board_length, kerf):
    """
    Calculates MDF cut list for ledge strips in half wall panelling.
    Stores result in section.ledge_cut_list and updates ledge_strips_var.
    """
    remaining = wall_width
    cuts = []

    while remaining > 0:
        piece = min(remaining, board_length)
        cuts.append(piece)
        remaining -= piece

    cut_list = layout_strips(cuts, board_length, kerf)
    section.ledge_cut_list = cut_list
    section.vars["ledge_strips_var"].set(str(len(cut_list)))

    # Optional debug
    index = section.vars.get("index", "?")
    print(f"\n[MDF Ledge Cut List] Wall Section {index}:")
    for name, data in cut_list.items():
        print(f"  {name}: {data['cuts']} | Used: {data['used']:.1f}mm")

def calc_ledge_stair(section, wall_width, board_length, kerf):
    """
    Calculates MDF cut list for ledge strips in half wall panelling.
    Stores result in section.ledge_cut_list and updates ledge_strips_var.
    """
    remaining = wall_width
    cuts = []

    while remaining > 0:
        piece = min(remaining, board_length)
        cuts.append(piece)
        remaining -= piece

    cut_list = layout_strips(cuts, board_length, kerf)
    section.ledge_cut_list = cut_list
    section.vars["ledge_strips_var"].set(str(len(cut_list)))

    # Optional debug
    index = section.vars.get("index", "?")
    print(f"\n[MDF Ledge Cut List] Stair Section {index}:")
    for name, data in cut_list.items():
        print(f"  {name}: {data['cuts']} | Used: {data['used']:.1f}mm")