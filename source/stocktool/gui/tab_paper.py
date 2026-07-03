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
from datetime import datetime
from typing import List, Dict, Optional

from .. import paper_trading as pt
from .. import paper_excel
from .. import paper_engine as pe


class PaperTradingTab:
    """模擬買賣 Tab - 由 StockTool.py 持有"""

    def __init__(self, parent_app, parent_frame):
        self.app = parent_app
        self.frame = parent_frame
        self.db_path = "portfolio.db"
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
        ttk.Button(op_frame, text="⏸ 暫停", width=7, command=self._on_pause).pack(side="left", padx=1)
        ttk.Button(op_frame, text="▶ 繼續", width=7, command=self._on_resume).pack(side="left", padx=1)
        ttk.Button(op_frame, text="🗑 刪除", width=7, command=self._on_delete).pack(side="left", padx=1)
        ttk.Button(op_frame, text="🔄 重新整理", width=9, command=self._refresh_portfolio_list).pack(side="left", padx=1)

        # === 執行控制 ===
        exec_frame = ttk.LabelFrame(parent, text="▶ 執行控制", padding=6)
        exec_frame.pack(fill="x", pady=(0, 6))

        ttk.Button(exec_frame, text="▶ 推進一天（手動）",
                   command=self._on_advance_one_day).pack(fill="x", pady=2)
        ttk.Button(exec_frame, text="⏩ 補跑到今天",
                   command=self._on_catch_up_to_today).pack(fill="x", pady=2)

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

        ttk.Button(parent, text="🔄 重新整理", command=self._refresh_trades).pack(pady=4)

    def _build_chart_tab(self, parent):
        """權益曲線（先放 placeholder、之後用 matplotlib 畫）"""
        self.chart_text = tk.Text(parent, wrap="word", font=("Consolas", 9))
        self.chart_text.pack(fill="both", expand=True)
        self.chart_text.insert("end", "（權益曲線尚未實作、之後用 matplotlib）\n")

    # ==========================================================
    # 事件處理
    # ==========================================================

    def _on_browse_excel(self):
        path = filedialog.askopenfilename(
            title="選擇選股 Excel",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        if path:
            self.new_excel_var.set(path)

    def _on_create_portfolio(self):
        name = self.new_name_var.get().strip()
        if not name:
            messagebox.showwarning("提醒", "請輸入組合名稱")
            return

        excel_path = self.new_excel_var.get().strip()
        stock_pool: List[str] = []
        if excel_path:
            if not os.path.exists(excel_path):
                messagebox.showerror("錯誤", f"Excel 不存在:\n{excel_path}")
                return
            stock_pool, warns = paper_excel.parse_excel_to_stock_pool(excel_path)
            for w in warns:
                self._log(w)
            if not stock_pool:
                if not messagebox.askyesno("確認", "Excel 解析後沒有任何股票代號、仍要建立嗎？"):
                    return

        try:
            initial_cash = float(self.new_cash_var.get())
            max_holdings = int(self.new_max_var.get())
        except ValueError:
            messagebox.showerror("錯誤", "總資金/持倉上限格式錯誤")
            return

        strategy = self.new_strategy_var.get()
        p = pt.PaperPortfolio(
            name=name,
            excel_file=excel_path or None,
            stock_pool=stock_pool,
            initial_cash=initial_cash,
            max_holdings=max_holdings,
            strategy_mode=strategy,
        )
        try:
            pid = pt.create_portfolio(self.db_path, p)
        except Exception as e:
            messagebox.showerror("錯誤", f"建立失敗: {e}")
            return

        self._log(f"✅ 已建立組合「{name}」(id={pid})，股票池 {len(stock_pool)} 檔")
        self._refresh_portfolio_list()
        self.new_name_var.set("")

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
            self.holdings_tree.insert("", "end", values=(
                h.stock_code, h.stock_name or "-",
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
            self.trades_tree.insert("", "end", values=(
                t.trade_date, action_icon, t.stock_code, t.stock_name or "-",
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
    # 執行（推進一天、補跑）
    # ==========================================================

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
        """對一個組合推進一天（用「當前可得價」模擬）"""
        p = pt.get_portfolio(self.db_path, portfolio_id)
        if not p or p.status != "active":
            self._log(f"⏭ 組合 {portfolio_id} 狀態為 {p.status if p else 'N/A'}、跳過")
            return

        today = datetime.now().strftime("%Y-%m-%d")

        # 抓股票池 + 持股的價格（用既有 fetch_market 邏輯）
        all_codes = list(set((p.stock_pool or []) + [h.stock_code for h in pt.list_holdings(self.db_path, portfolio_id)]))
        stock_data = self._fetch_stock_data(all_codes)

        if not stock_data:
            self._log("⚠️ 沒有抓到任何股票資料、無法推進")
            return

        # 觸發引擎
        if p.strategy_mode == "ai_meta":
            # AI 模式：用 regime + AI 決策
            regime = pe.detect_market_regime(None)  # 暫不傳歷史、給 sideways
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
                out[code] = {
                    "code": code,
                    "name": str(r.get("name", code)),
                    "price": price,
                    "pe": r.get("pe"),
                    "eps": r.get("eps"),
                    "rev_yoy": r.get("rev_yoy"),
                    "yield_pct": r.get("yield_pct"),
                }
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