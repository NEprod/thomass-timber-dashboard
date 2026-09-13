import tkinter as tk
from tkinter import ttk

class HalfWallStairSectionInputBlock:
    def __init__(self, parent, index=1, on_change=None):
        self.vars = {}  # Store all vars here if needed later
        self.on_change = on_change

        self.frame = ttk.LabelFrame(parent, text=f"Stair Wall Section {index}")
        self.frame.pack(fill="x", pady=(0, 5))

        self.vars['stair_wall_length_var'] = tk.StringVar()
        self.vars['panel_height_var'] = tk.StringVar()
        self.vars['lower_landing_wall_length_var'] = tk.StringVar()
        self.vars['top_landing_wall_length_var'] = tk.StringVar()
        self.vars['stair_slope_length_var'] = tk.StringVar()
        self.vars['horz_squares_var'] = tk.StringVar()
        self.vars['vert_squares_var'] = tk.StringVar()
        self.vars['angled_square_count_var'] = tk.StringVar()
        self.vars['transition_square_count_var'] = tk.StringVar()
        self.vars['square_width_var'] = tk.StringVar()
        self.vars['square_height_var'] = tk.StringVar()
        self.vars['angled_square_width_var'] = tk.StringVar()
        self.vars['angled_square_height_var'] = tk.StringVar()
        self.vars['slope_mitre_var'] = tk.StringVar()
        self.vars['angled_square_mitres_var'] = tk.StringVar()
        self.vars['vert_strips_var'] = tk.StringVar()
        self.vars['horz_strips_var'] = tk.StringVar()
        self.vars['horz_pieces_per_strip_var'] = tk.StringVar()
        self.vars['vert_pieces_per_strip_var'] = tk.StringVar()
        self.vars['ledge_strips_var'] = tk.StringVar()
        self.vars['bead_strips_var'] = tk.StringVar()

        row = ttk.Frame(self.frame)
        row.pack(fill="x")

        row.columnconfigure(1, weight=1)  # For first entry
        row.columnconfigure(3, weight=1)  # For second entry

        # --- Wall Measurements ---
        ttk.Label(row, text="Stair Wall Length(mm)").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(row, textvariable=self.vars['stair_wall_length_var']).grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        ttk.Label(row, text="Panel Height(mm)").grid(row=0, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(row, textvariable=self.vars['panel_height_var']).grid(row=0, column=3, sticky="ew", padx=5, pady=5)
        ttk.Label(row, text="Lower Landing Length(mm)").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(row, textvariable=self.vars['lower_landing_wall_length_var']).grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        ttk.Label(row, text="Top Landing Length(mm)").grid(row=1, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(row, textvariable=self.vars['top_landing_wall_length_var']).grid(row=1, column=3, sticky="ew", padx=5, pady=5)
        ttk.Label(row, text="Stair Slope Length(mm)").grid(row=3, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(row, textvariable=self.vars['stair_slope_length_var']).grid(row=3, column=3, sticky="ew", padx=5, pady=5)

        # --- Square Numbers ---
        ttk.Label(row, text="Horizontal Squares").grid(row=4, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(row, textvariable=self.vars['horz_squares_var']).grid(row=4, column=1, sticky="ew", padx=5, pady=5)
        ttk.Label(row, text="Vertical Squares").grid(row=4, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(row, textvariable=self.vars['vert_squares_var']).grid(row=4, column=3, sticky="ew", padx=5, pady=5)
        ttk.Label(row, text="Angled Squares").grid(row=5, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(row, textvariable=self.vars['angled_square_count_var']).grid(row=5, column=1, sticky="ew", padx=5, pady=5)
        ttk.Label(row, text="Transition Squares").grid(row=5, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(row, textvariable=self.vars['transition_square_count_var']).grid(row=5, column=3, sticky="ew", padx=5, pady=5)

        # --- Square Measurements ---
        ttk.Label(row, text="Square Width(mm)").grid(row=6, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(row, textvariable=self.vars['square_width_var'], state="readonly").grid(row=6, column=1, sticky="ew", padx=5, pady=5)
        ttk.Label(row, text="Square Height(mm)").grid(row=6, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(row, textvariable=self.vars['square_height_var'], state="readonly").grid(row=6, column=3, sticky="ew", padx=5, pady=5)
        ttk.Label(row, text="Angled Square Width(mm)").grid(row=7, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(row, textvariable=self.vars['angled_square_width_var'], state="readonly").grid(row=7, column=1, sticky="ew", padx=5, pady=5)
        ttk.Label(row, text="Angled Square Height(mm)").grid(row=7, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(row, textvariable=self.vars['angled_square_height_var'], state="readonly").grid(row=7, column=3, sticky="ew", padx=5, pady=5)

        ttk.Label(row, text="Slope Mitre").grid(row=8, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(row, textvariable=self.vars['slope_mitre_var'], state="readonly").grid(row=8, column=1, sticky="ew", padx=5, pady=5)
        ttk.Label(row, text="Angled Square Mitres").grid(row=8, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(row, textvariable=self.vars['angled_square_mitres_var'], state="readonly").grid(row=8, column=3, sticky="ew", padx=5, pady=5)

        # --- Strips Needed Measurements ---
        ttk.Label(row, text="Horizontal Strips Needed").grid(row=9, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(row, textvariable=self.vars['horz_strips_var'], state="readonly").grid(row=9, column=1, sticky="ew", padx=5, pady=5)
        ttk.Label(row, text="Vertical Strips Needed").grid(row=9, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(row, textvariable=self.vars['vert_strips_var'], state="readonly").grid(row=9, column=3, sticky="ew", padx=5, pady=5)

        # --- Pieces Per Strip Measurements ---
        ttk.Label(row, text="Horizontal Pieces Per Strip").grid(row=10, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(row, textvariable=self.vars['horz_pieces_per_strip_var'], state="readonly").grid(row=10, column=1, sticky="ew", padx=5, pady=5)
        ttk.Label(row, text="Vertical Pieces Per Strip").grid(row=10, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(row, textvariable=self.vars['vert_pieces_per_strip_var'], state="readonly").grid(row=10, column=3, sticky="ew", padx=5, pady=5)

        # --- Bead/Ledge Strip Measurements ---
        self.vars["ledge_pieces_label"] = ttk.Label(row, text="Ledge Strips Needed")
        self.vars["ledge_pieces_label"].grid(row=11, column=0, sticky="w", padx=5, pady=5)
        self.vars["ledge_pieces_entry"] = ttk.Entry(row, textvariable=self.vars['ledge_strips_var'], state="readonly")
        self.vars["ledge_pieces_entry"].grid(row=11, column=1, sticky="ew", padx=5, pady=5)
        self.vars["bead_pieces_label"] = ttk.Label(row, text="Bead Strips Needed")
        self.vars["bead_pieces_label"].grid(row=11, column=2, sticky="w", padx=5, pady=5)
        self.vars["bead_pieces_entry"] = ttk.Entry(row, textvariable=self.vars['bead_strips_var'], state="readonly")
        self.vars["bead_pieces_entry"].grid(row=11, column=3, sticky="ew", padx=5, pady=5)

        self.vars["bead_group"] = [
            self.vars["bead_pieces_label"],
            self.vars["bead_pieces_entry"]
        ]
        self.vars["ledge_group"] = [
            self.vars["ledge_pieces_label"],
            self.vars["ledge_pieces_entry"]
        ]

        # Optional trace
        def trigger_on_change(*_):
            print("[DEBUG] Stair Wall Sections Changed")
            if self.on_change:
                self.on_change()
        
        for widget in self.vars["bead_group"] + self.vars["ledge_group"]:
            widget.grid_remove()

        self.vars['stair_wall_length_var'].trace_add("write", trigger_on_change)
        self.vars['panel_height_var'].trace_add("write", trigger_on_change)
        self.vars['lower_landing_wall_length_var'].trace_add("write", trigger_on_change)
        self.vars['top_landing_wall_length_var'].trace_add("write", trigger_on_change)
        self.vars['stair_slope_length_var'].trace_add("write", trigger_on_change)
        self.vars['horz_squares_var'].trace_add("write", trigger_on_change)
        self.vars['vert_squares_var'].trace_add("write", trigger_on_change)

    def update_visible_fields(self, panel_type):
        if "ledge & bead" in panel_type.lower():
            for widget in self.vars["bead_group"] + self.vars["ledge_group"]:
                widget.grid()
        elif "bead" in panel_type.lower():
            for widget in self.vars["bead_group"]:
                widget.grid()
            for widget in self.vars["ledge_group"]:
                widget.grid_remove()
        elif "ledge" in panel_type.lower():
            for widget in self.vars["ledge_group"]:
                widget.grid()
            for widget in self.vars["bead_group"]:
                widget.grid_remove()
        else:
            for widget in self.vars["bead_group"] + self.vars["ledge_group"]:
                widget.grid_remove()

    def get_data(self):
        return {key: var.get() for key, var in self.vars.items()}

    def destroy(self):
        self.frame.destroy()