import tkinter as tk
from tkinter import ttk

class PanellingTypeDropdownBlock:
    def __init__(self, parent, on_change=None):
        self.var = tk.StringVar()
        self.on_change = on_change
        self.frame = ttk.LabelFrame(parent, text="Panelling Type")
        self.dropdown = ttk.Combobox(self.frame, textvariable=self.var, values=[], state="readonly") # values=[] populate dynamically
        self.dropdown.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.frame.columnconfigure(0, weight=1)
        self.var.trace_add("write", lambda *args: self._panel_type_changed())

    def set_options(self, values):
        """Set the dropdown options and reset selection."""
        self.dropdown["values"] = values
        if values:
            self.var.set(values[0])
            self.frame.grid
        else:
            self.var.set("")
            self.frame.grid_remove()

    def _panel_type_changed(self):
        if self.on_change:
            selected = self.var.get()
            print(f"[DEBUG] Panel Type selected: {selected}")
            self.on_change(selected)

    def get_value(self):
        return self.var.get()

    def clear(self):
        self.var.set("")