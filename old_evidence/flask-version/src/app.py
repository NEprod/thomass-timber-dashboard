from flask import Flask, render_template, jsonify, request
from core.logic.full_wall.calc_full_wall import calc_square_full
from core.logic.shared.bead_calculations import generate_bead_cut_list
from core.logic.shared.materials_totals import update_material_totals
from core.logic.shared.job_totals import calculate_job_totals
import sqlite3
import os

app = Flask(__name__)

def get_square_dado_options():
    sql_path = os.path.join("sql", "get_square_dado_options.sql")
    with open(sql_path, "r") as f:
        query = f.read()

    conn = sqlite3.connect("databases/dado_options.db")
    cursor = conn.cursor()
    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()
    return [row[0] for row in results]

@app.route("/api/square_dado_options")
def square_dado_options():
    options = get_square_dado_options()
    return jsonify(options)

def get_middle_dado_options():
    sql_path = os.path.join("sql", "get_middle_dado_options.sql")
    with open(sql_path, "r") as f:
        query = f.read()

    conn = sqlite3.connect("databases/dado_options.db")
    cursor = conn.cursor()
    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()
    return [row[0] for row in results]

@app.route("/api/middle_dado_options")
def middle_dado_options():
    options = get_middle_dado_options()
    return jsonify(options)

def get_mdf_thicknesses():
    # Load the SQL query from file
    sql_path = os.path.join("sql", "get_mdf_thicknesses.sql")
    with open(sql_path, "r") as f:
        query = f.read()

    # Execute the query
    conn = sqlite3.connect("databases/mdf_options.db")
    cursor = conn.cursor()
    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()
    return [row[0] for row in results]

@app.route("/api/mdf_thicknesses")
def mdf_thicknesses():
    thicknesses = get_mdf_thicknesses()
    return jsonify(thicknesses)

def get_moulding_labels(thickness):
    sql_path = os.path.join("sql", "get_moulding_labels_by_thickness.sql")
    with open(sql_path, "r") as f:
        query = f.read()

    conn = sqlite3.connect("databases/moulding_options.db")
    cursor = conn.cursor()

    # Pass thickness as a dictionary with the same key used in the SQL file
    cursor.execute(query, {"thickness": thickness})

    results = cursor.fetchall()
    conn.close()
    return [row[0] for row in results]

@app.route("/api/mouldings")
def mouldings():
    thickness = request.args.get("thickness", type=int)
    if thickness is None:
        return jsonify([])
    
    labels = get_moulding_labels(thickness)
    return jsonify(labels)

def get_board_length(thickness):
    sql_path = os.path.join("sql", "get_board_length.sql")
    with open(sql_path, "r") as f:
        query = f.read()

    conn = sqlite3.connect("databases/mdf_options.db")
    cursor = conn.cursor()

    # Pass thickness as a dictionary with the same key used in the SQL file
    cursor.execute(query, {"thickness": thickness})

    results = cursor.fetchall()
    conn.close()
    return [row[0] for row in results]

@app.route("/api/board_length")
def board_length():
    thickness = request.args.get("thickness", type=int)
    if thickness is None:
        return jsonify([])

    lengths = get_board_length(thickness)
    return jsonify(lengths)

def get_board_width(thickness):
    sql_path = os.path.join("sql", "get_board_width.sql")
    with open(sql_path, "r") as f:
        query = f.read()

    conn = sqlite3.connect("databases/mdf_options.db")
    cursor = conn.cursor()

    # Pass thickness as a dictionary with the same key used in the SQL file
    cursor.execute(query, {"thickness": thickness})

    results = cursor.fetchall()
    conn.close()
    return [row[0] for row in results]

@app.route("/api/board_width")
def board_width():
    thickness = request.args.get("thickness", type=int)
    if thickness is None:
        return jsonify([])

    lengths = get_board_width(thickness)
    return jsonify(lengths)

