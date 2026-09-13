import tkinter as tk
from tkinter import ttk

class JobMaterialTotalsBlock:
    def __init__(self, parent, on_change=None):
        self.frame = ttk.LabelFrame(parent, text="Material Totals")
        self.on_change = on_change
        self.job_type_var = None

        # Variables for all possible material fields
        self.vars = {
            # For Full and Half
            "total_hv_strips_var": tk.StringVar(),
            "ledge_strips_var": tk.StringVar(),
            "boards_needed_var": tk.StringVar(),
            "board_cost_var": tk.StringVar(),
            "beads_needed_var": tk.StringVar(),
            "bead_cost_var": tk.StringVar(),

            # For Dado
            "middle_dado_needed_var": tk.StringVar(),
            "middle_dado_cost_var": tk.StringVar(),
            "square_dado_needed_var": tk.StringVar(),
            "square_dado_cost_var": tk.StringVar(),

            # For all panelling styles
            "linear_meterage_panelling_var": tk.StringVar(),
            "linear_meterage_beading_ledge_var": tk.StringVar(),

            # Shared cost fields
            "mastic_needed_var": tk.StringVar(),
            "mastic_cost_var": tk.StringVar(),
            "cut_cost_var": tk.StringVar(),
            "delivery_cost_var": tk.StringVar()
        }

        # Labels dictionary for showing/hiding by job type
        self.labels = {}

        self.build_layout()

    def set_job_type_var(self, job_type_var):
        """Attach the job type dropdown variable and update on change."""
        self.job_type_var = job_type_var
        if self.job_type_var:
            self.job_type_var.trace_add("write", lambda *_: self.update_visible_fields())
            self.update_visible_fields()

    def build_layout(self):
        """Create read-only entry fields in a 2-column grid."""
        self.inputs = {}  # Keep track of field widgets for visibility toggling

        # Define the order you'd like the fields to appear
        field_order = [
            # Full/Half
            "total_hv_strips_var", "ledge_strips_var",
            "boards_needed_var", "board_cost_var",
            "beads_needed_var", "bead_cost_var",

            # Dado
            "middle_dado_needed_var", "middle_dado_cost_var",
            "square_dado_needed_var", "square_dado_cost_var",

            # Shared
            "linear_meterage_panelling_var", "linear_meterage_beading_ledge_var",
            "mastic_needed_var", "mastic_cost_var",
            "cut_cost_var", "delivery_cost_var"
        ]

        row = 0
        col = 0
        for key in field_order:
            label_text = key.replace("_var", "").replace("_", " ").capitalize()

            label = ttk.Label(self.frame, text=label_text + ":")
            entry = ttk.Entry(self.frame, textvariable=self.vars[key], state="readonly", width=18)

            label.grid(row=row, column=col*2, sticky="w", padx=(10, 5), pady=4)
            entry.grid(row=row, column=col*2+1, sticky="w", padx=(0, 15), pady=4)

            self.labels[key] = label
            self.inputs[key] = entry

            col += 1
            if col == 2:
                col = 0
                row += 1

    def update_visible_fields(self):
        """Show or hide fields depending on job type."""
        for key in self.labels:
            self.labels[key].grid_remove()
            self.inputs[key].grid_remove()

        if not self.job_type_var:
            return

        job_type = self.job_type_var.get().lower()
        visible_keys = {
            "linear_meterage_panelling_var", "mastic_needed_var", "mastic_cost_var", "cut_cost_var", "delivery_cost_var"
        }

        if "full" in job_type:
            visible_keys.update({
                "total_hv_strips_var", "boards_needed_var", "board_cost_var",
                "beads_needed_var", "bead_cost_var",
                "linear_meterage_beading_ledge_var"
            })

        if "half" in job_type:
            visible_keys.update({
                "total_hv_strips_var", "boards_needed_var", "board_cost_var",
                "ledge_strips_var", "beads_needed_var", "bead_cost_var",
                "linear_meterage_beading_ledge_var"
            })

        if "dado" in job_type:
            visible_keys.update({
                "middle_dado_needed_var", "middle_dado_cost_var",
                "square_dado_needed_var", "square_dado_cost_var"
            })

        for key in visible_keys:
            self.labels[key].grid()
            self.inputs[key].grid()

    def update_totals(self, data):
        """Update field values from provided dictionary."""
        for key, var in self.vars.items():
            if key in data:
                if "cost" in key:
                    var.set(f"£{float(data[key]):.2f}")
                elif "meterage" in key:
                    var.set(f"{float(data[key]):.2f}m")
                else:
                    var.set(str(data[key]))
            else:
                var.set("")  # Clear if not included