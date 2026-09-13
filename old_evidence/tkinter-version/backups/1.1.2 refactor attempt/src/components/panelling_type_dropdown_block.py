import tkinter as tk
from tkinter import ttk

class PanellingTypeDropdownBlock:
    def __init__(self, parent, on_change=None):
        self.var = tk.StringVar()
        self.on_change = on_change
        self.frame = ttk.LabelFrame(parent, text="Panelling Type")
        self.dropdown = ttk.Combobox(self.frame, textvariable=self.var, values=[], state="readonly") # values=[] populate dynamically
        self.dropdown.pack(padx=10, pady=10, fill="x")

        if self.on_change:
            self.var.trace_add("write", lambda *args: self.frame.after(10, lambda: self.on_change()))

    def set_options(self, values):
        """Set the dropdown options and reset selection."""
        self.dropdown["values"] = values
        if values:
            self.var.set(values[0])
            self.frame.pack(fill="x", pady=(5, 10))
        else:
            self.var.set("")
            self.frame.pack_forget()

    def get_value(self):
        return self.var.get()

    def clear(self):
        self.var.set("")