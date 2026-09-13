import os
import json
import math
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox, simpledialog

def get_json_data(filename, folder="json"):
    """
    Load and return JSON data from a file inside a relative folder.
    Defaults to looking inside a 'json' folder located one level up from this script.
    
    Args:
        filename (str): The name of the JSON file to load.
        folder (str): The folder name where the JSON file is stored.

    Returns:
        dict: Parsed JSON content from the specified file.
    """
    base_dir = os.path.dirname(__file__) # Get the directory of this script
    full_path = os.path.abspath(os.path.join(base_dir, "..", folder, filename)) # Resolve the full absolute path to the JSON
    with open(full_path, "r") as f:
        return json.load(f) # Parse and return the JSON as a Python dictionary

class SquarePanellingWindow(tk.Toplevel):
    """
    Main GUI window for calculating square panelling strip requirements.

    This class builds a standalone window (child of a Tkinter root) where the user
    can enter wall dimensions, select panelling styles, choose moulding and ledge types,
    and receive calculated strip counts and cut lists for MDF and bead materials.
    """
    def __init__(self, parent, log=None):
        """
        Initialise the panelling tool window.

        Args:
            parent (tk.Widget): The parent Tkinter window or root.
            log (callable, optional): Optional logging function to pipe messages into an external UI log box.
        """
        super().__init__(parent)  # Create the window as a child of the parent widget
        self.title("Square Panelling Measurements")
        self.geometry("800x900")  # Fixed window size
        self.resizable(False, False)  # Prevent resizing
        self.log = log  # Optional log output to external text box

        # Load material and moulding data from local JSON files
        self.moulding_data = get_json_data("moulding_prices.json")
        self.material_data = get_json_data("material_prices.json")
        self.pricing_data = get_json_data("pricing_config.json")

        # Build the full GUI layout and input form
        self.build_window()

    def update_job_totals(self):
        """
        Calculates and updates the final job cost totals:
        - Material cost (from visible material totals)
        - Labour cost (based on linear meterage × per-m rate)
        - Take home (greater of labour or calculated day/hour rate)
        - Final price (rounded to nearest £10)
        """
        pricing = self.pricing_data

        # --- Pull relevant prices ---
        mdf_slat_rate = pricing.get("mdf_slat_per_m_gbp", 0)
        bead_ledge_rate = pricing.get("bead_per_m_gbp", 0)  # Combined rate for bead + ledge
        day_rate = pricing.get("day_rate", 180)
        hourly_rate = pricing.get("hourly_rate", 22.5)

        # --- Get linear meterages from GUI ---
        try:
            panelling_m = float(self.material_totals["linear_meterage_panelling_var"].get().replace("m", "").strip())
        except:
            panelling_m = 0

        try:
            bead_ledge_m = float(self.material_totals["linear_meterage_beading_ledge_var"].get().replace("m", "").strip())
        except:
            bead_ledge_m = 0

        # --- Calculate labour cost ---
        labour_cost = round((panelling_m * mdf_slat_rate) + (bead_ledge_m * bead_ledge_rate), 2)
        

        # --- Take Home (higher of labour vs time-based rate) ---
        try:
            full_days = float(self.full_days_var.get())
        except:
            full_days = 0

        try:
            extra_hours = float(self.extra_hours_var.get())
        except:
            extra_hours = 0

        # Calculate fallback take home from time
        day_rate = self.pricing_data.get("day_rate", 180.00)
        hourly_rate = self.pricing_data.get("hourly_rate", 22.5)

        fallback_take_home = round((full_days * day_rate) + (extra_hours * hourly_rate), 2)

        # Final take home is higher of labour-based vs fallback
        take_home = max(labour_cost, fallback_take_home)

        # --- Material cost from visible fields ---
        def parse_cost(field):
            try:
                return float(self.material_totals[field].get().replace("£", "").strip())
            except:
                return 0.0

        material_cost = sum([
            parse_cost("board_cost_var"),
            parse_cost("bead_cost_var"),
            parse_cost("mastic_cost_var"),
            parse_cost("cut_cost_var"),
            parse_cost("delivery_cost_var")
        ])

        # --- Final job price ---

        final_price = math.ceil((material_cost + take_home) / 10) * 10

        # --- Update GUI ---
        self.job_totals["material_cost_var"].set(f"£{material_cost:.2f}")
        self.job_totals["labour_cost_var"].set(f"£{labour_cost:.2f}")
        self.job_totals["take_home_var"].set(f"£{take_home:.2f}")
        self.job_totals["price_of_job_var"].set(f"£{final_price}")

    def generate_board_cut_layout(self, total_slat_strips, total_ledge_strips, slat_width, ledge_width, board_width, kerf):
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

    def update_cut_list_display(self):
        """
        Updates the cut list display based on the current wall_sections.
        Intended to be triggered manually after measurement entry is complete.
        """

        if not hasattr(self, "measurements") or not hasattr(self, "cut_list_textbox"):
            return

        output = []

        for idx, section in enumerate(self.measurements):
            job_type = section.get("job_label", "Unknown")
            output.append(f"[MDF Strips Cut List] Wall Section {idx + 1} — {job_type}")

            # --- Full Wall Panelling ---
            cut_list = section.get("square_strip_cut_list", {})
            if cut_list:
                for group_name, strips in cut_list.items():
                    if strips:
                        output.append(f"  {group_name.replace('_', ' ').capitalize()} ({len(strips)} strips):")
                        for strip_name, data in strips.items():
                            output.append(f"    {strip_name}: {data['cuts']} | Used: {data['used']}mm")

            # --- Half Wall Panelling ---
            half_cut_list = section.get("half_square_strip_cut_list", {})
            for group_key, group_title in [
                ("top_and_bottom_horizontal", "Top & Bottom Horizontal"),
                ("vertical", "Vertical"),
                ("middle_horizontal", "Middle Horizontal")
            ]:
                strips = half_cut_list.get(group_key, {})
                if strips:
                    output.append(f"  {group_title} ({len(strips)} strips):")
                    for i, data in enumerate(strips.values(), start=1):
                        output.append(f"    Strip {i}: {data['cuts']} | Used: {data['used']}mm")

            # --- Ledge Strips ---
            ledges = half_cut_list.get("ledge", {})
            if ledges:
                output.append(f"\n[MDF Strips Cut List] Wall Section {idx + 1} — Ledge")
                output.append(f"  Ledge ({len(ledges)} strips):")
                for i, data in enumerate(ledges.values(), start=1):
                    output.append(f"    Strip {i}: {data['cuts']} | Used: {data['used']}mm")

            # --- Beading ---
            bead_list = section.get("bead_cut_list", {})
            if bead_list:
                output.append(f"\n[Bead Cut List] Wall Section {idx + 1}:")
                for bead_key, bead_title in [
                    ("square_beads", "Square Beads"),
                    ("ledge_beads", "Ledge Beads")
                ]:
                    strips = bead_list.get(bead_key, {})
                    if strips:
                        output.append(f"  {bead_title} ({len(strips)} strips):")
                        for i, data in enumerate(strips.values(), start=1):
                            output.append(f"    Strip {i}: {data['cuts']} | Used: {data['used']}mm")


            output.append("\n" + "-" * 60 + "\n")

        # Optionally add board summary if you build one later
        if hasattr(self, "board_cut_summary") and self.board_cut_summary:
            output.append(self.format_board_cut_summary())

        # Clear and update display
        self.cut_list_textbox.config(state="normal")
        self.cut_list_textbox.delete("1.0", tk.END)
        self.cut_list_textbox.insert("1.0", "\n".join(output))
        self.cut_list_textbox.config(state="disabled")

    def format_board_cut_summary(self):
        """
        Converts self.board_cut_summary into formatted lines for cut list display.
        """
        summary = self.board_cut_summary
        if not summary or "boards" not in summary:
            return ""

        output = []
        output.append("[MDF Board Cut List] All Walls")
        output.append(f"  Boards ({summary['total']} boards)")
        for idx, board in enumerate(summary["boards"], start=1):
            cuts = board["cuts"]
            used = board["used"]
            output.append(f"    Board {idx}: {cuts} | Used: {used}mm")

        output.append("\n" + "-" * 60 + "\n")
        return "\n".join(output)
    
    def clear_customer_details(self):
        # Clear customer/job details
        for var in self.job_details.values():
            var.set("")

        self.clear_measurements()
    
    def clear_job_totals(self):
        """
        Clears all job total and customer detail fields in the GUI.
        Currency fields are reset to '£0.00'.
        """
        # Clear job totals (reset currency values)
        self.job_totals["material_cost_var"].set("£0.00")
        self.job_totals["labour_cost_var"].set("£0.00")
        self.job_totals["take_home_var"].set("£0.00")
        self.job_totals["price_of_job_var"].set("£0.00")

    def clear_measurements(self):
        """
        Clear all user-entered and calculated values from all wall sections.
        This is used when switching panelling modes or clearing the form.
        """
        for section in self.measurements:
            # Clear all StringVar fields
            for var in section.values():
                if isinstance(var, tk.StringVar):
                    var.set("")  # Clear text entries

            # Remove calculated or temporary data
            for key in [
                "square_strip_cut_list",
                "half_square_strip_cut_list",
                "bead_cut_list",
                "job_label",
            ]:
                section.pop(key, None)
            
            self.clear_material_totals()
            self.clear_job_totals()
        
    def clear_material_totals(self):
        """
        Clears all material total fields in the GUI.
        """
        fields = self.material_totals
        fields["total_hv_strips_var"].set("0")
        fields["ledge_strips_var"].set("0")
        fields["boards_needed_var"].set("0")
        fields["board_cost_var"].set("£0.00")
        fields["beads_needed_var"].set("0")
        fields["bead_cost_var"].set("£0.00")
        fields["linear_meterage_panelling_var"].set("0.00m")
        fields["linear_meterage_beading_ledge_var"].set("0.00m")
        fields["mastic_needed_var"].set("0")
        fields["mastic_cost_var"].set("£0.00")
        fields["cut_cost_var"].set("£0.00")
        fields["delivery_cost_var"].set("£0.00")  # default fixed cost if desired

    def check_for_half_square_wall(self, *arg):
        """
        Show or hide extra input fields based on the selected panelling type.

        - For half wall panelling, shows vertical pieces per strip.
        - For ledge/bead combinations, shows extra material rows.
        """
        selected_panelling = self.square_panelling_type_var.get().lower()

        for section in self.measurements:
            if "square half" in selected_panelling:
                # Show "Vertical Pieces Per Strip" fields (only relevant for half walls)
                section["vert_pieces_label"].grid(row=4, column=2, sticky="w", pady=(15,0))
                section["vert_pieces_entry"].grid(row=4, column=3, sticky="ew", pady=(15,0))
            else:
                # Hide them for full wall panelling
                section["vert_pieces_entry"].grid_remove()
                section["vert_pieces_label"].grid_remove()

            if "ledge & bead" in selected_panelling:
                # Show both bead and ledge summary fields
                section["ledge_pieces_label"].grid(row=5, column=0, sticky="w", pady=(15,0))
                section["ledge_pieces_entry"].grid(row=5, column=1, sticky="ew", pady=(15,0))
                section["bead_pieces_label"].grid(row=5, column=2, sticky="ew", pady=(15,0))
                section["bead_pieces_entry"].grid(row=5, column=3, sticky="ew", pady=(15,0))

            elif "bead" in selected_panelling:
                # Show bead only, hide ledge
                section["bead_pieces_label"].grid(row=5, column=0, sticky="ew", pady=(15,0))
                section["bead_pieces_entry"].grid(row=5, column=1, sticky="ew", pady=(15,0))
                section["ledge_pieces_label"].grid_remove()
                section["ledge_pieces_entry"].grid_remove()

            elif "ledge" in selected_panelling:
                # Show ledge only, hide bead
                section["bead_pieces_label"].grid_remove()
                section["bead_pieces_entry"].grid_remove()
                section["ledge_pieces_label"].grid(row=5, column=0, sticky="ew", pady=(15,0))
                section["ledge_pieces_entry"].grid(row=5, column=1, sticky="ew", pady=(15,0))

            else:
                # Neither bead nor ledge selected — hide both
                section["bead_pieces_label"].grid_remove()
                section["bead_pieces_entry"].grid_remove()
                section["ledge_pieces_label"].grid_remove()
                section["ledge_pieces_entry"].grid_remove()

    def check_for_bead_ledge(self, *arg):
        """
        Controls visibility of the moulding and ledge dropdowns based on panelling type.
        Automatically clears inputs when switching type to avoid stale values.
        """
        selected_panelling = self.square_panelling_type_var.get().lower()
        self.clear_measurements()

        if "ledge & bead" in selected_panelling:
            # Show both moulding and ledge options
            self.moulding_label.grid(row=1, column=0, sticky="w")
            self.moulding_dropdown.grid(row=2, column=0, columnspan=4, sticky="ew")
            self.ledge_label.grid(row=3, column=0, sticky="w")
            self.ledge_dropdown.grid(row=4, column=0, columnspan=4, sticky="ew")
            self.slat_width_var.set(self.common_slat_widths[0])

        elif "bead" in selected_panelling:
            # Show moulding only
            self.moulding_label.grid(row=1, column=0, sticky="w")
            self.moulding_dropdown.grid(row=2, column=0, columnspan=4, sticky="ew")
            self.ledge_label.grid_remove()
            self.ledge_dropdown.grid_remove()
            self.slat_width_var.set(self.common_slat_widths[0])

        elif "ledge" in selected_panelling:
            # Show ledge only
            self.ledge_label.grid(row=1, column=0, sticky="w")
            self.ledge_dropdown.grid(row=2, column=0, columnspan=4, sticky="ew")
            self.moulding_label.grid_remove()
            self.moulding_dropdown.grid_remove()
            self.slat_width_var.set(self.common_slat_widths[1])

        else:
            # Neither bead nor ledge
            self.moulding_label.grid_remove()
            self.moulding_dropdown.grid_remove()
            self.ledge_label.grid_remove()
            self.ledge_dropdown.grid_remove()
            self.slat_width_var.set(self.common_slat_widths[1])

    def update_moulding_options(self):
        """
        Filters the moulding dropdown options based on the selected slat thickness.
        Only moulding styles that match the current thickness will appear.

        - Called whenever slat thickness changes.
        - Reads from `self.moulding_data` (from moulding_prices.json).
        """
        # Get selected slat thickness from the dropdown (e.g., "9mm") and strip 'mm'
        raw_value = self.slat_thickness_var.get().replace("mm", "")

        try:
            selected_thickness = int(raw_value)  # Convert to int for comparison
        except ValueError:
            selected_thickness = None

        # If invalid thickness or empty, clear dropdown and exit early
        if not selected_thickness:
            self.moulding_dropdown["values"] = []   # Clear dropdown options
            self.moulding_type_var.set("")          # Clear selection
            return

        options = []  # Will store valid labels to show in dropdown
        internal_sections = self.moulding_data     # Loaded JSON of all moulding types

        # Loop over all moulding types (e.g., 'glass_bead', 'barrel')
        for moulding_type, sizes in internal_sections.items():
            # Loop through each size (e.g., "9x9", "12x9")
            for size_label, entry in sizes.items():
                # Ensure entry is a valid dict and has matching thickness
                if isinstance(entry, dict) and entry.get("dimensions_mm", {}).get("thickness") == selected_thickness:
                    options.append(entry["label"])  # Append human-friendly label

        # Update dropdown with matched options
        self.moulding_dropdown["values"] = options

        # Auto-select first match, or show placeholder if none
        if options:
            self.moulding_type_var.set(options[0])
        else:
            self.moulding_type_var.set("No mouldings available")

    def get_board_length_mm(self):
        """
        Gets the default board length (in mm) based on the selected MDF thickness.
        Falls back to 2440mm if data is missing or fails to parse.
        """
        try:
            thickness = self.slat_thickness_var.get()  # e.g. "9mm"
            return self.material_data["mdf"][thickness]['dimensions_mm']["length"]
        except Exception as e:
            print("Error getting board length:", e)
            return 2440  # Safe default value if JSON or key lookup fails

    def update_ledge_options(self):
        """
        Updates the available ledge size(s) based on current panelling type and slat thickness.

        - For 'ledge & bead': ledge = 3 × slat thickness
        - For 'ledge' only:    ledge = 2 × slat thickness
        """
        try:
            raw = self.slat_thickness_var.get().replace("mm", "")
            if not raw.isdigit():
                self.ledge_dropdown["values"] = []
                self.ledge_type_var.set("")
                return
            thickness = int(raw)
        except:
            self.ledge_dropdown["values"] = []
            self.ledge_type_var.set("")
            return

        panelling = self.square_panelling_type_var.get().lower()
        options = []

        if "ledge & bead" in panelling:
            # Ledge should be thick enough to fit moulding — 3x slat
            ledge_3x = thickness * 3
            self.ledge_mm_value = ledge_3x
            options.append(f"{ledge_3x}mm ledge (3x Slat thicknes) to incorporate bead")
        else:
            # Default: 2x slat thickness for plain ledge
            ledge_2x = thickness * 2
            self.ledge_mm_value = ledge_2x
            options.append(f"{ledge_2x}mm ledge (2x Slat thicknes)")

        self.ledge_dropdown["values"] = options
        self.ledge_type_var.set(options[0] if options else "")

        # Recalculate each wall section if ledge value changed
        for section in self.measurements:
            if not section.get('_suspend_trace'):
                section['_suspend_trace'] = True
                try:
                    self.update_section_measurements(section)
                finally:
                    section['_suspend_trace'] = False

    def get_common_inputs(self, section):
        """
        Collects all the basic numeric inputs needed for calculations from the form.

        Inputs gathered:
        - Wall width and height (mm)
        - Number of horizontal and vertical squares
        - Slat width (converted from string, e.g., "75mm" → 75)
        - Board length (looked up from JSON based on thickness)

        Returns:
            dict with parsed values for calculations, or None if any parsing fails.
        """
        try:
            w = int(section['wall_length_var'].get())                # Wall width in mm
            h = int(section['wall_height_var'].get())                # Panel height in mm
            horz = int(section['horz_squares_var'].get())            # Horizontal square count
            vert = int(section['vert_squares_var'].get())            # Vertical square count
            slat = int(self.slat_width_var.get().replace("mm", ""))  # Slat width as number
            board = self.get_board_length_mm()                       # Get board length from material data

            return {
                'wall_width': w,
                'wall_height': h,
                'horz_squares': horz,
                'vert_squares': vert,
                'slat_width': slat,
                'board_length': board
            }
        except:
            return None  # Return None if any field is missing or invalid

    def generate_square_strip_cut_list_full(self, section, square_width, wall_height, horz_squares, vert_squares, board_length):
        """
        Lays out the MDF board strips required for full wall panelling.

        Full wall square layout includes:
        - Vertical slats: run full height, number = horz_squares + 1
        - Horizontal slats: sit between squares, number = horz_squares * (vert_squares + 1)

        The function packs these slats into 'strips' of MDF boards, minimizing waste.
        Each strip lists what cuts it contains and the total used length.

        Stores result in section['square_strip_cut_list'].

        Also prints a breakdown per direction for debug use.
        """
        kerf = 3  # cutting width in mm between slats

        # --- Vertical Slats: Full wall height ---
        vertical_slats = horz_squares + 1
        vertical_cuts = [wall_height] * vertical_slats

        # --- Horizontal Slats: between squares (horizontal grid lines) ---
        horizontal_slats = horz_squares * (vert_squares + 1)
        horizontal_cuts = [square_width] * horizontal_slats

        def layout_strips(cuts):
            """
            Packs a list of slat cut lengths into as few MDF strips as possible,
            respecting kerf spacing and max board length.

            Returns:
                Dict with strip names and their cut details.
            """
            strips = []
            for cut in sorted(cuts, reverse=True):  # sort long cuts first
                placed = False
                for strip in strips:
                    current_total = sum(strip) + kerf * len(strip)
                    if current_total + cut + kerf <= board_length:
                        strip.append(cut)
                        placed = True
                        break
                if not placed:
                    strips.append([cut])  # Start new strip

            return {
                f"Strip {i+1}": {
                    "cuts": strip,
                    "used": sum(strip) + kerf * (len(strip) - 1 if len(strip) > 1 else 0)
                } for i, strip in enumerate(strips)
            }

        # Generate result per direction
        result = {
            "vertical": layout_strips(vertical_cuts),
            "horizontal": layout_strips(horizontal_cuts)
        }

        # Save result to the section so other parts of the UI can read it
        section['square_strip_cut_list'] = result

        # Optional visual debug output
        index = self.measurements.index(section) + 1
        print(f"\n[MDF Strips Cut List] Wall Section {index} — Full Wall Panelling")
        for direction, strips in result.items():
            print(f"  {direction.capitalize()} Strips ({len(strips)} total):")
            for strip_name, data in strips.items():
                cuts = data["cuts"]
                used = data["used"]
                print(f"    {strip_name}: {cuts} | Used: {used:.1f}mm")

    def calc_square_full(self, section, wall_width, wall_height, horz_squares, vert_squares, slat_width, board_length):
        """
        Calculates square dimensions and MDF strip counts for full wall panelling.

        Inputs:
            - wall_width / wall_height: Total wall dimensions in mm
            - horz_squares / vert_squares: Number of squares in each direction
            - slat_width: Width of each slat between the squares
            - board_length: Usable MDF strip length in mm

        Output:
            - Square width/height stored in GUI variables
            - Estimated number of horizontal and vertical MDF strips required
            - MDF cutting layout is generated and stored in section['square_strip_cut_list']
        """

        # Calculate width of each square:
        # Remove slat gaps, divide remaining space by number of squares
        square_width = round((wall_width - ((horz_squares + 1) * slat_width)) / horz_squares, 2)

        # Same logic for height
        square_height = round((wall_height - ((vert_squares + 1) * slat_width)) / vert_squares, 2)

        # --- Estimate how many square-width pieces fit into one board ---
        horz_pieces_per = math.floor(board_length / square_width)

        # --- Vertical MDF strips (full height) needed: one between each square
        #vert_strips = horz_squares + 1

        # --- Horizontal MDF strips needed:
        # Total horizontal slats = horz_squares * (vert_squares + 1)
        # Divide by how many fit per board
        #horz_strips = math.ceil(((vert_squares + 1) * horz_squares) / horz_pieces_per)

        # Generate detailed cut list for these strips
        self.generate_square_strip_cut_list_full(
            section,
            square_width=square_width,
            wall_height=wall_height,
            horz_squares=horz_squares,
            vert_squares=vert_squares,
            board_length=board_length
        )

        # Store results in GUI read-only fields
        section['square_width_var'].set(str(square_width))
        section['square_height_var'].set(str(square_height))            
        section['horz_pieces_per_strip_var'].set(str(horz_pieces_per))  
        section['vert_strips_var'].set(str(len(section['square_strip_cut_list']['vertical'])))
        section['horz_strips_var'].set(str(len(section['square_strip_cut_list']['horizontal'])))

    def generate_half_square_strip_cut_list(self, section, wall_width, panel_height, horz_squares, vert_squares, square_width, slat_thickness, board_length):
        """
        Generates a detailed MDF strip cutting list for half-wall square panelling.

        This includes:
        - Top and bottom horizontal slats (run full width of the wall)
        - Vertical slats (between squares, shorter due to ledge and top trim)
        - Optional middle horizontal slats (only when more than one vertical square)

        All pieces are packed into strips with kerf spacing and stored as a dictionary
        in section['half_square_strip_cut_list'] under top/bottom/middle/vertical groups.
        """

        kerf = 3  # 3mm of waste per cut due to blade thickness

        # ------------------------------
        # STEP 1 — Top & Bottom Slats
        # ------------------------------

        # Helper function to split a long strip into segments if it's longer than the MDF board
        def split_into_joinable_pieces(length):
            segments = []
            remaining = length
            while remaining > 0:
                piece = min(remaining, board_length)  # take full boards where possible
                segments.append(piece)
                remaining -= piece
            return segments

        # Full-length top and bottom horizontal slats — may require joining
        top_pieces = split_into_joinable_pieces(wall_width)
        bottom_pieces = split_into_joinable_pieces(wall_width)

        # Combine into one list of cuts for packing
        top_bottom_cuts = top_pieces + bottom_pieces

        # ------------------------------
        # STEP 2 — Vertical Slats
        # ------------------------------

        # Calculate actual slat height (panel height minus top and bottom horizontal slats)
        vertical_cut_length = panel_height - (2 * slat_thickness)

        # One vertical slat between each square (i.e., squares + 1)
        vertical_cuts = [vertical_cut_length] * (horz_squares + 1)

        # ------------------------------
        # STEP 3 — Middle Horizontal Slats
        # ------------------------------

        middle_horizontal_cuts = []

        # If more than one row of squares, add middle slats (between rows)
        if vert_squares > 1:
            middle_horizontal_cuts = [square_width] * ((vert_squares - 1) * horz_squares)

        # ------------------------------
        # STEP 4 — Strip Packing Logic
        # ------------------------------

        def layout_strips(cuts):
            """
            Takes a list of cut lengths and packs them into strips as efficiently as possible,
            considering kerf spacing. Returns a dictionary of strips with cut lists and used length.
            """
            strips = []
            for cut in sorted(cuts, reverse=True):
                placed = False
                for strip in strips:
                    current_total = sum(strip) + kerf * len(strip)
                    if current_total + cut + kerf <= board_length:
                        strip.append(cut)
                        placed = True
                        break
                if not placed:
                    strips.append([cut])

            # Build result with used length per strip
            return {
                f"Strip {i+1}": {
                    "cuts": strip,
                    "used": sum(strip) + kerf * (len(strip) - 1 if len(strip) > 1 else 0)
                } for i, strip in enumerate(strips)
            }

        # Pack each group separately
        result = {
            "top_and_bottom_horizontal": layout_strips(top_bottom_cuts),
            "vertical": layout_strips(vertical_cuts),
            "middle_horizontal": layout_strips(middle_horizontal_cuts) if middle_horizontal_cuts else {}
        }

        # Save to section object for access in GUI or export
        section['half_square_strip_cut_list'] = result

        # ------------------------------
        # STEP 5 — Console Debug Output
        # ------------------------------

        index = self.measurements.index(section) + 1
        print(f"\n[MDF Strips Cut List] Wall Section {index} — Half Wall Panelling")

        for key, strips in result.items():
            label = key.replace("_", " ").title().replace("And", "&")
            print(f"  {label} ({len(strips)} strips):")
            for strip_name, data in strips.items():
                cuts = data["cuts"]
                used = data["used"]
                print(f"    {strip_name}: {cuts} | Used: {used:.1f}mm")

    def calc_square_half(self, section, wall_width, wall_height, horz_squares, vert_squares, slat_width, board_length):
        """
        Calculates square dimensions and MDF strip counts for HALF-wall square panelling.

        This is used when there is a horizontal top and bottom slat (forming a half-height grid).

        Inputs:
            - wall_width / wall_height: Wall dimensions in mm
            - horz_squares / vert_squares: Number of squares across and down
            - slat_width: Width of each MDF divider between squares
            - board_length: Usable length of MDF board in mm

        Output:
            - GUI fields are updated with square sizes and estimated strip counts
            - Cut layout is generated and stored in section['half_square_strip_cut_list']
        """

        # --- Calculate the width and height of each square ---

        # Square width: remove slat gaps across wall, divide space between squares
        square_width = round((wall_width - ((horz_squares + 1) * slat_width)) / horz_squares, 2)

        # Square height: remove slat gaps vertically, divide by vertical squares
        square_height = round((wall_height - ((vert_squares + 1) * slat_width)) / vert_squares, 2)

        # --- Estimate how many square-width pieces fit into one board ---
        if vert_squares == 1:
            horz_pieces_per = 0  # no middle pieces needed, skip packing
        else:
            horz_pieces_per = math.floor(board_length / square_width)

        # --- Vertical slat pieces per board ---
        # Each piece spans the height between top and bottom slats
        # Calculate how many of those fit per board
        vertical_piece_length = wall_height - (slat_width * 2)
        vert_pieces_per = math.floor(board_length / vertical_piece_length)

        # --- Total vertical strips needed ---
        # One between each square (n+1), divided by how many fit per board
        #vert_strips = math.ceil((horz_squares + 1) / vert_pieces_per)

        # --- Total horizontal strips needed ---
        #if vert_squares == 1:
            # Only top and bottom slats required (no middle rows)
        #    horz_strips = math.ceil(wall_width / board_length) * 2
        #else:
            # Top and bottom + middle slats
        #    top_bottom = math.ceil(wall_width / board_length) * 2
        #    middle = math.ceil(((vert_squares - 1) * horz_squares) / horz_pieces_per)
        #    horz_strips = top_bottom + middle

        # --- Generate the full MDF cut list and store results ---

        self.generate_half_square_strip_cut_list(
            section,
            wall_width=wall_width,
            panel_height=wall_height,
            horz_squares=horz_squares,
            vert_squares=vert_squares,
            square_width=square_width,
            slat_thickness=slat_width,
            board_length=board_length
        )

        # Update GUI with values
        section['square_width_var'].set(str(square_width))
        section['square_height_var'].set(str(square_height))            
        section['horz_pieces_per_strip_var'].set(str(horz_pieces_per))  
        cut_data = section.get('half_square_strip_cut_list', {})
        vert_strips = len(cut_data.get("vertical", {}))
        section['vert_strips_var'].set(str(vert_strips))  

        # Use the cut list to count how many horizontal strips were generated
        cut_data = section.get('half_square_strip_cut_list', {})
        total_horz_strips = len(cut_data.get("top_and_bottom_horizontal", {})) + len(cut_data.get("middle_horizontal", {}))
        section['horz_strips_var'].set(str(total_horz_strips))

        # Also update pieces per strip for verticals
        section['vert_pieces_per_strip_var'].set(str(vert_pieces_per))
    
    def calc_ledge_strips(self, section, wall_width, wall_height, horz_squares, vert_squares, slat_width, board_length):
        """
        Calculates cut list for the ledge used in half wall panelling.

        - The ledge runs the full width of the wall.
        - If the wall is wider than a single MDF board, it's split into smaller segments.
        - These segments are packed efficiently into strips, just like other MDF pieces.

        Output:
            - Updates section['ledge_strips_var'] with total number of strips
            - Stores strip layout under section['half_square_strip_cut_list']['ledge']
        """

        kerf = 3  # mm gap lost per cut

        # --- 1. Slice full ledge into joinable segments ---
        segments = []
        remaining = wall_width
        while remaining > 0:
            cut = min(remaining, board_length)
            segments.append(cut)
            remaining -= cut

        # --- 2. Efficiently pack the segments into MDF strips ---
        def layout_strips(cuts):
            strips = []
            for cut in sorted(cuts, reverse=True):
                placed = False
                for strip in strips:
                    current_total = sum(strip) + kerf * len(strip)
                    if current_total + cut + kerf <= board_length:
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

        # Generate the cut layout
        cut_list = layout_strips(segments)
        total_strips = len(cut_list)

        # --- 3. Store results in half wall MDF cut list ---
        if 'half_square_strip_cut_list' not in section:
            section['half_square_strip_cut_list'] = {}

        section['half_square_strip_cut_list']['ledge'] = cut_list
        section['ledge_strips_var'].set(str(total_strips))

        # --- 4. Console Printout ---
        index = self.measurements.index(section) + 1
        print(f"\n[MDF Strips Cut List] Wall Section {index} — Ledge")
        print(f"  Ledge ({total_strips} strips):")
        for strip_name, data in cut_list.items():
            print(f"    {strip_name}: {data['cuts']} | Used: {data['used']:.1f}mm")

    def generate_bead_cut_list(self, section, square_width, square_height, total_squares, bead_length, panelling_type, wall_width):
        """
        Generates the full bead cut list for a wall section.

        This includes:
        - Beads around each square (2 vertical + 2 horizontal per square)
        - An under-ledge bead run (if the panelling type includes a ledge)

        The resulting bead strip breakdowns are stored in section['bead_cut_list'],
        split into 'square_beads' and 'ledge_beads' for clarity.

        Each group is packed into strips using a kerf-aware layout, sorted longest-to-shortest.

        Args:
            section (dict): The GUI section dictionary for this wall
            square_width (float): Width of each square opening
            square_height (float): Height of each square opening
            total_squares (int): Total number of squares in the wall
            bead_length (int): Full usable moulding/bead strip length in mm
            panelling_type (str): Current selected panelling description
            wall_width (int): Wall width in mm, used for under-ledge bead if present
        """
        kerf = 3  # Amount lost per cut (mm)

        # --- 1. Build bead cuts for each square (2 vertical + 2 horizontal)
        square_bead_cuts = []
        for _ in range(total_squares):
            square_bead_cuts.extend([square_width, square_width, square_height, square_height])

        # Sort beads longest first (helps efficient packing)
        square_bead_cuts.sort(reverse=True)

        # --- Internal helper: Lay out a list of cuts across multiple strips efficiently ---
        def layout_strips(cuts):
            strips = []
            for cut in cuts:
                cut = float(cut)
                placed = False
                for strip in strips:
                    current_total = sum(strip) + kerf * len(strip)
                    if current_total + cut + kerf <= bead_length:
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

        # --- 2. Layout the square bead strips
        square_bead_strips = layout_strips(square_bead_cuts)

        # --- 3. Generate ledge bead cut if panelling type includes a ledge
        ledge_bead_strips = {}
        if "ledge" in panelling_type:
            remaining = wall_width
            ledge_cuts = []
            while remaining > 0:
                piece = min(remaining, bead_length)
                ledge_cuts.append(piece)
                remaining -= piece
            ledge_bead_strips = layout_strips(ledge_cuts)

        # --- 4. Store both bead groups in the wall section data
        section['bead_cut_list'] = {
            "square_beads": square_bead_strips,
            "ledge_beads": ledge_bead_strips
        }

        # --- 5. Optional: Printout to terminal for debugging/confirmation
        index = self.measurements.index(section) + 1
        print(f"\n[Bead Cut List] Wall Section {index}:")
        
        print(f"  Square Beads ({len(square_bead_strips)} strips):")
        for strip_name, data in square_bead_strips.items():
            print(f"    {strip_name}: {data['cuts']} | Used: {data['used']:.1f}mm")
        
        if ledge_bead_strips:
            print(f"  Ledge Beads ({len(ledge_bead_strips)} strips):")
            for strip_name, data in ledge_bead_strips.items():
                print(f"    {strip_name}: {data['cuts']} | Used: {data['used']:.1f}mm")

    def calc_bead_strips(self, section, wall_width, wall_height, horz_squares, vert_squares, slat_width, board_length):
        """
        Calculates how many full-length bead strips are required for a given wall section.

        It looks up the bead strip length based on the selected moulding type,
        then triggers the bead cut list generation (square beads + ledge if applicable).
        
        Results are stored in:
            - section['bead_cut_list']: Full breakdown of bead cuts
            - section['bead_strips_var']: Total number of full strips required

        Args:
            section (dict): The wall section this calculation belongs to
            wall_width (int): Width of the wall section in mm
            wall_height (int): Height of the wall section in mm
            horz_squares (int): Number of squares horizontally
            vert_squares (int): Number of squares vertically
            slat_width (int): Width of slats between squares in mm
            board_length (int): Full board/MDF length (not directly used here)
        """
        
        # --- Calculate total number of squares ---
        total_squares = horz_squares * vert_squares

        # --- Retrieve square dimensions from earlier calculations ---
        try:
            square_width = float(section['square_width_var'].get())
            square_height = float(section['square_height_var'].get())
        except:
            return  # If not yet calculated, skip this step

        # --- 1. Look up the selected moulding type's length (bead strip length) ---
        selected_label = self.moulding_type_var.get()
        
        # Build a dictionary to map each user-visible label to its actual bead length in mm
        self.bead_lookup = {}
        for moulding_type, sizes in self.moulding_data.items():
            for size_key, entry in sizes.items():
                label = entry.get("label")
                if label:
                    self.bead_lookup[label] = entry.get("dimensions_mm", {}).get("length", 0)

        # Get the length of a full bead strip
        bead_length = self.bead_lookup.get(selected_label)
        if not bead_length:
            print("Bead length not found.")
            return

        # --- 2. Trigger full bead cut list generation ---
        selected_panelling = self.square_panelling_type_var.get().lower()
        self.generate_bead_cut_list(
            section,
            square_width,
            square_height,
            total_squares,
            bead_length,
            selected_panelling,
            wall_width
        )

        # --- 3. Store total number of strips (square + ledge) into GUI ---
        bead_data = section.get('bead_cut_list', {})
        total_strips = len(bead_data.get('square_beads', {})) + len(bead_data.get('ledge_beads', {}))
        section['bead_strips_var'].set(str(total_strips))

    def update_section_measurements(self, section):
        """
        Recalculates all necessary measurements and cut lists for a single wall section.

        This method is called whenever a relevant input changes (wall size, square counts, etc.).
        It chooses which calculations to run based on the selected panelling type:
            - Full square panelling
            - Half wall square panelling
            - Ledge strips
            - Bead strips (including under-ledge bead)

        Args:
            section (dict): The current wall section dictionary with its associated StringVars
        """

        # --- Prevent recursive calls or duplicate recalculations ---
        if section.get('_suspend_trace'):
            return  # Exit early if this update was already triggered internally

        # Temporarily suspend any further updates while this one is running
        section['_suspend_trace'] = True
        try:
            # Print debug info to track when an update is running (can be removed in production)
            #print(f"Running update for section {id(section)}")

            # Gather all required inputs from the GUI fields (returns None if any are missing)
            section['job_label'] = self.square_panelling_type_var.get()
            raw_inputs = self.get_common_inputs(section)

            # If inputs are incomplete or invalid, skip calculations
            if not raw_inputs:
                return

            # Check what kind of panelling is selected (e.g., full square, half wall, etc.)
            selected_panelling = section['job_label'].lower()
            section['job_label'] = self.square_panelling_type_var.get()

            # --- MDF Slat Calculations (depends on panelling type) ---

            # Half wall square panelling uses slightly different layout rules
            if "square half" in selected_panelling:
                self.calc_square_half(section, **raw_inputs)

            # Full wall square panelling
            elif "square panelling" in selected_panelling:
                self.calc_square_full(section, **raw_inputs)

            # --- Ledge Calculations ---
            # If this panelling type includes a ledge, calculate how many full strips are needed
            if "ledge" in selected_panelling:
                self.calc_ledge_strips(section, **raw_inputs)

            # --- Bead Calculations ---
            # If moulding/beading is involved, generate bead cut list and count
            if "bead" in selected_panelling:
                self.calc_bead_strips(section, **raw_inputs)

        except Exception as e:
            # Catch any errors and print them for debugging
            print("Error in update_section_measurements:", e)

        finally:
            # Always re-enable updates after this function finishes
            section['_suspend_trace'] = False
        
        self.update_material_totals()

    def remove_wall_section(self):
        # Only allow removal if more than one section exists
        if len(self.measurements) > 1:
            last_section = self.measurements.pop()  # Remove the last section from the list
            last_section['section_frame'].destroy()  # Destroy its frame from the UI
        self.update_material_totals()

    def add_wall_section(self):
        section = {}

        section_index = len(self.measurements) + 1
        section_frame = ttk.LabelFrame(self.measurement_row, text=f"Wall Section {section_index}")
        section_frame.pack(fill="x", pady=(10, 0))  # Add spacing between sections

        row = ttk.Frame(section_frame)
        row.pack(fill="x")

        #row = ttk.Frame(self.measurement_row)
        #row.grid(row=len(self.measurements), column=0, columnspan=10, sticky="ew")

        self.measurement_row.columnconfigure(0, weight=1)

        row.columnconfigure(1, weight=1)  # For first entry
        row.columnconfigure(3, weight=1)  # For second entry

        section['wall_length_var'] = tk.StringVar()
        section['wall_height_var'] = tk.StringVar()
        section['horz_squares_var'] = tk.StringVar()
        section['vert_squares_var'] = tk.StringVar()
        section['square_width_var'] = tk.StringVar()
        section['square_height_var'] = tk.StringVar()
        section['vert_strips_var'] = tk.StringVar()
        section['horz_strips_var'] = tk.StringVar()
        section['horz_pieces_per_strip_var'] = tk.StringVar()
        section['vert_pieces_per_strip_var'] = tk.StringVar()
        section['ledge_strips_var'] = tk.StringVar()
        section['bead_strips_var'] = tk.StringVar()

        # --- Wall Measurements ---
        ttk.Label(row, text="Wall Length(mm)").grid(row=0, column=0, sticky="w")
        ttk.Entry(row, textvariable=section['wall_length_var']).grid(row=0, column=1, sticky="ew")
        ttk.Label(row, text="Wall(Panel) Height(mm)").grid(row=0, column=2, sticky="w")
        ttk.Entry(row, textvariable=section['wall_height_var']).grid(row=0, column=3, sticky="ew")

        # --- Square Numbers ---
        ttk.Label(row, text="Horizontal Squares").grid(row=1, column=0, sticky="w")
        ttk.Entry(row, textvariable=section['horz_squares_var']).grid(row=1, column=1, sticky="ew")
        ttk.Label(row, text="Vertical Squares").grid(row=1, column=2, sticky="w")
        ttk.Entry(row, textvariable=section['vert_squares_var']).grid(row=1, column=3, sticky="ew")

        # --- Square Measurements ---
        ttk.Label(row, text="Square Width(mm)").grid(row=2, column=0, sticky="w", pady=(15,0))
        ttk.Entry(row, textvariable=section['square_width_var'], state="readonly").grid(row=2, column=1, sticky="ew", pady=(15,0))
        ttk.Label(row, text="Square Height(mm)").grid(row=2, column=2, sticky="w", pady=(15,0))
        ttk.Entry(row, textvariable=section['square_height_var'], state="readonly").grid(row=2, column=3, sticky="ew", pady=(15,0))

        # --- Strips Needed Measurements ---
        ttk.Label(row, text="Horizontal Strips Needed").grid(row=3, column=0, sticky="w", pady=(15,0))
        ttk.Entry(row, textvariable=section['horz_strips_var'], state="readonly").grid(row=3, column=1, sticky="ew", pady=(15,0))
        ttk.Label(row, text="Vertical Strips Needed").grid(row=3, column=2, sticky="w", pady=(15,0))
        ttk.Entry(row, textvariable=section['vert_strips_var'], state="readonly").grid(row=3, column=3, sticky="ew", pady=(15,0))

        # --- Pieces Per Strip Measurements ---
        ttk.Label(row, text="Horizontal Pieces Per Strip").grid(row=4, column=0, sticky="w", pady=(15,0))
        ttk.Entry(row, textvariable=section['horz_pieces_per_strip_var'], state="readonly").grid(row=4, column=1, sticky="ew", pady=(15,0))
        section["vert_pieces_label"] = ttk.Label(row, text="Vertical Pieces Per Strip")
        section["vert_pieces_entry"] = ttk.Entry(row, textvariable=section['vert_pieces_per_strip_var'], state="readonly")

        # --- ledge and bead Measurements ---
        section["ledge_pieces_label"] = ttk.Label(row, text="Ledge Strips Per Wall")
        section["ledge_pieces_entry"] = ttk.Entry(row, textvariable=section['ledge_strips_var'], state="readonly")
        section["bead_pieces_label"] = ttk.Label(row, text="Bead Strips Per Wall")
        section["bead_pieces_entry"] = ttk.Entry(row, textvariable=section['bead_strips_var'], state="readonly")

        section['_update_after_id'] = None  # Store debounce timer ID
        section['_suspend_trace'] = False

        def debounce_update(*args, s=section):
            if s.get('_update_after_id'):
                self.after_cancel(s['_update_after_id'])
            s['_update_after_id'] = self.after(300, lambda: self.update_section_measurements(s))

        for key in ['wall_length_var', 'wall_height_var', 'horz_squares_var', 'vert_squares_var']:
            section[key].trace_add("write", debounce_update)

        self.slat_width_var.trace_add("write", lambda *a, s=section: self.update_section_measurements(s))

        self.measurements.append(section)
        self.update_section_measurements(section)
        self.check_for_half_square_wall(section)

        section['section_frame'] = section_frame  # Save the frame reference for later removal

    def calc_boards_needed(self, board_width, slat_count, slat_width, ledge_count, ledge_width, kerf):
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

    def update_material_totals_visibility(self):
        panelling = self.square_panelling_type_var.get().lower()

        # Show/hide bead-related fields
        bead_fields = ["beads_needed_var", "bead_cost_var", "linear_meterage_beading_ledge_var"]
        ledge_fields = ["ledge_strips_var"]

        for var in bead_fields:
            for widget in self.material_total_widgets.get(var, []):
                widget.grid() if "bead" in panelling else widget.grid_remove()

        for var in ledge_fields:
            for widget in self.material_total_widgets.get(var, []):
                widget.grid() if "ledge" in panelling else widget.grid_remove()

    def update_material_totals(self):
        """
        Calculates and updates all material usage and cost totals based on current wall sections.
        """
        kerf = 3
        board_length = self.get_board_length_mm()     # still needed for strip layout
        board_width = self.material_data["mdf"][self.slat_thickness_var.get()]["dimensions_mm"]["width"]

        total_hv_strips = 0
        total_ledge_strips = 0
        total_bead_strips = 0
        total_linear_m_panelling = 0
        total_linear_m_bead_ledge = 0

        for section in self.measurements:
            # MDF cut lists
            if 'square_strip_cut_list' in section:
                for group in ['vertical', 'horizontal']:
                    strips = section['square_strip_cut_list'].get(group, {})
                    total_hv_strips += len(strips)
                    total_linear_m_panelling += sum(d['used'] for d in strips.values()) / 1000

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
                        total_linear_m_bead_ledge += sum(d['used'] for d in strips.values()) / 1000
                    else:
                        total_hv_strips += len(strips)
                        total_linear_m_panelling += sum(d['used'] for d in strips.values()) / 1000

            # Bead strips
            bead_strips = section.get('bead_cut_list', {})
            for group in ['square_beads', 'ledge_beads']:
                strips = bead_strips.get(group, {})
                total_bead_strips += len(strips)
                total_linear_m_bead_ledge += sum(d['used'] for d in strips.values()) / 1000

        # Strip counts
        combined_strips = total_hv_strips + total_ledge_strips

        # --- Accurate kerf-aware calculation for strips per board ---
        try:
            slat_width = int(self.slat_width_var.get().replace("mm", ""))
            ledge_width = self.ledge_mm_value if hasattr(self, 'ledge_mm_value') else slat_width * 2
            
            boards_needed = self.calc_boards_needed(
                board_width=board_width,
                slat_count=total_hv_strips,
                slat_width=slat_width,
                ledge_count=total_ledge_strips,
                ledge_width=ledge_width,
                kerf=kerf
            )

            if total_hv_strips > 0 or total_ledge_strips > 0:
                self.board_cut_summary = self.generate_board_cut_layout(
                    total_slat_strips=total_hv_strips,
                    total_ledge_strips=total_ledge_strips,
                    slat_width=slat_width,
                    ledge_width=ledge_width,
                    board_width=board_width,
                    kerf=kerf
                )
            else:
                self.board_cut_summary = {}
        except:
            boards_needed = 0

        # --- Get board cost from material_data ---
        try:
            thickness = self.slat_thickness_var.get()
            board_cost_each = float(self.material_data["mdf"][thickness]["price"])
        except:
            board_cost_each = 100.00  # default fallback

        # --- Get bead cost from moulding_data ---
        try:
            label = self.moulding_type_var.get()
            bead_cost_each = 0
            for sizes in self.moulding_data.values():
                for entry in sizes.values():
                    if entry.get("label") == label:
                        bead_cost_each = float(entry.get("price", 0))
        except:
            bead_cost_each = 100.00  # fallback

        pricing = self.pricing_data
        mastic_unit_price = pricing.get("mastic_unit_price")
        cut_cost_per_strip = pricing.get("cut_cost_per_strip")
        delivery_cost = pricing.get("delivery_cost")
        mastic_linear_coverage = pricing.get("mastic_linear_coverage")

        # --- Cost calculations ---
        mastic_needed = math.ceil((total_linear_m_panelling + total_linear_m_bead_ledge) / mastic_linear_coverage * 1.5)
        mastic_cost = round(mastic_needed * mastic_unit_price, 2)
        board_cost = round(boards_needed * board_cost_each, 2)
        bead_cost = round(total_bead_strips * bead_cost_each, 2)
        cut_cost = round((combined_strips + 1) * cut_cost_per_strip, 2)

        # --- Update GUI ---
        self.material_totals["total_hv_strips_var"].set(str(total_hv_strips))
        self.material_totals["ledge_strips_var"].set(str(total_ledge_strips))
        self.material_totals["boards_needed_var"].set(str(boards_needed))
        self.material_totals["board_cost_var"].set(f"£{board_cost:.2f}")
        self.material_totals["beads_needed_var"].set(str(total_bead_strips))
        self.material_totals["bead_cost_var"].set(f"£{bead_cost:.2f}")
        self.material_totals["linear_meterage_panelling_var"].set(f"{total_linear_m_panelling:.2f}m")
        self.material_totals["linear_meterage_beading_ledge_var"].set(f"{total_linear_m_bead_ledge:.2f}m")
        self.material_totals["mastic_needed_var"].set(str(mastic_needed))
        self.material_totals["mastic_cost_var"].set(f"£{mastic_cost:.2f}")
        self.material_totals["cut_cost_var"].set(f"£{cut_cost:.2f}")
        self.material_totals["delivery_cost_var"].set(f"£{delivery_cost:.2f}")

        self.update_job_totals()

    def build_window(self):
        # --- Main Canvas + Scrollbar ---
        canvas = tk.Canvas(self, borderwidth=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.canvas_window = canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        def resize_scrollable_frame(event):
            canvas.itemconfig(self.canvas_window, width=event.width)

        canvas.bind("<Configure>", resize_scrollable_frame)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # --- Main Frame ---
        main_frame = ttk.Frame(self.scrollable_frame)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Top Frame ---
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill="both", expand=True)

        # --- buttons for loading, saving, clearing
        control_frame = ttk.LabelFrame(top_frame, text=("File Actions"))
        control_frame.pack(fill="x")

        button_row = ttk.Frame(control_frame)
        button_row.pack(anchor="center", pady=10)

        ttk.Button(button_row, text="Create New" , width=15).pack(side="left", padx=(0, 10))
        ttk.Button(button_row, text="Save Measurements" , width=15).pack(side="left", padx=(0, 10))
        ttk.Button(button_row, text="Load Measurements" , width=15).pack(side="left",  padx=(0, 10))
        ttk.Button(button_row, text="Clear Form", command=self.clear_customer_details, width=15).pack(side="left")

        # --- Loaded File
        path_frame = ttk.LabelFrame(top_frame, text=("Loaded File"))
        path_frame.pack(fill="x", pady=(10,0))

        path_row = ttk.Frame(path_frame)
        path_row.pack(fill="x", padx=10, pady=10)

        loaded_path_label = ttk.Label(path_row, text="No file loaded", foreground="gray", font=("Segoe UI", 10, "italic"))
        loaded_path_label.pack(anchor="w")

        # Details of Customer and time
        job_details_frame = ttk.LabelFrame(top_frame, text="Customers Details / Duration ToDo / Status")
        job_details_frame.pack(fill="x", pady=(10, 0))

        job_details_row = ttk.Frame(job_details_frame)
        job_details_row.pack(fill="x", padx=10, pady=10)

        job_details_row.columnconfigure(1, weight=1)  # For first entry
        job_details_row.columnconfigure(3, weight=1)  # For second entry

        self.job_details = {
            "customers_name_var": tk.StringVar(),
            "customers_street_var": tk.StringVar(),
            "customers_postcode_var": tk.StringVar(),
            "date_of_quote_var": tk.StringVar(),
            "full_days_var": tk.StringVar(),
            "extra_hours_var": tk.StringVar()
        }

        self.full_days_var = self.job_details["full_days_var"]
        self.extra_hours_var = self.job_details["extra_hours_var"]

        job_details_fields = [
            ("Customers Name", "customers_name_var"),
            ("Street Name", "customers_street_var"),
            ("Postcode", "customers_postcode_var"),
            ("Date of Quote", "date_of_quote_var"),
            ("Duration of Job", "full_days_var"),
            ("Extra Hours", "extra_hours_var")
        ]

        self.job_details_widgets = {}

        for idx, (label_text, var_name) in enumerate(job_details_fields):
            row = idx // 2
            col = (idx % 2) * 2

            label = ttk.Label(job_details_row, text=label_text)
            entry = ttk.Entry(job_details_row, textvariable=self.job_details[var_name])

            label.grid(row=row, column=col, sticky="w", pady=(15 if row else 0, 0))
            entry.grid(row=row, column=col + 1, sticky="ew", pady=(15 if row else 0, 0))

        # --- Entry fields
        job_type_frame = ttk.LabelFrame(top_frame, text=(""))
        job_type_frame.pack(fill="x")

        job_type_row = ttk.Frame(job_type_frame)
        job_type_row.pack(fill="x", padx=10, pady=10)

        self.square_panelling_type_var = tk.StringVar()
        ttk.Label(job_type_row, text="Panelling Type").pack(anchor="w")
        ttk.Combobox(job_type_row, textvariable=self.square_panelling_type_var, values=[ 
                        "Square Panelling", "Square Panelling with bead", "Square Half Wall Panelling",
                        "Square Half Wall Panelling with Bead", "Square Half Wall Panelling with Ledge",
                        "Square Half Wall Panelling with Ledge & Bead"], state="readonly"
                        ).pack(fill="x")
        
        self.square_panelling_type_var.set("Square Panelling")
        
        # --- Material data
        materials_frame = ttk.LabelFrame(top_frame, text=("Material Details"))
        materials_frame.pack(fill="x", pady=(10,0))

        materials_row = ttk.Frame(materials_frame)
        materials_row.pack(fill="x", padx=10, pady=10)

        # Grid weight configuration to allow resizing
        materials_row.columnconfigure(1, weight=1)  # For first combobox
        materials_row.columnconfigure(3, weight=1)  # For second combobox

        # Slat Thickness
        mdf_thicknesses = list(self.material_data.get("mdf", {}).keys()) # get keys for mdf ie thicknesses
        
        self.slat_thickness_var = tk.StringVar()
        ttk.Label(materials_row, text="Slat Thickness").grid(row=0, column=0, sticky="w")
        ttk.Combobox(materials_row, textvariable=self.slat_thickness_var, values=mdf_thicknesses, state="readonly").grid(row=0, column=1, sticky="ew")
        
        # Slat Width
        self.common_slat_widths = ["75mm", "100mm"]
        self.slat_width_var = tk.StringVar()
        ttk.Label(materials_row, text="Slat Width").grid(row=0, column=2, sticky="w")
        ttk.Combobox(materials_row, textvariable=self.slat_width_var, values=[""] + self.common_slat_widths, state="normal").grid(row=0, column=3, sticky="ew")

        if mdf_thicknesses:
            self.slat_thickness_var.set(mdf_thicknesses[1])

        selected_panelling = self.square_panelling_type_var.get().lower()

        if selected_panelling:
            self.slat_width_var.set(self.common_slat_widths[1])

        # Moulding Type
        self.moulding_type_var = tk.StringVar()
        self.moulding_label = ttk.Label(materials_row, text="Moulding Type")
        self.moulding_dropdown = ttk.Combobox(materials_row, textvariable=self.moulding_type_var, state="readonly")

        self.square_panelling_type_var.trace_add("write", self.check_for_bead_ledge)

        # Ledge width
        self.ledge_type_var = tk.StringVar()
        self.ledge_label = ttk.Label(materials_row, text="Ledge Thickness")
        self.ledge_dropdown = ttk.Combobox(materials_row, textvariable=self.ledge_type_var, state="normal")

        self.square_panelling_type_var.trace_add("write", self.check_for_bead_ledge)
        self.square_panelling_type_var.trace_add("write", lambda *a: self.update_ledge_options())        
        self.slat_thickness_var.trace_add("write", lambda *a: self.update_ledge_options())
        self.slat_thickness_var.trace_add("write", lambda *a: self.update_moulding_options())


        # Job Measurements
        measurement_frame = ttk.LabelFrame(top_frame, text=("Measurment Input"))
        measurement_frame.pack(fill="x", pady=(10,0))
        
        self.measurements = []

        self.measurement_row = ttk.Frame(measurement_frame)
        self.measurement_row.pack(fill="x", padx=10, pady=10)

        self.add_wall_section()

        self.square_panelling_type_var.trace_add("write", self.check_for_half_square_wall)
        self.square_panelling_type_var.trace_add("write", self.check_for_bead_ledge)

        section_button_row = ttk.Frame(measurement_frame)
        section_button_row.pack(fill="x", pady=10)

        section_button_row.columnconfigure(0, weight=1)  # For first entry
        section_button_row.columnconfigure(1, weight=1)  # For second entry

        ttk.Button(section_button_row, text="+ Wall/Section", command=self.add_wall_section).grid(row=0, column=0, sticky="ew",  padx=(10, 5))
        ttk.Button(section_button_row, text="- Wall/Section", command=self.remove_wall_section).grid(row=0, column=1, sticky="ew", padx=(5, 10))

        # Material Total Calcs and costs
        material_calc_frame = ttk.LabelFrame(top_frame, text=("Material Total Calculations/Costs"))
        material_calc_frame.pack(fill="x", pady=(10,0))

        material_calc_row = ttk.Frame(material_calc_frame)
        material_calc_row.pack(fill="x", padx=10, pady=10)

        material_calc_row.columnconfigure(1, weight=1)  # For first entry
        material_calc_row.columnconfigure(3, weight=1)  # For second entry

        self.material_totals = {
            "total_hv_strips_var": tk.StringVar(),
            "ledge_strips_var": tk.StringVar(),
            "boards_needed_var": tk.StringVar(),
            "board_cost_var": tk.StringVar(),
            "beads_needed_var": tk.StringVar(),
            "bead_cost_var": tk.StringVar(),
            "linear_meterage_panelling_var": tk.StringVar(),
            "linear_meterage_beading_ledge_var": tk.StringVar(),
            "mastic_needed_var": tk.StringVar(),
            "mastic_cost_var": tk.StringVar(),
            "cut_cost_var": tk.StringVar(),
            "delivery_cost_var": tk.StringVar(),
        }

        total_fields = [
            ("Total H/V Strips Needed", "total_hv_strips_var"),
            ("Ledge Strips Needed", "ledge_strips_var"),
            ("Boards Needed", "boards_needed_var"),
            ("Board Cost", "board_cost_var"),
            ("Total Beads Needed", "beads_needed_var"),
            ("Bead Cost", "bead_cost_var"),
            ("Linear Meterage Panelling", "linear_meterage_panelling_var"),
            ("Linear Meterage B/L", "linear_meterage_beading_ledge_var"),
            ("Mastic Needed", "mastic_needed_var"),
            ("Mastic Cost", "mastic_cost_var"),
            ("Cut Cost", "cut_cost_var"),
            ("Delivery Cost", "delivery_cost_var"),
        ]

        self.material_total_widgets = {}

        for idx, (label_text, var_name) in enumerate(total_fields):
            row = idx // 2
            col = (idx % 2) * 2

            label = ttk.Label(material_calc_row, text=label_text)
            entry = ttk.Entry(material_calc_row, textvariable=self.material_totals[var_name], state="readonly")

            label.grid(row=row, column=col, sticky="w", pady=(15 if row else 0, 0))
            entry.grid(row=row, column=col + 1, sticky="ew", pady=(15 if row else 0, 0))

            # Save widgets so we can show/hide later
            self.material_total_widgets[var_name] = (label, entry)

        # Job Cost Totals
        job_total_frame = ttk.LabelFrame(top_frame, text="Final Costs Display")
        job_total_frame.pack(fill="x", pady=(10, 0))

        job_total_row = ttk.Frame(job_total_frame)
        job_total_row.pack(fill="x", padx=10, pady=10)

        job_total_row.columnconfigure(1, weight=1)  # For first entry
        job_total_row.columnconfigure(3, weight=1)  # For second entry

        self.job_totals = {
            "material_cost_var": tk.StringVar(),
            "labour_cost_var": tk.StringVar(),
            "take_home_var": tk.StringVar(),
            "price_of_job_var": tk.StringVar(),
        }

        job_total_fields = [
            ("Total Material Costs", "material_cost_var"),
            ("Labour Costs", "labour_cost_var"),
            ("Take Home", "take_home_var"),
            ("Price of Job", "price_of_job_var"),
        ]

        self.job_totals_widgets = {}

        for idx, (label_text, var_name) in enumerate(job_total_fields):
            row = idx // 2
            col = (idx % 2) * 2

            label = ttk.Label(job_total_row, text=label_text)
            entry = ttk.Entry(job_total_row, textvariable=self.job_totals[var_name], state="readonly")

            label.grid(row=row, column=col, sticky="w", pady=(15 if row else 0, 0))
            entry.grid(row=row, column=col + 1, sticky="ew", pady=(15 if row else 0, 0))

        # Cut List Display
        job_cutlist_frame = ttk.LabelFrame(top_frame, text="Cut List Display")
        job_cutlist_frame.pack(fill="x", pady=(10, 0))

        job_cutlist_row = ttk.Frame(job_cutlist_frame)
        job_cutlist_row.pack(fill="x", padx=10, pady=10)

        # Textbox fills horizontally with a scrollbar-friendly layout
        self.cut_list_textbox = tk.Text(job_cutlist_row, height=25, font=("Courier", 12), wrap="none")
        self.cut_list_textbox.pack(fill="x")

        # Button to manually trigger the cut list display
        cutlist_button = ttk.Button(job_cutlist_row, text="Generate Cut List", command=self.update_cut_list_display)
        cutlist_button.pack(fill="x", pady=(10, 0))

        self.square_panelling_type_var.trace_add("write", lambda *a: self.update_material_totals_visibility())
        self.update_material_totals_visibility()

        self.check_for_bead_ledge()
        self.update_moulding_options()
        self.update_ledge_options()