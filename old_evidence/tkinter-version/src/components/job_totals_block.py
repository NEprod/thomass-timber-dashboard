import tkinter as tk
from tkinter import ttk

class JobTotalsBlock:
    def __init__(self, parent):
        self.vars = {
            "material_cost_var": tk.StringVar(),
            "labour_cost_var": tk.StringVar(),
            "take_home_var": tk.StringVar(),
            "final_price_var": tk.StringVar()
        }

        self.frame = ttk.LabelFrame(parent, text="Job Totals")
        self.build_fields()

    def build_fields(self):
        for idx, (label_text, var_name) in enumerate(self.vars.items()):
            row = idx // 2
            col = (idx % 2) * 2

            label = ttk.Label(self.frame, text=label_text.replace("_var", "").replace("_", " ").title())
            entry = ttk.Entry(self.frame, textvariable=var_name, state="readonly")

            label.grid(row=row, column=col, sticky="w", padx=5, pady=5)
            entry.grid(row=row, column=col + 1, sticky="ew", padx=5, pady=5)

        for i in range(4):
            self.frame.columnconfigure(i, weight=1)

    def update_totals(self, material, labour, take_home, final):
        self.vars["material_cost_var"].set(f"£{material:.2f}")
        self.vars["labour_cost_var"].set(f"£{labour:.2f}")
        self.vars["take_home_var"].set(f"£{take_home:.2f}")
        self.vars["final_price_var"].set(f"£{final:.2f}")

    def clear(self):
        for var in self.vars.values():
            var.set("")