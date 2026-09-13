def layout_strips(cuts, material_length, kerf):
    """
    Packs a list of cuts into strips minimizing waste.

    Args:
        cuts (list of float): List of cut lengths.
        board_length (int): Usable length of a board (mm).
        kerf (int): Width lost to each cut (mm).

    Returns:
        dict: Mapping of strip names to cut details.
    """
    strips = []
    for cut in sorted(cuts, reverse=True):
        placed = False
        for strip in strips:
            current_total = sum(strip) + kerf * len(strip)
            if current_total + cut + kerf <= material_length:
                strip.append(cut)
                placed = True
                break
        if not placed:
            strips.append([cut])
    return {
        f"Strip {i+1}": {
            "cuts": strip,
            "used": sum(strip) + kerf * (len(strip) - 1 if len(strip) > 1 else 0)
        } for i, strip in enumerate(strips)
    }