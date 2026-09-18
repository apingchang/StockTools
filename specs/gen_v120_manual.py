"""
V1.2.0-paper-trading 使用者手冊產生器
======================================
執行：python3 specs/gen_v120_manual.py
產出：documents/股神_StockTool_使用者手冊_v1.2.0-paper-trading.docx

與 V0.9.5-etf-fix 使用者手冊的差異：
- 章節四從「四大 Tab」改為「六大 Tab」（多了「模擬買賣」Tab）
- 新增章節「模擬買賣完全指南」（組合管理 / 補跑 / 排程 / 權益曲線）
- 章節六報表輸出加 5 sheet 模擬買賣報表說明
- 章節八常見錯誤加「為什麼 BUY/SELL 都是 0」
- 章節十已知問題加 hover 殘留 + scheduler App-level only
- 章節十二版本紀錄延伸到 v1.2.0
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
    "documents",
    "股神_StockTool_使用者手冊_v1.2.0-paper-trading.docx"
)

# ──── helpers（與 gen_v094_spec.py / gen_v120_spec.py 一致）────
def set_zh_font(run, size=10.5, bold=False, italic=False, color=None):
    run.font.name = "Consolas"
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
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

def add_h4(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6); p.paragraph_format.space_after = Pt(3)
    r = p.add_run(text)
    set_zh_font(r, size=11, bold=True, color=RGBColor(0x66,0x66,0x66))

def add_p(doc, text, bold=False, italic=False):
    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(4)
    r = p.add_run(text); set_zh_font(r, size=10.5, bold=bold, italic=italic)

def add_bullet(doc, text, level=0):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.left_indent = Cm(0.5 + 0.5 * level)
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
    for txt, sz, color in [
        ("StockTool / 股神", 22, RGBColor(0x1F,0x3A,0x5F)),
        ("使用者手冊 v1.2.0-paper-trading", 26, RGBColor(0x2E,0x5A,0x88)),
        ("台灣股市量化選股 + 模擬買賣組合管理系統", 14, RGBColor(0x66,0x66,0x66)),
    ]:
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(txt); set_zh_font(r, size=sz, color=color)

    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(20)
    now = datetime.now().strftime("%Y-%m-%d")
    r = p.add_run(f"發行日期:{now}    版本:v1.2.0-paper-trading-kb-focus-v26    作者:William Chang")
    set_zh_font(r, size=11, color=RGBColor(0x66,0x66,0x66))

    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Window title:StockTool v1.2.0-paper-trading-kb-focus-v26 (Multi-Factor + Top10 Backtest + Portfolio + ETF + Paper Trading + goodinfo)")
    set_zh_font(r, size=9, color=RGBColor(0x88,0x88,0x88))

    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("前版手冊:V0.9.5-etf-fix(2026-06-19)")
    set_zh_font(r, size=10, color=RGBColor(0x88,0x88,0x88))

    doc.add_page_break()

    # 目錄
    add_h1(doc, "目錄")
    toc = [
        "一、這支在做什麼",
        "二、安裝",
        "　2.1 Python 環境",
        "　2.2 抓程式碼",
        "　2.3 SSL 警告",
        "三、啟動",
        "　3.1 圖形介面(推薦)",
        "　3.2 第一次啟動會建立",
        "四、GUI 操作(六大 Tab)",
        "　4.1 ⚙️ 策略參數 Tab — 基本參數",
        "　4.2 ⚙️ 策略參數 Tab — 評分系統",
        "　4.3 ⚙️ 策略參數 Tab — 技術指標",
        "　4.4 ⚙️ 策略參數 Tab — 回測設定",
        "　4.5 ⚙️ 策略參數 Tab — 模式切換",
        "　4.6 🔍 手動選股 Tab",
        "　4.7 📊 主動式 ETF Tab",
        "　4.8 📒 買賣記錄 Tab",
        "　4.9 📈 系統選股 Tab",
        "　4.10 📊 回測模擬 Tab",
        "　4.11 📅 模擬買賣 Tab ⭐新",
        "五、自選股清單模式(use_excel_stock_list)",
        "六、報表輸出",
        "　6.1 選股報表工作表",
        "　6.2 模擬買賣報表工作表 ⭐新",
        "　6.3 報表常用欄位速查",
        "七、執行流程詳解",
        "　7.1 第一次跑會比較慢",
        "　7.2 模擬買賣補跑流程 ⭐新",
        "八、常見錯誤對照",
        "　8.1 🆘 為什麼 BUY/SELL 都是 0 ⭐新",
        "九、快取管理",
        "　9.1 模擬買賣的 cache 過舊處理 ⭐新",
        "十、已知問題與限制",
        "　10.1 🟡 Hover 殘留(v22-v26 fix2 已試)",
        "　10.2 🟡 Scheduler App-level only",
        "　10.3 🟡 StockTool 無 self.session",
        "　10.4 🟡 EPS YoY 年初失效(已緩解)",
        "　10.5 🟢 Walk-forward 不做樣本外驗證",
        "　10.6 🟢 DEBUG 訊息太多(已消大部分)",
        "十一、進階:手動跑回測(不開 GUI)",
        "　11.1 模擬買賣單獨執行 ⭐新",
        "十二、版本紀錄",
        "十三、檔案結構",
        "十四、技術支援",
    ]
    for line in toc:
        p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(2)
        r = p.add_run(line); set_zh_font(r, size=10.5)

    doc.add_page_break()

    # 一、這支在做什麼
    add_h1(doc, "一、這支在做什麼")
    add_p(doc, "StockTool(股神)是一支給台股投資人用的「量化選股 + 模擬買賣」工具。")
    add_p(doc, "從「找股票」到「驗證策略」一條龍:")
    add_bullet(doc, "📊 選股:系統選股 / 手動選股 / ETF / 回測 — 四種方式挑股票")
    add_bullet(doc, "💰 買賣記錄:手動新增買入/賣出 → 自動算平均成本、即時損益")
    add_bullet(doc, "📅 模擬買賣(本版新):組合管理 + 14:00 自動排程 + 補跑到今天 — 真的用歷史價跑策略驗證")
    add_bullet(doc, "📁 Excel 報表:選股結果、組合持倉、交易明細、權益曲線 — 全部匯出")
    add_p(doc, "整個套件 100% 本機跑、不上雲、不抓個資、不接券商 API。")
    add_p(doc, "本版 v1.2.0-paper-trading-kb-focus-v26 重點新增「模擬買賣組合管理」(paper trading)Tab。", bold=True)

    # 二、安裝
    add_h1(doc, "二、安裝")
    add_h2(doc, "2.1 Python 環境")
    add_p(doc, "確認 Python ≥ 3.8(本版測過 3.12):")
    add_code_block(doc,
"""$ python --version
Python 3.12.3

