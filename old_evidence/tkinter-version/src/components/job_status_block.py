import tkinter as tk
from tkinter import ttk

class JobStatusBlock:
    def __init__(self, parent):
        self.vars = {
            "sent_quote_var": tk.BooleanVar(),
            "quote_accepted_var": tk.BooleanVar(),
            "date_agreed_var": tk.BooleanVar(),
            "job_completed_var": tk.BooleanVar(),
            "agreed_date_var": tk.StringVar()
        }

        self.frame = ttk.LabelFrame(parent, text="Job Status")
        self.build_fields()

    def build_fields(self):
        # Row 0: Four checkboxes
        checkbox_labels = [
            ("Sent Quote", "sent_quote_var"),
            ("Quote Accepted", "quote_accepted_var"),
            ("Date Agreed", "date_agreed_var"),
            ("Job Completed", "job_completed_var")
        ]

        for col, (label, var_key) in enumerate(checkbox_labels):
            cb = ttk.Checkbutton(
                self.frame,
                text=label,
                variable=self.vars[var_key]
            )
            cb.grid(row=0, column=col, padx=5, pady=5, sticky="w")

        # Row 1: Agreed Date entry field (full width)
        date_label = ttk.Label(self.frame, text="Agreed Date")
        date_label.grid(row=1, column=0, sticky="w", padx=5, pady=5)

        date_entry = ttk.Entry(self.frame, textvariable=self.vars["agreed_date_var"])
        date_entry.grid(row=1, column=1, columnspan=3, sticky="ew", padx=5, pady=5)

        for i in range(4):
            self.frame.columnconfigure(i, weight=1)

    def get_values(self):
        return {k: v.get() for k, v in self.vars.items()}

    def clear(self):
        for var in self.vars.values():
            if isinstance(var, tk.BooleanVar):
                var.set(False)
            else:
                var.set("")