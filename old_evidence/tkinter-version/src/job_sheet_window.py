import os
import json
import math
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox, simpledialog
from components.job_status_block import JobStatusBlock
from components.customer_details_block import CustomerDetailsBlock
from components.job_type_dropdown_block import JobTypeDropdownBlock
from components.panelling_type_dropdown_block import PanellingTypeDropdownBlock
from components.square_input_block import SquareInputBlock
from components.dado_input_block import DadoInputBlock
from components.full_wall_measurements_block import FullWallMeasurementsBlock
from components.half_wall_measurements_block import HalfWallMeasurementsBlock
from components.dado_wall_measurements_block import DadoWallMeasurementsBlock
from components.job_material_totals_block import JobMaterialTotalsBlock
from components.job_totals_block import JobTotalsBlock
from components.job_cut_list_block import JobCutListBlock
from core.logic.full_wall.calc_full_wall import calc_square_full
from core.logic.half_wall.calc_half_wall import calc_square_half
from core.logic.half_wall.calc_half_ledge import calc_ledge_half, calc_ledge_stair
from core.logic.half_wall.calc_half_stairs import calc_stair_half
from core.logic.shared.bead_calculations import generate_bead_cut_list, generate_bead_cut_list_stair

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
class JobSheetWindow(tk.Toplevel):
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
        self.material_data = get_json_data("mdf_prices.json")
        self.dado_data = get_json_data("dado_prices.json")
        self.pricing_data = get_json_data("pricing_config.json")

        self.gui_ready = False
        self.square_inputs = None
        self.dado_inputs = None
        self.on_change = self.on_change

        # Build the full GUI layout and input form
        self.build_window()

    def get_board_length_mm(self):
        """
        Gets the default board length (in mm) based on the selected MDF thickness.
        Falls back to 2440mm if data is missing or fails to parse.
        """
        try:
            thickness = self.square_inputs.slat_thickness_var.get()  # e.g. "9mm"
            return self.square_inputs.material_data["mdf"][thickness]['dimensions_mm']["length"]
        except Exception as e:
            print("Error getting board length:", e)
            return 5000
        
    def get_bead_length_from_label(self):
        """
        Searches the bead JSON for a matching label and returns its length in mm.
        """
        selected_label = self.square_inputs.moulding_type_var.get()

        try:
            for category_data in self.moulding_data.values():
                for option_data in category_data.values():
                    if option_data.get("label") == selected_label:
                        return option_data["dimensions_mm"]["length"]
        except Exception as e:
            print(f"[ERROR] Failed to look up bead length: {e}")

        print(f"[WARNING] Bead label '{selected_label}' not found in material data.")
        return 5000  # fallback
    
    def update_half_wall_measurements(self):
        """
        Updates all half wall sections based on current inputs.
        Calculates strip layout and bead cut list if needed.
        """
        panel_type = self.panelling_type_dropdown.get_value().lower()
        board_length = self.get_board_length_mm()
        kerf = self.pricing_data.get("kerf", 3)

        for section in self.half_wall_measurements.sections:
            try:
                wall_width_str = section.vars['wall_length_var'].get()
                panel_height_str = section.vars['panel_height_var'].get()
                horz_squares_str = section.vars['horz_squares_var'].get()
                vert_squares_str = section.vars['vert_squares_var'].get()

                if not all([wall_width_str, panel_height_str, horz_squares_str, vert_squares_str]):
                    continue  # Skip section until it's fully filled in

                wall_width = float(wall_width_str)
                panel_height = float(panel_height_str)
                horz_squares = int(horz_squares_str)
                vert_squares = int(vert_squares_str)
                slat_width_str = self.square_inputs.slat_width_var.get().replace("mm", "").strip()
                slat_width = float(slat_width_str)

                calc_square_half(
                    section,
                    wall_width,
                    panel_height,
                    horz_squares, 
                    vert_squares,
                    slat_width,
                    board_length,
                    kerf
                )

                if "ledge" in panel_type:
                    calc_ledge_half(section, wall_width, board_length, kerf)

                if "bead" in panel_type:
                    bead_length = self.get_bead_length_from_label()
                    total_squares = horz_squares * vert_squares  # one row of squares
                    square_width = float(section.vars['square_width_var'].get())
                    square_height = float(section.vars['square_height_var'].get())

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

            except Exception as e:
                print(f"[ERROR] Failed to update section: {e}")


        for section in self.half_wall_measurements.stair_sections:
            try:
                # Get GUI values
                wall_width = section.vars['stair_wall_length_var'].get()
                stair_panel_height = section.vars['panel_height_var'].get()
                bottom_flat = section.vars['lower_landing_wall_length_var'].get()
                top_flat = section.vars['top_landing_wall_length_var'].get()
                stair_slope = section.vars['stair_slope_length_var'].get()
                stair_horz_squares = section.vars['horz_squares_var'].get()
                stair_vert_squares = section.vars['vert_squares_var'].get()
                slat_width_str = self.square_inputs.slat_width_var.get().replace("mm", "").strip()
                slat_width = float(slat_width_str)

                if not all([wall_width, stair_panel_height, stair_slope, bottom_flat, top_flat, stair_horz_squares, stair_vert_squares]):
                    continue
                
                wall_width = float(section.vars['stair_wall_length_var'].get())
                stair_panel_height = float(section.vars['panel_height_var'].get())
                stair_slope = float(section.vars['stair_slope_length_var'].get())
                bottom_flat = int(section.vars['lower_landing_wall_length_var'].get())
                top_flat = int(section.vars['top_landing_wall_length_var'].get())
                stair_horz_squares = int(float(section.vars['horz_squares_var'].get()))
                stair_vert_squares = int(float(section.vars['vert_squares_var'].get()))
                
                # Run stair logic
                calc_stair_half(
                    section,
                    wall_width,
                    stair_panel_height,
                    bottom_flat,
                    top_flat,
                    stair_slope,
                    stair_horz_squares,
                    stair_vert_squares,
                    slat_width,
                    board_length,
                    kerf
                )

                if "ledge" in panel_type:
                    stair_run_wall_width = bottom_flat + top_flat + stair_slope
                    calc_ledge_stair(section, stair_run_wall_width, board_length, kerf)

                if "bead" in panel_type:
                    bead_length = self.get_bead_length_from_label()
                    angled_squares = int(section.vars["angled_square_count_var"].get())
                    trans_squares = int(section.vars["transition_square_count_var"].get())
                    total_angled_trans = angled_squares + trans_squares
                    total_squares = stair_horz_squares * stair_vert_squares -  total_angled_trans # one row of squares
                    square_width = float(section.vars['square_width_var'].get())
                    square_height = float(section.vars['square_height_var'].get())
                    angled_width = float(section.vars['angled_square_width_var'].get())
                    angled_height = float(section.vars['angled_square_height_var'].get())

                    generate_bead_cut_list_stair(
                        section,
                        flat_dims=(square_width, square_height, total_squares),
                        angled_dims=(angled_width, angled_height, total_angled_trans),
                        bead_length=bead_length,
                        panelling_type=panel_type,
                        wall_width=wall_width,
                        kerf=kerf
                    )

            except Exception as e:
                print(f"[ERROR] Failed to update section: {e}")
            
    def update_full_wall_measurements(self):
        """
        Updates all full wall sections based on current inputs.
        Calculates strip layout and bead cut list if needed.
        """
        panel_type = self.panelling_type_dropdown.get_value().lower()
        board_length = self.get_board_length_mm()

        for section in self.full_wall_measurements.sections:
            try:
                wall_width_str = section.vars['wall_length_var'].get()
                wall_height_str = section.vars['wall_height_var'].get()
                horz_squares_str = section.vars['horz_squares_var'].get()
                vert_squares_str = section.vars['vert_squares_var'].get()

                if not all([wall_width_str, wall_height_str, horz_squares_str, vert_squares_str]):
                    continue  # Skip section until it's fully filled in

                wall_width = float(wall_width_str)
                wall_height = float(wall_height_str)
                horz_squares = int(horz_squares_str)
                vert_squares = int(vert_squares_str)
                slat_width_str = self.square_inputs.slat_width_var.get().replace("mm", "").strip()
                slat_width = float(slat_width_str)

                kerf = self.pricing_data.get("kerf", 5000)

                # Perform square panelling logic
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

                if "bead" in panel_type:
                    total_squares = horz_squares * vert_squares
                    square_width = float(section.vars['square_width_var'].get())
                    square_height = float(section.vars['square_height_var'].get())

                    try:
                        bead_length = self.get_bead_length_from_label()
                    except Exception as e:
                        print("[ERROR] Failed to get bead length:", e)
                        bead_length = 5000  # fallback

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

            except Exception as e:
                print(f"[ERROR] Failed to update section: {e}")

    def update_visible_fields(self):
        if not self.gui_ready:
            return
        
        job_type = self.job_type_dropdown.get_value().lower()
        panel_type = self.panelling_type_dropdown.get_value()

        # Hide all input blocks
        self.square_inputs.frame.grid_remove()
        self.dado_inputs.frame.grid_remove()
        self.full_wall_measurements.frame.grid_remove()
        self.half_wall_measurements.frame.grid_remove()
        self.dado_wall_measurements.frame.grid_remove()

        # Show relevant blocks
        if job_type == "full square wall":
            self.square_inputs.frame.grid()
            self.full_wall_measurements.frame.grid()
        elif job_type == "half square wall":
            self.square_inputs.frame.grid()
            self.half_wall_measurements.frame.grid()
        elif job_type == "dado rail":
            self.dado_inputs.frame.grid()
            self.dado_wall_measurements.frame.grid()

        if hasattr(self, "square_inputs") and self.square_inputs:
            self.square_inputs.update_layout_for_job_type(panel_type)  # handle special Square layout
        if hasattr(self, "dado_inputs") and self.dado_inputs:
            self.dado_inputs.update_layout_for_job_type(panel_type)  # handle special Dado layout

    def on_change(self):
        # Triggered when any block reports a change
        job_type = self.job_type_dropdown.get_value()

        if "Full Square Wall" in job_type:
            self.update_full_wall_measurements()
        elif "Half Square Wall" in job_type:
            self.update_half_wall_measurements()

    def on_panelling_type_change(self, *args):
        """Triggered when the panelling type dropdown changes."""
        panel_type = self.panelling_type_dropdown.get_value()
        job_type = self.job_type_dropdown.get_value()

        if hasattr(self, "square_inputs") and self.square_inputs:
            self.square_inputs.update_moulding_dropdown_for_panelling_type(panel_type)
            self.square_inputs.update_ledge_options_from_thickness(panel_type)
            self.full_wall_measurements.update_all_section_visibility(panel_type)
            self.half_wall_measurements.update_all_section_visibility(panel_type)
            self.dado_wall_measurements.update_all_section_visibility(panel_type)
        
        if "Full Square Wall" in job_type:
            self.update_full_wall_measurements()
        elif "Half Square Wall" in job_type:
            self.update_half_wall_measurements()

        self.update_visible_fields()  # updates all visual logic based on dropdown

    def on_job_type_change(self, *args):
        """Triggered when the job type dropdown changes."""
        job_type = self.job_type_dropdown.get_value()

        subtype_options = {
            "Full Square Wall": ["Square Panelling", "Square Panelling with Bead"],
            "Half Square Wall": ["Half Wall", "Half Wall with Bead", "Half Wall with Ledge", "Half Wall with Ledge & Bead"],
            "Dado Rail": ["Dado", "Dado Squares Top & Bottom", "Dado Double Squares Top & Bottom", "Dado Squares Bottom", "Dado Double Squares Bottom"]
        }

        options = subtype_options.get(job_type, [])
        print(f"[DEBUG] Panelling options found: {options}")
        self.panelling_type_dropdown.set_options(options)

        self.update_visible_fields()  # updates all visual logic based on dropdown

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
        main_frame.columnconfigure(0, weight=1)

        # --- Top Frame ---
        top_frame = ttk.Frame(main_frame)
        top_frame.grid(row=0, column=0, sticky="nsew")
        top_frame.columnconfigure(0, weight=1)

        # --- buttons for loading, saving, clearing
        control_frame = ttk.LabelFrame(top_frame, text=("File Actions"))
        control_frame.grid(row=0, column=0, sticky="ew", pady=(5, 10))

        button_row = ttk.Frame(control_frame)
        button_row.pack(anchor="center", pady=10)

        ttk.Button(button_row, text="Create New" , width=15).pack(side="left", padx=(0, 10))
        ttk.Button(button_row, text="Save Measurements" , width=15).pack(side="left", padx=(0, 10))
        ttk.Button(button_row, text="Load Measurements" , width=15).pack(side="left",  padx=(0, 10))
        ttk.Button(button_row, text="Clear Form", width=15).pack(side="left")

        # --- Loaded File
        path_frame = ttk.LabelFrame(top_frame, text=("Loaded File"))
        path_frame.grid(row=1, column=0, sticky="ew", pady=(5, 10))

        path_row = ttk.Frame(path_frame)
        path_row.pack(fill="x", padx=10, pady=10)

        loaded_path_label = ttk.Label(path_row, text="No file loaded", foreground="gray", font=("Segoe UI", 10, "italic"))
        loaded_path_label.pack(anchor="w")

        # declare measurement sections
        self.full_wall_measurements = FullWallMeasurementsBlock(parent=top_frame, on_change=self.on_change)
        self.half_wall_measurements = HalfWallMeasurementsBlock(parent=top_frame, on_change=self.on_change)
        self.dado_wall_measurements = DadoWallMeasurementsBlock(parent=top_frame, on_change=self.on_change)

        # job status block
        self.job_status = JobStatusBlock(top_frame)
        self.job_status.frame.grid(row=2, column=0, sticky="ew", pady=(5, 10))

        # customer details page:
        self.customer_details = CustomerDetailsBlock(top_frame)
        self.customer_details.frame.grid(row=3, column=0, sticky="ew", pady=(5, 10))

        # Create the Job Type Dropdown Block
        self.job_type_dropdown = JobTypeDropdownBlock(top_frame, on_change=self.on_job_type_change)
        self.job_type_dropdown.frame.grid(row=4, column=0, sticky="ew", pady=(5, 10))

        self.panelling_type_dropdown = PanellingTypeDropdownBlock(top_frame, on_change=self.on_panelling_type_change)
        self.panelling_type_dropdown.frame.grid(row=5, column=0, sticky="ew", pady=(5, 10))

        self.square_inputs = SquareInputBlock(
            parent=top_frame,
            material_data=self.material_data,
            moulding_data=self.moulding_data,
            on_change=self.on_panelling_type_change
        )
        self.square_inputs.frame.grid(row=6, column=0, sticky="ew", pady=(5, 10))
        self.square_inputs.update_layout_for_job_type(self.panelling_type_dropdown.get_value())

        self.dado_inputs = DadoInputBlock(
            parent=top_frame,
            dado_data=self.dado_data,
            on_change=self.on_panelling_type_change
        )
        self.dado_inputs.frame.grid(row=7, column=0, sticky="ew", pady=(5, 10))
        self.dado_inputs.update_layout_for_job_type(self.panelling_type_dropdown.get_value())

        self.full_wall_measurements.set_panel_type_var(self.panelling_type_dropdown.var)
        self.half_wall_measurements.set_panel_type_var(self.panelling_type_dropdown.var)
        self.dado_wall_measurements.set_panel_type_var(self.panelling_type_dropdown.var)

        # Show Measurments Sections
        self.full_wall_measurements.frame.grid(row=8, column=0, sticky="ew", pady=(5, 10))
        self.half_wall_measurements.frame.grid(row=9, column=0, sticky="ew", pady=(5, 10))
        self.dado_wall_measurements.frame.grid(row=10, column=0, sticky="ew", pady=(5, 10))

        self.job_material_totals_block = JobMaterialTotalsBlock(parent=top_frame, on_change=self.on_change)
        self.job_material_totals_block.set_job_type_var(self.job_type_dropdown.var)
        self.job_material_totals_block.frame.grid(row=11, column=0, sticky="ew", pady=(5, 10))

        self.job_totals = JobTotalsBlock(top_frame)
        self.job_totals.frame.grid(row=12, column=0, sticky="ew", pady=(5, 10))

        self.job_cutlist_block = JobCutListBlock(parent=top_frame)
        self.job_cutlist_block.frame.grid(row=13, column=0, sticky="ew", pady=(5, 10))

        self.gui_ready = True
        self.update_visible_fields()