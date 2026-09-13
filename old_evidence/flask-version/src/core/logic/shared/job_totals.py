import math

def calculate_job_totals(
    board_cost, bead_cost, mastic_cost, cut_cost, delivery_cost,
    panelling_lm, bead_ledge_lm,
    full_days, extra_hours,
    mdf_slat_rate, bead_ledge_rate,
    day_rate, hourly_rate
):
    """
    Calculates job total costs.

    Returns a dictionary with:
    - material_cost
    - labour_cost
    - take_home
    - final_price
    """

    # --- Labour cost from linear meterage ---
    labour_cost = round((panelling_lm * mdf_slat_rate) + (bead_ledge_lm * bead_ledge_rate), 2)

    # --- Time-based fallback take home ---
    fallback_take_home = round((full_days * day_rate) + (extra_hours * hourly_rate), 2)

    # --- Take home: higher of labour or fallback ---
    take_home = max(labour_cost, fallback_take_home)

    # --- Material cost ---
    material_cost = round(board_cost + bead_cost + mastic_cost + cut_cost + delivery_cost, 2)

    # --- Final job price (rounded to nearest £10) ---
    final_price = math.ceil((material_cost + take_home) / 10) * 10

    return {
        "material_cost": round(material_cost, 2),
        "labour_cost": round(labour_cost, 2),
        "take_home": round(take_home, 2),
        "final_price": round(final_price, 2)
    }