import tkinter as tk
from tkinter import ttk

class DadoInputBlock:
    def __init__(self, parent, dado_data, on_change=None):
        self.dado_data = dado_data
        self.on_change = on_change

        self.middle_dado_var = tk.StringVar()
        self.gap_width_var = tk.StringVar()
        self.square_dado_var = tk.StringVar()

        # --- Wrapper Frame ---
        self.frame = ttk.LabelFrame(parent, text="Dado Panelling Options")
        self.frame.columnconfigure(1, weight=1)
        self.frame.columnconfigure(3, weight=1)

        self._get_dado_styles()

        # Middle Dado
        self.middle_dado_label = ttk.Label(self.frame, text="Middle Dado:")
        self.middle_dado_label.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.middle_dado_dropdown = ttk.Combobox(self.frame, textvariable=self.middle_dado_var, state="readonly")
        self.middle_dado_dropdown["values"] = self.middle_dado_simple
        self.middle_dado_dropdown.set(self.middle_dado_simple[0])
        self.middle_dado_dropdown.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        # Gap Width
        self.gap_width_label = ttk.Label(self.frame, text="Gap Width:")
        self.gap_width_label.grid(row=0, column=2, sticky="w", padx=5, pady=5)
        self.gap_width_dropdown = ttk.Combobox(self.frame, textvariable=self.gap_width_var, values=["75mm", "100mm", "125mm", "150mm"])
        self.gap_width_var.set("100mm")
        self.gap_width_dropdown.grid(row=0, column=3, sticky="ew", padx=5, pady=5)

        # Square Dado
        self.square_dado_dropdown = ttk.Combobox(self.frame, textvariable=self.square_dado_var, state="readonly")
        self.square_dado_dropdown["values"] = self.combined_dado_options
        self.square_dado_dropdown.set(self.combined_dado_options[0])
        self.square_dado_dropdown.grid(row=1, column=0, columnspan=4, sticky="ew", padx=5, pady=10)

        self.middle_dado_var.trace_add("write", self._trigger_on_change)
        self.gap_width_var.trace_add("write", self._trigger_on_change)
        self.square_dado_var.trace_add("write", self._trigger_on_change)

    def _get_dado_styles(self):

        self.middle_dado_simple = [
            f"{key} Dado Rail" for key in self.dado_data.get("dado", {}).keys() if "mm" in key
        ]

        self.square_dado_styles = []

        for key, entry in self.dado_data.items():
            # Only include styles that aren't mm-based or the main 'dado' group
            if "mm" not in key.lower() and key.lower() != "dado":
                variants = entry.get("variants", {})
                for variant in variants.values():
                    self.square_dado_styles.append(variant["label"])

        self.combined_dado_options = self.middle_dado_simple + self.square_dado_styles

    def update_layout_for_job_type(self, panel_type):
        if panel_type.lower()== "dado":
            # Only show the Middle Dado option, full width
            self.middle_dado_dropdown.grid(row=0, column=0, columnspan=4, sticky="ew", padx=5, pady=10)

            # Hide the other controls
            self.gap_width_label.grid_remove()
            self.gap_width_dropdown.grid_remove()
            self.square_dado_dropdown.grid_remove()
        else:
            # Restore standard layout for full dado styles
            self.middle_dado_label.grid(row=0, column=0, sticky="w", padx=5, pady=5)
            self.middle_dado_dropdown.grid(row=0, column=1, columnspan=1, sticky="ew", padx=5, pady=5)
            self.gap_width_label.grid(row=0, column=2, sticky="w", padx=5, pady=5)
            self.gap_width_dropdown.grid(row=0, column=3, sticky="ew", padx=5, pady=5)
            self.square_dado_dropdown.grid(row=1, column=0, columnspan=4, sticky="ew", padx=5, pady=10)

    def _trigger_on_change(self, *args):
        if self.on_change:
            self.on_change()

    def show(self):
        self.frame.update_idletasks()

    def hide(self):
        self.frame.pack_forget()