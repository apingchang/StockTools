"""【V1.1-etf-popup-detail】ETF 今日異動 popup per-ETF 明細守護

2026-06-29 09:47 William 反映：
- 移到「今日異動」欄的數字上、popup 只顯示一行總和、看不出各檔 ETF 異動

【根因】
- _show_etf_popup mode="changes" 之前用 stock-level row 的欄位：
    etf_code (空字串, 該 row 沒這欄)
    etf_name (空字串)
    today_change_lots (這是總和、不是 per-ETF)
- per-ETF 異動其實在 etf_changes_json (JSON string) 內、一直沒 parse

【修法】
- json.loads(cr["etf_changes_json"]) 拿 per-ETF list
- 從 _etf_agg_df 的 etf_list 補 etf_name (json 內 etf_name="")
- 標題列 + 各 ETF 一行 + 總和
"""
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
STOCKTOOL_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "StockTool.py"
)


# ──────────────────── 靜態 code 結構守護 ────────────────────

def test_popup_detail_parses_etf_changes_json():
    """【核心守護】_show_etf_popup mode=changes 必須 json.loads etf_changes_json

    之前的 bug：直接讀 cr.get("etf_code", "") → 空字串（stock-level row 沒這欄）
    修法：json.loads(cr["etf_changes_json"]) 拿 per-ETF list
    """
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # 確認有 json.loads(cr.get("etf_changes_json", "")  或 .get("etf_changes_json"
    assert re.search(
        r'json\.loads\([^)]*etf_changes_json',
        content,
    ), (
        "❌ _show_etf_popup mode=changes 沒 parse etf_changes_json！\n"
        "  之前用 cr.get('etf_code', '') 拿空字串、所以 popup 看不到 per-ETF 異動。\n"
        "  改成 json.loads(cr['etf_changes_json']) 拿 per-ETF list。"
    )

    # 反面：不再有「cr.get('etf_code', '')」這種錯誤讀法
    # （etf_code 在 stock-level row 是空、不是 per-ETF 來源）
    # 注意：etf_code 在 etf_name_map 跟 etf_name_str 之間仍會出現、這裡只擋「在 popup_changes block 內」的誤用
    # 比較寬鬆：確保 stock_changes.iterrows() 拿 stock-level 然後用 etf_code / etf_name 的誤用 pattern 不見了
    # 改用比較精準的：必須有 etf_changes_json 的 read
    # 上面已擋, 這裡 OK


def test_popup_detail_enriches_etf_name_from_etf_list():
    """【核心守護】etf_name 必須從 _etf_agg_df 的 etf_list 補上
    因為 etf_changes_json 內 etf_name="" 空字串、要有 fallback
    """
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # 確認有從 etf_list parse etf_name 的邏輯
    # 模式：re.match r"^(\S+)\s+(.+?)\([\d.]+%\)\s*$"
    assert re.search(
        r"re\.match\([^)]*\\S\+\\s\+\(\.\+\?\)",
        content,
    ) or re.search(
        r"etf_name_map\[m\.group\(1\)",
        content,
    ), (
        "❌ popup 沒從 etf_list parse etf_name！\n"
        "  etf_changes_json 內 etf_name 是空字串、必須從 agg_df 的 etf_list 補。\n"
        "  etf_list 格式：'0050 元大台灣50(9.37%)\\n006208 富邦台50(8.71%)'"
    )

    # 確認有 etf_name_map 變數
    assert "etf_name_map" in content, (
        "❌ 缺少 etf_name_map 變數（從 etf_list 補 etf_name 用）"
    )


def test_popup_detail_shows_header_and_total():
    """【核心守護】popup 必須有標題列（含 stock_code/name + etf_count + 異動檔數）+ 總和行

    之前：只顯示總和一行
    之後：標題列 + 各 ETF 各一行 + 分隔線 + 總和行
    """
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # 標題列：f"{stock_code} {stock_name}（{etf_count} 檔 ETF、今日..."
    # 允許 multi-line（可能拆成 if/else 兩種寫法）
    # 直接搜「檔 ETF、今日」這個關鍵字串
    assert "檔 ETF、今日" in content, (
        "❌ popup 沒標題列！\n"
        "  應該有「{stock_code} {stock_name}（{etf_count} 檔 ETF、今日 N 檔異動）」"
    )
    # 確認有 stock_code 跟 stock_name 在標題列中
    assert "{stock_code}" in content and "{stock_name}" in content, (
        "❌ 標題列應包含 stock_code / stock_name"
    )

    # 總和行：f"總和  {sign}{total:,.1f}  張"
    assert re.search(
        r"總和\s+\{sign\}?\{total:,\.1f\}\s*張",
        content,
    ), (
        "❌ popup 沒總和行！\n"
        "  應該有「總和  {sign}{total:,.1f}  張」"
    )


def test_popup_detail_sorts_by_absolute_change():
    """【核心守護】各 ETF 應依「絕對值」由大到小排、最大異動在最上面"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # 確認有 sort key=lambda x: abs(x[0]), reverse=True
    assert re.search(
        r"sort\s*\(\s*key\s*=\s*lambda\s+\w+\s*:\s*abs\(",
        content,
    ), (
        "❌ popup 沒依絕對值排序！\n"
        "  應該 sort(key=lambda x: abs(x[0]), reverse=True)"
    )


def test_popup_detail_filters_zero_changes():
    """【核心守護】abs(cl) < 0.001 的要過濾掉、避免雜訊"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # 確認在 mode=changes 區塊有「if abs(cl) < 0.001: continue」
    # 用較寬鬆的字串（不要被註解或舊邏輯誤判）
    assert "abs(cl) < 0.001" in content, (
        "❌ popup 沒過濾 abs(cl) < 0.001 的項目、會顯示 0.0 雜訊"
    )