def get_bead_length(moulding_type):
    sql_path = os.path.join("sql", "get_bead_length.sql")
    with open(sql_path, "r") as f:
        query = f.read()

    conn = sqlite3.connect("databases/moulding_options.db")
    cursor = conn.cursor()

    # Pass thickness as a dictionary with the same key used in the SQL file
    cursor.execute(query, {"moulding_type": moulding_type})

    results = cursor.fetchall()
    conn.close()
    return [row[0] for row in results]

@app.route("/api/bead_length")
def bead_length():
    moulding_type = request.args.get("moulding_type", type=str)
    if moulding_type is None:
        return jsonify([])

    lengths = get_bead_length(moulding_type)
    return jsonify(lengths)

def get_kerf():
    sql_path = os.path.join("sql", "get_kerf.sql")
    with open(sql_path, "r") as f:
        query = f.read()

    conn = sqlite3.connect("databases/price_config.db")
    cursor = conn.cursor()

    # Pass thickness as a dictionary with the same key used in the SQL file
    cursor.execute(query)

    results = cursor.fetchall()
    conn.close()
    return [row[0] for row in results]

@app.route("/api/get_kerf")
def kerf():
    kerf = get_kerf()
    return jsonify(kerf)

def get_bead_price(moulding_type):
    sql_path = os.path.join("sql", "get_bead_price.sql")
    with open(sql_path, "r") as f:
        query = f.read()

    conn = sqlite3.connect("databases/moulding_options.db")
    cursor = conn.cursor()

    # Pass label as a dictionary with the same key used in the SQL file
    cursor.execute(query, {"moulding_type": moulding_type})

    results = cursor.fetchall()
    conn.close()
    return [row[0] for row in results]

@app.route("/api/bead_price")
def bead_price():
    moulding_type = request.args.get("moulding_type", type=str)
    if moulding_type is None:
        return jsonify([])

    price = get_bead_price(moulding_type)
    return jsonify(price)

def get_board_price(thickness):
    sql_path = os.path.join("sql", "get_board_price.sql")
    with open(sql_path, "r") as f:
        query = f.read()

    conn = sqlite3.connect("databases/mdf_options.db")
    cursor = conn.cursor()

    # Pass thickness as a dictionary with the same key used in the SQL file
    cursor.execute(query, {"thickness": thickness})

    results = cursor.fetchall()
    conn.close()
    return [row[0] for row in results]

@app.route("/api/board_price")
def board_price():
    thickness = request.args.get("thickness", type=int)
    if thickness is None:
        return jsonify([])

    price = get_board_price(thickness)
    return jsonify(price)

def get_cut_price():
    sql_path = os.path.join("sql", "get_cut_price.sql")
    with open(sql_path, "r") as f:
        query = f.read()

    conn = sqlite3.connect("databases/price_config.db")
    cursor = conn.cursor()
    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()
    return [row[0] for row in results]

@app.route("/api/cut_price")
def cut_price():
    cut_price = get_cut_price()
    return jsonify(cut_price)

def get_delivery_cost():
    sql_path = os.path.join("sql", "get_delivery_cost.sql")
    with open(sql_path, "r") as f:
        query = f.read()

    conn = sqlite3.connect("databases/price_config.db")
    cursor = conn.cursor()
    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()
    return [row[0] for row in results]

@app.route("/api/delivery_cost")
def delivery_cost():
    delivery_cost = get_delivery_cost()
    return jsonify(delivery_cost)

def get_mastic_price():
    sql_path = os.path.join("sql", "get_mastic_price.sql")
    with open(sql_path, "r") as f:
        query = f.read()

    conn = sqlite3.connect("databases/price_config.db")
    cursor = conn.cursor()
    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()
    return [row[0] for row in results]

@app.route("/api/mastic_price")
def mastic_price():
    mastic_price = get_mastic_price()
    return jsonify(mastic_price)

def get_mastic_coverage():
    sql_path = os.path.join("sql", "get_mastic_coverage.sql")
    with open(sql_path, "r") as f:
        query = f.read()

    conn = sqlite3.connect("databases/price_config.db")
    cursor = conn.cursor()
    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()
    return [row[0] for row in results]

@app.route("/api/mastic_coverage")
def mastic_coverage():
    mastic_coverage = get_mastic_coverage()
    return jsonify(mastic_coverage)

