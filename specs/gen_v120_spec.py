"""
V1.2.0-paper-trading 規格書產生器
===================================
執行：python3 specs/gen_v120_spec.py
產出：documents/V1.2.0-paper-trading_規格書.docx
"""
from __future__ import annotations
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from datetime import datetime
import os

OUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "documents", "V1.2.0-paper-trading_規格書.docx"
)

# ──── 樣式 helper ────
def set_zh_font(run, size=10.5, bold=False, italic=False, color=None):
    run.font.name = "Consolas"
    run.font.size = Pt(size)
    run.font.italic = italic
    run.font.bold = bold
    if color:
        run.font.color.rgb = color
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    rFonts.set(qn("w:eastAsia"), "標楷體")
    rFonts.set(qn("w:ascii"), "Consolas")
    rFonts.set(qn("w:hAnsi"), "Consolas")

def add_h1(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(18); p.paragraph_format.space_after = Pt(8)
    r = p.add_run(text)
    set_zh_font(r, size=18, bold=True, color=RGBColor(0x1F,0x3A,0x5F))

def add_h2(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12); p.paragraph_format.space_after = Pt(6)
    r = p.add_run(text)
    set_zh_font(r, size=14, bold=True, color=RGBColor(0x2E,0x5A,0x88))

def add_h3(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8); p.paragraph_format.space_after = Pt(4)
    r = p.add_run(text)
    set_zh_font(r, size=12, bold=True, color=RGBColor(0x44,0x44,0x44))

def add_p(doc, text, bold=False, italic=False):
    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(4)
    r = p.add_run(text); set_zh_font(r, size=10.5, bold=bold, italic=italic)

def add_bullet(doc, text):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.left_indent = Cm(0.5)
    if not p.runs: p.add_run("")
    r = p.add_run(text); set_zh_font(r, size=10.5)

def add_code_block(doc, code: str):
    tbl = doc.add_table(rows=1, cols=1); tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    cell = tbl.rows[0].cells[0]
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd"); shd.set(qn("w:val"),"clear"); shd.set(qn("w:color"),"auto"); shd.set(qn("w:fill"),"F0F0F0")
    tcPr.append(shd)
    cell.text = ""
    for line in code.split("\n"):
        p = cell.add_paragraph(); r = p.add_run(line if line else " ")
        set_zh_font(r, size=9.5)
    cell._tc.remove(cell.paragraphs[0]._p)
    tblPr = tbl._element.find(qn("w:tblPr"))
    borders = OxmlElement("w:tblBorders")
    for edge in ("top","left","bottom","right"):
        b = OxmlElement(f"w:{edge}"); b.set(qn("w:val"),"single"); b.set(qn("w:sz"),"4"); b.set(qn("w:color"),"CCCCCC")
        borders.append(b)
    tblPr.append(borders)

def add_table(doc, headers, rows, widths_cm=None):
    tbl = doc.add_table(rows=1+len(rows), cols=len(headers)); tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    for i,h in enumerate(headers):
        cell = tbl.rows[0].cells[i]; cell.text = ""
        p = cell.paragraphs[0]; r = p.add_run(h)
        set_zh_font(r, size=10.5, bold=True, color=RGBColor(0xFF,0xFF,0xFF))
        tcPr = cell._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd"); shd.set(qn("w:val"),"clear"); shd.set(qn("w:color"),"auto"); shd.set(qn("w:fill"),"2E5A88")
        tcPr.append(shd)
    for ri,row in enumerate(rows):
        for ci,v in enumerate(row):
            cell = tbl.rows[1+ri].cells[ci]; cell.text = ""
            p = cell.paragraphs[0]; r = p.add_run(str(v)); set_zh_font(r, size=10)
            if ri % 2 == 1:
                tcPr = cell._tc.get_or_add_tcPr()
                shd = OxmlElement("w:shd"); shd.set(qn("w:val"),"clear"); shd.set(qn("w:color"),"auto"); shd.set(qn("w:fill"),"F5F8FC")
                tcPr.append(shd)
    if widths_cm:
        for i,w in enumerate(widths_cm):
            for row in tbl.rows: row.cells[i].width = Cm(w)


def build():
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = sec.bottom_margin = Cm(2.0)
    sec.left_margin = sec.right_margin = Cm(2.2)

    # 封面
    for txt, sz, color, space_before in [
        ("StockTool / 股神", 22, RGBColor(0x1F,0x3A,0x5F), 0),
        ("V1.2.0-paper-trading-kb-focus-v26 規格書", 26, RGBColor(0x2E,0x5A,0x88), 0),
        ("台灣股市量化選股 + 模擬買賣組合管理系統", 14, RGBColor(0x66,0x66,0x66), 40),
    ]:
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if space_before: p.paragraph_format.space_before = Pt(space_before)
        r = p.add_run(txt); set_zh_font(r, size=sz, color=color)

    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(20)
    now = datetime.now().strftime("%Y-%m-%d")
    r = p.add_run(f"發行日期:{now}    版本:v1.2.0-paper-trading-kb-focus-v26    作者:William Chang")
    set_zh_font(r, size=11, color=RGBColor(0x66,0x66,0x66))

    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("前版規格書:V0.9.4(2026-06-10)、V0.9.5-etf-fix(2026-06-19)")
    set_zh_font(r, size=10, color=RGBColor(0x88,0x88,0x88))

    doc.add_page_break()

    # 1. 概述
    add_h1(doc, "1. 概述")
    add_h2(doc, "1.1 版本歷程")
    add_p(doc, "從 V0.9.4(2026-06-10)到本版 V1.2.0-paper-trading-kb-focus-v26(2026-07-12),歷經 13 個版本演進。", bold=True)
    add_table(doc,
        ["版本","日期","重點"],
        [
            ["V0.9.3-HOTFIX","2026-06-08","修正 EPS YoY / Score 無限值 / Top10 全為 ETF 等問題"],
            ["V0.9.4","2026-06-10","新增「買賣記錄」模組:SQLite + Tab 化 GUI + Excel 匯出"],
            ["V0.9.5","2026-06-13","🔍 手動選股 Tab + Preset 機制"],
            ["V0.9.5-etf","2026-06-19","📊 主動式 ETF Tab + 19 檔清單"],
            ["V0.9.5-vol-no-divide","2026-06-21","📊 ETF Tab 加「重新抓股價」按鈕(共用快取)"],
            ["V0.9.5-goodinfo4+5","2026-06-22","goodinfo retry + cache 現價 fillna + vol=0 顯示 -"],
            ["V0.9.5g3 / g6","2026-06-26","殖利率 3 位小數 cash bug 修正 + 半年殖利率資料匯入"],
            ["V1.0","2026-07-01","EPS YoY 上游補資料 + 5 項 P0/P1/P2 修正"],
            ["V1.1.0","2026-07-02","重構:2363 行單檔 → StockTool.py + stocktool/ 子模組"],
            ["V1.1.3","2026-07-02","no-double-score + WF docstring + cache TTL 分層"],
            ["V1.1.5c","2026-07-03","📊 系統選股 Tab「重新抓股價」按鈕"],
            ["V1.2.0 stage1-5","2026-07-03","🆕 模擬買賣組合管理(paper trading)模組化"],
            ["V1.2.0 stage 6","2026-07-04","PaperScheduler 14:00 自動排程 + GUI console 接線"],
            ["V1.2.0 keyboard-toggle","2026-07-06","Treeview ↑/↓ + Space toggle 鍵盤導航(4 個 tab)"],
            ["V1.2.0-keyboard-focus v8-v26","2026-07-08~10","v8→v26 fix2 連 19 版 hover/keyboard 殘留修正"],
            ["V1.2.0 fix3","2026-07-12","消 PyCharm console 噪音(_v18_log 改寫檔)"],
            ["V1.2.0 規格書","2026-09-18","📘 本規格書 + 使用者手冊改版"],
        ], widths_cm=[4.2, 2.6, 10])

    add_h2(doc, "1.2 改版動機")
    add_p(doc, "V0.9.4 之前 StockTool 能「選股 + 回測 + 買賣記錄」,但還缺一個關鍵環節:自動化的策略驗證。")
    add_p(doc, "使用者挑了一組股票後,要靠肉眼 + Excel 模擬「如果我 7/1 買進、8/1 賣出,績效如何」。")
    add_p(doc, "V1.2.0-paper-trading 把這件事變成「模擬買賣組合管理」:")
    add_bullet(doc, "📦 一個「組合」= 一組股票池 + 一個策略(ai_meta / manual) + 一份起始資金")
    add_bullet(doc, "⏰ 14:00 自動排程補跑(App 開著時自動跑,沒開則下次手動補跑)")
    add_bullet(doc, "💰 每日自動進出場決策 → 持倉、損益、交易明細、權益曲線、Excel 匯出")
    add_bullet(doc, "🧪 真正的「paper trading」= 用真實歷史價模擬、但不下單,純粹驗證策略 alpha")

    add_h2(doc, "1.3 範圍與限制")
    add_h3(doc, "範圍")
    add_bullet(doc, "選股:系統選股 / 手動選股 / ETF 選股 / 回測(4 個核心 tab)")
    add_bullet(doc, "模擬買賣:組合 CRUD、ai_meta / manual 兩種策略模式、補跑、排程、權益曲線")
    add_bullet(doc, "買賣記錄:手動新增買入/賣出、平均成本、即時損益、Excel 匯出")
    add_bullet(doc, "資料來源:TWSE / TPEX 月線 + 日線 + 殖利率 + ETF 成份股 + goodinfo 驗證")

    add_h3(doc, "不做")
    add_bullet(doc, "❌ 不做:自動下單(無券商 API 串接)")
    add_bullet(doc, "❌ 不做:即時報價推送(補跑用歷史收盤價、推進一天用即時抓的價格)")
    add_bullet(doc, "❌ 不做:多帳戶、跨組合再平衡、稅負計算")
    add_bullet(doc, "❌ 不做:盤中逐筆交易(純 EOD 模擬)")

    add_h3(doc, "排程方式")
    add_bullet(doc, "App 啟動後 PaperScheduler 每分鐘檢查 → 過了 14:05 且今天還沒跑 → 自動觸發 catch_up_all_active")
    add_bullet(doc, "App 關閉期間不補跑 → 下次手動按「⏩ 補跑到今天」可一次補齊")
    add_bullet(doc, "14:05 而非 14:00:寬限 5 分鐘避開剛收盤 TWSE 資料未更新")

    # 2. 功能需求
    add_h1(doc, "2. 功能需求")
    add_h2(doc, "2.1 模擬買賣組合資料模型")
    add_p(doc, "核心資料實體:PaperPortfolio / SimHolding / SimTrade / DailySnapshot。", bold=True)

    add_h3(doc, "PaperPortfolio(組合)")
    add_table(doc,
        ["欄位","型態","說明"],
        [
            ["id","INTEGER PK","自動編號"],
            ["name","TEXT UNIQUE","組合名稱"],
            ["strategy_mode","TEXT","ai_meta / manual"],
            ["strategy_params","TEXT (JSON)","策略參數(ma_slope_days、rsi_oversold 等)"],
            ["stock_pool","TEXT (JSON list)","股票池代號清單"],
            ["initial_cash","REAL","起始資金(預設 1,000,000)"],
            ["max_holdings","INT","持倉上限(預設 10)"],
            ["topk","INT","TopK 選股數"],
            ["hold_days","INT","持有天數(0 = 無限)"],
            ["stop_loss","REAL","停損(例 -0.03)"],
            ["take_profit","REAL","停利(例 0.08)"],
            ["status","TEXT","active / paused / archived"],
            ["started_at","TEXT","YYYY-MM-DD HH:MM:SS"],
            ["last_run_date","TEXT","YYYY-MM-DD(最後補跑到的日期)"],
            ["created_at","TEXT","建立時間(自動)"],
        ], widths_cm=[3, 3, 11])

    add_h3(doc, "SimHolding(持倉)")
    add_table(doc,
        ["欄位","型態","說明"],
        [
            ["portfolio_id","INTEGER FK","組合 ID"],
            ["stock_code","TEXT","股票代號"],
            ["stock_name","TEXT","股票名稱"],
            ["shares","REAL","持有股數"],
            ["avg_cost","REAL","平均成本(含手續費加權)"],
            ["current_price","REAL","目前現價"],
            ["entry_date","TEXT","進場日期"],
            ["entry_price","REAL","進場均價"],
        ], widths_cm=[3, 3, 11])

    add_h3(doc, "SimTrade(交易明細)")
    add_table(doc,
        ["欄位","型態","說明"],
        [
            ["portfolio_id","INTEGER FK","組合 ID"],
            ["stock_code","TEXT","股票代號"],
            ["stock_name","TEXT","股票名稱"],
            ["action","TEXT","BUY / SELL"],
            ["trade_date","TEXT","YYYY-MM-DD"],
            ["shares","REAL","成交股數"],
            ["price","REAL","成交價"],
            ["amount","REAL","成交金額"],
            ["fee","REAL","手續費"],
            ["tax","REAL","交易稅"],
            ["reasoning","TEXT","進出場理由"],
        ], widths_cm=[3, 3, 11])

    add_h3(doc, "DailySnapshot(每日權益快照)")
    add_p(doc, "給權益曲線用的快照表:portfolio_id × trade_date → 總市值、現金、累積報酬、持倉數。")
    add_p(doc, "寫入時機:每次 catch_up_portfolio 完成後逐日寫入。")

    add_h2(doc, "2.2 策略模式")
    add_h3(doc, "ai_meta(AI meta 評分模式,預設)")
    add_p(doc, "從 stock_pool 每日打分數 → 取 TopK → 進場。AI score 計算:")
    add_code_block(doc,
"""# 簡化版 pseudo-code(完整見 stocktool/paper_engine.py:ai_meta_decision)
score = (
    +0.25 * 營收 YoY (z-score)
    +0.25 * EPS YoY (z-score)
    +0.15 * 1 月動能
    +0.15 * 3 月動能
    +0.20 * 6 月動能
    -0.05 * PE (z-score, 反向)
    +bonus if MA20 trend up + RSI recovers from oversold
)
""")

    add_h3(doc, "manual(手動模式)")
    add_p(doc, "使用者挑好股票 → 全部放進 stock_pool → 系統按等權重買入持有。")
    add_p(doc, "賣出條件:到達 hold_days / 觸發 stop_loss / 觸發 take_profit / 組合停損。")

    add_h2(doc, "2.3 GUI 操作流程(6 個 Tab)")
    add_table(doc,
        ["Tab","功能","本版狀態"],
        [
            ["⚙️ 策略參數","全部選股 / 回測 / 評分參數","V0.9.3 起保留,本版不動"],
            ["🔍 手動選股","Preset + 條件篩選 + Excel","V0.9.5 新增"],
            ["📊 主動式 ETF","ETF 19 檔清單 + 持股抓取","V0.9.5-etf 新增"],
            ["📈 系統選股","多因子評分 + TopN","V1.1.5c 加「重新抓股價」"],
            ["📊 回測模擬","Top10 基本面回測","V0.9.2 起保留"],
            ["📅 模擬買賣","組合 CRUD + 補跑 + 排程","V1.2.0 新增(本版重點)"],
        ], widths_cm=[3, 7, 7])

    add_h2(doc, "2.4 模擬買賣 Tab 子區塊")
    add_h3(doc, "上方:組合清單 Treeview")
    add_bullet(doc, "欄位:ID / 名稱 / 策略 / 股票池數 / 啟動日 / 最後跑日 / 狀態 / 總資金 / 累積報酬 / 持倉")
    add_bullet(doc, "雙擊 → 進入下方 detail(手動設定 tab)")
    add_h3(doc, "下方(手動設定 tab):6 個區塊")
    add_bullet(doc, "Row 1:基本資料(名稱 / Excel / 策略下拉 / 總資金 / 持倉上限)")
    add_bullet(doc, "Row 1 右側:執行控制(▶ 推進一天 / ⏩ 補跑到今天 / AI 模式開關)")
    add_bullet(doc, "Row 2:系統選股回購狀態(衝刺 / 啟動時間 / 摘要 4 項)")
    add_bullet(doc, "Tab 群組:持倉 / 買賣記錄 / 權益曲線 / 我的組合(左下)")
    add_h3(doc, "新增 / 編輯組合對話框(dialog_paper.py)")
    add_bullet(doc, "必填:名稱、策略模式、總資金、持倉上限")
    add_bullet(doc, "選填:股票池(多選清單 + 搜尋)、TopK、hold_days、stop_loss、take_profit")
    add_bullet(doc, "📥「採用回測參數」一鍵帶入:從 backtest 結果的 Top10 平均參數帶入此組合")

    add_h2(doc, "2.5 補跑邏輯(paper_catchup.py)")
    add_h3(doc, "觸發方式")
    add_bullet(doc, "手動:GUI「⏩ 補跑到今天」按鈕")
    add_bullet(doc, "自動:PaperScheduler 每天 14:05 後(App 開著時)")
    add_h3(doc, "執行流程")
    add_code_block(doc,
"""for portfolio in active_portfolios:
    start = last_run_date + 1 day   # 從上次跑完隔天開始
    end   = today (or 指定日期)
    for trade_date in [start..end]:
        # 1) 抓 stock_pool + 持股的歷史收盤價
        #    (用 cache/history/<code>_<months>m.xlsx)
        # 2) 偵測 market regime (多頭 / 空頭 / 盤整)
        # 3) 呼叫 engine 跑 BUY/SELL 決策
        if strategy == "ai_meta":
            engine.evaluate_ai_portfolio_one_day(...)
        else:
            engine.evaluate_portfolio_one_day(...)
        # 4) 寫入 trades + 持倉 + 當日 snapshot
""")

    add_h3(doc, "Cache 過舊處理(V1.2.0-2026-08-20 新增)")
    add_p(doc, "若 cache 的最新日期 < trade_date → 自動 refresh(需 session != None 才會觸發)。", italic=True)
    add_bullet(doc, "正常:有 session → 呼叫 get_stock_history 抓新資料 + 寫回 cache")
    add_bullet(doc, "降級:無 session(PyCharm 開發模式 / 測試環境)→ skip 該日,繼續下一檔")
    add_bullet(doc, "🟡 已知限制:StockTool 主類別無 self.session 屬性 → 需外部傳入")

    add_h2(doc, "2.6 排程邏輯(paper_scheduler.py)")
    add_code_block(doc,
"""class PaperScheduler:
    AUTO_RUN_HOUR = 14      # 14:00
    AUTO_RUN_MINUTE = 5     # 寬限到 14:05
    CHECK_INTERVAL_MS = 60_000   # 每分鐘 tick

    def _tick(self):
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        # 過了 14:05 且今天還沒跑 → 觸發
        if (now.hour > 14 or (now.hour == 14 and now.minute >= 5)):
            if self._last_auto_date != today:
                self._run_auto_today(today)
        # 排下一次
        self._job_id = self.app.after(60_000, self._tick)

    def _run_auto_today(self, today):
        session = getattr(self.app, "session", None)
        cfg = getattr(self.app, "cfg", None)
        results = paper_catchup.catch_up_all_active(
            self.db_path, end_date=today,
            session=session, cfg=cfg, logger=self._logger()
        )
""")

    add_h2(doc, "2.7 匯出 Excel 規格")
    add_table(doc,
        ["工作表名稱","內容"],
        [
            ["組合總覽","總成本、總市值、未實現損益、已實現損益、總報酬率"],
            ["組合持倉","每檔股票:代號、名稱、股數、平均成本、現價、未實現損益、報酬率%"],
            ["交易明細","所有 BUY / SELL:日期、代號、名稱、買/賣、股數、價格、金額、手續費、理由"],
            ["權益曲線","每日總市值、累積報酬%(給 chart 用)"],
            ["匯出資訊","匯出時間、總交易筆數、組合名稱、StockTool 版本"],
        ], widths_cm=[3.5, 13.5])
    add_p(doc, "樣式:表頭藍底白字、數字千分位、負數紅字、百分比格式、日期 YYYY-MM-DD。")

    # 3. 技術架構
    add_h1(doc, "3. 技術架構")
    add_h2(doc, "3.1 檔案結構")
    add_code_block(doc,
"""StockTools/                                  ← GitHub repo
├── source/
│   ├── StockTool.py                          ← 主程式(9838 行)
│   ├── portfolio.py                          ← 買賣記錄 DB(V0.9.4 起)
│   └── stocktool/                            ← V1.1.0 起重構出的子模組
│       ├── __init__.py                       (143 行)
│       ├── backtest.py                       (543 行) - 回測引擎
│       ├── cache.py                          (246 行) - 多源 cache 管理
│       ├── config.py                         (451 行) - VERSION + CONFIG
│       ├── database.py                       (524 行) - DB 共用 helper
│       ├── etf.py                            (365 行) - ETF 抓取 + GUI
│       ├── export_excel.py                   (151 行) - Excel 報表
│       ├── fetch_market.py                   (1585 行) - TWSE / TPEX
│       ├── pipeline.py                       (752 行) - 選股 pipeline
│       ├── scoring.py                        (588 行) - 多因子評分
│       ├── technical.py                      (135 行) - RSI / MA / MACD
│       ├── paper_config.py                   (75 行) - ⭐ 回測→模擬參數映射
│       ├── paper_engine.py                   (703 行) - ⭐ 每日 BUY/SELL 決策
│       ├── paper_trading.py                  (470 行) - ⭐ DB CRUD
│       ├── paper_catchup.py                  (305 行) - ⭐ 補跑到今天
│       ├── paper_scheduler.py                (131 行) - ⭐ 14:00 自動排程
│       ├── paper_excel.py                    (126 行) - ⭐ Excel 匯出
│       └── gui/
│           ├── calendar.py                   (213 行)
│           ├── dialog_paper.py               (282 行) - ⭐ 對話框
│           └── tab_paper.py                  (751 行) - ⭐ 模擬買賣 Tab
├── documents/
│   ├── V0.9.4_規格書.docx                     ← 舊版規格書
│   ├── 股神_StockTool_使用者手冊_v0.9.5-etf-fix.docx
│   ├── V1.2.0-paper-trading_規格書.docx       ← ⭐ 本檔
│   └── 股神_StockTool_使用者手冊_v1.2.0-paper-trading.docx  ← ⭐ 改版手冊
├── specs/
│   ├── gen_v094_spec.py
│   └── gen_v120_spec.py                      ← ⭐ 本規格書產生器
├── tests/                                     ← 95+ 個 pytest
│   ├── test_paper_trading.py (384)
│   ├── test_paper_config.py (75)
│   ├── test_paper_scheduler.py (140)
│   ├── test_paper_catchup_cache_refresh.py (204)
│   └── test_paper_catchup_history_months.py (188)
├── portfolio.db / stocktool_config.json / requirements.txt
└── .gitignore / .gitattributes
""")

    add_h2(doc, "3.2 模擬買賣模組分工(新增的 6 個 + GUI 2 個)")
    add_table(doc,
        ["模組","職責","行數"],
        [
            ["paper_trading.py","PaperPortfolio / SimHolding / SimTrade dataclass + CRUD + 平均成本","470"],
            ["paper_engine.py","StockSignal / DailyRunResult / MarketRegime + evaluate_*_portfolio_one_day","703"],
            ["paper_config.py","BacktestParamsMapping + apply_backtest_params_to_portfolio","75"],
            ["paper_catchup.py","CatchUpResult + catch_up_portfolio / catch_up_all_active","305"],
            ["paper_scheduler.py","PaperScheduler class(14:00 自動排程、App-level)","131"],
            ["paper_excel.py","模擬買賣 Excel 匯出(5 sheet)","126"],
            ["gui/tab_paper.py","PaperTradingTab class(GUI 主體)","751"],
            ["gui/dialog_paper.py","新增/編輯組合對話框","282"],
            ["合計","—","2843 行"],
        ], widths_cm=[4.5, 9.5, 2.5])

    add_h2(doc, "3.3 SQLite Schema")
    add_code_block(doc,
"""-- 模擬買賣組合
CREATE TABLE IF NOT EXISTS paper_portfolios (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL UNIQUE,
    strategy_mode   TEXT    NOT NULL DEFAULT 'ai_meta',
    strategy_params TEXT    NOT NULL DEFAULT '{}',
    stock_pool      TEXT    NOT NULL DEFAULT '[]',
    initial_cash    REAL    NOT NULL DEFAULT 1000000,
    max_holdings    INTEGER NOT NULL DEFAULT 10,
    topk            INTEGER NOT NULL DEFAULT 7,
    hold_days       INTEGER NOT NULL DEFAULT 10,
    stop_loss       REAL    NOT NULL DEFAULT -0.03,
    take_profit     REAL    NOT NULL DEFAULT 0.08,
    status          TEXT    NOT NULL DEFAULT 'active',
    started_at      TEXT    NOT NULL,
    last_run_date   TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

-- 持倉
CREATE TABLE IF NOT EXISTS paper_holdings (
    portfolio_id    INTEGER NOT NULL,
    stock_code      TEXT    NOT NULL,
    stock_name      TEXT,
    shares          REAL    NOT NULL,
    avg_cost        REAL    NOT NULL,
    current_price   REAL,
    entry_date      TEXT,
    entry_price     REAL,
    PRIMARY KEY (portfolio_id, stock_code)
);

-- 交易明細
CREATE TABLE IF NOT EXISTS paper_trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id    INTEGER NOT NULL,
    stock_code      TEXT    NOT NULL,
    stock_name      TEXT,
    action          TEXT    NOT NULL CHECK(action IN ('BUY','SELL')),
    trade_date      TEXT    NOT NULL,
    shares          REAL    NOT NULL,
    price           REAL    NOT NULL,
    amount          REAL    NOT NULL,
    fee             REAL    NOT NULL DEFAULT 0,
    tax             REAL    NOT NULL DEFAULT 0,
    reasoning       TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_pt_portfolio ON paper_trades(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_pt_date      ON paper_trades(trade_date);

-- 每日權益快照
CREATE TABLE IF NOT EXISTS paper_snapshots (
    portfolio_id    INTEGER NOT NULL,
    trade_date      TEXT    NOT NULL,
    total_value     REAL    NOT NULL,
    cash            REAL    NOT NULL,
    holdings_count  INTEGER NOT NULL,
    cumulative_return REAL  NOT NULL,
    PRIMARY KEY (portfolio_id, trade_date)
);

-- 既有買賣記錄(V0.9.4)
CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id    TEXT    NOT NULL,
    stock_name  TEXT,
    action      TEXT    NOT NULL CHECK(action IN ('BUY','SELL')),
    trade_date  TEXT    NOT NULL,
    shares      REAL    NOT NULL,
    price       REAL    NOT NULL,
    fee         REAL    NOT NULL DEFAULT 0,
    note        TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
""")

    add_h2(doc, "3.4 引擎核心演算法")
    add_h3(doc, "ai_meta_decision(每日 BUY/SELL 決策)")
    add_code_block(doc,
"""def ai_meta_decision(info, p, regime):
    # info:  {code, name, price, ...}
    # p:     PaperPortfolio
    # regime: MarketRegime (Bull / Bear / Sideways)

    # 1) 多因子 z-score 評分
    factors = {
        'rev_yoy':  zscore(info['rev_yoy']),
        'eps_yoy':  zscore(info['eps_yoy']),
        'mom1':     zscore(info['mom1']),
        'mom3':     zscore(info['mom3']),
        'mom6':     zscore(info['mom6']),
        'pe_inv':   -zscore(info['pe']),
    }
    weights = p.strategy_params['weights']
    score = sum(factors[k] * weights[k] for k in factors)

    # 2) 技術面 bonus
    if info['ma20_slope'] > 0 and info['rsi_recover_from_oversold']:
        score += 0.5

    # 3) 進出場決策
    action = None
    if regime == 'Bull' and score > p.topk_threshold:
        action = 'BUY'
    elif info['price'] < info['avg_cost'] * (1 + p.stop_loss):
        action = 'SELL'  # 觸停損
    elif info['price'] > info['avg_cost'] * (1 + p.take_profit):
        action = 'SELL'  # 觸停利
    elif (today - info['entry_date']).days >= p.hold_days:
        action = 'SELL'  # 到期出場

    reasoning = f"score={score:.2f} regime={regime.value}"
    return score, reasoning, confidence=0.7
""")

    add_h3(doc, "detect_market_regime(市場狀態偵測)")
    add_p(doc, "用 TWSE 加權指數近 20 日 MA20 vs MA60 判斷:")
    add_bullet(doc, "MA20 > MA60 × 1.02 → Bull(多頭)")
    add_bullet(doc, "MA20 < MA60 × 0.98 → Bear(空頭)")
    add_bullet(doc, "其餘 → Sideways(盤整)")
    add_p(doc, "空頭時 BUY 門檻提高 50%、停損放寬。", italic=True)

    add_h2(doc, "3.5 Config 參數(stocktool_config.json)")
    add_h3(doc, "核心選股 / 評分參數")
    add_table(doc,
        ["參數","預設值","說明"],
        [
            ["top_n_for_tech","60","技術面 Top N"],
            ["history_months","60","歷史月線抓取月數"],
            ["use_enhanced_score","true","用多因子評分(vs 簡易)"],
            ["factor_weight_mom1","0.15","1 月動能權重"],
            ["factor_weight_mom3","0.15","3 月動能權重"],
            ["factor_weight_mom6","0.20","6 月動能權重"],
            ["factor_weight_rev","0.25","營收 YoY 權重"],
            ["factor_weight_eps","0.25","EPS YoY 權重"],
            ["use_mtf_confirmation","true","MTF(多時框)確認"],
            ["use_divergence_detection","true","背離偵測"],
            ["volume_surge_multiplier","2.0","爆量倍數門檻"],
        ], widths_cm=[5, 3, 9])

    add_h3(doc, "簡易評分參數")
    add_table(doc,
        ["參數","預設值","說明"],
        [
            ["simple_score_weight_rev","35.0","營收權重"],
            ["simple_score_weight_eps","35.0","EPS 權重"],
            ["simple_score_weight_div","20.0","殖利率權重"],
            ["simple_score_weight_pe","-5.0","PE 權重(負向)"],
            ["simple_min_rev_yoy","-999.0","最低營收 YoY"],
            ["simple_min_eps_yoy","-999.0","最低 EPS YoY"],
            ["simple_min_eps","-999.0","最低 EPS"],
            ["simple_max_pe","999.0","最高 PE"],
        ], widths_cm=[5, 3, 9])

    add_h3(doc, "Walk-forward 參數")
    add_table(doc,
        ["參數","預設值","說明"],
        [
            ["wf_enabled","false","是否啟用 walk-forward"],
            ["wf_train_years","2","訓練年數"],
            ["wf_test_years","1","測試年數"],
            ["wf_step_years","1","前進步長"],
        ], widths_cm=[5, 3, 9])

    add_h3(doc, "TWSE / 抓取參數")
    add_table(doc,
        ["參數","預設值","說明"],
        [
            ["timeout","30","HTTP timeout (秒)"],
            ["verify_ssl","false","是否驗證 SSL"],
            ["twse_retries","3","TWSE 重試次數"],
            ["twse_backoff","0.8","重試退避秒數"],
            ["twse_sleep","0.12","每次請求間隔秒數"],
        ], widths_cm=[5, 3, 9])

    add_h3(doc, "模擬買賣預設(會被組合覆蓋)")
    add_table(doc,
        ["參數","預設值","說明"],
        [
            ["topk","7","TopK 選股數"],
            ["hold_days","10","持有天數"],
            ["roundtrip_cost_pct","0.004","買賣來回成本(手續費 + 稅)"],
            ["stop_loss","-0.03","停損 -3%"],
            ["take_profit","0.08","停利 +8%"],
            ["exit_rsi","70","RSI 突破 70 出場"],
        ], widths_cm=[5, 3, 9])

    add_h2(doc, "3.6 資料流")
    add_code_block(doc,
"""[TWSE / TPEX / goodinfo]
        │
        ▼
[fetch_market.py]  ──→  [cache.py]  (cache/<code>_<months>m.xlsx)
        │
        ▼
[pipeline.py]  (run_pipeline: fetch + merge + 評分 + 強勢股過濾)
        │
        ├──────────────────────────┐
        ▼                          ▼
[export_excel.py]         [paper_engine.py]
(選股報表.xlsx)         (evaluate_*_portfolio_one_day)
                                  │
                                  ▼
                          [paper_trading.py]
                          (paper_holdings + paper_trades + paper_snapshots)
                                  │
                                  ▼
                          [paper_excel.py]
                          (模擬買賣報表.xlsx)

[PaperScheduler 每分鐘 tick] ──→ [paper_catchup.py] ──→ [paper_engine]
""")

    # 4. 介面設計
    add_h1(doc, "4. 介面設計")
    add_h2(doc, "4.1 主視窗")
    add_p(doc, "視窗大小:1024×640 起,自動 resize(V0.9.3 起保留)。")
    add_p(doc, "頂部 ttk.Notebook,6 個 Tab(V1.2.0 從 5 個 Tab 升上來):")

    add_h2(doc, "4.2 「模擬買賣」Tab 文字佈局圖")
    add_code_block(doc,
"""┌──────────────────────────────────────────────────────────────┐
│ 📅 模擬買賣                                                     │
├──────────────────────────────────────────────────────────────┤
│ ┌─ 我的組合(左下)────────────────────────────────────────┐   │
│ │ ID 名稱              策略     股票池 啟動日 狀態   累積報酬 │   │
│ │ 7  ETF買股             ai_meta  19    07-13 active +0.0%  │   │
│ │ 8  ETFvse逆勢買股     ai_meta  19    07-13 active +0.0%  │   │
│ │ 9  手選               ai_meta  5     07-13 active +0.0%  │   │
│ │ ...                                                    │   │
│ │ [+ 新增組合] [編輯] [啟動] [暫停] [刪除]               │   │
│ └────────────────────────────────────────────────────────┘   │
│                                                              │
│ ┌─ 手動設定(上方 tab 群組)─────────────────────────────┐    │
│ │ 名稱:[_____] Excel:[_____] 策略:[ai_meta ▾]             │    │
│ │ 總資金:[1,000,000] 持倉上限:[10]                        │    │
│ │ [+ 新增] [編輯] [刪除]                                  │    │
│ ├────────────────────────────────────────────────────────┤    │
│ │ Row 2:▶ 推進一天  ⏩ 補跑到今天  ☑ AI 模式              │    │
│ ├────────────────────────────────────────────────────────┤    │
│ │ Row 3:系統選股回購狀態                                  │    │
│ │  active / 衝刺:ai_meta / 啟動:2026-07-13 15:03:33       │    │
│ │  摘要: 初始 1,000,000 / 目前 1,000,000 / 累積報酬 +0.00% │   │
│ │  持倉 0/10 / 交易 0 / 勝率 0.0% (0/0)                  │    │
│ └────────────────────────────────────────────────────────┘    │
│                                                              │
│ [持倉] [買賣記錄] [權益曲線]                                  │
│ ┌────────────────────────────────────────────────────────┐    │
│ │ (對應 tab 的 Treeview)                                 │    │
│ └────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
""")

    add_h2(doc, "4.3 新增 / 編輯組合對話框")
    add_code_block(doc,
"""┌─ 新增模擬買賣組合 ───────────────────────────────────────┐
│                                                            │
│ 名稱:        [_____________________]                       │
│ 策略模式:    [ai_meta ▾]  / [manual ▾]                     │
│ 起始資金:    [1,000,000  ]                                 │
│ 持倉上限:    [10          ]                                │
│ TopK:        [7           ]                                │
│ 持有天數:    [10          ]                                │
│ 停損:        [-0.03       ]                                │
│ 停利:        [0.08        ]                                │
│                                                            │
│ 股票池: (多選清單 + 搜尋)                                  │
│ ┌──────────────────────────────────────┐                   │
│ │ ☑ 2330  台積電                       │                   │
│ │ ☑ 2317  鴻海                         │                   │
│ │ ☐ 2454  聯發科                       │                   │
│ │ ...                                  │                   │
│ └──────────────────────────────────────┘                   │
│ [全選] [全清] [+ 加入股票] [- 移除] [搜尋:________]        │
│                                                            │
│ [📥 採用回測參數] (從最近一次回測結果帶入)                  │
│                                                            │
│                          [確定]  [取消]                      │
└────────────────────────────────────────────────────────────┘
""")

    # 5. 開發時程
    add_h1(doc, "5. 開發時程")
    add_p(doc, "從 V0.9.4 到 V1.2.0-paper-trading,總計約 5 週(2026-06-08 → 2026-07-12)。")
    add_table(doc,
        ["階段","週次","項目"],
        [
            ["W1","2026-06-08~14","V0.9.3 HOTFIX → V0.9.4 買賣記錄"],
            ["W2","2026-06-15~21","V0.9.5 手動選股 + Preset → V0.9.5-etf 主動式 ETF Tab"],
            ["W3","2026-06-22~28","V0.9.5-goodinfo4+5 + vol=0 顯示 + 殖利率 3 位小數 + 半年殖利率"],
            ["W4","2026-06-29~07-05","V1.0 EPS YoY 補資料 → V1.1.0 重構 → V1.2.0 paper trading stage1-5"],
            ["W5","2026-07-06~12","V1.2.0 keyboard-toggle → v8-v26 fix2 連 19 版 hover → v26 fix3 消 console 噪音"],
            ["W14","2026-09-18","📘 V1.2.0 規格書 + 使用者手冊(本檔)"],
        ], widths_cm=[3, 4, 10])

    # 6. 測試計畫
    add_h1(doc, "6. 測試計畫")
    add_h2(doc, "6.1 pytest 覆蓋")
    add_p(doc, "本版有 95+ 個 pytest 測試檔,總計 743+ pass + 7 pre-existing fail。", bold=True)

    add_h3(doc, "模擬買賣相關(新增)")
    add_table(doc,
        ["測試檔","行數","守護項目"],
        [
            ["test_paper_trading.py","384","PaperPortfolio CRUD + 平均成本 + 損益計算"],
            ["test_paper_config.py","75","BacktestParamsMapping + 參數帶入"],
            ["test_paper_scheduler.py","140","PaperScheduler tick + 14:05 觸發"],
            ["test_paper_catchup_cache_refresh.py","204","Cache 過舊自動 refresh(session=None graceful skip)"],
            ["test_paper_catchup_history_months.py","188","history_months 多版本 cache 相容(12 / 60 / cfg)"],
        ], widths_cm=[6.5, 2, 8.5])

    add_h3(doc, "其他重要測試(既有)")
    add_table(doc,
        ["測試檔","行數","守護項目"],
        [
            ["test_keyboard_space_toggle.py","947","↑/↓ + Space 鍵盤導航(4 個 Treeview)"],
            ["test_no_double_score.py","85","評分不被呼叫兩次"],
            ["test_wf_docstring.py","128","Walk-forward docstring 正確"],
            ["test_cache_ttl.py","284","Cache TTL 分層"],
            ["test_etf_session_attr.py","147","ETF 模組不使用 self.session"],
            ["test_etf_closure.py","95","ETF closure fix"],
            ["test_click_sort.py","547","Treeview 點欄排序"],
        ], widths_cm=[6.5, 2, 8.5])

    add_h2(doc, "6.2 整合測試")
    add_bullet(doc, "啟動 GUI → 切到「模擬買賣」Tab → 新增組合 → 按「補跑到今天」→ 看到 BUY/SELL")
    add_bullet(doc, "模擬買賣 → 持倉 tab 顯示 → 買賣記錄 tab 顯示 → 權益曲線 tab 顯示")
    add_bullet(doc, "匯出 Excel → 開啟確認 5 sheet 與資料正確")
    add_bullet(doc, "關閉 GUI → 重啟 → 組合 / 持倉 / 交易資料仍存在(SQLite 持久化)")
    add_bullet(doc, "14:00 自動排程(修改系統時間測試)")

    add_h2(doc, "6.3 不回歸")
    add_bullet(doc, "V0.9.3 / V0.9.4 既有功能:選股 / 回測 / 買賣記錄 → 不破壞")
    add_bullet(doc, "V0.9.5 手動選股 Tab + Preset → 不破壞")
    add_bullet(doc, "V0.9.5-etf 主動式 ETF Tab → 不破壞")
    add_bullet(doc, "V0.9.5-vol-no-divide 系統選股「重新抓股價」→ 不破壞")
    add_bullet(doc, "V1.0 EPS 歷史庫自動補 → 不破壞")

    add_h2(doc, "6.4 已知問題")
    add_h3(doc, "🟡 Hover 殘留(V22-V26 fix2 已試,仍未根治)")
    add_p(doc, "v8 → v26 fix2 連 19 版 debug,最終決定 v26 fix3 commit 後暫停。")
    add_p(doc, "行為:mouse/key 切換 hover 不會自動消舊的高亮(舊的仍亮黃色)。")
    add_p(doc, "影響:純視覺問題,主要功能(選股、回測、模擬買賣)正常運作。")
    add_p(doc, "暫行解:用 key 導航就別混 mouse、用 mouse 點別處就解。", italic=True)

    add_h3(doc, "🟡 StockTool 主類別無 self.session 屬性")
    add_p(doc, "在 PaperScheduler / 補跑按鈕內呼叫 catch_up 時,session 永遠是 None。")
    add_p(doc, "影響:cache 過舊時無法自動 refresh → 跳過該日 → 看不到 BUY/SELL。")
    add_p(doc, "暫行解:手動按「▶ 推進一天」或 GUI 啟動後點「重新抓股價」讓 cache 補新。", italic=True)

    add_h3(doc, "🟡 PaperScheduler App-level only")
    add_p(doc, "App 關閉期間不排程 → 2 個月沒開就漏 60 天。")
    add_p(doc, "暫行解:下次打開 App 按「⏩ 補跑到今天」一次補齊。", italic=True)

    add_h3(doc, "🟢 DEBUG 訊息(已消大部分)")
    add_p(doc, "V26 fix3 後 _v18_log() 預設改寫檔不 print、消 25 個 console 噪音。")
    add_p(doc, "Debug 時設 self._v18_debug_console = True 可回流 console。", italic=True)

    # 文件尾
    doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("— 文件結束 —"); set_zh_font(r, size=10, color=RGBColor(0x99,0x99,0x99))

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    doc.save(OUT_PATH)
    print(f"✅ 規格書已產出:{OUT_PATH}")
    print(f"   檔案大小:{os.path.getsize(OUT_PATH):,} bytes")


if __name__ == "__main__":
    build()
