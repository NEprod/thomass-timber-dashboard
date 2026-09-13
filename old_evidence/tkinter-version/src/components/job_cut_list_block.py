import tkinter as tk
from tkinter import ttk

class JobCutListBlock:
    def __init__(self, parent):
        self.frame = ttk.LabelFrame(parent, text="Cut List Display")

        # Main content frame
        content_frame = ttk.Frame(self.frame)
        content_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Scrollbar
        scrollbar = ttk.Scrollbar(content_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        # Text box with fixed-width font and no word wrap
        self.textbox = tk.Text(
            content_frame,
            height=25,
            font=("Courier", 12),
            wrap="none",
            yscrollcommand=scrollbar.set
        )
        self.textbox.pack(fill="both", expand=True)
        self.textbox.config(state="disabled")
        scrollbar.config(command=self.textbox.yview)

        # Button
        button = ttk.Button(self.frame, text="Generate Cut List", command=self.generate_cut_list)
        button.pack(fill="x", padx=10, pady=(0, 10))

    def generate_cut_list(self):
        # TEMP placeholder logic until real data integration
        output = ["[Cut List Placeholder]\n", "This will display the MDF and Bead cut lists per wall."]
        
        self.textbox.config(state="normal")
        self.textbox.delete("1.0", tk.END)
        self.textbox.insert("1.0", "\n".join(output))
        self.textbox.config(state="disabled")