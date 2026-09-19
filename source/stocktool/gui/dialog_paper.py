"""
stocktool.gui.dialog_paper - 投資組合編輯對話框
=============================================

【V1.2.0-paper-trading】

設計：
- 「建立」或「編輯」投資組合
- 完整買入/賣出參數設定
- 提供「📥 採用回測參數」一鍵帶入
- 提供「🔄 重設預設值」一鍵還原
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Callable

import pandas as pd

from .. import paper_trading as pt
from .. import paper_config


class PortfolioEditorDialog:
    """新增 / 編輯 投資組合對話框"""

    def __init__(self, parent, title: str = "新增組合", portfolio: Optional[pt.PaperPortfolio] = None,
                 cfg=None, app=None):
        self.parent = parent
        self.title = title
        self.portfolio = portfolio
        self.cfg = cfg
        self.app = app
        self.result: Optional[pt.PaperPortfolio] = None

        self.win = tk.Toplevel(parent)
        self.win.title(title)
        self.win.geometry("540x720")
        self.win.transient(parent)
        self.win.grab_set()

        # 變數
        self.name_var = tk.StringVar()
        self.excel_var = tk.StringVar()
        self.strategy_var = tk.StringVar(value="manual")
        self.initial_cash_var = tk.StringVar(value="1000000")
        self.max_holdings_var = tk.StringVar(value="10")

        # 買入
        self.buy_score_var = tk.StringVar(value="70.0")
        self.buy_rev_var = tk.StringVar(value="0.0")
        self.buy_eps_var = tk.StringVar(value="0.0")
        self.buy_pe_var = tk.StringVar(value="50.0")
        self.buy_yield_var = tk.StringVar(value="0.0")

        # 賣出
        self.sell_stop_var = tk.StringVar(value="8.0")
        self.sell_tp_var = tk.StringVar(value="20.0")
        self.sell_hold_var = tk.StringVar(value="30")
        self.ai_threshold_var = tk.StringVar(value="70.0")

        self._build()

        # 若是編輯模式、預先填入
        if self.portfolio is not None:
            self._load_from_portfolio(self.portfolio)

    # ==========================================================
    # UI 建構
    # ==========================================================

    def _build(self):
        main = ttk.Frame(self.win, padding=10)
        main.pack(fill="both", expand=True)

        # === 基本設定 ===
        basic = ttk.LabelFrame(main, text="基本設定", padding=8)
        basic.pack(fill="x", pady=(0, 6))

        ttk.Label(basic, text="名稱：").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        ttk.Entry(basic, textvariable=self.name_var, width=30).grid(row=0, column=1, sticky="ew", padx=2, pady=2)

        ttk.Label(basic, text="Excel 股票池：").grid(row=1, column=0, sticky="w", padx=2, pady=2)
        excel_row = ttk.Frame(basic)
        excel_row.grid(row=1, column=1, sticky="ew", padx=2, pady=2)
        ttk.Entry(excel_row, textvariable=self.excel_var).pack(side="left", fill="x", expand=True)
        ttk.Button(excel_row, text="📂", width=3, command=self._on_browse).pack(side="left", padx=1)

        ttk.Label(basic, text="策略模式：").grid(row=2, column=0, sticky="w", padx=2, pady=2)
        strategy_combo = ttk.Combobox(
            basic, textvariable=self.strategy_var,
            values=["manual", "ai_meta"], state="readonly", width=27
        )
        strategy_combo.grid(row=2, column=1, sticky="ew", padx=2, pady=2)
        strategy_combo.bind("<<ComboboxSelected>>", lambda e: self._update_strategy_ui())

        ttk.Label(basic, text="AI 進場門檻：").grid(row=3, column=0, sticky="w", padx=2, pady=2)
        self.ai_entry = ttk.Entry(basic, textvariable=self.ai_threshold_var, width=30)
        self.ai_entry.grid(row=3, column=1, sticky="ew", padx=2, pady=2)

        basic.columnconfigure(1, weight=1)

        # === 資金設定 ===
        cap = ttk.LabelFrame(main, text="資金 / 持倉", padding=8)
        cap.pack(fill="x", pady=(0, 6))

        ttk.Label(cap, text="總資金 (TWD)：").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        ttk.Entry(cap, textvariable=self.initial_cash_var, width=18).grid(row=0, column=1, sticky="ew", padx=2, pady=2)

        ttk.Label(cap, text="同時持倉上限：").grid(row=1, column=0, sticky="w", padx=2, pady=2)
        ttk.Entry(cap, textvariable=self.max_holdings_var, width=18).grid(row=1, column=1, sticky="ew", padx=2, pady=2)

        cap.columnconfigure(1, weight=1)

        # === 買入條件 ===
        buy = ttk.LabelFrame(main, text="買入條件", padding=8)
        buy.pack(fill="x", pady=(0, 6))

        self._labeled_entry(buy, "訊號分數門檻 (0~100)：", self.buy_score_var, 0,
                            help_text="訊號分數 >= 此值才進場")
        self._labeled_entry(buy, "最小營收 YoY (%)：", self.buy_rev_var, 1)
        self._labeled_entry(buy, "最小 EPS YoY (%)：", self.buy_eps_var, 2)
        self._labeled_entry(buy, "最大 PE (倍)：", self.buy_pe_var, 3)
        self._labeled_entry(buy, "最小殖利率 (%)：", self.buy_yield_var, 4)

        buy.columnconfigure(1, weight=1)

        # === 賣出條件 ===
        sell = ttk.LabelFrame(main, text="賣出條件", padding=8)
        sell.pack(fill="x", pady=(0, 6))

        self._labeled_entry(sell, "停損 (% 虧損)：", self.sell_stop_var, 0,
                            help_text="虧損達此 % 自動停損賣出")
        self._labeled_entry(sell, "停利 (% 獲利)：", self.sell_tp_var, 1,
                            help_text="獲利達此 % 自動停利賣出")
        self._labeled_entry(sell, "最大持有天數：", self.sell_hold_var, 2,
                            help_text="持有天數達此值且訊號轉弱就換股")

        sell.columnconfigure(1, weight=1)

        # === 快捷按鈕 ===
        quick = ttk.Frame(main)
        quick.pack(fill="x", pady=(0, 6))
        ttk.Button(quick, text="📥 採用回測參數", command=self._apply_backtest_params).pack(side="left", padx=2)
        ttk.Button(quick, text="🔄 重設預設值", command=self._reset_defaults).pack(side="left", padx=2)

        # === 底部按鈕 ===
        bottom = ttk.Frame(main)
        bottom.pack(fill="x", pady=(8, 0))
        ttk.Button(bottom, text="取消", command=self._on_cancel).pack(side="right", padx=2)
        ttk.Button(bottom, text="💾 儲存", command=self._on_save).pack(side="right", padx=2)

        self._update_strategy_ui()

    def _labeled_entry(self, parent, label, var, row, help_text=None):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=2, pady=2)
        ttk.Entry(parent, textvariable=var, width=18).grid(row=row, column=1, sticky="ew", padx=2, pady=2)

    # ==========================================================
    # 動作
    # ==========================================================

    def _on_browse(self):
        path = filedialog.askopenfilename(
            title="選擇選股 Excel",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            parent=self.win,
        )
        if path:
            self.excel_var.set(path)

    def _update_strategy_ui(self):
        if self.strategy_var.get() == "ai_meta":
            self.ai_entry.state(["!disabled"])
        else:
            self.ai_entry.state(["disabled"])

    def _load_from_portfolio(self, p: pt.PaperPortfolio):
        self.name_var.set(p.name)
        self.excel_var.set(p.excel_file or "")
        self.strategy_var.set(p.strategy_mode)
        self.initial_cash_var.set(str(p.initial_cash))
        self.max_holdings_var.set(str(p.max_holdings))
        self.buy_score_var.set(str(p.buy_score_threshold))
        self.buy_rev_var.set(str(p.buy_min_rev_yoy))
        self.buy_eps_var.set(str(p.buy_min_eps_yoy))
        self.buy_pe_var.set(str(p.buy_max_pe))
        self.buy_yield_var.set(str(p.buy_min_yield))
        self.sell_stop_var.set(str(p.sell_stop_loss_pct))
        self.sell_tp_var.set(str(p.sell_take_profit_pct))
        self.sell_hold_var.set(str(p.sell_max_hold_days))
        self.ai_threshold_var.set(str(p.ai_threshold))

    def _apply_backtest_params(self):
        if self.cfg is None:
            messagebox.showwarning("提醒", "沒有回測參數可用（cfg 未傳入）", parent=self.win)
            return
        try:
            mapping = paper_config.BacktestParamsMapping(cfg=self.cfg)
            tpl = mapping.to_paper_portfolio()
            self.initial_cash_var.set(str(tpl.initial_cash))
            self.max_holdings_var.set(str(tpl.max_holdings))
            self.buy_rev_var.set(str(tpl.buy_min_rev_yoy))
            self.buy_eps_var.set(str(tpl.buy_min_eps_yoy))
            self.buy_pe_var.set(str(tpl.buy_max_pe))
            self.sell_stop_var.set(f"{tpl.sell_stop_loss_pct:.2f}")
            self.sell_tp_var.set(f"{tpl.sell_take_profit_pct:.2f}")
            self.sell_hold_var.set(str(tpl.sell_max_hold_days))
            messagebox.showinfo("已套用", "回測參數已帶入表單（請按「💾 儲存」確認）", parent=self.win)
        except Exception as e:
            messagebox.showerror("錯誤", f"套用失敗：{e}", parent=self.win)

    def _reset_defaults(self):
        self.initial_cash_var.set("1000000")
        self.max_holdings_var.set("10")
        self.buy_score_var.set("70.0")
        self.buy_rev_var.set("0.0")
        self.buy_eps_var.set("0.0")
        self.buy_pe_var.set("50.0")
        self.buy_yield_var.set("0.0")
        self.sell_stop_var.set("8.0")
        self.sell_tp_var.set("20.0")
        self.sell_hold_var.set("30")
        self.ai_threshold_var.set("70.0")
        self.strategy_var.set("manual")
        self._update_strategy_ui()

    def _on_save(self):
        try:
            name = self.name_var.get().strip()
            if not name:
                messagebox.showwarning("提醒", "請輸入組合名稱", parent=self.win)
                return
            initial_cash = float(self.initial_cash_var.get())
            max_holdings = int(self.max_holdings_var.get())

            excel_path = self.excel_var.get().strip()
            stock_pool: list = []
            if excel_path:
                if not os.path.exists(excel_path):
                    messagebox.showerror("錯誤", f"Excel 不存在：\n{excel_path}", parent=self.win)
                    return
                from ..paper_excel import parse_excel_to_stock_pool
                stock_pool, warns = parse_excel_to_stock_pool(excel_path)
                if not stock_pool:
                    if not messagebox.askyesno("確認", "Excel 沒有解析到任何股票，仍要繼續嗎？", parent=self.win):
                        return

            strategy = self.strategy_var.get()
            p = pt.PaperPortfolio(
                id=self.portfolio.id if self.portfolio else None,
                name=name,
                excel_file=excel_path or None,
                stock_pool=stock_pool,
                initial_cash=initial_cash,
                max_holdings=max_holdings,
                buy_score_threshold=float(self.buy_score_var.get()),
                buy_min_rev_yoy=float(self.buy_rev_var.get()),
                buy_min_eps_yoy=float(self.buy_eps_var.get()),
                buy_max_pe=float(self.buy_pe_var.get()),
                buy_min_yield=float(self.buy_yield_var.get()),
                sell_stop_loss_pct=float(self.sell_stop_var.get()),
                sell_take_profit_pct=float(self.sell_tp_var.get()),
                sell_max_hold_days=int(self.sell_hold_var.get()),
                strategy_mode=strategy,
                ai_threshold=float(self.ai_threshold_var.get()),
            )
            self.result = p
            self.win.destroy()
        except ValueError as e:
            messagebox.showerror("格式錯誤", f"請檢查數字欄位：{e}", parent=self.win)

    def _on_cancel(self):
        self.result = None
        self.win.destroy()

    def show(self) -> Optional[pt.PaperPortfolio]:
        """Modal 顯示、回傳 PaperPortfolio 或 None"""
        self.win.wait_window()
        return self.result


class RollbackDaysDialog:
    """回推 N 日 / 指定日期對話框"""

    def __init__(self, parent, portfolio_name: str, simulated_dates: list[str]):
        self.parent = parent
        self.portfolio_name = portfolio_name
        self.dates = simulated_dates  # 由小到大排列
        self.result: Optional[Tuple[Optional[str], int]] = None  # (target_date, days)

        self.win = tk.Toplevel(parent)
        self.win.title(f"⏪ 回推交易日 — {portfolio_name}")
        self.win.geometry("450x330")
        self.win.transient(parent)
        self.win.grab_set()

        self._build()

    def _build(self):
        pad = 10
        frame = ttk.Frame(self.win, padding=pad)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text=f"組合：{self.portfolio_name}", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 4))

        info_text = f"目前已模擬：{len(self.dates)} 個交易日 ({self.dates[0]} ~ {self.dates[-1]})"
        ttk.Label(frame, text=info_text, foreground="gray").pack(anchor="w", pady=(0, 10))

        # 選項框架
        opt_frame = ttk.LabelFrame(frame, text="設定回退目標", padding=10)
        opt_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(opt_frame, text="回推至日期：").grid(row=0, column=0, sticky="w", pady=6)

        # 產生選單項目 (倒序排列，預設回退 1 日)
        self.options = []
        for i in range(1, len(self.dates)):
            target = self.dates[-(i + 1)]
            self.options.append((f"{target}（回推 {i} 日）", target, i))
        self.options.append(("重設為初始狀態（回推全部）", None, len(self.dates)))

        combo_labels = [opt[0] for opt in self.options]
        self.combo_var = tk.StringVar(value=combo_labels[0])
        self.combo = ttk.Combobox(opt_frame, textvariable=self.combo_var, values=combo_labels, state="readonly", width=28)
        self.combo.grid(row=0, column=1, sticky="ew", pady=6, padx=4)
        self.combo.bind("<<ComboboxSelected>>", self._on_combo_change)

        ttk.Label(opt_frame, text="或回推天數：").grid(row=1, column=0, sticky="w", pady=6)
        self.days_var = tk.IntVar(value=1)
        self.spin_days = ttk.Spinbox(opt_frame, from_=1, to=len(self.dates), textvariable=self.days_var, width=8, command=self._on_days_change)
        self.spin_days.grid(row=1, column=1, sticky="w", pady=6, padx=4)
        self.spin_days.bind("<KeyRelease>", lambda e: self._on_days_change())

        opt_frame.columnconfigure(1, weight=1)

        # 警告說明
        warn_lbl = ttk.Label(
            frame,
            text="⚠️ 注意：回推後，目標日期之後的交易紀錄與快照\n將會永久清除，並將持倉與現金還原至該日狀態。",
            foreground="#b22222", font=("Segoe UI", 9)
        )
        warn_lbl.pack(fill="x", pady=(0, 12))

        # 按鈕列
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", side="bottom")
        ttk.Button(btn_frame, text="❌ 取消", command=self.win.destroy).pack(side="right", padx=4)
        ttk.Button(btn_frame, text="✅ 確定回推", command=self._on_confirm).pack(side="right", padx=4)

    def _on_combo_change(self, event=None):
        idx = self.combo.current()
        if 0 <= idx < len(self.options):
            days = self.options[idx][2]
            self.days_var.set(days)

    def _on_days_change(self):
        try:
            d = self.days_var.get()
            d = max(1, min(len(self.dates), d))
            for opt in self.options:
                if opt[2] == d:
                    self.combo_var.set(opt[0])
                    break
        except Exception:
            pass

    def _on_confirm(self):
        try:
            d = self.days_var.get()
            d = max(1, min(len(self.dates), d))
        except Exception:
            d = 1

        target_date = None
        for opt in self.options:
            if opt[2] == d:
                target_date = opt[1]
                break

        self.result = (target_date, d)
        self.win.destroy()

    def show(self) -> Optional[Tuple[Optional[str], int]]:
        self.win.wait_window()
        return self.result