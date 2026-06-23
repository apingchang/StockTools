"""
stocktool.gui.calendar - 純 Tkinter 日期挑選對話框
====================================================

v1.1 重構：把 _CalendarDialog 從 StockTool.py 抽出

被依賴：gui/tab_portfolio.py（買賣記錄）
依賴：無（純 Tkinter）
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import tkinter as tk
from tkinter import ttk


class _CalendarDialog:
    """
    簡單彈出式月曆。
    使用方式：
        date_str = _CalendarDialog.pick(parent, initial="2026-06-11")
        # date_str == "YYYY-MM-DD"（str）或 None（取消）
    """
    DAY_HEADER = ["一", "二", "三", "四", "五", "六", "日"]

    def __init__(self, parent, initial: str = ""):
        self.result: Optional[str] = None

        self.win = tk.Toplevel(parent)
        self.win.withdraw()
        self.win.title("挑選日期")
        self.win.resizable(False, False)
        self.win.transient(parent)
        self.win.grab_set()
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        if initial:
            try:
                self.current = datetime.strptime(initial, "%Y-%m-%d")
            except ValueError:
                self.current = datetime.now()
        else:
            self.current = datetime.now()

        self._build()
        self.win.deiconify()
        # wait_window() blocks until win is destroyed (_select / _cancel / X).
        # GUI stays fully responsive; grab_set() makes this window modal.
        self.win.wait_window()

    def _build(self):
        win = self.win

        # ── 頂部導航列 ──
        nav = ttk.Frame(win)
        nav.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(nav, text="◀◀", width=3,
                   command=lambda: self._navigate_years(-1)).pack(side="left")
        ttk.Button(nav, text="◀", width=3,
                   command=lambda: self._navigate(-1)).pack(side="left")

        # 年份 label（點擊可直接修改年份）
        self._year_lbl = tk.Label(nav, text="", font=("Segoe UI", 9, "bold"),
                                   cursor="hand2", bg="#e8f0fe", padx=4)
        self._year_lbl.pack(side="left", padx=(4, 0))
        self._year_lbl.bind("<Button-1>", lambda e: self._open_year_dialog())

        # 月份 label（點擊可直接修改月份）
        self._month_lbl = tk.Label(nav, text="", width=10, font=("Segoe UI", 10, "bold"),
                                   cursor="hand2", bg="#fff8e1", padx=4)
        self._month_lbl.pack(side="left", padx=4, expand=True)
        self._month_lbl.bind("<Button-1>", lambda e: self._open_month_menu())

        ttk.Button(nav, text="▶", width=3,
                   command=lambda: self._navigate(1)).pack(side="right")
        ttk.Button(nav, text="▶▶", width=3,
                   command=lambda: self._navigate_years(1)).pack(side="right")

        # ── 星期抬頭 ──
        hdr = ttk.Frame(win)
        hdr.pack(fill="x", padx=8, pady=(0, 2))
        for d in self.DAY_HEADER:
            lbl = ttk.Label(hdr, text=d, width=4, anchor="center",
                             font=("Segoe UI", 8, "bold"))
            lbl.pack(side="left", padx=1)
            if d == "六":
                lbl.config(foreground="#0070c0")
            elif d == "日":
                lbl.config(foreground="#c00000")

        # ── 日按鈕區域 ──
        self._day_frame = ttk.Frame(win)
        self._day_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._render_days()

        # ── 底部按鈕 ──
        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=(0, 8))
        ttk.Button(btn_frame, text="取消", command=self._cancel).pack(side="left", padx=8)

    def _navigate_years(self, delta: int):
        """往前/往後跳一年"""
        self.current = self.current.replace(year=self.current.year + delta)
        self._render_days()

    def _navigate(self, delta: int):
        """往前/往後跳一個月"""
        y, m = self.current.year, self.current.month
        m += delta
        if m > 12:
            m, y = 1, y + 1
        elif m < 1:   # Bugfix: month=0 → 12 月（往前翻年）
            m, y = 12, y - 1
        self.current = self.current.replace(year=y, month=m)
        self._render_days()

    def _open_year_dialog(self):
        """點年份 → 彈出對話框直接輸入年份"""
        dlg = tk.Toplevel(self.win)
        dlg.overrideredirect(True)
        dlg.attributes("-topmost", True)
        rx = self._year_lbl.winfo_rootx()
        ry = self._year_lbl.winfo_rooty() + self._year_lbl.winfo_height()
        dlg.geometry(f"+{rx}+{ry}")
        tk.Label(dlg, text="年份：", font=("Segoe UI", 10)).pack(side="left")
        var = tk.StringVar(value=str(self.current.year))
        ent = tk.Entry(dlg, textvariable=var, width=6, font=("Segoe UI", 10))
        ent.pack(side="left")
        ent.focus()
        ent.select_range(0, "end")

        def commit():
            try:
                yr = int(var.get())
                if 1950 <= yr <= 2100:
                    self.current = self.current.replace(year=yr)
                    self._render_days()
            except ValueError:
                pass
            dlg.destroy()

        tk.Button(dlg, text="確定", font=("Segoe UI", 9), command=commit).pack(side="left", padx=4)
        tk.Button(dlg, text="取消", font=("Segoe UI", 9), command=dlg.destroy).pack(side="left")
        ent.bind("<Return>", lambda e: commit())
        ent.bind("<Escape>", lambda e: dlg.destroy())

    def _open_month_menu(self):
        """點月份 → 彈出 1-12 月快速選單"""
        mnu = tk.Toplevel(self.win)
        mnu.overrideredirect(True)
        mnu.attributes("-topmost", True)
        mx = self._month_lbl.winfo_rootx()
        my = self._month_lbl.winfo_rooty() + self._month_lbl.winfo_height()
        mnu.geometry(f"+{mx}+{my}")
        for m in range(1, 13):
            tk.Button(mnu, text=f"{m} 月", font=("Segoe UI", 10), width=5,
                      command=lambda month=m: self._apply_month_and_close(month, mnu)
                      ).pack(fill="x")

    def _apply_month_and_close(self, month: int, mnu: tk.Toplevel):
        self.current = self.current.replace(month=month)
        mnu.destroy()
        self._render_days()

    def _render_days(self):
        for w in self._day_frame.winfo_children():
            w.destroy()
        year, month = self.current.year, self.current.month
        self._year_lbl.config(text=f"{year} 年")
        self._month_lbl.config(text=f"{month} 月")
        first_wd = datetime(year, month, 1).weekday()
        days_in_month = (datetime(year, month + 1, 1) - datetime(year, month, 1)).days
        for _ in range(first_wd):
            ttk.Label(self._day_frame).grid(row=0, column=_, padx=1, pady=1)
        for d in range(1, days_in_month + 1):
            row = (first_wd + d - 1) // 7
            col = (first_wd + d - 1) % 7
            date_str = f"{year:04d}-{month:02d}-{d:02d}"
            btn = tk.Button(self._day_frame, text=str(d), width=4, height=1,
                           font=("Segoe UI", 9),
                           command=lambda ds=date_str: self._select(ds))
            btn.grid(row=row, column=col, padx=1, pady=1, sticky="nsew")
            wd = (first_wd + d - 1) % 7
            if wd == 5:
                btn.config(foreground="#0070c0", bg="#f0f4ff")
            elif wd == 6:
                btn.config(foreground="#c00000", bg="#fff0f0")
            else:
                btn.config(foreground="#222222", bg="#f5f5f5")
        for c in range(7):
            self._day_frame.columnconfigure(c, weight=1)

    def _select(self, date_str: str):
        self.result = date_str
        self.win.destroy()

    def _cancel(self):
        self.result = None
        self.win.destroy()

    def _on_close(self):
        self._cancel()

    @staticmethod
    def pick(parent, initial: str = "") -> Optional[str]:
        return _CalendarDialog(parent, initial).result
# ==========================================================
# GUI 主視窗
# ==========================================================

