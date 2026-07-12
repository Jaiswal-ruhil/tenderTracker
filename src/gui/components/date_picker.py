import tkinter as tk
import re
from datetime import datetime
import calendar

# Local imports
from config import PANEL, CARD, ACCENT, TEXT, MUTED, BG

class DatePickerPopup(tk.Toplevel):
    def __init__(self, parent, entry_var, x, y):
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=PANEL, highlightthickness=1, highlightbackground="#30363D")
        self.entry_var = entry_var
        self.geometry(f"240x240+{x}+{y}")
        
        # Focus/Grab handling
        self.grab_set()
        
        self.year = datetime.now().year
        self.month = datetime.now().month
        
        # Initialize to entry value if valid
        try:
            curr_val = entry_var.get().strip()
            m = re.search(r"\b([0-9]{1,2})[-/]([0-9]{1,2})[-/]([0-9]{4})\b", curr_val)
            if m:
                d, m_val, y = map(int, m.groups())
                self.year = y
                self.month = m_val
            else:
                m2 = re.search(r"\b([0-9]{4})[-/]([0-9]{1,2})[-/]([0-9]{1,2})\b", curr_val)
                if m2:
                    y, m_val, d = map(int, m2.groups())
                    self.year = y
                    self.month = m_val
        except Exception:
            pass
            
        self.header_fr = tk.Frame(self, bg=PANEL)
        self.header_fr.pack(fill="x", pady=4)
        
        btn_prev = tk.Button(self.header_fr, text="<", command=self.prev_month,
                             bg=CARD, fg=TEXT, relief="flat", font=("Segoe UI", 9, "bold"),
                             padx=6, pady=2, activebackground=ACCENT, activeforeground=BG, cursor="hand2")
        btn_prev.pack(side="left", padx=6)
        
        self.title_lbl = tk.Label(self.header_fr, text="", font=("Segoe UI", 9, "bold"), bg=PANEL, fg=TEXT)
        self.title_lbl.pack(side="left", fill="x", expand=True)
        
        btn_next = tk.Button(self.header_fr, text=">", command=self.next_month,
                             bg=CARD, fg=TEXT, relief="flat", font=("Segoe UI", 9, "bold"),
                             padx=6, pady=2, activebackground=ACCENT, activeforeground=BG, cursor="hand2")
        btn_next.pack(side="right", padx=6)
        
        days_fr = tk.Frame(self, bg=PANEL)
        days_fr.pack(fill="x")
        for d in ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]:
            lbl = tk.Label(days_fr, text=d, font=("Segoe UI", 8, "bold"), bg=PANEL, fg=MUTED, width=3)
            lbl.pack(side="left", fill="x", expand=True)
            
        self.grid_fr = tk.Frame(self, bg=PANEL)
        self.grid_fr.pack(fill="both", expand=True, pady=4)
        
        self.bind("<Button-1>", self._check_click_outside)
        
        self.draw_grid()

    def prev_month(self):
        if self.month == 1:
            self.month = 12
            self.year -= 1
        else:
            self.month -= 1
        self.draw_grid()
        
    def next_month(self):
        if self.month == 12:
            self.month = 1
            self.year += 1
        else:
            self.month += 1
        self.draw_grid()

    def draw_grid(self):
        for widget in self.grid_fr.winfo_children():
            widget.destroy()
            
        self.title_lbl.configure(text=f"{calendar.month_name[self.month]} {self.year}")
        
        cal = calendar.Calendar()
        try:
            weeks = cal.monthdayscalendar(self.year, self.month)
        except Exception:
            weeks = []
            
        for r_idx, week in enumerate(weeks):
            w_frame = tk.Frame(self.grid_fr, bg=PANEL)
            w_frame.pack(fill="x")
            for c_idx, day in enumerate(week):
                if day == 0:
                    lbl = tk.Label(w_frame, text="", bg=PANEL, width=3)
                    lbl.pack(side="left", fill="x", expand=True)
                else:
                    btn = tk.Button(w_frame, text=str(day),
                                    command=lambda d=day: self.select_date(d),
                                    bg=CARD, fg=TEXT, relief="flat",
                                    font=("Segoe UI", 8), width=3,
                                    activebackground=ACCENT, activeforeground=BG, cursor="hand2")
                    if self.year == datetime.now().year and self.month == datetime.now().month and day == datetime.now().day:
                        btn.configure(fg=ACCENT, font=("Segoe UI", 8, "bold"))
                    btn.pack(side="left", fill="x", expand=True, padx=1, pady=1)

    def select_date(self, day):
        formatted_date = f"{day:02d}-{self.month:02d}-{self.year}"
        self.entry_var.set(formatted_date)
        self.destroy()

    def _check_click_outside(self, event):
        x, y = event.x_root, event.y_root
        w_x = self.winfo_rootx()
        w_y = self.winfo_rooty()
        w_w = self.winfo_width()
        w_h = self.winfo_height()
        if not (w_x <= x <= w_x + w_w and w_y <= y <= w_y + w_h):
            self.destroy()
