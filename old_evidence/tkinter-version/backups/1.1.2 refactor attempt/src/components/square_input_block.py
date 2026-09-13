import tkinter as tk
from tkinter import ttk

class SquareInputBlock:
    def __init__(self, parent, material_data, on_change=None):
        self.material_data = material_data
        self.on_change = on_change

        self.slat_thickness_var = tk.StringVar()
        self.slat_width_var = tk.StringVar()
        self.moulding_type_var = tk.StringVar()
        self.ledge_type_var = tk.StringVar()

        # --- Wrapper Frame ---
        self.frame = ttk.LabelFrame(parent, text="Square Panelling Options")
        self.frame.columnconfigure(1, weight=1)
        self.frame.columnconfigure(3, weight=1)

        self.common_slat_widths = ["75mm", "100mm"]

        mdf_thicknesses = list(self.material_data.get("mdf", {}).keys())

        # --- Slat Thickness ---
        ttk.Label(self.frame, text="Slat Thickness:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.slat_thickness_dropdown = ttk.Combobox(self.frame, textvariable=self.slat_thickness_var, values=mdf_thicknesses, state="readonly")
        self.slat_thickness_dropdown.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        self.slat_thickness_var.set(mdf_thicknesses[1])

        # --- Slat Width ---
        ttk.Label(self.frame, text="Slat Width:").grid(row=0, column=2, sticky="w", padx=5, pady=5)
        self.slat_width_entry = ttk.Combobox(self.frame, textvariable=self.slat_width_var, values= [""] + self.common_slat_widths, state="normal")
        self.slat_width_entry.grid(row=0, column=3, sticky="ew", padx=5, pady=5)

        # --- Moulding Type ---
        self.moulding_type_label = ttk.Label(self.frame, text="Moulding Type:")
        self.moulding_type_label.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        self.moulding_type_dropdown = ttk.Combobox(
            self.frame, textvariable=self.moulding_type_var, values=["Astragal", "Bead", "Chamfered"]
        )
        self.moulding_type_dropdown.grid(row=4, column=0, columnspan=4, sticky="ew", padx=5, pady=5)

        # --- Ledge Type ---        
        self.ledge_type_label = ttk.Label(self.frame, text="Ledge Thicknes:")
        self.ledge_type_label.grid(row=3, column=1, sticky="w", padx=5, pady=5)
        self.ledge_type_dropdown = ttk.Combobox(
            self.frame, textvariable=self.ledge_type_var, values=["Standard", "Shelf Ledge", "None"]
        )
        self.ledge_type_dropdown.grid(row=4, column=0, columnspan=4, sticky="ew", padx=5, pady=5)

        # --- Traces ---
        self.slat_thickness_var.trace_add("write", self._trigger_on_change)
        self.slat_width_var.trace_add("write", self._trigger_on_change)
        self.moulding_type_var.trace_add("write", self._trigger_on_change)
        self.ledge_type_var.trace_add("write", self._trigger_on_change)

    def update_layout_for_job_type(self, panel_type):
        if "ledge & bead" in panel_type.lower():
            # Only show the Middle Dado option, full width
            self.moulding_type_label.grid(row=1, column=0, sticky="w", padx=5, pady=5)
            self.moulding_type_dropdown.grid(row=2, column=0, columnspan=4, sticky="ew", padx=5, pady=5)
            self.ledge_type_label.grid(row=3, column=0, sticky="w", padx=5, pady=5)
            self.ledge_type_dropdown.grid(row=4, column=0, columnspan=4, sticky="ew", padx=5, pady=5)
            # Set default if it's blank or not in the expected options
            if self.slat_width_var.get() not in self.common_slat_widths:
                self.slat_width_var.set(self.common_slat_widths[1])  # or [1], depending on context
        elif "bead" in panel_type.lower():
            self.moulding_type_label.grid(row=1, column=0, sticky="w", padx=5, pady=5)
            self.moulding_type_dropdown.grid(row=2, column=0, columnspan=4, sticky="ew", padx=5, pady=5)
            self.ledge_type_label.grid_remove()
            self.ledge_type_dropdown.grid_remove()
            if self.slat_width_var.get() not in self.common_slat_widths:
                self.slat_width_var.set(self.common_slat_widths[1])  # or [1], depending on context
        elif "ledge" in panel_type.lower():
            # Show ledge only
            self.ledge_type_label.grid(row=1, column=0, sticky="w", padx=5, pady=5)
            self.ledge_type_dropdown.grid(row=2, column=0, columnspan=4, sticky="ew", padx=5, pady=5)
            self.moulding_type_label.grid_remove()
            self.moulding_type_dropdown.grid_remove()
            if self.slat_width_var.get() not in self.common_slat_widths:
                self.slat_width_var.set(self.common_slat_widths[2])  # or [1], depending on context
        else:
            # Neither bead nor ledge
            self.moulding_type_label.grid_remove()
            self.moulding_type_dropdown.grid_remove()
            self.ledge_type_label.grid_remove()
            self.ledge_type_dropdown.grid_remove()
            if self.slat_width_var.get() not in self.common_slat_widths:
                self.slat_width_var.set(self.common_slat_widths[2])  # or [1], depending on context

    def _trigger_on_change(self, *args):
        if self.on_change:
            self.on_change()

    def show(self):
        self.frame.pack(fill="x", pady=(5, 10))

    def clear(self):
        self.frame.pack_forget()