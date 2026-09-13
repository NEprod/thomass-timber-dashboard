import math

def update_material_totals(sections, slat_thickness, slat_width, ledge_width, bead_length, board_length, board_width, kerf, board_cost_each, bead_cost_each, mastic_unit_price, cut_cost_per_strip, delivery_cost, mastic_linear_coverage):
    """
    Calculates and updates all material usage and cost totals based on current wall sections.
    """

    total_hv_strips = 0
    total_ledge_strips = 0
    total_bead_strips = 0
    total_linear_m_panelling = 0
    total_linear_m_bead_ledge = 0

    for section in sections:
        # MDF cut lists
        if 'square_strip_cut_list' in section:
            for group in ['vertical', 'horizontal']:
                strips = section['square_strip_cut_list'].get(group, {})
                total_hv_strips += len(strips)
                total_linear_m_panelling = total_hv_strips * (board_length/1000)

        if 'half_square_strip_cut_list' in section:
            for group, is_ledge in [
                ('top_and_bottom_horizontal', False),
                ('middle_horizontal', False),
                ('vertical', False),
                ('ledge', True)
            ]:
                strips = section['half_square_strip_cut_list'].get(group, {})
                if is_ledge:
                    total_ledge_strips += len(strips)
                    total_linear_m_bead_ledge = total_bead_strips * (bead_length/1000)
                else:
                    total_hv_strips += len(strips)
                    total_linear_m_panelling = total_hv_strips * (board_length/1000)

        # Bead strips
        bead_strips = section.get('bead_cut_list', {})
        for group in ['square_beads', 'ledge_beads']:
            strips = bead_strips.get(group, {})
            total_bead_strips += len(strips)
            total_linear_m_bead_ledge = total_bead_strips * (bead_length/1000)

    # Strip counts
    combined_strips = total_hv_strips + total_ledge_strips

    # --- Accurate kerf-aware calculation for strips per board ---
    try:
        boards_needed = calc_boards_needed(
            board_width=board_width,
            slat_count=total_hv_strips,
            slat_width=slat_width,
            ledge_count=total_ledge_strips,
            ledge_width=ledge_width,
            kerf=kerf
        )

        if total_hv_strips > 0 or total_ledge_strips > 0:
            board_cut_summary = generate_board_cut_layout(
                total_slat_strips=total_hv_strips,
                total_ledge_strips=total_ledge_strips,
                slat_width=slat_width,
                ledge_width=ledge_width,
                board_width=board_width,
                kerf=kerf
            )
        else:
            board_cut_summary = {}
    except:
        boards_needed = 0

    # --- Cost calculations ---
    mastic_needed = math.ceil((total_linear_m_panelling + total_linear_m_bead_ledge) / mastic_linear_coverage * 1.5)

    return {
        "total_hv_strips": total_hv_strips,
        "ledge_strips": total_ledge_strips,
        "boards_needed": boards_needed,
        "board_cost": round(boards_needed * board_cost_each, 2),
        "beads_needed": total_bead_strips,
        "bead_cost": round(total_bead_strips * bead_cost_each, 2),
        "linear_meterage_panelling": round(total_linear_m_panelling, 2),
        "linear_meterage_beading_ledge": round(total_linear_m_bead_ledge, 2),
        "mastic_needed": mastic_needed,
        "mastic_cost": round(mastic_needed * mastic_unit_price, 2),
        "cut_cost": round((combined_strips + 1) * cut_cost_per_strip, 2),
        "delivery_cost": round(delivery_cost, 2),
        "board_cut_summary": board_cut_summary
    }

def calc_boards_needed(board_width, slat_count, slat_width, ledge_count, ledge_width, kerf):
    """
    Simulates cutting both slats and ledges from shared boards to minimize waste.
    Returns the number of boards needed.
    """
    remaining_strips = (["slat"] * slat_count) + (["ledge"] * ledge_count)
    board_count = 0

    while remaining_strips:
        board_used = 0
        cut_count = 0
        board_count += 1

        # While we can fit more strips on this board
        i = 0
        while i < len(remaining_strips):
            w = slat_width if remaining_strips[i] == "slat" else ledge_width
            if board_used + w <= board_width:
                board_used += w + kerf
                del remaining_strips[i]
                cut_count += 1
            else:
                i += 1  # Try next strip on a new board
                
    return board_count

def generate_board_cut_layout(total_slat_strips, total_ledge_strips, slat_width, ledge_width, board_width, kerf):
    """
    Efficiently packs slat and ledge strips onto boards.
    Returns a dict of board cut layouts like:
    {
        "Board 1": {"cuts": [100, 100, 65], "used": 271},
        ...
    }
    """
    boards = []
    board_index = 1

    slats_left = total_slat_strips
    ledges_left = total_ledge_strips

    while slats_left > 0 or ledges_left > 0:
        available_width = board_width
        cuts = []

        # --- Add as many slat strips as fit ---
        while slats_left > 0:
            required = slat_width + (kerf if cuts else 0)
            if available_width >= required:
                cuts.append(slat_width)
                available_width -= required
                slats_left -= 1
            else:
                break

        # --- Fill remaining space with ledge strips ---
        while ledges_left > 0:
            required = ledge_width + (kerf if cuts else 0)
            if available_width >= required:
                cuts.append(ledge_width)
                available_width -= required
                ledges_left -= 1
            else:
                break

        # --- Finalize this board ---
        used_total = sum(cuts) + (kerf * (len(cuts) - 1 if len(cuts) > 1 else 0))
        boards.append({
            "cuts": cuts,
            "used": round(used_total, 2)
        })
        board_index += 1

    return {
        "total": len(boards),
        "boards": boards
    }