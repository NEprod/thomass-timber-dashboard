from core.logic.shared.layout_strips import layout_strips

def generate_bead_cut_list(section, square_width, square_height, total_squares, bead_length, panelling_type, wall_width, kerf):
    """
    Generates square bead and under-ledge bead cut lists for a section.
    """
    # Square bead cuts (4 per square)
    square_bead_cuts = []
    for _ in range(total_squares):
        square_bead_cuts.extend([square_width, square_width, square_height, square_height])
    square_bead_cuts.sort(reverse=True)

    square_bead_strips = layout_strips(square_bead_cuts, bead_length, kerf)

    # Optional ledge bead
    ledge_bead_strips = {}
    if "ledge" in panelling_type.lower():
        remaining = wall_width
        ledge_cuts = []
        while remaining > 0:
            piece = min(remaining, bead_length)
            ledge_cuts.append(piece)
            remaining -= piece
        ledge_bead_strips = layout_strips(ledge_cuts, bead_length, kerf)

    section.vars['bead_cut_list'] = {
        "square_beads": square_bead_strips,
        "ledge_beads": ledge_bead_strips
    }

    bead_data = section.vars.get('bead_cut_list', {})

    total_bead_strips = len(square_bead_strips) + len(ledge_bead_strips)
    section.vars['bead_strips_var'] = (str(total_bead_strips))

    # Optional debug
    index = section.vars.get('index', '?')
    print(f"\n[Bead Cut List] Wall Section {index}:")
    print(f"  Square Beads ({len(square_bead_strips)} strips):")
    for strip_name, data in square_bead_strips.items():
        print(f"    {strip_name}: {data['cuts']} | Used: {data['used']:.1f}mm")
    if ledge_bead_strips:
        print(f"  Ledge Beads ({len(ledge_bead_strips)} strips):")
        for strip_name, data in ledge_bead_strips.items():
            print(f"    {strip_name}: {data['cuts']} | Used: {data['used']:.1f}mm")

def generate_bead_cut_list_stair(section, flat_dims, angled_dims, bead_length, panelling_type, wall_width, kerf):
    """
    Handles bead cut list generation for stair sections with both flat and angled/transition squares.
    
    - flat_dims: tuple (square_width, square_height, count)
    - angled_dims: tuple (angled_width, angled_height, count)
    """
    # --- Unpack dimensions ---
    flat_width, flat_height, flat_count = flat_dims
    angled_width, angled_height, angled_count = angled_dims

    # --- Prepare square bead cuts ---
    flat_beads = []
    for _ in range(flat_count):
        flat_beads.extend([flat_width, flat_width, flat_height, flat_height])
    angled_beads = []
    for _ in range(angled_count):
        angled_beads.extend([angled_width, angled_width, angled_height, angled_height])

    # --- Sort and pack ---
    flat_beads.sort(reverse=True)
    angled_beads.sort(reverse=True)

    flat_bead_strips = layout_strips(flat_beads, bead_length, kerf)
    angled_bead_strips = layout_strips(angled_beads, bead_length, kerf)

    # --- Ledge beads (once only) ---
    ledge_bead_strips = {}
    if "ledge" in panelling_type.lower():
        remaining = wall_width
        ledge_cuts = []
        while remaining > 0:
            piece = min(remaining, bead_length)
            ledge_cuts.append(piece)
            remaining -= piece
        ledge_bead_strips = layout_strips(ledge_cuts, bead_length, kerf)

    # --- Save to section vars ---
    section.vars['bead_cut_list'] = {
        "flat_square_beads": flat_bead_strips,
        "angled_square_beads": angled_bead_strips,
        "ledge_beads": ledge_bead_strips
    }

    total_bead_strips = len(flat_bead_strips) + len(angled_bead_strips) + len(ledge_bead_strips)
    section.vars['bead_strips_var'] = (str(total_bead_strips))

    # --- Terminal output ---
    index = section.vars.get('index', '?')
    print(f"\n[Bead Cut List] Stair Section {index} — Half Wall Panelling:")
    
    print(f"  Flat Square Beads ({len(flat_bead_strips)} strips):")
    for name, data in flat_bead_strips.items():
        print(f"    {name}: {data['cuts']} | Used: {data['used']:.1f}mm")

    print(f"  Angled / Transition Square Beads ({len(angled_bead_strips)} strips):")
    for name, data in angled_bead_strips.items():
        print(f"    {name}: {data['cuts']} | Used: {data['used']:.1f}mm")

    if ledge_bead_strips:
        print(f"  Ledge Beads ({len(ledge_bead_strips)} strips):")
        for name, data in ledge_bead_strips.items():
            print(f"    {name}: {data['cuts']} | Used: {data['used']:.1f}mm")