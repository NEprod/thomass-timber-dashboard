from tkinter import ttk
from components.full_wall_section_input_block import FullWallSectionInputBlock

class FullWallMeasurementsBlock:
    def __init__(self, parent, on_change=None):
        self.panel_type_var = None
        self.on_change = on_change

        self.frame = ttk.LabelFrame(parent, text="Full Wall Measurements")
        self.section_container = ttk.Frame(self.frame)
        self.section_container.pack(fill="x", padx=10, pady=10)

        self.sections = []
        self.on_change = on_change

        # Button row
        button_row = ttk.Frame(self.frame)
        button_row.pack(fill="x", pady=(0,10))

        # Ensure all columns stay equal width even if buttons are hidden
        for col in range(2):
            button_row.columnconfigure(col, weight=1, minsize=100, uniform="equal")

        ttk.Button(button_row, text="+ Wall Section", command=self.add_wall_section).grid(row=0, column=0, sticky="ew", padx=(10, 5))
        self.remove_button =  ttk.Button(button_row, text="- Wall Section", command=self.remove_wall_section)
        self.remove_button.grid(row=0, column=1, sticky="ew", padx=(5, 10))

        self.add_wall_section()  # Add one by default

    def add_wall_section(self):
        index = len(self.sections) + 1
        section_block = FullWallSectionInputBlock(self.section_container, index=index, on_change=self.on_change)
        section_block.vars['index'] = index

        if self.panel_type_var:
            section_block.update_visible_fields(self.panel_type_var.get())
            
        self.sections.append(section_block)
        self.update_remove_button_state()

    def remove_wall_section(self):
        if len(self.sections) > 1:
            last = self.sections.pop()
            last.destroy()
            self.update_remove_button_state()

            if self.on_change:
                self.on_change()

    def update_remove_button_state(self):
        if len(self.sections) <= 1:
            self.remove_button.grid_remove()
        else:
            self.remove_button.grid()

    def update_all_section_visibility(self, panel_type):
            for section in self.sections:
                section.update_visible_fields(panel_type)

    def set_panel_type_var(self, panel_type_var):
        self.panel_type_var = panel_type_var