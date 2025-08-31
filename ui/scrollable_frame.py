# ui/scrollable_frame.py
import tkinter as tk
from tkinter import ttk

class ScrollableFrame(ttk.Frame):
    def __init__(self, container, *args, **kwargs):
        fit_width = kwargs.pop("fit_width", False)
        super().__init__(container, *args, **kwargs)

        style = ttk.Style()
        bg_color = style.lookup("TFrame", "background")

        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0, bg=bg_color)
        self.scrollbar_y = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        self.scrollable_frame.bind("<Configure>", self._on_frame_configure)
        if fit_width:
            self.canvas.bind("<Configure>", self._on_canvas_configure_fit_width)

        self.canvas.configure(yscrollcommand=self.scrollbar_y.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar_y.pack(side="right", fill="y")

        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", self._on_mousewheel) # Linux scroll up
        self.canvas.bind("<Button-5>", self._on_mousewheel) # Linux scroll down

    def _on_mousewheel(self, event):
        if event.num == 4: delta = -1
        elif event.num == 5: delta = 1
        else: delta = -1 * (event.delta // 120)
        try:
            self.canvas.yview_scroll(delta, "units")
        except tk.TclError: pass

    def _on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure_fit_width(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def on_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))