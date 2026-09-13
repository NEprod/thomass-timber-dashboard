import tkinter as tk
from tkinter import ttk

class SquareInputBlock:
    def __init__(self, parent, material_data, moulding_data, on_change=None):
        self.material_data = material_data
        self.moulding_data = moulding_data
        self.on_change = on_change

        self.slat_width_user_modified = False

        self.slat_thickness_var = tk.StringVar()
        self.slat_width_var = tk.StringVar()
        self.moulding_type_var = tk.StringVar()
        self.ledge_type_var = tk.StringVar()

        # --- Wrapper Frame ---
        self.frame = ttk.LabelFrame(parent, text="Square Panelling Options")
        self.frame.columnconfigure(1, weight=1)
        self.frame.columnconfigure(3, weight=1)

        mdf_thicknesses = list(self.material_data.get("mdf", {}).keys())

        # --- Slat Thickness ---
        ttk.Label(self.frame, text="Slat Thickness:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.slat_thickness_dropdown = ttk.Combobox(self.frame, textvariable=self.slat_thickness_var, values=mdf_thicknesses, state="readonly")
        self.slat_thickness_dropdown.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        self.slat_thickness_var.set(mdf_thicknesses[1])

        # --- Slat Width ---
        self.slat_widths = ["","75mm","100mm"]
        ttk.Label(self.frame, text="Slat Width:").grid(row=0, column=2, sticky="w", padx=5, pady=5)
        self.slat_width_entry = ttk.Combobox(self.frame, textvariable=self.slat_width_var, values=self.slat_widths, state="normal")
        self.slat_width_entry.grid(row=0, column=3, sticky="ew", padx=5, pady=5)

        self.slat_width_entry.bind("<<ComboboxSelected>>", self._on_slat_width_selected)
        self.slat_width_entry.bind("<Key>", self._on_slat_width_typed)

        # --- Moulding Type ---
        self.moulding_type_label = ttk.Label(self.frame, text="Moulding Type:")
        self.moulding_type_label.grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.moulding_type_dropdown = ttk.Combobox(
            self.frame, textvariable=self.moulding_type_var, values=["Astragal", "Bead", "Chamfered"]
        )
        self.moulding_type_dropdown.grid(row=2, column=0, columnspan=4, sticky="ew", padx=5, pady=5)

        # --- Ledge Type ---        
        self.ledge_type_label = ttk.Label(self.frame, text="Ledge Thicknes:")
        self.ledge_type_label.grid(row=3, column=0, sticky="w", padx=5, pady=5)
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
            self.moulding_type_label.grid()
            self.moulding_type_dropdown.grid()
            self.ledge_type_label.grid()
            self.ledge_type_dropdown.grid()
        elif "bead" in panel_type.lower():
            self.moulding_type_label.grid()
            self.moulding_type_dropdown.grid()
            self.ledge_type_label.grid_remove()
            self.ledge_type_dropdown.grid_remove()
        elif "ledge" in panel_type.lower():
            # Show ledge only
            self.ledge_type_label.grid()
            self.ledge_type_dropdown.grid()
            self.moulding_type_label.grid_remove()
            self.moulding_type_dropdown.grid_remove()
        else:
            # Neither bead nor ledge
            self.moulding_type_label.grid_remove()
            self.moulding_type_dropdown.grid_remove()
            self.ledge_type_label.grid_remove()
            self.ledge_type_dropdown.grid_remove()

        if not self.slat_width_user_modified:
            if "bead" in panel_type.lower():
                self.slat_width_var.set(self.slat_widths[1])
            else:
                self.slat_width_var.set(self.slat_widths[2])


    def update_moulding_dropdown_for_panelling_type(self, panel_type):
        raw_value = self.slat_thickness_var.get().replace("mm", "")

        try:
            selected_thickness = int(raw_value)  # Convert to int for comparison
        except ValueError:
            selected_thickness = None

        # If invalid thickness or empty, clear dropdown and exit early
        if not selected_thickness:
            self.moulding_type_dropdown["values"] = []   # Clear dropdown options
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
        self.moulding_type_dropdown["values"] = options

        # Auto-select first match, or show placeholder if none
        if options:
            current = self.moulding_type_var.get()
            if current not in options:
                self.moulding_type_var.set(options[0])
        else:
            self.moulding_type_var.set("No mouldings available")

    def update_ledge_options_from_thickness(self, panel_type):
        try:
            raw = self.slat_thickness_var.get().replace("mm", "")
            if not raw.isdigit():
                self.ledge_type_dropdown["values"] = []
                self.ledge_type_var.set("")
                return
            thickness = int(raw)
        except:
            self.ledge_type_dropdown["values"] = []
            self.ledge_type_var.set("")
            return

        options = []

        if "ledge & bead" in panel_type.lower():
            # Ledge should be thick enough to fit moulding — 3x slat
            ledge_3x = thickness * 3
            self.ledge_mm_value = ledge_3x
            options.append(f"{ledge_3x}mm ledge (3x Slat thicknes) to incorporate bead")
        else:
            # Default: 2x slat thickness for plain ledge
            ledge_2x = thickness * 2
            self.ledge_mm_value = ledge_2x
            options.append(f"{ledge_2x}mm ledge (2x Slat thicknes)")

        self.ledge_type_dropdown["values"] = options
        self.ledge_type_var.set(options[0] if options else "")

    def _trigger_on_change(self, *args):
        if self.on_change:
            self.on_change()

    def _on_slat_width_change(self, *args):
        if self.slat_width_var.get():  # Only set flag if not blank
            self.slat_width_user_modified = True
        self._trigger_on_change()

    def _on_slat_width_selected(self, event):
        # Chose from dropdown set the flag
        self.slat_width_user_modified = True

    def _on_slat_width_typed(self, event):
        # They typed — now set the flag
        self.slat_width_user_modified = True