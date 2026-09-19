"""
stocktool.gui.tab_paper - 模擬買賣 Tab 的 UI 建構
================================================

【V1.2.0-paper-trading】

設計：
- 左欄：組合管理 + 全域參數
- 右側：選中組合的詳情（持倉、買賣紀錄、權益曲線）
- 底部：執行控制（▶ 推進一天、⏩ 補跑到今天、AI 模式開關）
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import pandas as pd

from .. import paper_trading as pt
from .. import paper_excel
from .. import paper_engine as pe
from .dialog_paper import PortfolioEditorDialog, RollbackDaysDialog


class PaperTradingTab:
    """模擬買賣 Tab - 由 StockTool.py 持有"""

    def __init__(self, parent_app, parent_frame):
        self.app = parent_app
        self.frame = parent_frame
        from stocktool.config import get_data_path
        self.db_path = get_data_path("portfolio.db")
        self.selected_portfolio_id: Optional[int] = None

        # UI 元件參考
        self.portfolio_listbox: Optional[tk.Listbox] = None
        self.status_label: Optional[ttk.Label] = None
        self.detail_notebook: Optional[ttk.Notebook] = None
        # 子分頁
        self.holdings_tree: Optional[ttk.Treeview] = None
        self.trades_tree: Optional[ttk.Treeview] = None
        self.summary_labels: Dict[str, ttk.Label] = {}

        self._build()

    # ==========================================================
    # UI 建構
    # ==========================================================

    def _build(self):
        # 主容器：左 (管理) + 右 (詳情)
        main = ttk.Frame(self.frame)
        main.pack(fill="both", expand=True, padx=8, pady=8)

        # 左欄
        left = ttk.Frame(main, width=320)
        left.pack(side="left", fill="y", padx=(0, 6))
        left.pack_propagate(False)
        self._build_left(left)

        # 右欄
        right = ttk.Frame(main)
        right.pack(side="left", fill="both", expand=True)
        self._build_right(right)

        # 初始化 DB
        pt.init_paper_trading_db(self.db_path)

        # 載入現有組合
        self._refresh_portfolio_list()

    def _build_left(self, parent):
        """左欄：組合管理 + 全域控制"""
        # === 標題 ===
        ttk.Label(parent, text="📈 模擬買賣組合管理",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 6))

        # === 新增組合 ===
        new_frame = ttk.LabelFrame(parent, text="➕ 新增組合", padding=6)
        new_frame.pack(fill="x", pady=(0, 6))

        ttk.Label(new_frame, text="名稱：").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        self.new_name_var = tk.StringVar()
        ttk.Entry(new_frame, textvariable=self.new_name_var, width=18).grid(row=0, column=1, sticky="ew", padx=2, pady=2)

        ttk.Label(new_frame, text="Excel：").grid(row=1, column=0, sticky="w", padx=2, pady=2)
        self.new_excel_var = tk.StringVar()
        excel_row = ttk.Frame(new_frame)
        excel_row.grid(row=1, column=1, sticky="ew", padx=2, pady=2)
        ttk.Entry(excel_row, textvariable=self.new_excel_var, width=12).pack(side="left", fill="x", expand=True)
        ttk.Button(excel_row, text="📂", width=3,
                   command=self._on_browse_excel).pack(side="left", padx=1)

        ttk.Label(new_frame, text="策略：").grid(row=2, column=0, sticky="w", padx=2, pady=2)
        self.new_strategy_var = tk.StringVar(value="manual")
        strategy_combo = ttk.Combobox(new_frame, textvariable=self.new_strategy_var,
                                       values=["manual", "ai_meta"], state="readonly", width=15)
        strategy_combo.grid(row=2, column=1, sticky="ew", padx=2, pady=2)

        ttk.Label(new_frame, text="總資金：").grid(row=3, column=0, sticky="w", padx=2, pady=2)
        self.new_cash_var = tk.StringVar(value="1000000")
        ttk.Entry(new_frame, textvariable=self.new_cash_var, width=18).grid(row=3, column=1, sticky="ew", padx=2, pady=2)

        ttk.Label(new_frame, text="持倉上限：").grid(row=4, column=0, sticky="w", padx=2, pady=2)
        self.new_max_var = tk.StringVar(value="10")
        ttk.Entry(new_frame, textvariable=self.new_max_var, width=18).grid(row=4, column=1, sticky="ew", padx=2, pady=2)

        new_frame.columnconfigure(1, weight=1)

        ttk.Button(new_frame, text="✅ 建立組合", command=self._on_create_portfolio).grid(
            row=5, column=0, columnspan=2, sticky="ew", pady=(6, 0)
        )

        # === 組合清單 ===
        list_frame = ttk.LabelFrame(parent, text="📋 我的組合", padding=4)
        list_frame.pack(fill="both", expand=True, pady=(0, 6))

        self.portfolio_listbox = tk.Listbox(list_frame, height=8, font=("Consolas", 9))
        self.portfolio_listbox.pack(side="left", fill="both", expand=True)
        self.portfolio_listbox.bind("<<ListboxSelect>>", self._on_select_portfolio)

        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self.portfolio_listbox.yview)
        sb.pack(side="right", fill="y")
        self.portfolio_listbox.config(yscrollcommand=sb.set)

        # 組合操作按鈕
        op_frame = ttk.Frame(parent)
        op_frame.pack(fill="x", pady=(0, 6))
        ttk.Button(op_frame, text="✎ 編輯", width=7, command=self._on_edit).pack(side="left", padx=1)
        ttk.Button(op_frame, text="⏸ 暫停", width=7, command=self._on_pause).pack(side="left", padx=1)
        ttk.Button(op_frame, text="▶ 繼續", width=7, command=self._on_resume).pack(side="left", padx=1)
        ttk.Button(op_frame, text="🗑 刪除", width=7, command=self._on_delete).pack(side="left", padx=1)
        ttk.Button(op_frame, text="🔄 重新整理", width=9, command=self._refresh_portfolio_list).pack(side="left", padx=1)

        # 2026-08-20: 執行控制按鈕已搬到右邊 trades tab btn_frame
        # (左邊 session area 太窄、按鈕顯示不出來)

        # 狀態列
        self.status_label = ttk.Label(parent, text="就緒", foreground="gray",
                                       font=("Segoe UI", 9))
        self.status_label.pack(anchor="w", pady=(6, 0))

    def _build_right(self, parent):
        """右欄：組合詳情"""
        # === 頂部資訊列 ===
        info_frame = ttk.Frame(parent)
        info_frame.pack(fill="x", pady=(0, 6))

        self.info_name_var = tk.StringVar(value="（未選擇組合）")
        ttk.Label(info_frame, textvariable=self.info_name_var,
                  font=("Segoe UI", 11, "bold")).pack(side="left")

        self.info_status_var = tk.StringVar(value="")
        ttk.Label(info_frame, textvariable=self.info_status_var,
                  font=("Segoe UI", 10), foreground="blue").pack(side="left", padx=10)

        # === 摘要資訊（總資產、累積報酬、勝率） ===
        summary_frame = ttk.LabelFrame(parent, text="📊 摘要", padding=6)
        summary_frame.pack(fill="x", pady=(0, 6))

        fields = [
            ("初始資金", "initial"),
            ("目前總資產", "total"),
            ("累積報酬", "cum_return"),
            ("持倉數", "holdings_count"),
            ("交易次數", "trade_count"),
            ("勝率", "win_rate"),
        ]
        for i, (label, key) in enumerate(fields):
            row, col = i // 3, (i % 3) * 2
            ttk.Label(summary_frame, text=f"{label}：").grid(row=row, column=col, sticky="e", padx=2, pady=2)
            lbl = ttk.Label(summary_frame, text="-", font=("Segoe UI", 10, "bold"))
            lbl.grid(row=row, column=col + 1, sticky="w", padx=2, pady=2)
            self.summary_labels[key] = lbl

        # === Notebook：持倉 / 買賣紀錄 / 權益曲線 ===
        self.detail_notebook = ttk.Notebook(parent)
        self.detail_notebook.pack(fill="both", expand=True)

        # Tab 1: 持倉
        holdings_tab = ttk.Frame(self.detail_notebook)
        self.detail_notebook.add(holdings_tab, text="💼 持倉")
        self._build_holdings_tab(holdings_tab)

        # Tab 2: 買賣紀錄
        trades_tab = ttk.Frame(self.detail_notebook)
        self.detail_notebook.add(trades_tab, text="📋 買賣紀錄")
        self._build_trades_tab(trades_tab)

        # Tab 3: 權益曲線
        chart_tab = ttk.Frame(self.detail_notebook)
        self.detail_notebook.add(chart_tab, text="📈 權益曲線")
        self._build_chart_tab(chart_tab)
        # 切到權益曲線 tab 時重繪
        self.detail_notebook.bind("<<NotebookTabChanged>>", self._on_detail_tab_changed)

    def _build_holdings_tab(self, parent):
        cols = ("代號", "名稱", "股數", "均成本", "現價", "市值", "報酬率", "持有天", "進場理由")
        self.holdings_tree = ttk.Treeview(parent, columns=cols, show="headings", height=12)
        for c in cols:
            self.holdings_tree.heading(c, text=c)
        self.holdings_tree.column("代號", width=70)
        self.holdings_tree.column("名稱", width=80)
        self.holdings_tree.column("股數", width=80)
        self.holdings_tree.column("均成本", width=80)
        self.holdings_tree.column("現價", width=80)
        self.holdings_tree.column("市值", width=90)
        self.holdings_tree.column("報酬率", width=70)
        self.holdings_tree.column("持有天", width=60)
        self.holdings_tree.column("進場理由", width=300)

        sb = ttk.Scrollbar(parent, orient="vertical", command=self.holdings_tree.yview)
        self.holdings_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.holdings_tree.config(yscrollcommand=sb.set)

        ttk.Button(parent, text="🔄 重新整理", command=self._refresh_holdings).pack(pady=4)

    def _build_trades_tab(self, parent):
        cols = ("日期", "動作", "代號", "名稱", "股數", "價格", "金額", "手續費", "稅", "分數", "依據")
        self.trades_tree = ttk.Treeview(parent, columns=cols, show="headings", height=15)
        for c in cols:
            self.trades_tree.heading(c, text=c)
        widths = {"日期": 90, "動作": 50, "代號": 60, "名稱": 70,
                  "股數": 70, "價格": 70, "金額": 90, "手續費": 60,
                  "稅": 50, "分數": 50, "依據": 350}
        for c in cols:
            self.trades_tree.column(c, width=widths.get(c, 80), anchor="w")

        sb = ttk.Scrollbar(parent, orient="vertical", command=self.trades_tree.yview)
        self.trades_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.trades_tree.config(yscrollcommand=sb.set)

        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill="x", pady=4)
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        # Row 0: 資料相關 (refresh + export)
        ttk.Button(btn_frame, text="🔄 重新整理", command=self._refresh_trades).grid(row=0, column=0, padx=4, pady=2, sticky="ew")
        ttk.Button(btn_frame, text="💾 匯出 Excel", command=self._export_trades_excel).grid(row=0, column=1, padx=4, pady=2, sticky="ew")
        # Row 1: 執行控制 (推進 / 補跑)
        ttk.Button(btn_frame, text="▶ 推進一天", command=self._on_advance_one_day).grid(row=1, column=0, padx=4, pady=2, sticky="ew")
        ttk.Button(btn_frame, text="⏩ 補跑到今天", command=self._on_catch_up_to_today).grid(row=1, column=1, padx=4, pady=2, sticky="ew")
        # Row 2: 時間回推 (回推一日 / 回推多日)
        ttk.Button(btn_frame, text="◀ 回推一日", command=self._on_rollback_one_day).grid(row=2, column=0, padx=4, pady=2, sticky="ew")
        ttk.Button(btn_frame, text="⏪ 回推 N 日...", command=self._on_rollback_n_days).grid(row=2, column=1, padx=4, pady=2, sticky="ew")

        # 右鍵選單：回推至指定交易日
        self._build_trades_context_menu()

    def _build_chart_tab(self, parent):
        """權益曲線（matplotlib）"""
        try:
            import matplotlib
            matplotlib.use("TkAgg")
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

            self._matplotlib_available = True
            self.fig = Figure(figsize=(10, 6), dpi=100)
            self.ax = self.fig.add_subplot(111)
            self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
            self.canvas.get_tk_widget().pack(fill="both", expand=True)

            btn_frame = ttk.Frame(parent)
            btn_frame.pack(fill="x")
            ttk.Button(btn_frame, text="🔄 重繪", command=self._draw_equity_curve).pack(side="left", padx=4)
            ttk.Button(btn_frame, text="💾 存為 PNG", command=self._save_chart_png).pack(side="left", padx=4)
        except ImportError:
            self._matplotlib_available = False
            self.chart_text = tk.Text(parent, wrap="word", font=("Consolas", 9))
            self.chart_text.pack(fill="both", expand=True)
            self.chart_text.insert("end", "（matplotlib 未裝、權益曲線無法顯示）\n")

    def _draw_equity_curve(self):
        if not getattr(self, "_matplotlib_available", False):
            return
        if not self.selected_portfolio_id:
            return
        df = pt.list_snapshots(self.db_path, self.selected_portfolio_id)
        if df is None or df.empty:
            self.ax.clear()
            self.ax.text(0.5, 0.5, "（無快照資料、請先跑一次模擬）",
                         ha="center", va="center", transform=self.ax.transAxes)
            self.canvas.draw()
            return

        self.ax.clear()
        # 主軸：總資產
        dates = pd.to_datetime(df["trade_date"])
        self.ax.plot(dates, df["total_value"], "b-", label="總資產", linewidth=2)
        self.ax.plot(dates, df["cash"], "g--", label="現金", alpha=0.6)
        self.ax.set_xlabel("日期")
        self.ax.set_ylabel("總資產 (TWD)", color="b")
        self.ax.tick_params(axis="y", labelcolor="b")
        self.ax.grid(True, alpha=0.3)

        # 副軸：累積報酬率
        ax2 = self.ax.twinx()
        cum = df["cumulative_return_pct"].fillna(0)
        ax2.plot(dates, cum, "r-", label="累積報酬率 (%)", alpha=0.6)
        ax2.set_ylabel("累積報酬率 (%)", color="r")
        ax2.tick_params(axis="y", labelcolor="r")

        # 大盤對比（如果有）
        if "benchmark_return_pct" in df.columns and df["benchmark_return_pct"].notna().any():
            bench = df["benchmark_return_pct"].fillna(0)
            ax2.plot(dates, bench, "gray", linestyle="--", label="加權指數 (%)", alpha=0.5)

        self.ax.set_title(f"📈 權益曲線 - {self._portfolios_cache.get(self.selected_portfolio_id, None) and self._portfolios_cache[self.selected_portfolio_id].name or ''}")
        self.fig.autofmt_xdate()
        self.fig.tight_layout()
        self.canvas.draw()

    def _save_chart_png(self):
        if not getattr(self, "_matplotlib_available", False):
            return
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            title="存權益曲線",
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("All", "*.*")],
        )
        if path:
            try:
                self.fig.savefig(path, dpi=150, bbox_inches="tight")
                self._log(f"💾 已存：{path}")
            except Exception as e:
                self._log(f"❌ 存檔失敗: {e}")

    def _export_trades_excel(self):
        if not self.selected_portfolio_id:
            messagebox.showinfo("提醒", "請先選一個組合")
            return
        try:
            trades = pt.list_trades(self.db_path, self.selected_portfolio_id, limit=99999)
            snapshots = pt.list_snapshots(self.db_path, self.selected_portfolio_id)
            holdings = pt.list_holdings(self.db_path, self.selected_portfolio_id)
            p = pt.get_portfolio(self.db_path, self.selected_portfolio_id)
            if not p:
                return

            # 轉成 DataFrame
            import pandas as pd
            trades_df = pd.DataFrame([t.to_dict() for t in trades]) if trades else pd.DataFrame()
            snap_df = snapshots if not snapshots.empty else pd.DataFrame()
            holdings_df = pd.DataFrame([h.to_dict() for h in holdings]) if holdings else pd.DataFrame()

            from tkinter import filedialog
            from datetime import datetime
            default_name = f"模擬買賣_{p.name}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            path = filedialog.asksaveasfilename(
                title="匯出模擬買賣記錄",
                initialfile=default_name,
                defaultextension=".xlsx",
                filetypes=[("Excel", "*.xlsx")],
            )
            if not path:
                return

            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                # 組合設定
                info_df = pd.DataFrame([{
                    "組合名稱": p.name,
                    "策略模式": p.strategy_mode,
                    "總資金": p.initial_cash,
                    "持倉上限": p.max_holdings,
                    "買入門檻": p.buy_score_threshold,
                    "停損%": p.sell_stop_loss_pct,
                    "停利%": p.sell_take_profit_pct,
                    "最大持有天": p.sell_max_hold_days,
                    "狀態": p.status,
                    "啟動時間": p.started_at,
                    "最後執行": p.last_run_date,
                }])
                info_df.to_excel(writer, sheet_name="組合設定", index=False)

                if not holdings_df.empty:
                    holdings_df.to_excel(writer, sheet_name="持倉現況", index=False)
                if not trades_df.empty:
                    trades_df.to_excel(writer, sheet_name="買賣紀錄", index=False)
                if not snap_df.empty:
                    snap_df.to_excel(writer, sheet_name="每日快照", index=False)

            self._log(f"💾 已匯出：{path}")
            messagebox.showinfo("匯出成功", f"已存：\n{path}")
        except Exception as e:
            self._log(f"❌ 匯出失敗: {e}")
            messagebox.showerror("匯出失敗", str(e))

    # ==========================================================
    # 事件處理
    # ==========================================================

    def _on_detail_tab_changed(self, event=None):
        # 切到權益曲線 tab 時重繪
        try:
            current = self.detail_notebook.index(self.detail_notebook.select())
            if current == 2:  # 權益曲線 tab
                if getattr(self, "_matplotlib_available", False):
                    self._draw_equity_curve()
        except Exception:
            pass

    def _on_browse_excel(self):
        path = filedialog.askopenfilename(
            title="選擇選股 Excel",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        if path:
            self.new_excel_var.set(path)

    def _on_create_portfolio(self):
        """【V1.2.0 修正】改用對話框取代內嵌欄位、可設定完整買入賣出參數"""
        cfg = getattr(self.app, "cfg", None)
        dlg = PortfolioEditorDialog(
            self.frame, title="新增組合",
            portfolio=None, cfg=cfg, app=self.app,
        )
        result = dlg.show()
        if result is None:
            return
        try:
            if result.id is None:
                pid = pt.create_portfolio(self.db_path, result)
            else:
                pt.update_portfolio(self.db_path, result)
                pid = result.id
        except Exception as e:
            messagebox.showerror("錯誤", f"儲存失敗: {e}")
            return

        self._log(f"✅ 已建立組合「{result.name}」(id={pid})、股票池 {len(result.stock_pool)} 檔")
        self._refresh_portfolio_list()

    def _refresh_portfolio_list(self):
        if self.portfolio_listbox is None:
            return
        self.portfolio_listbox.delete(0, "end")
        portfolios = pt.list_portfolios(self.db_path)
        self._portfolios_cache = {p.id: p for p in portfolios}
        for p in portfolios:
            status_icon = {"active": "🟢", "paused": "🟡", "finished": "⚫"}.get(p.status, "❓")
            label = f"{status_icon} [{p.id}] {p.name}  ({p.strategy_mode})"
            self.portfolio_listbox.insert("end", label)

    def _on_select_portfolio(self, event=None):
        sel = self.portfolio_listbox.curselection()
        if not sel:
            return
        label = self.portfolio_listbox.get(sel[0])
        # 從 label parse id
        try:
            pid = int(label.split("]")[0].split("[")[-1])
        except Exception:
            return
        self.selected_portfolio_id = pid
        self._refresh_detail()

    def _refresh_detail(self):
        if not self.selected_portfolio_id:
            return
        p = pt.get_portfolio(self.db_path, self.selected_portfolio_id)
        if not p:
            return

        self.info_name_var.set(f"📈 {p.name}")
        self.info_status_var.set(f"狀態: {p.status} | 策略: {p.strategy_mode} | 啟動: {p.started_at or '-'}")

        # 摘要
        try:
            initial_cash = p.initial_cash
            cash = pt.get_current_cash(self.db_path, p.id, initial_cash)
            holdings = pt.list_holdings(self.db_path, p.id)
            trades = pt.list_trades(self.db_path, p.id, limit=99999)
            snaps = pt.list_snapshots(self.db_path, p.id)

            total_holdings_value = 0.0
            for h in holdings:
                # 用 trade 表的最後一筆價格當現價
                latest_price = h.avg_cost
                for t in trades:
                    if t.stock_code == h.stock_code:
                        latest_price = t.price
                        break
                total_holdings_value += h.shares * latest_price

            total_value = cash + total_holdings_value
            cum_return = (total_value - initial_cash) / initial_cash * 100 if initial_cash else 0

            # 勝率
            sell_trades = [t for t in trades if t.action == "SELL"]
            wins = 0
            for t in sell_trades:
                # 找對應的 BUY 均成本
                buys = [b for b in trades if b.action == "BUY" and b.stock_code == t.stock_code and b.trade_date <= t.trade_date]
                if buys:
                    avg_cost = sum(b.price for b in buys) / len(buys)
                    if t.price > avg_cost:
                        wins += 1
            win_rate = (wins / len(sell_trades) * 100) if sell_trades else 0

            self.summary_labels["initial"].config(text=f"{initial_cash:,.0f}")
            self.summary_labels["total"].config(text=f"{total_value:,.0f}")
            cum_label = self.summary_labels["cum_return"]
            cum_label.config(text=f"{cum_return:+.2f}%",
                             foreground="green" if cum_return >= 0 else "red")
            self.summary_labels["holdings_count"].config(text=f"{len(holdings)} / {p.max_holdings}")
            self.summary_labels["trade_count"].config(text=f"{len(trades)}")
            self.summary_labels["win_rate"].config(text=f"{win_rate:.1f}% ({wins}/{len(sell_trades)})")
        except Exception as e:
            self._log(f"⚠️ 摘要計算失敗: {e}")

        self._refresh_holdings()
        self._refresh_trades()
        if getattr(self, "_matplotlib_available", False):
            try:
                self._draw_equity_curve()
            except Exception:
                pass

    def _refresh_holdings(self):
        if not self.holdings_tree or not self.selected_portfolio_id:
            return
        for item in self.holdings_tree.get_children():
            self.holdings_tree.delete(item)
        holdings = pt.list_holdings(self.db_path, self.selected_portfolio_id)
        trades = pt.list_trades(self.db_path, self.selected_portfolio_id, limit=99999)
        for h in holdings:
            # 現價 = 最後一次該股的 trade 價格
            latest_price = h.avg_cost
            for t in trades:
                if t.stock_code == h.stock_code:
                    latest_price = t.price
                    break
            value = h.shares * latest_price
            profit_pct = (latest_price - h.avg_cost) / h.avg_cost * 100 if h.avg_cost else 0
            days = (datetime.now() - datetime.strptime(h.entry_date, "%Y-%m-%d")).days
            stock_name = h.stock_name
            if not stock_name or stock_name == h.stock_code:
                stock_name = pt.get_stock_name(h.stock_code) or stock_name or "-"
            self.holdings_tree.insert("", "end", values=(
                h.stock_code, stock_name,
                f"{h.shares:,.0f}", f"{h.avg_cost:.2f}", f"{latest_price:.2f}",
                f"{value:,.0f}", f"{profit_pct:+.1f}%",
                days, h.entry_reason or "-"
            ))

    def _refresh_trades(self):
        if not self.trades_tree or not self.selected_portfolio_id:
            return
        for item in self.trades_tree.get_children():
            self.trades_tree.delete(item)
        trades = pt.list_trades(self.db_path, self.selected_portfolio_id, limit=500)
        for t in trades:
            action_icon = "🟢 買" if t.action == "BUY" else "🔴 賣"
            score = f"{t.signal_score:.0f}" if t.signal_score is not None else "-"
            stock_name = t.stock_name
            if not stock_name or stock_name == t.stock_code:
                stock_name = pt.get_stock_name(t.stock_code) or stock_name or "-"
            self.trades_tree.insert("", "end", values=(
                t.trade_date, action_icon, t.stock_code, stock_name,
                f"{t.shares:,.0f}", f"{t.price:.2f}", f"{t.amount:,.0f}",
                f"{t.fee:.0f}", f"{t.tax:.0f}", score,
                (t.reasoning or "-")[:80]
            ))

    def _on_pause(self):
        if not self.selected_portfolio_id:
            return
        pt.update_portfolio_status(self.db_path, self.selected_portfolio_id, "paused")
        self._log(f"⏸ 組合 {self.selected_portfolio_id} 已暫停")
        self._refresh_portfolio_list()
        self._refresh_detail()

    def _on_resume(self):
        if not self.selected_portfolio_id:
            return
        pt.update_portfolio_status(self.db_path, self.selected_portfolio_id, "active")
        self._log(f"▶ 組合 {self.selected_portfolio_id} 已繼續")
        self._refresh_portfolio_list()
        self._refresh_detail()

    def _on_edit(self):
        """【V1.2.0】編輯組合參數"""
        if not self.selected_portfolio_id:
            messagebox.showinfo("提醒", "請先選一個組合")
            return
        p = pt.get_portfolio(self.db_path, self.selected_portfolio_id)
        if not p:
            return
        cfg = getattr(self.app, "cfg", None)
        dlg = PortfolioEditorDialog(
            self.frame, title=f"編輯組合 — {p.name}",
            portfolio=p, cfg=cfg, app=self.app,
        )
        result = dlg.show()
        if result is None:
            return
        try:
            pt.update_portfolio(self.db_path, result)
        except Exception as e:
            messagebox.showerror("錯誤", f"儲存失敗: {e}")
            return
        self._log(f"✎ 組合「{result.name}」已更新")
        self._refresh_portfolio_list()
        self._refresh_detail()

    def _on_delete(self):
        if not self.selected_portfolio_id:
            return
        if not messagebox.askyesno("確認刪除", f"真的要刪除組合 {self.selected_portfolio_id}？\n（會連同持倉與交易紀錄一起刪除）"):
            return
        pt.delete_portfolio(self.db_path, self.selected_portfolio_id)
        self.selected_portfolio_id = None
        self._refresh_portfolio_list()
        self._refresh_detail()
        self._log("🗑 已刪除組合")

    # ==========================================================
    # 執行（推進一天、補跑、回推）
    # ==========================================================

    def _build_trades_context_menu(self):
        self._trades_menu = tk.Menu(self.trades_tree, tearoff=0)
        self._trades_menu.add_command(label="⏪ 回推至此交易日", command=self._on_rollback_to_selected_trade)
        self.trades_tree.bind("<Button-3>", self._on_trades_right_click)
        self.trades_tree.bind("<Button-2>", self._on_trades_right_click)

    def _on_trades_right_click(self, event):
        item = self.trades_tree.identify_row(event.y)
        if item:
            self.trades_tree.selection_set(item)
            try:
                self._trades_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self._trades_menu.grab_release()

    def _on_rollback_to_selected_trade(self):
        if not self.selected_portfolio_id:
            return
        sel = self.trades_tree.selection()
        if not sel:
            return
        vals = self.trades_tree.item(sel[0], "values")
        if not vals:
            return
        target_date = vals[0]
        self._confirm_and_rollback_to_date(target_date)

    def _confirm_and_rollback_to_date(self, target_date: str):
        if not self.selected_portfolio_id:
            return
        dates = pt.get_portfolio_simulated_dates(self.db_path, self.selected_portfolio_id)
        if not dates:
            messagebox.showinfo("提醒", "目前沒有可回推的模擬紀錄")
            return
        if target_date >= dates[-1]:
            messagebox.showinfo("提醒", f"交易日 {target_date} 已是最新模擬日，無需回推。")
            return

        p = pt.get_portfolio(self.db_path, self.selected_portfolio_id)
        name = p.name if p else f"組合 {self.selected_portfolio_id}"
        msg = (
            f"確定要將組合「{name}」回推至交易日 {target_date} 嗎？\n\n"
            f"• 目前最新模擬日：{dates[-1]}\n"
            f"• 回推後最新日期：{target_date}\n\n"
            f"⚠️ 該日期之後的所有買賣紀錄與資產快照將被清除，持倉與現金將還原至該日狀態。"
        )
        if not messagebox.askyesno("確認回推交易日", msg):
            return

        del_trades, del_snaps = pt.rollback_portfolio(self.db_path, self.selected_portfolio_id, target_date)
        self._log(f"⏪ 已成功回推至 {target_date}（清除 {del_trades} 筆交易、{del_snaps} 筆快照）")
        self._refresh_portfolio_list()
        self._refresh_detail()

    def _on_rollback_one_day(self):
        if not self.selected_portfolio_id:
            messagebox.showinfo("提醒", "請先選一個組合")
            return
        dates = pt.get_portfolio_simulated_dates(self.db_path, self.selected_portfolio_id)
        if not dates:
            messagebox.showinfo("提醒", "目前沒有可回推的模擬紀錄")
            return

        p = pt.get_portfolio(self.db_path, self.selected_portfolio_id)
        name = p.name if p else f"組合 {self.selected_portfolio_id}"

        if len(dates) == 1:
            target_date = None
            target_str = "重設為初始狀態（清除首日模擬紀錄）"
        else:
            target_date = dates[-2]
            target_str = target_date

        msg = (
            f"確定要將組合「{name}」回推 1 個交易日嗎？\n\n"
            f"• 目前最新模擬日：{dates[-1]}\n"
            f"• 回推後最新日期：{target_str}\n\n"
            f"⚠️ 該日期之後的所有買賣紀錄與資產快照將被清除，持倉與現金將還原至該日狀態。"
        )
        if not messagebox.askyesno("確認回推一日", msg):
            return

        del_trades, del_snaps = pt.rollback_portfolio(self.db_path, self.selected_portfolio_id, target_date)
        self._log(f"⏪ 已成功回推 1 日至 {target_str}（清除 {del_trades} 筆交易、{del_snaps} 筆快照）")
        self._refresh_portfolio_list()
        self._refresh_detail()

    def _on_rollback_n_days(self):
        if not self.selected_portfolio_id:
            messagebox.showinfo("提醒", "請先選一個組合")
            return
        dates = pt.get_portfolio_simulated_dates(self.db_path, self.selected_portfolio_id)
        if not dates:
            messagebox.showinfo("提醒", "目前沒有可回推的模擬紀錄")
            return

        p = pt.get_portfolio(self.db_path, self.selected_portfolio_id)
        name = p.name if p else f"組合 {self.selected_portfolio_id}"

        dlg = RollbackDaysDialog(self.frame, name, dates)
        res = dlg.show()
        if res is None:
            return

        target_date, days = res
        target_str = target_date if target_date else "初始狀態"

        msg = (
            f"確定要將組合「{name}」回推 {days} 個交易日嗎？\n\n"
            f"• 目前最新模擬日：{dates[-1]}\n"
            f"• 回推後最新日期：{target_str}\n\n"
            f"⚠️ 該日期之後的所有買賣紀錄與資產快照將被清除，持倉與現金將還原至該日狀態。"
        )
        if not messagebox.askyesno("確認回推", msg):
            return

        del_trades, del_snaps = pt.rollback_portfolio(self.db_path, self.selected_portfolio_id, target_date)
        self._log(f"⏪ 已成功回推 {days} 日至 {target_str}（清除 {del_trades} 筆交易、{del_snaps} 筆快照）")
        self._refresh_portfolio_list()
        self._refresh_detail()

    def _on_advance_one_day(self):
        if not self.selected_portfolio_id:
            messagebox.showinfo("提醒", "請先選一個組合")
            return
        self._advance_one_day_for(self.selected_portfolio_id)

    def _on_catch_up_to_today(self):
        if not self.selected_portfolio_id:
            messagebox.showinfo("提醒", "請先選一個組合")
            return
        self._log("⏩ 開始補跑到今天…")
        from .. import paper_catchup
        try:
            session = getattr(self.app, "session", None)
            cfg = getattr(self.app, "cfg", None)
            result = paper_catchup.catch_up_portfolio(
                self.db_path, self.selected_portfolio_id,
                end_date=None, session=session, cfg=cfg, logger=self._logger(),
            )
            self._log(f"✅ 補跑完成：BUY {result.total_buys} / SELL {result.total_sells} / 跳過 {len(result.skipped_dates)} / 錯誤 {len(result.errors)}")
            self._refresh_detail()
        except Exception as e:
            self._log(f"❌ 補跑失敗: {e}")
            messagebox.showerror("補跑失敗", str(e))

    def _advance_one_day_for(self, portfolio_id: int):
        """對一個組合推進一天（支援歷史日 K 推進與當日即時報價模擬）"""
        p = pt.get_portfolio(self.db_path, portfolio_id)
        if not p or p.status != "active":
            self._log(f"⏭ 組合 {portfolio_id} 狀態為 {p.status if p else 'N/A'}、跳過")
            return

        today = datetime.now().strftime("%Y-%m-%d")
        last_date = p.last_run_date
        if last_date and " " in last_date:
            last_date = last_date.split(" ")[0]

        # 若最後執行日小於今天，嘗試推進至下一個歷史交易日
        if last_date and last_date < today:
            from ..paper_catchup import _list_trade_dates, catch_up_portfolio
            start_dt = datetime.strptime(last_date, "%Y-%m-%d") + timedelta(days=1)
            start_str = start_dt.strftime("%Y-%m-%d")
            upcoming_dates = _list_trade_dates(start_str, today)
            if upcoming_dates:
                next_date = upcoming_dates[0]
                if next_date < today:
                    self._log(f"▶ 推進一天：{next_date} (歷史推進)...")
                    session = getattr(self.app, "session", None)
                    cfg = getattr(self.app, "cfg", None)
                    try:
                        result = catch_up_portfolio(
                            self.db_path, portfolio_id, end_date=next_date,
                            session=session, cfg=cfg, logger=self._logger()
                        )
                        self._log(f"✅ 推進至 {next_date}：BUY {result.total_buys} / SELL {result.total_sells}")
                        self._refresh_detail()
                        return
                    except Exception as e:
                        self._log(f"❌ 歷史推進失敗: {e}")
                        messagebox.showerror("推進失敗", str(e))
                        return
        elif last_date and last_date >= today:
            if not messagebox.askyesno("今日已執行", f"組合「{p.name}」今日 ({today}) 已經執行過模擬。\n是否要重新以最新報價評估當日決策？"):
                return

        # 抓股票池 + 持股的價格（用既有 fetch_market 邏輯）
        all_codes = list(set((p.stock_pool or []) + [h.stock_code for h in pt.list_holdings(self.db_path, portfolio_id)]))
        stock_data = self._fetch_stock_data(all_codes)

        if not stock_data:
            self._log("⚠️ 沒有抓到任何股票資料、無法推進")
            return

        # 觸發引擎
        if p.strategy_mode == "ai_meta":
            # AI 模式：用 regime + AI 決策
            regime = pe.detect_market_regime(None)
            self._log(f"[AI] 盤勢判定: {regime.description}")
            result = pe.evaluate_ai_portfolio_one_day(
                self.db_path, portfolio_id, today, stock_data, regime, logger=self._logger(),
            )
        else:
            result = pe.evaluate_portfolio_one_day(
                self.db_path, portfolio_id, today, stock_data, logger=self._logger(),
            )

        pt.update_portfolio_last_run(self.db_path, portfolio_id, today)

        self._log(
            f"✅ {p.name} @ {today}：BUY {len(result.buy_actions)} / SELL {len(result.sell_actions)} / 跳過 {len(result.skipped)}"
        )
        for t in result.buy_actions:
            self._log(f"   🟢 BUY {t.stock_code} {t.shares:,.0f}股 @ {t.price:.2f}")
        for t in result.sell_actions:
            self._log(f"   🔴 SELL {t.stock_code} {t.shares:,.0f}股 @ {t.price:.2f} - {t.reasoning}")

        self._refresh_detail()

    def _fetch_stock_data(self, codes: List[str]) -> Dict[str, Dict]:
        """
        抓股票池的當日資料（從既有 fetch_prices / scoring 結果）

        V1.2.0 簡化版：用 app 既有的快取 / 重抓單股報價
        """
        out: Dict[str, Dict] = {}
        if not codes:
            return out

        try:
            from stocktool.fetch_market import _fetch_twse_realtime_batch
            session = getattr(self.app, "session", None)
            logger = getattr(self.app, "logger", None)
            cfg = getattr(self.app, "cfg", None)
            if not session or not cfg:
                self._log("⚠️ app 沒有 session/cfg、無法抓股價")
                return out
            df = _fetch_twse_realtime_batch(session, codes, logger=logger)
            if df is None or df.empty:
                return out

            for code in codes:
                row = df[df["stock_id"] == code]
                if row.empty:
                    continue
                r = row.iloc[0]
                price = float(r.get("close") or r.get("price") or 0)
                if price <= 0:
                    continue
                raw_name = str(r.get("name") or "").strip()
                if not raw_name or raw_name == code:
                    raw_name = pt.get_stock_name(code) or code
                out[code] = {
                    "code": code,
                    "name": raw_name,
                    "price": price,
                    "pe": r.get("pe"),
                    "eps": r.get("eps"),
                    "rev_yoy": r.get("rev_yoy"),
                    "yield_pct": r.get("yield_pct"),
                }

            if out:
                from ..paper_catchup import enrich_stock_fundamentals
                today = datetime.now().strftime("%Y-%m-%d")
                eps_db = getattr(cfg, "eps_history_db", None) if cfg else None
                out = enrich_stock_fundamentals(out, today, eps_db=eps_db)
        except Exception as e:
            self._log(f"⚠️ 抓股價失敗: {e}")
        return out

    # ==========================================================
    # 輔助
    # ==========================================================

    def _logger(self):
        """回傳 logging.Logger（給 engine 用）"""
        import logging
        logger = logging.getLogger(f"paper.{self.selected_portfolio_id}")
        if not logger.handlers:
            h = logging.StreamHandler()
            h.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
            logger.addHandler(h)
            logger.setLevel(logging.INFO)
        return logger

    def _log(self, msg: str):
        try:
            if hasattr(self.app, "logger") and hasattr(self.app.logger, "log"):
                self.app.logger.log(msg)
            else:
                print(msg)
        except Exception:
            print(msg)
        if self.status_label:
            self.status_label.config(text=msg[:60])