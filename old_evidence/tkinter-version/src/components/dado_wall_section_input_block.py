import tkinter as tk
from tkinter import ttk

class DadoWallSectionInputBlock:
    def __init__(self, parent, index=1, on_change=None):
        self.vars = {}  # Store all vars here if needed later
        self.on_change = on_change

        self.frame = ttk.LabelFrame(parent, text=f"Wall Section {index}")
        self.frame.pack(fill="x", pady=(0, 5))

        self.vars['wall_length_var'] = tk.StringVar()
        self.vars['dado_height_var'] = tk.StringVar()
        self.vars['horz_bottom_squares_var'] = tk.StringVar()
        self.vars['horz_top_squares_var'] = tk.StringVar()
        self.vars['bottom_square_width_var'] = tk.StringVar()
        self.vars['bottom_square_height_var'] = tk.StringVar()
        self.vars['top_square_width_var'] = tk.StringVar()
        self.vars['top_square_height_var'] = tk.StringVar()
        self.vars['inner_bottom_square_width_var'] = tk.StringVar()
        self.vars['inner_bottom_square_height_var'] = tk.StringVar()
        self.vars['inner_top_square_width_var'] = tk.StringVar()
        self.vars['inner_top_square_height_var'] = tk.StringVar()
        self.vars['middle_dado_strips_var'] = tk.StringVar()
        self.vars['outer_square_strips_var'] = tk.StringVar()
        self.vars['inner_square_strips_var'] = tk.StringVar()

        row = ttk.Frame(self.frame)
        row.pack(fill="x")

        row.columnconfigure(1, weight=1)  # For first entry
        row.columnconfigure(3, weight=1)  # For second entry

        # --- Wall Measurements ---
        ttk.Label(row, text="Wall Length(mm)").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(row, textvariable=self.vars['wall_length_var']).grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        ttk.Label(row, text="Dado Height(mm)").grid(row=0, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(row, textvariable=self.vars['dado_height_var']).grid(row=0, column=3, sticky="ew", padx=5, pady=5)

        # --- Square Numbers ---
        self.vars["horz_bottom_squares_label"] = ttk.Label(row, text="Horizontal Bottom Squares")
        self.vars["horz_bottom_squares_label"].grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.vars["horz_bottom_squares_entry"] = ttk.Entry(row, textvariable=self.vars['horz_bottom_squares_var'])
        self.vars["horz_bottom_squares_entry"].grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        
        self.vars["horz_top_squares_label"] = ttk.Label(row, text="Horizontal Top Squares")
        self.vars["horz_top_squares_label"].grid(row=1, column=2, sticky="w", padx=5, pady=5)
        self.vars["horz_top_squares_entry"] = ttk.Entry(row, textvariable=self.vars['horz_top_squares_var'])
        self.vars["horz_top_squares_entry"].grid(row=1, column=3, sticky="ew", padx=5, pady=5)

        # --- Square Measurements ---
        self.vars["bottom_square_width_label"] = ttk.Label(row, text="Bottom SqW(mm)")
        self.vars["bottom_square_width_label"].grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.vars["bottom_square_width_entry"] = ttk.Entry(row, textvariable=self.vars['bottom_square_width_var'], state="readonly")
        self.vars["bottom_square_width_entry"].grid(row=2, column=1, sticky="ew", padx=5, pady=5)

        self.vars["bottom_square_height_label"] = ttk.Label(row, text="Bottom SqH(mm)")
        self.vars["bottom_square_height_label"].grid(row=2, column=2, sticky="w", padx=5, pady=5)
        self.vars["bottom_square_height_entry"] = ttk.Entry(row, textvariable=self.vars['bottom_square_height_var'], state="readonly")
        self.vars["bottom_square_height_entry"].grid(row=2, column=3, sticky="ew", padx=5, pady=5)

        self.vars["top_square_width_label"] = ttk.Label(row, text="Top SqW(mm)")
        self.vars["top_square_width_label"].grid(row=3, column=0, sticky="w", padx=5, pady=5)
        self.vars["top_square_width_entry"] = ttk.Entry(row, textvariable=self.vars['top_square_width_var'], state="readonly")
        self.vars["top_square_width_entry"].grid(row=3, column=1, sticky="ew", padx=5, pady=5)

        self.vars["top_square_height_label"] = ttk.Label(row, text="Top SqH(mm)")
        self.vars["top_square_height_label"].grid(row=3, column=2, sticky="w", padx=5, pady=5)
        self.vars["top_square_height_entry"] = ttk.Entry(row, textvariable=self.vars['top_square_height_var'], state="readonly")
        self.vars["top_square_height_entry"].grid(row=3, column=3, sticky="ew", padx=5, pady=5)

        self.vars["inner_bottom_square_width_label"] = ttk.Label(row, text="Inner Bottom SqW(mm)")
        self.vars["inner_bottom_square_width_label"].grid(row=4, column=0, sticky="w", padx=5, pady=5)
        self.vars["inner_bottom_square_width_entry"] = ttk.Entry(row, textvariable=self.vars['inner_bottom_square_width_var'], state="readonly")
        self.vars["inner_bottom_square_width_entry"].grid(row=4, column=1, sticky="ew", padx=5, pady=5)

        self.vars["inner_bottom_square_height_label"] = ttk.Label(row, text="Inner Bottom SqH(mm)")
        self.vars["inner_bottom_square_height_label"].grid(row=4, column=2, sticky="w", padx=5, pady=5)
        self.vars["inner_bottom_square_height_entry"] = ttk.Entry(row, textvariable=self.vars['inner_bottom_square_height_var'], state="readonly")
        self.vars["inner_bottom_square_height_entry"].grid(row=4, column=3, sticky="ew", padx=5, pady=5)

        self.vars["inner_top_square_width_label"] = ttk.Label(row, text="Inner Top SqW(mm)")
        self.vars["inner_top_square_width_label"].grid(row=5, column=0, sticky="w", padx=5, pady=5)
        self.vars["inner_top_square_width_entry"] = ttk.Entry(row, textvariable=self.vars['inner_top_square_width_var'], state="readonly")
        self.vars["inner_top_square_width_entry"].grid(row=5, column=1, sticky="ew", padx=5, pady=5)

        self.vars["inner_top_square_height_label"] = ttk.Label(row, text="Inner Top SqH(mm)")
        self.vars["inner_top_square_height_label"].grid(row=5, column=2, sticky="w", padx=5, pady=5)
        self.vars["inner_top_square_height_entry"] = ttk.Entry(row, textvariable=self.vars['inner_top_square_height_var'], state="readonly")
        self.vars["inner_top_square_height_entry"].grid(row=5, column=3, sticky="ew", padx=5, pady=5)

        # --- Pieces Needed ---
        ttk.Label(row, text="Middle Dado Strips").grid(row=6, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(row, textvariable=self.vars['middle_dado_strips_var'], state="readonly").grid(row=6, column=1, columnspan=3, sticky="ew", padx=5, pady=5)

        self.vars["outer_square_strips_label"] = ttk.Label(row, text="Outer Square Strips")
        self.vars["outer_square_strips_label"].grid(row=7, column=0, sticky="w", padx=5, pady=5)
        self.vars["outer_square_strips_entry"] = ttk.Entry(row, textvariable=self.vars['outer_square_strips_var'], state="readonly")
        self.vars["outer_square_strips_entry"].grid(row=7, column=1, columnspan=3, sticky="ew", padx=5, pady=5)

        self.vars["inner_square_strips_label"] = ttk.Label(row, text="Inner Square Strips")
        self.vars["inner_square_strips_label"].grid(row=8, column=0, sticky="w", padx=5, pady=5)
        self.vars["inner_square_strips_entry"] = ttk.Entry(row, textvariable=self.vars['inner_square_strips_var'], state="readonly")
        self.vars["inner_square_strips_entry"].grid(row=8, column=1, columnspan=3, sticky="ew", padx=5, pady=5)

        self.vars["group_bottom_squares"] = [
            self.vars["horz_bottom_squares_label"],
            self.vars["bottom_square_width_label"],
            self.vars["bottom_square_height_label"],
            self.vars["horz_bottom_squares_entry"],
            self.vars["bottom_square_width_entry"],
            self.vars["bottom_square_height_entry"]
        ]

        self.vars["group_top_squares"] = [
            self.vars["horz_top_squares_label"],
            self.vars["top_square_width_label"],
            self.vars["top_square_height_label"],
            self.vars["horz_top_squares_entry"],
            self.vars["top_square_width_entry"],
            self.vars["top_square_height_entry"]
        ]

        self.vars["group_outer_strips"] = [
            self.vars["outer_square_strips_label"],
            self.vars["outer_square_strips_entry"]
        ]

        self.vars["group_inner_bottom"] = [
            self.vars["inner_bottom_square_width_label"],
            self.vars["inner_bottom_square_height_label"],
            self.vars["inner_bottom_square_width_entry"],
            self.vars["inner_bottom_square_height_entry"]
        ]

        self.vars["group_inner_top"] = [
            self.vars["inner_top_square_width_label"],
            self.vars["inner_top_square_height_label"],
            self.vars["inner_top_square_width_entry"],
            self.vars["inner_top_square_height_entry"]
        ]

        self.vars["group_inner_strips"] = [
            self.vars["inner_square_strips_label"],
            self.vars["inner_square_strips_entry"]
        ]

        # Optional trace
        def trigger_on_change(*_):
            print("[DEBUG] Dado Wall Sections Changed")
            if self.on_change:
                self.on_change()
        
        self.vars["wall_length_var"].trace_add("write", trigger_on_change)
        self.vars["dado_height_var"].trace_add("write", trigger_on_change)
        self.vars["horz_top_squares_var"].trace_add("write", trigger_on_change)
        self.vars["horz_bottom_squares_var"].trace_add("write", trigger_on_change)

    def update_visible_fields(self, panel_type):
        pt = panel_type.lower()

        # Hide everything first
        for group in [
            "group_bottom_squares", "group_top_squares",
            "group_outer_strips", "group_inner_bottom",
            "group_inner_top", "group_inner_strips"
        ]:
            self._hide_group(group)

        # Logic per panel type
        if "dado squares top & bottom" in pt:
            self._show_group("group_bottom_squares")
            self._show_group("group_top_squares")
            self._show_group("group_outer_strips")

        elif "dado double squares top & bottom" in pt:
            self._show_group("group_bottom_squares")
            self._show_group("group_top_squares")
            self._show_group("group_outer_strips")
            self._show_group("group_inner_bottom")
            self._show_group("group_inner_top")
            self._show_group("group_inner_strips")

        elif "dado squares bottom" in pt:
            self._show_group("group_bottom_squares")
            self._show_group("group_outer_strips")

        elif "dado double squares bottom" in pt:
            self._show_group("group_bottom_squares")
            self._show_group("group_outer_strips")
            self._show_group("group_inner_bottom")
            self._show_group("group_inner_strips")

    def _show_group(self, group_name):
        for widget in self.vars[group_name]:
            widget.grid()

    def _hide_group(self, group_name):
        for widget in self.vars[group_name]:
            widget.grid_remove()

    def get_data(self):
        return {key: var.get() for key, var in self.vars.items()}

    def destroy(self):
        self.frame.destroy()