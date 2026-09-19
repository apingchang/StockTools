"""
【2026-08-20 bug fix 2】Regression test for HISTORY_DIR → user home

背景：
- source/stocktool/config.py HISTORY_DIR = "cache/history" (相對路徑)
- .bin 跑時 cwd = dist/ → cache/history/ 解析成 dist/cache/history/
- 但實際資料在 source/cache/history/ (121 個 *_60m.xlsx)
- → 從 .bin 跑讀不到任何 cache → 模擬買賣永遠 28 跳過

修法 (2026-08-20 方案 A):
- config.py 加 get_data_dir_path(subdir)
- HISTORY_DIR = get_data_dir_path("cache/history") → ~/.local/share/stocktool/cache/history/
- PyCharm + .bin 都從 user home 讀
- 121 個檔案已 migrate 過去

期望：
1. HISTORY_DIR 是絕對路徑
2. 是 user home 下的 .local/share/stocktool/cache/history/
3. 從該路徑可以讀到 *_60m.xlsx
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))


def test_history_dir_is_absolute():
    """HISTORY_DIR 必須是絕對路徑 (不能是相對路徑 'cache/history')"""
    from stocktool.config import HISTORY_DIR
    assert os.path.isabs(HISTORY_DIR), (
        f"❌ HISTORY_DIR 是相對路徑 → .bin 跑時 cwd 不對會找不到 cache\n"
        f"   got={HISTORY_DIR!r}"
    )


def test_history_dir_under_user_home():
    """HISTORY_DIR 必須在 user home ~/.local/share/stocktool/cache/history/"""
    from stocktool.config import HISTORY_DIR
    home = os.path.expanduser("~")
    expected = os.path.join(home, ".local", "share", "stocktool", "cache", "history")
    assert HISTORY_DIR == expected, (
        f"❌ HISTORY_DIR 應該在 user home\n"
        f"   expected: {expected}\n"
        f"   got:      {HISTORY_DIR}"
    )


def test_history_dir_exists_and_has_files():
    """HISTORY_DIR 必須存在且有 cache 檔案 (migrate 後的 121 個 xlsx)"""
    from stocktool.config import HISTORY_DIR
    assert os.path.isdir(HISTORY_DIR), f"❌ HISTORY_DIR 不存在: {HISTORY_DIR}"

    files = [f for f in os.listdir(HISTORY_DIR) if f.endswith(".xlsx")]
    assert len(files) >= 50, (
        f"❌ HISTORY_DIR 內 xlsx 太少 ({len(files)}) — migrate 沒做完？\n"
        f"   預期 ≥50, 實際 {len(files)}"
    )

    # 至少要有一個 *_60m.xlsx
    has_60m = any(f.endswith("_60m.xlsx") for f in files)
    assert has_60m, (
        f"❌ 沒有 *_60m.xlsx — 模擬買賣補跑會讀不到 cache\n"
        f"   files: {files[:5]}..."
    )


def test_get_history_file_returns_absolute():
    """get_history_file() 必須回絕對路徑 (任何 cwd 都能讀)"""
    from stocktool import export_excel
    from stocktool.config import HISTORY_DIR

    fp = export_excel.get_history_file("2330", 60)
    assert os.path.isabs(fp), f"❌ get_history_file 回相對路徑: {fp!r}"

    # 預期路徑的 prefix 是 HISTORY_DIR
    assert fp.startswith(HISTORY_DIR), (
        f"❌ get_history_file 不在 HISTORY_DIR 內\n"
        f"   fp={fp}\n"
        f"   HISTORY_DIR={HISTORY_DIR}"
    )


def test_get_history_file_60m_exists_in_production():
    """至少一個常見的 60m cache 檔要存在 (2330 台積電)"""
    from stocktool import export_excel
    fp = export_excel.get_history_file("2330", 60)
    assert os.path.exists(fp), (
        f"❌ 2330_60m.xlsx 不存在\n"
        f"   path={fp}\n"
        f"   → migrate 沒做、或 HISTOR_DIR 還指錯地方"
    )
