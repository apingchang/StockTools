"""
V0.9.4 規格書產生器
===================
執行：python3 specs/gen_v094_spec.py
產出：documents/V0.9.4_規格書.docx

設計原則：
- 不直接編輯 .docx（會破樣式）
- 改這個 .py 重新跑一次
- 章節、表格、程式碼統一在這裡管理
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
    "documents", "V0.9.4_規格書.docx"
)

# ──────────────── 樣式 helper ────────────────
def set_zh_font(run, size=10.5, bold=False, color=None):
    """設定中文字型（標楷體）、英文 Consolas、字級"""
    run.font.name = "Consolas"
    run.font.size = Pt(size)
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
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after = Pt(8)
    r = p.add_run(text)
    set_zh_font(r, size=18, bold=True, color=RGBColor(0x1F, 0x3A, 0x5F))

def add_h2(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run(text)
    set_zh_font(r, size=14, bold=True, color=RGBColor(0x2E, 0x5A, 0x88))

def add_h3(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(text)
    set_zh_font(r, size=12, bold=True, color=RGBColor(0x44, 0x44, 0x44))

def add_p(doc, text, bold=False, italic=False, code=False):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(text)
    set_zh_font(r, size=10.5, bold=bold)

def add_bullet(doc, text, level=0):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.left_indent = Cm(0.5 + 0.5 * level)
    r = p.runs[0] if p.runs else p.add_run("")
    r.text = ""
    r2 = p.add_run(text)
    set_zh_font(r2, size=10.5)

def add_code_block(doc, code: str):
    """等寬字 + 灰底，模擬程式碼區塊"""
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    cell = tbl.rows[0].cells[0]
    # 灰底
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), "F0F0F0")
    tcPr.append(shd)
    cell.text = ""
    for line in code.split("\n"):
        p = cell.add_paragraph()
        r = p.add_run(line if line else " ")
        set_zh_font(r, size=9.5)
    # 拿掉第一個空 paragraph
    cell._tc.remove(cell.paragraphs[0]._p)
    # 邊框
    tblPr = tbl._element.find(qn("w:tblPr"))
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right"):
        b = OxmlElement(f"w:{edge}")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), "4")
        b.set(qn("w:color"), "CCCCCC")
        borders.append(b)
    tblPr.append(borders)

def add_table(doc, headers: list, rows: list, widths_cm: list = None):
    tbl = doc.add_table(rows=1 + len(rows), cols=len(headers))
    tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    # header
    for i, h in enumerate(headers):
        cell = tbl.rows[0].cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        r = p.add_run(h)
        set_zh_font(r, size=10.5, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
        tcPr = cell._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), "2E5A88")
        tcPr.append(shd)
    # body
    for ri, row in enumerate(rows):
        for ci, v in enumerate(row):
            cell = tbl.rows[1 + ri].cells[ci]
            cell.text = ""
            p = cell.paragraphs[0]
            r = p.add_run(str(v))
            set_zh_font(r, size=10)
            if ri % 2 == 1:
                tcPr = cell._tc.get_or_add_tcPr()
                shd = OxmlElement("w:shd")
                shd.set(qn("w:val"), "clear")
                shd.set(qn("w:color"), "auto")
                shd.set(qn("w:fill"), "F5F8FC")
                tcPr.append(shd)
    if widths_cm:
        for i, w in enumerate(widths_cm):
            for row in tbl.rows:
                row.cells[i].width = Cm(w)

# ──────────────── 內容 ────────────────
def build():
    doc = Document()
    # 頁面設定
    section = doc.sections[0]
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(2.2)

    # 封面
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("StockTool / 股神")
    set_zh_font(r, size=22, bold=True, color=RGBColor(0x1F, 0x3A, 0x5F))

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("V0.9.4 規格書")
    set_zh_font(r, size=26, bold=True, color=RGBColor(0x2E, 0x5A, 0x88))

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(40)
    r = p.add_run("台灣股市量化選股系統")
    set_zh_font(r, size=14, color=RGBColor(0x66, 0x66, 0x66))

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(20)
    now = datetime.now().strftime("%Y-%m-%d")
    r = p.add_run(f"發行日期：{now}    版本：V0.9.4    作者：William Chang")
    set_zh_font(r, size=11, color=RGBColor(0x66, 0x66, 0x66))

    doc.add_page_break()

    # ───── 1. 概述 ─────
    add_h1(doc, "1. 概述")
    add_h2(doc, "1.1 版本歷程")
    add_table(doc,
        ["版本", "日期", "重點"],
        [
            ["V0.9.3-HOTFIX", "2026-06-08", "修正 EPS YoY / Score 無限值 / Top10 全為 ETF 等問題"],
            ["V0.9.4", "2026-06-10", "新增「買賣記錄」模組：SQLite + Tab 化 GUI + Excel 匯出"],
        ],
        widths_cm=[3.5, 3, 10]
    )

    add_h2(doc, "1.2 改版動機")
    add_p(doc, "V0.9.3 之前 StockTool 只能「選股 + 回測」，沒有真實持倉追蹤。")
    add_p(doc, "使用者買入後要自己用 Excel 記，沒辦法在程式裡看到「未實現損益」「已實現損益」「總報酬率」。")
    add_p(doc, "V0.9.4 把「選股 → 買入 → 持倉追蹤 → 賣出 → 績效檢視」打通成完整閉環。")

    add_h2(doc, "1.3 範圍與限制")
    add_bullet(doc, "範圍：買入 / 賣出記錄、持倉清單、即時損益計算、Excel 匯出")
    add_bullet(doc, "不做：自動下單（無券商 API 串接）、即時報價（成本價由使用者手動維護）")
    add_bullet(doc, "不做：多帳戶、組合再平衡、稅負計算")
    add_bullet(doc, "選股演算法沿用 V0.9.3，本版不動")
    add_bullet(doc, "排程方式：使用者手動執行 StockTool.py（每日 08:50 跑一次）")

    # ───── 2. 功能需求 ─────
    add_h1(doc, "2. 功能需求")
    add_h2(doc, "2.1 買賣記錄資料模型")
    add_p(doc, "採用平均成本法（FIFO/LIFO 不實作）。一筆買入或賣出就是一筆交易紀錄，")
    add_p(doc, "同一檔股票可以有多筆買入，平均成本會自動加權計算。")

    add_h3(doc, "交易紀錄欄位")
    add_table(doc,
        ["欄位", "型態", "說明"],
        [
            ["id", "INTEGER PK", "自動編號"],
            ["stock_id", "TEXT", "股票代號（例如 2330）"],
            ["stock_name", "TEXT", "股票名稱（選填，手動輸入或帶入）"],
            ["action", "TEXT", "BUY / SELL"],
            ["trade_date", "TEXT", "YYYY-MM-DD"],
            ["shares", "REAL", "股數（支援零股，小數）"],
            ["price", "REAL", "成交價（單一股）"],
            ["fee", "REAL", "手續費（選填，預設 0）"],
            ["note", "TEXT", "備註（選填）"],
            ["created_at", "TEXT", "建立時間（自動）"],
        ],
        widths_cm=[3, 3, 11]
    )

    add_h3(doc, "持倉計算公式（平均成本法）")
    add_p(doc, "對每檔股票統計所有 BUY 與 SELL：", bold=True)
    add_code_block(doc,
"""avg_cost = SUM(buy_shares * (buy_price + buy_fee/buy_shares)) / SUM(buy_shares)
         = 總買入成本(含手續費) / 總買入股數

