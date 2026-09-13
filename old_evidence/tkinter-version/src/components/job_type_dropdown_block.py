import tkinter as tk
from tkinter import ttk

class JobTypeDropdownBlock:
    def __init__(self, parent, on_change=None):
        """
        Dropdown selector for the main Job Type.
        :param parent: Parent Tkinter frame to attach to
        :param on_change: Callback when selection changes
        """
        self.on_change = on_change
        self.var = tk.StringVar()
        self.var.trace_add("write", lambda *args: self.frame.after(10, lambda: self._job_type_changed(self.var.get()) if self.on_change else None))

        self.frame = ttk.LabelFrame(parent, text="Job Type")
        self.dropdown = ttk.Combobox(self.frame, textvariable=self.var, state="readonly")
        self.dropdown["values"] = ["Full Square Wall", "Half Square Wall", "Dado Rail"]
        self.dropdown.current(0)  # Default selection
        self.dropdown.pack(padx=10, pady=10, fill="x")

    def _job_type_changed(self, *_):
        if self.on_change:
            selected = self.var.get()
            print(f"[DEBUG] Job Type selected: {selected}")
            self.on_change(self.var.get())

    def get_value(self):
        return self.var.get()

    def set(self, value):
        self.var.set(value)

    def clear(self):
        self.var.set("")