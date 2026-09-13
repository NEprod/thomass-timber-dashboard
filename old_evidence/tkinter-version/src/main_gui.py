import os
import tkinter as tk
from tkinter import ttk
from job_sheet_window import JobSheetWindow

class TimberPricingApp:

    def __init__(self, root, log=None):
        self.root = root
        self.root.title("Thomas's Timber Management Quote Management Page")
        self.root.geometry("800x600")
        self.root.resizable(False, False)
        self.log = log

        self.build_interface()

    def open_job_sheet_window(self):
        JobSheetWindow(self.root)

    def build_interface(self):
        # --- Main Frame ---
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Top Frame ---
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill="x", anchor="n")

        # --- Left: Job Information Frame will hold [Jobs Awaiting Reply Accepted Jobs and Jobs To Do counts]
        job_count_frame = ttk.LabelFrame(top_frame, text=("Job Count"))
        job_count_frame.pack(side="left", expand=True, fill="both")

        # --- Placeholder labels for coding later
        tk.Label(job_count_frame, text="Total Job Count:").grid(row=1, column=0, sticky="w")
        self.total_jobs = tk.Label(job_count_frame, text="ToDo") # Need function to find out how many total jobs saved.
        self.total_jobs.grid(row=1, column=2, sticky="w")

        # --- Right: Insert Job Measurments ---
        job_measurments_frame = ttk.LabelFrame(top_frame, text="Job Measurements")
        job_measurments_frame.pack(side="left", expand=True, fill="both")

        tk.Button(job_measurments_frame, text="Square Panelling", command=self.open_job_sheet_window, width=20).pack(padx=0, pady=0)

if __name__ == "__main__":
    root =tk.Tk()
    app = TimberPricingApp(root)
    root.mainloop()