def get_day_rate():
    sql_path = os.path.join("sql", "get_day_rate.sql")
    with open(sql_path, "r") as f:
        query = f.read()

    conn = sqlite3.connect("databases/price_config.db")
    cursor = conn.cursor()
    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()
    return [row[0] for row in results]

@app.route("/api/day_rate")
def day_rate():
    day_rate = get_day_rate()
    return jsonify(day_rate)

def get_hourly_rate():
    sql_path = os.path.join("sql", "get_hourly_rate.sql")
    with open(sql_path, "r") as f:
        query = f.read()

    conn = sqlite3.connect("databases/price_config.db")
    cursor = conn.cursor()
    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()
    return [row[0] for row in results]

@app.route("/api/hourly_rate")
def hourly_rate():
    hourly_rate = get_hourly_rate()
    return jsonify(hourly_rate)

def get_mdf_slat_per_m():
    sql_path = os.path.join("sql", "get_mdf_slat_per_m.sql")
    with open(sql_path, "r") as f:
        query = f.read()

    conn = sqlite3.connect("databases/price_config.db")
    cursor = conn.cursor()
    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()
    return [row[0] for row in results]

@app.route("/api/mdf_slat_per_m")
def mdf_slat_per_m():
    mdf_slat_per_m = get_mdf_slat_per_m()
    return jsonify(mdf_slat_per_m)

def get_bead_per_m():
    sql_path = os.path.join("sql", "get_bead_per_m.sql")
    with open(sql_path, "r") as f:
        query = f.read()

    conn = sqlite3.connect("databases/price_config.db")
    cursor = conn.cursor()
    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()
    return [row[0] for row in results]

@app.route("/api/bead_per_m")
def bead_per_m():
    bead_per_m = get_bead_per_m()
    return jsonify(bead_per_m)

@app.route("/api/calculate/full_wall", methods=["POST"])
def calculate_full_wall():
    data = request.get_json()

    # Extract values from the request
    wall_width = data.get("wall_width")
    wall_height = data.get("wall_height")
    horz_squares = data.get("horz_squares")
    vert_squares = data.get("vert_squares")
    slat_width = data.get("slat_width")
    panel_type = data.get("panel_type", "")
    board_length = data.get("board_length")
    bead_length = data.get("bead_length")
    kerf = data.get("kerf")
    section_index = data.get("section_id")

    # Create a simulated "section" object
    section = type("Section", (), {})()
    section.vars = {"index": section_index}
    section.square_strip_cut_list = {}

    # Run the MDF calculation logic
    calc_square_full(
        section,
        wall_width,
        wall_height,
        horz_squares,
        vert_squares,
        slat_width,
        board_length,
        kerf
    )

    # If panel type mentions bead, calculate bead cut list too
    if "bead" in panel_type.lower():
        square_width = float(section.vars['square_width_var'])
        square_height = float(section.vars['square_height_var'])
        total_squares = horz_squares * vert_squares
        generate_bead_cut_list(
            section,
            square_width,
            square_height,
            total_squares,
            bead_length,
            panel_type,
            wall_width,
            kerf
        )

    # Return key values for the front end
    return jsonify({
        "square_width": section.vars['square_width_var'],
        "square_height": section.vars['square_height_var'],
        "horz_strips": section.vars['horz_strips_var'],
        "vert_strips": section.vars['vert_strips_var'],
        "horz_pieces_per_strip": section.vars['horz_pieces_per_strip_var'],
        "bead_strips": section.vars.get('bead_strips_var', ""),
        "square_strip_cut_list": section.square_strip_cut_list,
        "bead_cut_list": section.vars.get('bead_cut_list', {})
    })

@app.route("/api/material_totals/full_wall", methods=["POST"])
def material_totals_full_wall():
    data = request.get_json()
    try:
        results = update_material_totals(**data)
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/job_totals", methods=["POST"])
def api_job_totals():
    data = request.get_json()
    try:
        result = calculate_job_totals(**data)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def dashboard():
    return render_template("base.html")

@app.route("/quote")
def quote_form():
    return render_template("quote_form.html")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=2112, debug=True)