import tkinter as tk
from tkinter import ttk

class CustomerDetailsBlock:
    def __init__(self, parent):
        self.vars = {
            "customers_name_var": tk.StringVar(),
            "customers_street_var": tk.StringVar(),
            "customers_postcode_var": tk.StringVar(),
            "date_of_quote_var": tk.StringVar(),
            "full_days_var": tk.StringVar(),
            "extra_hours_var": tk.StringVar()
        }

        self.frame = ttk.LabelFrame(parent, text="Customer & Job Details")
        self.build_fields()

    def build_fields(self):
        for idx, (label_text, var_name) in enumerate(self.vars.items()):
            row = idx // 2
            col = (idx % 2) * 2

            label = ttk.Label(self.frame, text=label_text.replace("_var", "").replace("_", " ").title())
            entry = ttk.Entry(self.frame, textvariable=var_name)

            label.grid(row=row, column=col, sticky="w", padx=5, pady=5)
            entry.grid(row=row, column=col + 1, sticky="ew", padx=5, pady=5)

        # Make entries expand
        for i in range(4):
            self.frame.columnconfigure(i, weight=1)

    def get_values(self):
        return {k: v.get() for k, v in self.vars.items()}

    def clear(self):
        for var in self.vars.values():
            var.set("")