$ pip install -r requirements.txt
# 主要套件:pandas / requests / openpyxl / numpy / python-docx / lxml""")

    add_h2(doc, "2.2 抓程式碼")
    add_p(doc, "從 GitHub clone:")
    add_code_block(doc,
"""$ git clone https://github.com/yourname/StockTools.git
$ cd StockTools
$ python -m venv .venv
$ source .venv/bin/activate   # Linux/Mac
# .venv\\Scripts\\activate    # Windows
$ pip install -r requirements.txt""")

    add_h2(doc, "2.3 SSL 警告")
    add_p(doc, "TWSE / TPEX 某些 endpoint SSL 憑證過期,預設 verify_ssl=false 跳過驗證。")
    add_p(doc, "若你不放心,可在 stocktool_config.json 把 verify_ssl 改 true,但可能要忍受偶爾抓不到。", italic=True)

    # 三、啟動
    add_h1(doc, "三、啟動")
    add_h2(doc, "3.1 圖形介面(推薦)")
    add_code_block(doc, "$ python source/StockTool.py")
    add_p(doc, "啟動後 Window title:")
    add_code_block(doc,
"""StockTool v1.2.0-paper-trading-kb-focus-v26
(Multi-Factor + Top10 Backtest + Portfolio + ETF + Paper Trading + goodinfo)""")
    add_p(doc, "title 內含版本字串,可用來確認你跑的是哪一版。", italic=True)

    add_h2(doc, "3.2 第一次啟動會建立")
    add_bullet(doc, "portfolio.db — SQLite,放買賣記錄 + 模擬買賣組合 / 持倉 / 交易 / 快照")
    add_bullet(doc, "stocktool_config.json — 設定檔(評分權重、回測參數、抓取參數…)")
    add_bullet(doc, "cache/history/ — 個股歷史價 xlsx(*_60m.xlsx)")

    # 四、GUI 操作(六大 Tab)
    add_h1(doc, "四、GUI 操作(六大 Tab)")
    add_p(doc, "從 V0.9.3 的 2 個 Tab → V0.9.5-etf-fix 的 4 個 Tab → 本版 V1.2.0-paper-trading 的 6 個 Tab。", bold=True)
    add_table(doc,
        ["#","Tab","版本","主要功能"],
        [
            ["1","⚙️ 策略參數","V0.9.3+","全部選股 / 回測 / 評分參數"],
            ["2","🔍 手動選股","V0.9.5+","Preset + 條件篩選 + Excel"],
            ["3","📊 主動式 ETF","V0.9.5-etf+","ETF 19 檔清單 + 持股抓取"],
            ["4","📈 系統選股","V0.9.5-vol-no-divide+","多因子評分 + TopN"],
            ["5","📊 回測模擬","V0.9.2+","Top10 基本面回測"],
            ["6","📅 模擬買賣","V1.2.0+","組合管理 + 補跑 + 排程 ⭐"],
        ], widths_cm=[1.5, 3.5, 3, 9])

    add_h2(doc, "4.1 ⚙️ 策略參數 Tab — 基本參數")
    add_p(doc, "StockTool 參數全在這裡調,改完按「儲存設定」才會生效。")
    add_table(doc,
        ["區塊","參數","預設","說明"],
        [
            ["基本","top_n_for_tech","60","技術面 Top N(選到第幾名做技術分析)"],
            ["基本","history_months","60","歷史月線抓取月數(60 = 5 年)"],
            ["基本","timeout","30","HTTP 抓取 timeout(秒)"],
            ["基本","verify_ssl","false","是否驗證 SSL(關掉可避 TWSE 過期憑證)"],
            ["清單","use_excel_stock_list","false","是否從 Excel 讀股票清單(見第五章)"],
            ["清單","excel_stock_file","stock_list.xlsx","Excel 檔名"],
        ], widths_cm=[2.5, 4.5, 2, 8])

    add_h2(doc, "4.2 ⚙️ 策略參數 Tab — 評分系統")
    add_h3(doc, "多因子評分(預設,進階)")
    add_p(doc, "用 5 個 z-score 加權打分:")
    add_table(doc,
        ["因子","權重","說明"],
        [
            ["factor_weight_mom1","0.15","1 月動能(過去 1 個月報酬)"],
            ["factor_weight_mom3","0.15","3 月動能"],
            ["factor_weight_mom6","0.20","6 月動能"],
            ["factor_weight_rev","0.25","營收 YoY"],
            ["factor_weight_eps","0.25","EPS YoY"],
        ], widths_cm=[5, 2, 10])

    add_h3(doc, "簡易評分(可調權重 + 門檻)")
    add_table(doc,
        ["參數","預設","說明"],
        [
            ["simple_score_weight_rev","35.0","營收權重"],
            ["simple_score_weight_eps","35.0","EPS 權重"],
            ["simple_score_weight_div","20.0","殖利率權重"],
            ["simple_score_weight_pe","-5.0","PE 權重(負向)"],
            ["simple_min_rev_yoy","-999.0","最低營收 YoY 門檻"],
            ["simple_min_eps_yoy","-999.0","最低 EPS YoY 門檻"],
            ["simple_min_eps","-999.0","最低 EPS 門檻"],
            ["simple_max_pe","999.0","最高 PE 門檻"],
        ], widths_cm=[5, 3, 9])

    add_h2(doc, "4.3 ⚙️ 策略參數 Tab — 技術指標")
    add_table(doc,
        ["參數","預設","說明"],
        [
            ["rsi_oversold","40","RSI 超跌門檻(低於此視為超跌)"],
            ["oversold_lookback","10","回看幾天內出現超跌"],
            ["rsi_recover","40","RSI 回升門檻"],
            ["rsi_aggressive","45","積極版 RSI 回升門檻"],
            ["use_aggressive_signal","true","是否用積極版訊號"],
            ["require_trend_filter","true","是否要求站穩 MA20"],
            ["ma_slope_days","3","MA 斜率計算天數"],
            ["ma20_tolerance","0.01","站穩 MA20 容差(1%)"],
            ["require_volume_filter","true","是否過濾成交量"],
        ], widths_cm=[5, 2, 10])

    add_h2(doc, "4.4 ⚙️ 策略參數 Tab — 回測設定")
    add_table(doc,
        ["參數","預設","說明"],
        [
            ["topk","7","TopK 選股數"],
            ["hold_days","10","持有天數"],
            ["roundtrip_cost_pct","0.004","買賣來回成本(0.4%)"],
            ["stop_loss","-0.03","停損 -3%"],
            ["take_profit","0.08","停利 +8%"],
            ["exit_rsi","70","RSI 突破 70 出場"],
        ], widths_cm=[5, 2, 10])

    add_h2(doc, "4.5 ⚙️ 策略參數 Tab — 模式切換")
    add_bullet(doc, "use_enhanced_score — true 用多因子、false 用簡易")
    add_bullet(doc, "use_top10_backtest — true 跑 Top10 回測")
    add_bullet(doc, "excel_force_buy — true 把 Excel 清單全部強制設為買點")
    add_bullet(doc, "use_mtf_confirmation — true 多時框確認")
    add_bullet(doc, "use_divergence_detection — true 背離偵測")
    add_bullet(doc, "use_gate — true 啟用閘門(需 min_rev_yoy > 0、min_eps_yoy > 0)")

    add_h2(doc, "4.6 🔍 手動選股 Tab(v0.9.5 新增)")
    add_h4(doc, "左面板:篩選條件 + Preset + 按鈕")
    add_bullet(doc, "Preset 下拉選單:可存常用的篩選條件組合")
    add_bullet(doc, "「💾 存 Preset」把當前條件存成新 preset")
    add_bullet(doc, "「📂 讀 Preset」載入 preset")
    add_bullet(doc, "「▶ 執行篩選」跑出右側 Treeview 結果")
    add_bullet(doc, "「📊 匯出 Excel」把 Treeview 結果匯出")

    add_h4(doc, "右面板:Treeview 結果(14 欄)")
    add_bullet(doc, "代號 / 名稱 / 收盤 / 漲跌 / 漲跌% / 成交量 / 營收 YoY / EPS YoY / PE / 殖利率 / 技術買點 / 評分 / 趨勢 / 勾選")
    add_p(doc, "[截圖位置:手動選股 Tab — 左側篩選面板 + 右側 14 欄 Treeview]", italic=True)

    add_h4(doc, "Treeview 互動")
    add_bullet(doc, "點欄標題 → 該欄排序(再點反向)")
    add_bullet(doc, "↑/↓ 鍵移動 highlight row")
    add_bullet(doc, "Space 鍵 toggle 該列勾選(可連續勾多檔)")
    add_bullet(doc, "勾完按「📊 匯出 Excel」只匯出有勾選的")

    add_h2(doc, "4.7 📊 主動式 ETF Tab(v0.9.5-etf 新增)")
    add_h4(doc, "資料來源")
    add_bullet(doc, "TWSE API + etfinfo.tw 雙來源驗證")
    add_bullet(doc, "19 檔 domestic ETF × 前 10 大持股")
    add_bullet(doc, "去重後約 100 檔個股")

    add_h4(doc, "左面板:篩選 + 按鈕")
    add_bullet(doc, "「🔄 重新抓 ETF 持股」按鈕 — 從 cache 讀(若過期會 refresh)")
    add_bullet(doc, "「▶ 執行篩選」按鈕")
    add_bullet(doc, "「📊 匯出 Excel」按鈕")

    add_h4(doc, "右面板:Treeview(5 欄)")
    add_bullet(doc, "代號 / 名稱 / ETF 名稱 / 持股權重 / 收盤價")
    add_p(doc, "[截圖位置:主動式 ETF Tab — ETF 持股清單]", italic=True)

    add_h2(doc, "4.8 📒 買賣記錄 Tab(v0.9.4 新增)")
    add_h4(doc, "支援功能")
    add_bullet(doc, "📊 持倉總覽:總成本、總市值、未實現損益、已實現損益、總報酬率(5 個 LabelFrame 上方)")
    add_bullet(doc, "🌳 持倉明細 Treeview:代號/名稱/股數/均價/現價/未實現損益")
    add_bullet(doc, "📋 交易明細 Treeview:可依股票 / 日期篩選")
    add_bullet(doc, "🔘 操作按鈕:+ 新增買入 / + 新增賣出 / 更新現價 / 刪除 / 匯出 Excel / 重新整理")
    add_bullet(doc, "平均成本法:多次買入自動加權、手續費併入成本")
    add_bullet(doc, "開盤 30 秒 refresh(V0.9.5 加)")
    add_p(doc, "[截圖位置:買賣記錄 Tab — 持倉總覽 + 持倉明細 + 交易明細]", italic=True)

    add_h2(doc, "4.9 📈 系統選股 Tab")
    add_h4(doc, "主要功能")
    add_bullet(doc, "多因子評分 + TopN(預設 60 檔)")
    add_bullet(doc, "強勢股過濾(營收 YoY > 10% + PE < 30 + 現價 > 10)")
    add_bullet(doc, "「🔄 重新抓股價」按鈕(V1.1.5c 加、共用快取)")

    add_h4(doc, "Treeview 欄位(12 欄)")
    add_bullet(doc, "代號 / 名稱 / 收盤 / 漲跌 / 漲跌% / 成交量 / 營收 YoY / EPS YoY / PE / 殖利率 / 評分 / 技術買點")

    add_h2(doc, "4.10 📊 回測模擬 Tab")
    add_h4(doc, "Top10 基本面回測")
    add_bullet(doc, "從最近一次選股結果取 Top10")
    add_bullet(doc, "hold_days 後出場、扣 roundtrip_cost_pct")
    add_bullet(doc, "統計勝率 / 累積報酬 / 最大回落")
    add_p(doc, "Excel 中讀到少檔就用多少檔去模擬(已驗證、現狀就是這樣)", italic=True)

    add_h2(doc, "4.11 📅 模擬買賣 Tab ⭐新")

    add_h3(doc, "整體佈局")
    add_p(doc, "本 Tab 是 V1.2.0 重點,分三塊:")
    add_bullet(doc, "🅰 左下「我的組合」Treeview:列出所有組合、雙擊進入下方 detail")
    add_bullet(doc, "🅱 下方「手動設定」tab 群組:基本資料 + 執行控制 + 回購狀態 + 持倉/交易/權益曲線")
    add_bullet(doc, "🅲 左下「組合操作」按鈕:+ 新增組合 / 編輯 / 啟動 / 暫停 / 刪除")
    add_p(doc, "[截圖位置:模擬買賣 Tab — 整體三塊佈局]", italic=True)

    add_h3(doc, "🅰 我的組合 Treeview(左下)")
    add_table(doc,
        ["欄","說明"],
        [
            ["ID","組合編號"],
            ["名稱","使用者自訂"],
            ["策略","ai_meta / manual"],
            ["股票池","池內幾檔"],
            ["啟動日","created_at 日期"],
            ["最後跑","last_run_date(補跑到哪天)"],
            ["狀態","active / paused / archived"],
            ["總資金","initial_cash"],
            ["累積報酬","%"],
            ["持倉","現有幾檔"],
        ], widths_cm=[3, 14])

    add_h3(doc, "🅱 手動設定(下方 tab 群組)")
    add_h4(doc, "Row 1:基本資料")
    add_bullet(doc, "名稱(必填)")
    add_bullet(doc, "Excel(選填、搭配 use_excel_stock_list)")
    add_bullet(doc, "策略下拉:ai_meta / manual")
    add_bullet(doc, "總資金(預設 1,000,000)")
    add_bullet(doc, "持倉上限(預設 10)")

    add_h4(doc, "Row 2:執行控制")
    add_bullet(doc, "「▶ 推進一天」按鈕 — 用當前即時價模擬買賣一天")
    add_bullet(doc, "「⏩ 補跑到今天」按鈕 — 從 last_run_date 補到今天(若中間 60 天沒開,一次補齊)")
    add_bullet(doc, "「☑ AI 模式」開關 — 啟用 ai_meta 自動決策")

    add_h4(doc, "Row 3:系統選股回購狀態")
    add_bullet(doc, "狀態:active / paused")
    add_bullet(doc, "衝刺:ai_meta")
    add_bullet(doc, "啟動:2026-07-13 15:03:33")
    add_bullet(doc, "摘要:初始 1,000,000 / 目前 1,000,000 / 累積報酬 +0.00%")
    add_bullet(doc, "持倉 0/10 / 交易 0 / 勝率 0.0% (0/0)")

    add_h3(doc, "🅲 新增 / 編輯組合對話框")
    add_p(doc, "按「+ 新增組合」打開 dialog_paper.py 對話框:")
    add_table(doc,
        ["欄位","必填","預設","說明"],
        [
            ["名稱","✓","—","組合名稱(unique)"],
            ["策略模式","✓","ai_meta","ai_meta / manual"],
            ["起始資金","","1,000,000","模擬起始資金"],
            ["持倉上限","","10","最多同時持有幾檔"],
            ["TopK","","7","每日選幾檔買"],
            ["持有天數","","10","0 = 無限持有"],
            ["停損","","-0.03","-3% 自動賣"],
            ["停利","","0.08","+8% 自動賣"],
            ["股票池","","[]","多選清單 + 搜尋框"],
        ], widths_cm=[3, 1.5, 2.5, 10])
    add_p(doc, "「📥 採用回測參數」一鍵帶入:從最近一次回測結果的 Top10 平均參數帶入此組合。")
    add_p(doc, "[截圖位置:新增組合對話框 — 含「採用回測參數」按鈕]", italic=True)

    add_h3(doc, "持倉 / 買賣記錄 / 權益曲線 子 Tab")
    add_p(doc, "選定組合後,下方 Tab 群組切換:")
    add_h4(doc, "持倉 tab")
    add_bullet(doc, "Treeview 欄位:代號 / 名稱 / 股數 / 平均成本 / 現價 / 未實現損益 / 報酬率%")
    add_h4(doc, "買賣記錄 tab")
    add_bullet(doc, "Treeview 欄位:日期 / 代號 / 名稱 / 買/賣 / 股數 / 價格 / 金額 / 手續費 / 理由")
    add_h4(doc, "權益曲線 tab")
    add_bullet(doc, "內嵌 matplotlib 圖:每日總市值折線圖")
    add_bullet(doc, "X 軸:trade_date、Y 軸:TWD")

    # 五、自選股清單
    add_h1(doc, "五、自選股清單模式(use_excel_stock_list)")
    add_p(doc, "若你想跑特定股票清單而不是全市場:")
    add_code_block(doc,
"""$ cat > stock_list.xlsx << EOF
代號,名稱
2330,台積電
2317,鴻海
2454,聯發科
EOF
""")
    add_p(doc, "在 stocktool_config.json:")
    add_code_block(doc,
"""{
  "use_excel_stock_list": true,
  "excel_stock_file": "stock_list.xlsx"
}""")
    add_p(doc, "重啟 StockTool,選股就只會跑清單內的股票。")

    # 六、報表輸出
    add_h1(doc, "六、報表輸出")
    add_h2(doc, "6.1 選股報表工作表")
    add_table(doc,
        ["Sheet","內容"],
        [
            ["選股結果","Treeview 全部欄位"],
            ["回測結果","勝率 / 累積報酬 / 最大回落 / 平均持有天數"],
            ["強勢股清單","過濾後清單"],
            ["參數設定","當下跑這次用的 config 完整 snapshot"],
            ["匯出資訊","匯出時間、StockTool 版本、Filter 條件"],
        ], widths_cm=[3, 14])

    add_h2(doc, "6.2 模擬買賣報表工作表 ⭐新")
    add_p(doc, "在「模擬買賣」Tab 選定組合後,按「匯出 Excel」產出 5 sheet:")
    add_table(doc,
        ["Sheet","內容"],
        [
            ["組合總覽","總成本、總市值、未實現損益、已實現損益、總報酬率"],
            ["組合持倉","每檔股票:代號、名稱、股數、平均成本、現價、未實現損益、報酬率%"],
            ["交易明細","所有 BUY / SELL:日期、代號、名稱、買/賣、股數、價格、金額、手續費、理由"],
            ["權益曲線","每日總市值、累積報酬%(給 chart 用)"],
            ["匯出資訊","匯出時間、總交易筆數、組合名稱、StockTool 版本"],
        ], widths_cm=[3, 14])

    add_h2(doc, "6.3 報表常用欄位速查")
    add_table(doc,
        ["欄位","說明"],
        [
            ["代號 / stock_id","股票代號(例 2330)"],
            ["名稱 / stock_name","股票名稱"],
            ["營收 YoY / rev_yoy","最近月份營收年增率(%)"],
            ["EPS YoY / eps_yoy","最近季度 EPS 年增率(%)"],
            ["PE","本益比(Price / EPS TTM)"],
            ["殖利率 / div_yield","近 12 個月殖利率(%)"],
            ["評分 / score","多因子綜合評分"],
            ["技術買點","bool,True = 買點成立"],
        ], widths_cm=[4, 13])

    # 七、執行流程詳解
    add_h1(doc, "七、執行流程詳解")
    add_h2(doc, "7.1 第一次跑會比較慢")
    add_p(doc, "原因:")
    add_bullet(doc, "要抓全部股票的月線(60 個月 × 全部上市櫃 ≈ 1800 檔,首次約 5-10 分鐘)")
    add_bullet(doc, "要合併 goodinfo 殖利率驗證")
    add_bullet(doc, "要算多因子評分")
    add_p(doc, "第二次以後:有 cache,只抓當日新增 → 1-2 分鐘。", italic=True)

    add_h2(doc, "7.2 模擬買賣補跑流程 ⭐新")
    add_p(doc, "按下「⏩ 補跑到今天」後背景流程:")
    add_code_block(doc,
"""for portfolio in active_portfolios:
    start = last_run_date + 1 day
    end   = today

    for trade_date in [start..end]:
        # 1) 抓 stock_pool + 持股的歷史收盤價
        #    (用 cache/history/<code>_<months>m.xlsx)
        # 2) 偵測 market regime (多頭 / 空頭 / 盤整)
        # 3) engine.evaluate_*_portfolio_one_day 跑 BUY/SELL 決策
        # 4) 寫入 trades + 持倉 + 當日 snapshot""")
    add_p(doc, "若 last_run_date 是 7/13、今天是 9/16 → 補 64 天交易日(扣假日 ≈ 45 天)。")
    add_p(doc, "Console 會顯示每個組合的「完成:BUY X / SELL Y / 跳過 Z / 錯誤 W」。")

    # 八、常見錯誤對照
    add_h1(doc, "八、常見錯誤對照")

    add_h3(doc, "🆘 為什麼 BUY/SELL 都是 0 ⭐新")
    add_p(doc, "如果你的模擬買賣跑了很久但 BUY=0 / SELL=0、持倉 0/10、累積報酬 +0.00%,常見原因:")
    add_bullet(doc, "❶ StockTool 主類別沒有 self.session 屬性 → cache 過舊時 catch_up 抓不到新資料 → 整段 skip")
    add_bullet(doc, "❷ PaperScheduler 是 App-level only → App 沒開就不排程,中間漏掉的日子不會自動補")
    add_bullet(doc, "❸ cache/history/ 裡的 xlsx 檔太舊(超過 trade_date) → 沒辦法 refresh 就 skip")
    add_bullet(doc, "❹ last_run_date 已是今天 → 沒事可做")
    add_p(doc, "解法(見第九章 cache 過舊處理 + 第十章已知問題):")
    add_p(doc, "1) 手動按「▶ 推進一天」一次看會不會動", italic=True)
    add_p(doc, "2) 確認 cache/history/ 內有 *_60m.xlsx 檔", italic=True)
    add_p(doc, "3) 在「📈 系統選股」Tab 按「🔄 重新抓股價」讓 cache 補新", italic=True)
    add_p(doc, "4) 再按「⏩ 補跑到今天」", italic=True)

    add_h3(doc, "其他常見錯誤")
    add_table(doc,
        ["症狀","可能原因","解法"],
        [
            ["EPS YoY 全為 0","1-4 月(尚未公告去年 Q1)","等 TWSE 補上 114Q1 或手動補 EPS 歷史庫"],
            ["Top10 全是 ETF","ETF 欄位混入","用 use_excel_stock_list 排除 ETF"],
            ["Score = -1e+18","門檻過嚴導致全部排除","simple_min_* 改成 -999"],
            ["PE 顯示 inf","EPS 為負","multi_factor_score 加 inf 處理"],
            ["執行策略按鈕沒反應","config 沒存","改完參數按「💾 儲存設定」"],
            ["找不到模組","虛擬環境沒啟動","source .venv/bin/activate"],
            ["抓不到資料","網路問題 / TWSE 維護","retry 3 次自動失敗、改 verify_ssl=true"],
        ], widths_cm=[4, 5, 8])

    # 九、快取管理
    add_h1(doc, "九、快取管理")
    add_p(doc, "刪除快取強制重抓:")
    add_code_block(doc,
"""$ rm -rf cache/
$ ls cache/
# price.xlsx  revenue.xlsx  eps.xlsx""")
    add_p(doc, "看快取內容(cache/history/ 內個股歷史):")
    add_code_block(doc,
"""$ ls cache/history/ | head -5
# 2330_60m.xlsx  2454_60m.xlsx  2317_60m.xlsx  ...""")
    add_p(doc, "檔名規則:<股票代號>_<歷史月數>m.xlsx(例 2330_60m.xlsx = 2330 過去 60 個月)。")

    add_h2(doc, "9.1 模擬買賣的 cache 過舊處理 ⭐新")
    add_p(doc, "V1.2.0-2026-08-20 新增邏輯:")
    add_p(doc, "若 cache 的最新日期 < trade_date → 自動 refresh(需 session != None 才會觸發)。")
    add_table(doc,
        ["情況","行為"],
        [
            ["正常:有 session","呼叫 get_stock_history 抓新資料 + 寫回 cache"],
            ["降級:無 session(PyCharm 開發模式 / 測試環境)","graceful skip 該日、繼續下一檔(會印 warning)"],
            ["🟡 已知限制","StockTool 主類別無 self.session 屬性 → 需外部傳入(目前都傳 None)"],
        ], widths_cm=[5, 12])
    add_p(doc, "如果你看到 console 一直印「cache 過舊且無 session、跳過」,解法:")
    add_p(doc, "1) 在「📈 系統選股」Tab 按「🔄 重新抓股價」", italic=True)
    add_p(doc, "2) 再回模擬買賣 Tab 按「⏩ 補跑到今天」", italic=True)
    add_p(doc, "3) 那次就會用新抓的 cache 跑", italic=True)

    # 十、已知問題
    add_h1(doc, "十、已知問題與限制")

    add_h2(doc, "10.1 🟡 Hover 殘留(v22-v26 fix2 已試,仍未根治)")
    add_p(doc, "症狀:mouse/key 切換 Treeview hover bar 不會自動消舊的高亮(舊的仍亮黃色)。")
    add_p(doc, "影響:純視覺問題,主要功能(選股、回測、模擬買賣)正常運作。")
    add_p(doc, "目前狀態:V26 fix3 commit 後決定暫停 debug。")
    add_p(doc, "暫行解:用 key 導航就別混 mouse、用 mouse 點別處就解。", italic=True)

    add_h2(doc, "10.2 🟡 PaperScheduler App-level only")
    add_p(doc, "症狀:App 關閉期間不排程,2 個月沒開就漏 60 天。")
    add_p(doc, "暫行解:下次打開 App 按「⏩ 補跑到今天」一次補齊。", italic=True)

    add_h2(doc, "10.3 🟡 StockTool 主類別無 self.session 屬性")
    add_p(doc, "症狀:PaperScheduler / 補跑按鈕內呼叫 catch_up 時,session 永遠是 None。")
    add_p(doc, "影響:cache 過舊時無法自動 refresh → 跳過該日 → 看不到 BUY/SELL。")
    add_p(doc, "暫行解:手動按「▶ 推進一天」或 GUI 啟動後點「重新抓股價」讓 cache 補新。", italic=True)

    add_h2(doc, "10.4 🟡 EPS YoY 年初失效(已緩解)")
    add_p(doc, "症狀:每年 1-4 月 TWSE 還沒公告去年 Q1,EPS YoY 全為 0。")
    add_p(doc, "緩解:V1.0 起 EPS 歷史庫自動補每日抓到的新一季、CSV 沒有去年同期時自動從歷史庫補。")
    add_p(doc, "限制:114Q1 從未在 TWSE 出現,歷史庫也補不滿。")
    add_p(doc, "解法:等 TWSE 補上 114Q1(季中公告後應該會放上來)、或加 MOPS 個股頁備援。", italic=True)

    add_h2(doc, "10.5 🟢 Walk-forward 不做樣本外驗證")
    add_p(doc, "雖然有 wf_enabled 開關,但目前實作只切訓練/測試區間,沒做樣本外驗證。")
    add_p(doc, "若你要嚴謹回測,請自行用 backtest.py 跑多組參數比較。", italic=True)

    add_h2(doc, "10.6 🟢 DEBUG 訊息太多(已消大部分)")
    add_p(doc, "V26 fix3 後 _v18_log() 預設改寫檔不 print、消 25 個 console 噪音。")
    add_p(doc, "Debug 時設 self._v18_debug_console = True 可回流 console。", italic=True)
    add_p(doc, "Log 檔位置:/tmp/stocktool_v18.log、/tmp/stocktool_v19_module.log", italic=True)

    # 十一、進階
    add_h1(doc, "十一、進階:手動跑回測(不開 GUI)")
    add_p(doc, "從 command line 跑回測:")
    add_code_block(doc,
"""$ python -c "
from stocktool import backtest
result = backtest.run(
    start='2025-01-01',
    end='2025-12-31',
    topk=10,
    hold_days=10
)
print(result.summary())
"
""")
    add_p(doc, "好處:可批次跑多組參數組合、輸出 CSV 比對。")

    add_h2(doc, "11.1 模擬買賣單獨執行 ⭐新")
    add_p(doc, "不開 GUI 也能跑模擬買賣 catch-up:")
    add_code_block(doc,
"""$ python -c "
from stocktool import paper_catchup
from stocktool.config import get_data_path

db_path = get_data_path('portfolio.db')
results = paper_catchup.catch_up_all_active(
    db_path,
    end_date='2026-09-18',
    session=None,  # PyCharm 開發模式傳 None
    cfg=None,
    logger=None
)
for r in results:
    print(f'{r.portfolio_name}: BUY {r.total_buys} / SELL {r.total_sells}')
"
""")
    add_p(doc, "注意:傳 session=None 會 graceful skip cache 過舊的日期(見 9.1)。")

    # 十二、版本紀錄
    add_h1(doc, "十二、版本紀錄")
    add_table(doc,
        ["版本","日期","重點"],
        [
            ["V0.9.3-HOTFIX","2026-06-08","修正 EPS YoY / Score 無限值 / Top10 全為 ETF"],
            ["V0.9.4","2026-06-10","新增「買賣記錄」模組:SQLite + Tab 化 GUI + Excel 匯出"],
            ["V0.9.5","2026-06-13","🔍 手動選股 Tab + Preset 機制"],
            ["V0.9.5-etf","2026-06-19","📊 主動式 ETF Tab + 19 檔清單"],
            ["V0.9.5-vol-no-divide","2026-06-21","📊 ETF Tab 加「重新抓股價」按鈕"],
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
            ["V1.2.0 使用者手冊","2026-09-18","📘 本手冊 + 規格書改版"],
        ], widths_cm=[4.5, 2.5, 10])

    # 十三、檔案結構
    add_h1(doc, "十三、檔案結構")
    add_code_block(doc,
"""StockTools/                              ← GitHub repo
├── source/
│   ├── StockTool.py                      ← 主程式(9838 行)
│   ├── portfolio.py                      ← 買賣記錄 DB
│   └── stocktool/                        ← V1.1.0 起重構出的子模組
│       ├── backtest.py                   ← 回測引擎
│       ├── cache.py                      ← 多源 cache 管理
│       ├── config.py                     ← VERSION + CONFIG + 常數
│       ├── database.py                   ← DB 共用 helper
│       ├── etf.py                        ← ETF 抓取 + GUI
│       ├── export_excel.py               ← Excel 報表
│       ├── fetch_market.py               ← TWSE / TPEX / goodinfo 抓取
│       ├── pipeline.py                   ← 選股 pipeline
│       ├── scoring.py                    ← 多因子評分
│       ├── technical.py                  ← RSI / MA / MACD
│       ├── paper_config.py               ← 回測→模擬參數映射 ⭐
│       ├── paper_engine.py               ← 每日 BUY/SELL 決策 ⭐
│       ├── paper_trading.py              ← DB CRUD ⭐
│       ├── paper_catchup.py              ← 補跑到今天 ⭐
│       ├── paper_scheduler.py            ← 14:00 自動排程 ⭐
│       ├── paper_excel.py                ← 模擬買賣 Excel 匯出 ⭐
│       └── gui/
│           ├── calendar.py               ← 交易日曆
│           ├── dialog_paper.py           ← 新增/編輯組合對話框 ⭐
│           └── tab_paper.py              ← 模擬買賣 Tab 主體 ⭐
├── documents/
│   ├── V0.9.4_規格書.docx                 ← 舊版規格書
│   ├── 股神_StockTool_使用者手冊_v0.9.5-etf-fix.docx
│   ├── V1.2.0-paper-trading_規格書.docx   ← 本版規格書 ⭐
│   └── 股神_StockTool_使用者手冊_v1.2.0-paper-trading.docx  ← 本手冊 ⭐
├── specs/
│   ├── gen_v094_spec.py                  ← 舊規格書產生器
│   ├── gen_v120_spec.py                  ← 本版規格書產生器 ⭐
│   ├── gen_v094_manual.py                ← 舊手冊產生器
│   └── gen_v120_manual.py                ← 本手冊產生器 ⭐
├── tests/                                 ← 95+ 個 pytest
├── portfolio.db / stocktool_config.json
├── requirements.txt
└── .gitignore / .gitattributes""")

    # 十四、技術支援
    add_h1(doc, "十四、技術支援")
    add_p(doc, "問題回報:GitHub issue 或 William Chang")
    add_p(doc, "Email:wjc@local.dev")
    add_p(doc, "Log 檔位置:")
    add_bullet(doc, "/tmp/stocktool_v18.log")
    add_bullet(doc, "/tmp/stocktool_v19_module.log")
    add_bullet(doc, "PyCharm console(若 _v18_debug_console = True)")

    # 文件尾
    doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("— 文件結束 —"); set_zh_font(r, size=10, color=RGBColor(0x99,0x99,0x99))

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    doc.save(OUT_PATH)
    print(f"✅ 使用者手冊已產出:{OUT_PATH}")
    print(f"   檔案大小:{os.path.getsize(OUT_PATH):,} bytes")


if __name__ == "__main__":
    build()