def test_popup_detail_method_compiles():
    """【語法守護】改完沒漏逗號 / indent 錯誤"""
    import py_compile
    try:
        py_compile.compile(STOCKTOOL_PY, doraise=True)
    except py_compile.PyCompileError as e:
        pytest.fail(f"❌ StockTool.py 編譯失敗：\n{e}")


# ──────────────────── 整合測試：實際 parse 邏輯 ────────────────────

def test_parse_etf_changes_json_round_trip():
    """【整合測試】模擬 _compute_etf_changes 寫進 DB、再從 change_df 讀出來的格式

    確認 json.loads 拿到的 list 結構正確、可正確抓出每檔 ETF
    """
    # 模擬 database.py 寫進 DB 的 etf_changes_json
    etf_changes_json = json.dumps([
        {"etf_code": "0050", "etf_name": "", "change_lots": 1234.5},
        {"etf_code": "006208", "etf_name": "", "change_lots": -500.0},
        {"etf_code": "00981A", "etf_name": "", "change_lots": 0.0},  # 應該被過濾
        {"etf_code": "00403A", "etf_name": "", "change_lots": 50.3},
    ], ensure_ascii=False)

    # 模擬 _show_etf_popup 的 parse 邏輯
    etf_changes = json.loads(etf_changes_json)
    assert len(etf_changes) == 4, "❌ json.loads 拿到的 list 數量不對"

    # 過濾 0.0
    entries = []
    for ec_entry in etf_changes:
        cl = float(ec_entry.get("change_lots", 0) or 0)
        if abs(cl) < 0.001:
            continue
        ec = str(ec_entry.get("etf_code", "")).strip()
        entries.append((cl, ec, ""))

    # 3 個有異動的、1 個 0.0 被過濾
    assert len(entries) == 3, f"❌ 過濾後應該 3 個、實際 {len(entries)}: {entries}"

    # sort by abs 降冪
    entries.sort(key=lambda x: abs(x[0]), reverse=True)
    assert entries[0][0] == 1234.5, f"❌ 第一個應該是 +1234.5 (最大絕對值), 實際 {entries[0]}"
    assert entries[0][1] == "0050", f"❌ 第一個 ETF 應該是 0050, 實際 {entries[0]}"
    assert entries[1][0] == -500.0, f"❌ 第二個應該是 -500.0, 實際 {entries[1]}"
    assert entries[2][0] == 50.3, f"❌ 第三個應該是 50.3, 實際 {entries[2]}"


def test_parse_etf_list_to_name_map():
    """【整合測試】從 agg_df 的 etf_list 拆出 etf_name_map

    etf_list 格式：「0050 元大台灣50(9.37%)\n006208 富邦台50(8.71%)\n00403A 主動統一升級50(18.29%)」
    """
    etf_list_str = (
        "0050 元大台灣50(9.37%)\n"
        "006208 富邦台50(8.71%)\n"
        "00403A 主動統一升級50(18.29%)"
    )

    etf_name_map = {}
    for line in etf_list_str.split("\n"):
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(\S+)\s+(.+?)\([\d.]+%\)\s*$", line)
        if m:
            etf_name_map[m.group(1).strip()] = m.group(2).strip()

    assert etf_name_map == {
        "0050": "元大台灣50",
        "006208": "富邦台50",
        "00403A": "主動統一升級50",
    }, f"❌ etf_name_map 解析錯誤：{etf_name_map}"


def test_popup_text_format_full():
    """【整合測試】完整組裝 popup_text、驗證所有要素

    模擬一個有 3 檔 ETF 異動的個股、確認 popup 文字格式正確
    """
    stock_code = "2330"
    stock_name = "台積電"
    etf_count = 5
    etf_name_map = {
        "0050": "元大台灣50",
        "006208": "富邦台50",
        "00403A": "主動統一升級50",
    }
    entries = [
        (1234.5, "0050", ""),
        (-500.0, "006208", ""),
        (50.3, "00403A", ""),
    ]

    # 補 etf_name
    for i, (cl, ec, en) in enumerate(entries):
        entries[i] = (cl, ec, en or etf_name_map.get(ec, ""))

    # sort
    entries.sort(key=lambda x: abs(x[0]), reverse=True)

    # 組裝 popup_text
    change_lines = [f"{stock_code} {stock_name}（{etf_count} 檔 ETF、今日 {len(entries)} 檔異動）"]
    change_lines.append("─" * 20)
    total = 0.0
    for cl, ec, en in entries:
        total += cl
        sign = "+" if cl > 0 else ""
        change_lines.append(f"{sign}{cl:,.1f}  {ec}  {en}")
    change_lines.append("─" * 20)
    sign = "+" if total > 0 else ""
    change_lines.append(f"總和  {sign}{total:,.1f}  張")
    popup_text = "\n".join(change_lines)

    # 驗證
    assert "2330 台積電（5 檔 ETF、今日 3 檔異動）" in popup_text, f"❌ 標題列不對：{popup_text}"
    assert "+1,234.5  0050  元大台灣50" in popup_text, f"❌ 第一個 ETF 行不對：{popup_text}"
    assert "-500.0  006208  富邦台50" in popup_text, f"❌ 第二個 ETF 行不對：{popup_text}"
    assert "+50.3  00403A  主動統一升級50" in popup_text, f"❌ 第三個 ETF 行不對：{popup_text}"
    assert "總和  +784.8  張" in popup_text, f"❌ 總和行不對（1234.5-500.0+50.3=784.8）：{popup_text}"
