import tkinter as tk
from tkinter import ttk

class PanellingInputBlock(ttk.Frame):
    def __init__(self, parent, material_data, dado_data, on_change=None):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        style = ttk.Style()
        style.configure("Debug.TLabelframe", borderwidth=2, relief="solid")


        self.parent = parent
        self.material_data = material_data
        self.dado_data = dado_data
        self.on_change = on_change

        self.load_dado_options()
        
        # Variables
        self.slat_thickness_var = tk.StringVar()
        self.slat_width_var = tk.StringVar()
        self.middle_dado_var = tk.StringVar()
        self.gap_width_var = tk.StringVar()
        self.square_dado_var = tk.StringVar()

        # Containers
        self.square_frame = ttk.LabelFrame(self, text="Square Panelling Options")
        self.square_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(5, 10))
        self.square_frame.grid_remove()

        self.dado_frame = ttk.LabelFrame(self, text="Dado Panelling Options")
        self.dado_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 10))
        self.dado_frame.grid_remove()

        # Build inputs
        self.build_square_inputs(self.square_frame)
        self.build_dado_inputs(self.dado_frame)

    def load_dado_options(self):
        # Simple middle dado options (top-level keys like "45mm", "75mm")
        self.middle_dado_simple = [
            f"{key} Dado Rail" for key in self.dado_data.get("dado", {}).keys() if "mm" in key
        ]

        # Complex square dado styles (e.g., "45mm Astragal Curve")
        self.square_dado_styles = []
        for size, variants in self.material_data.get("dado_moulds", {}).items():
            for name in variants:
                self.square_dado_styles.append(f"{size} {name}")

    def configure_dado_inputs(self, panel_type):
        for widget in self.dado_frame.winfo_children():
            widget.grid_remove()

        if panel_type.strip().lower() == "dado":
            # Middle Dado only — full width, properly styled
            ttk.Label(self.dado_frame, text="Middle Dado:").grid(
                row=0, column=0, padx=5, pady=8, sticky="w"
            )
            self.middle_dado_dropdown["values"] = self.middle_dado_simple
            self.middle_dado_dropdown.grid(
                row=0, column=1, columnspan=3, padx=5, pady=8, sticky="ew"
            )

            # Hide the others just in case
            self.gap_width_dropdown.grid_forget()
            self.square_dado_dropdown.grid_forget()

        else:
            # Full Dado layout
            ttk.Label(self.dado_frame, text="Middle Dado:").grid(
                row=0, column=0, padx=5, pady=2, sticky="w"
            )
            self.middle_dado_dropdown["values"] = ["45mm", "75mm"]
            self.middle_dado_dropdown.grid(
                row=0, column=1, padx=5, pady=2, sticky="ew"
            )

            ttk.Label(self.dado_frame, text="Gap Width:").grid(
                row=0, column=2, padx=5, pady=2, sticky="w"
            )
            self.gap_width_var.set("100mm")
            self.gap_width_dropdown["values"] = ["75mm", "100mm", "125mm", "150mm"]
            self.gap_width_dropdown.grid(
                row=0, column=3, padx=5, pady=2, sticky="ew"
            )

            ttk.Label(self.dado_frame, text="Square Dado:").grid(
                row=1, column=0, padx=5, pady=(10, 2), sticky="w"
            )
            self.square_dado_dropdown["values"] = self.square_dado_styles
            self.square_dado_dropdown.grid(
                row=1, column=1, columnspan=3, padx=5, pady=(10, 2), sticky="ew"
            )

        for i in range(4):
            self.dado_frame.columnconfigure(i, weight=1)

    def show_ledge_fields(self):
        if hasattr(self, 'ledge_frame'):
            self.ledge_frame.grid()

    def hide_ledge_fields(self):
        if hasattr(self, 'ledge_frame'):
            self.ledge_frame.grid_remove()

    def show_moulding_fields(self):
        if hasattr(self, 'moulding_frame'):
            self.moulding_frame.grid()

    def hide_moulding_fields(self):
        if hasattr(self, 'moulding_frame'):
            self.moulding_frame.grid_remove()

    def build_square_inputs(self, parent):
        row = 0
        # 🔍 Debug labels — add these right here
        tk.Label(self.square_frame, text="Square Frame DEBUG", bg="red").grid(row=0, column=0, columnspan=2, sticky="ew")
        row += 1

        # Slat Thickness
        ttk.Label(self.square_frame, text="Slat Thickness:").grid(row=row, column=0, sticky="w", padx=2, pady=2)
        self.slat_thickness_dropdown = ttk.Combobox(
            self.square_frame,
            textvariable=self.slat_thickness_var,
            state="readonly",
        )
        thicknesses = [f"{entry['thickness_mm']}mm" for entry in self.material_data.get("mdf_boards", {}).values()]
        self.slat_thickness_dropdown["values"] = thicknesses
        self.slat_thickness_dropdown.grid(row=row+1, column=0, padx=2, pady=2, sticky="ew")

        # Slat Width
        ttk.Label(self.square_frame, text="Slat Width:").grid(row=row, column=1, sticky="w", padx=10, pady=2)
        self.slat_width_entry = ttk.Combobox(
            self.square_frame,
            textvariable=self.slat_width_var,
            values=["75mm", "100mm"],
        )
        self.slat_width_entry.grid(row=row+1, column=1, padx=10, pady=2, sticky="ew")

        for col in range(2):
            self.square_frame.columnconfigure(col, weight=1)

        # Traces
        self.slat_thickness_var.trace_add("write", self.trigger_on_change)
        self.slat_width_var.trace_add("write", self.trigger_on_change)

    def build_dado_inputs(self, parent):
        self.middle_dado_dropdown = ttk.Combobox(parent, textvariable=self.middle_dado_var, state="readonly")
        self.gap_width_dropdown = ttk.Combobox(parent, textvariable=self.gap_width_var, state="readonly")
        self.square_dado_dropdown = ttk.Combobox(parent, textvariable=self.square_dado_var, state="readonly")

        # Traces
        self.middle_dado_var.trace_add("write", self.trigger_on_change)
        self.gap_width_var.trace_add("write", self.trigger_on_change)
        self.square_dado_var.trace_add("write", self.trigger_on_change)

    def update_visibility(self, panel_type):
        if panel_type in ["Square Panelling", "Square Panelling with Bead"]:
            self.square_frame.grid()
            self.dado_frame.grid_remove()
        elif panel_type.lower().startswith("dado"):
            self.dado_frame.grid()
            self.square_frame.grid_remove()
        else:
            self.square_frame.grid_remove()
            self.dado_frame.grid_remove()

    def trigger_on_change(self, *args):
        print("[DEBUG] Panelling Sections Changed")
        if self.on_change:
            self.on_change()