current_shares = SUM(buy_shares) - SUM(sell_shares)

realized_pl = SUM(sell_shares * (sell_price - avg_cost_at_sell_time))
            = 賣出價 × 賣出股數 - 對應的均價成本

unrealized_pl = current_shares * (current_price - avg_cost)
              = 持有股數 × (目前市價 - 平均成本)
              ※ current_price 由使用者手動更新（不抓即時報價）
"""
    )

    add_h2(doc, "2.2 GUI 操作流程")
    add_h3(doc, "主視窗 Tab 化")
    add_p(doc, "V0.9.3 的「單一 scrollable frame」改為 Notebook（Tkinter 標準 Tab 控件）：")
    add_bullet(doc, "Tab 1：⚙️ 策略參數（V0.9.3 全部內容）")
    add_bullet(doc, "Tab 2：📒 買賣記錄（本版新增）")

    add_h3(doc, "「買賣記錄」Tab 子區塊")
    add_bullet(doc, "📊 持倉總覽：總成本、總市值、未實現損益、已實現損益、總報酬率（5 個 LabelFrame 上方）")
    add_bullet(doc, "🌳 持倉明細：Treeview 列出每檔股票（代號/名稱/股數/均價/現價/未實現損益）")
    add_bullet(doc, "📋 交易明細：Treeview 列出所有買賣歷史（可依股票 / 日期篩選）")
    add_bullet(doc, "🔘 操作按鈕：新增買入 / 新增賣出 / 更新現價 / 刪除紀錄 / 匯出 Excel / 重新整理")

    add_h3(doc, "對話框設計")
    add_p(doc, "「新增買入」對話框欄位：")
    add_bullet(doc, "股票代號（必填，自動帶入最新持倉）")
    add_bullet(doc, "股票名稱（選填，記住上次輸入）")
    add_bullet(doc, "買入日期（預設今天，可改）")
    add_bullet(doc, "買入股數（必填，支援零股）")
    add_bullet(doc, "買入價格（必填）")
    add_bullet(doc, "手續費（選填，預設 0）")
    add_bullet(doc, "備註（選填）")
    add_p(doc, "「新增賣出」對話框類似，但多了「從哪一筆買入扣」資訊（平均成本法下不指定，自動算）")

    add_h2(doc, "2.3 匯出 Excel 規格")
    add_p(doc, "按「匯出 Excel」按鈕，產出 portfolio_YYYYMMDD_HHMM.xlsx，內含 4 個 sheet：")
    add_table(doc,
        ["Sheet 名稱", "內容"],
        [
            ["持倉總覽", "總成本、總市值、未實現損益、已實現損益、總報酬率"],
            ["持倉明細", "每檔股票一列：代號、名稱、股數、平均成本、現價、未實現損益、報酬率%"],
            ["交易明細", "所有買賣紀錄：日期、代號、名稱、買/賣、股數、價格、手續費、備註"],
            ["匯出資訊", "匯出時間、總交易筆數、資料區間、StockTool 版本"],
        ],
        widths_cm=[4, 13]
    )
    add_p(doc, "樣式：表頭藍底白字、數字千分位、負數紅字、百分比格式（沿用 V0.9.3 既有風格）")

    # ───── 3. 技術架構 ─────
    add_h1(doc, "3. 技術架構")
    add_h2(doc, "3.1 檔案結構")
    add_code_block(doc,
"""StockTools/                              ← GitHub repo
├── source/
│   ├── StockTool.py                      ← 主程式（2363 行，V0.9.3 基礎）
│   └── portfolio.py                      ← 新增：PortfolioDB 模組
├── documents/
│   ├── V0.9.3_規格書.docx                 ← 補建
│   ├── V0.9.4_規格書.docx                 ← 本檔
│   ├── 使用者手冊_v0.9.4.docx              ← 補建
│   └── ...
├── specs/
│   └── gen_v094_spec.py                  ← 本規格書產生器
├── tests/
│   └── test_portfolio.py                 ← 新增：portfolio 單元測試
├── portfolio.db                          ← SQLite（執行時自動建立，git 忽略）
├── .gitignore                            ← 新增
└── .gitattributes                        ← *.docx / *.xlsx 走 LFS
"""
    )

    add_h2(doc, "3.2 模組分工")
    add_table(doc,
        ["模組", "職責", "行數預估"],
        [
            ["portfolio.py", "PortfolioDB class：CRUD + 計算 + 匯出", "600-800"],
            ["StockTool.py（修改）", "StrategyGUI 加 Tab 框架 + 訊號接線", "+200"],
            ["test_portfolio.py", "pytest 單元測試", "150-200"],
        ],
        widths_cm=[4, 9, 4]
    )

    add_h2(doc, "3.3 SQLite Schema")
    add_code_block(doc,
"""CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id    TEXT    NOT NULL,
    stock_name  TEXT,
    action      TEXT    NOT NULL CHECK(action IN ('BUY','SELL')),
    trade_date  TEXT    NOT NULL,         -- YYYY-MM-DD
    shares      REAL    NOT NULL CHECK(shares > 0),
    price       REAL    NOT NULL CHECK(price > 0),
    fee         REAL    NOT NULL DEFAULT 0,
    note        TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_tx_stock   ON transactions(stock_id);
CREATE INDEX IF NOT EXISTS idx_tx_date    ON transactions(trade_date);
CREATE INDEX IF NOT EXISTS idx_tx_action  ON transactions(action);
"""
    )

    # ───── 4. 介面設計 ─────
    add_h1(doc, "4. 介面設計")
    add_h2(doc, "4.1 主視窗（Tab 化）")
    add_p(doc, "視窗大小：1024×640（沿用 V0.9.3）")
    add_p(doc, "頂部加 ttk.Notebook，2 個 Tab：")
    add_bullet(doc, "Tab 1「⚙️ 策略參數」：完整保留 V0.9.3 所有 LabelFrame，只是不再 scroll，改用 Tab 內 scroll")
    add_bullet(doc, "Tab 2「📒 買賣記錄」：本版新增，內容見 4.2")

    add_h2(doc, "4.2 「買賣記錄」Tab 文字佈局圖")
    add_code_block(doc,
"""┌────────────────────────────────────────────────────────────┐
│ 📒 買賣記錄                                                   │
├────────────────────────────────────────────────────────────┤
│ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌────────┐│
│ │總成本   │ │總市值   │ │未實現   │ │已實現   │ │總報酬率││
│ │ 500,000 │ │ 540,000 │ │ +40,000 │ │ +20,000 │ │+12.0% ││
│ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └────────┘│
│                                                            │
│ ┌─ 持倉明細 ─────────────────────────────────────────────┐ │
│ │ 代號  名稱    股數     均價     現價    未實現損益  報酬│ │
│ │ 2330  台積電  1000    580.0    620.0   +40,000  +6.9%│ │
│ │ ...                                                     │ │
│ └────────────────────────────────────────────────────────┘ │
│                                                            │
│ ┌─ 交易明細 ─────────────────────────────────────────────┐ │
│ │ 日期       代號  名稱  買/賣  股數   價格    手續費   │ │
│ │ 2026-06-01 2330  TSMC  BUY   500   580    145      │ │
│ │ 2026-06-15 2330  TSMC  BUY   500   600    150      │ │
│ │ ...                                                     │ │
│ └────────────────────────────────────────────────────────┘ │
│                                                            │
│ [+ 新增買入] [+ 新增賣出] [更新現價] [刪除] [匯出 Excel]    │
└────────────────────────────────────────────────────────────┘
"""
    )

    add_h2(doc, "4.3 對話框設計")
    add_p(doc, "「新增買入」對話框 Toplevel：")
    add_code_block(doc,
"""┌─ 新增買入 ─────────────────────┐
│ 股票代號:  [2330           ]   │
│ 股票名稱:  [台積電         ]   │
│ 買入日期:  [2026-06-10     ]   │
│ 買入股數:  [1000           ]   │
│ 買入價格:  [580            ]   │
│ 手續費:    [145            ]   │
│ 備註:      [首次建倉       ]   │
│                                 │
│         [確定]    [取消]         │
└─────────────────────────────────┘
"""
    )

    # ───── 5. 開發時程 ─────
    add_h1(doc, "5. 開發時程")
    add_table(doc,
        ["階段", "項目", "預計時間"],
        [
            ["Phase 1", "portfolio.py 模組（CRUD + 計算 + 匯出）", "0.5 天"],
            ["Phase 2", "StockTool.py 加 Tab + 接線（不動評分邏輯）", "0.5 天"],
            ["Phase 3", "test_portfolio.py 單元測試", "0.5 天"],
            ["Phase 4", "GUI 互調 + bug 修正", "0.5 天"],
            ["Phase 5", "規格書 + 使用者手冊更新", "0.5 天"],
            ["合計", "—", "2.5 天"],
        ],
        widths_cm=[3, 9, 3]
    )

    # ───── 6. 測試計畫 ─────
    add_h1(doc, "6. 測試計畫")
    add_h2(doc, "6.1 單元測試（test_portfolio.py）")
    add_bullet(doc, "新增買入 → DB 寫入正確")
    add_bullet(doc, "新增賣出 → 庫存正確扣減")
    add_bullet(doc, "平均成本計算（多次買入加權）")
    add_bullet(doc, "未實現損益（手動現價）")
    add_bullet(doc, "已實現損益（多次賣出）")
    add_bullet(doc, "Excel 匯出 4 sheet 結構正確")

    add_h2(doc, "6.2 整合測試")
    add_bullet(doc, "啟動 GUI → 切到「買賣記錄」Tab → 跑一輪新增買入 → 持倉明細即時更新")
    add_bullet(doc, "匯出 Excel → 開啟確認 4 sheet 與資料正確")
    add_bullet(doc, "關閉 GUI → 重啟 → 持倉資料仍存在（SQLite 持久化）")

    add_h2(doc, "6.3 不回歸")
    add_bullet(doc, "V0.9.3 「執行策略」按鈕按下，選股報表產出正常（不破壞既有功能）")
    add_bullet(doc, "Config 載入 / 儲存 / 重置 三按鈕功能正常")

    # ───── 文件尾 ─────
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("— 文件結束 —")
    set_zh_font(r, size=10, color=RGBColor(0x99, 0x99, 0x99))

    # 儲存
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    doc.save(OUT_PATH)
    print(f"✅ 規格書已產出：{OUT_PATH}")
    print(f"   檔案大小：{os.path.getsize(OUT_PATH):,} bytes")

if __name__ == "__main__":
    build()
