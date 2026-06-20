"""V0.9.5-tab-split-phase3 Commit B-2: 強勢股過濾實際生效守護

驗證：
- _apply_strong_filter helper 定義在 run_pipeline 內
- 兩條路徑（use_top10_backtest + 正常回測）都有呼叫
- UI label 從「💪 強勢股過濾 (報表用)」改為「💪 強勢股過濾」
"""
import os
import re

STOCKTOOL_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "StockTool.py"
)


def test_strong_filter_helper_exists():
    """run_pipeline 內必須有 _apply_strong_filter helper"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    assert "def _apply_strong_filter" in content, "❌ 缺少 _apply_strong_filter helper"
    # helper 必須在 run_pipeline 內（nested function）
    m = re.search(
        r"def run_pipeline\(cfg: StrategyConfig.*?def _apply_strong_filter",
        content,
        re.DOTALL,
    )
    assert m, "❌ _apply_strong_filter 不在 run_pipeline 內"
    print("✅ _apply_strong_filter 在 run_pipeline 內")


def test_helper_filters_all_four_conditions():
    """helper 必須過濾 4 個條件：營收YoY、EPS>0、PE、股價"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # 找 helper body
    m = re.search(
        r"def _apply_strong_filter\(.*?(?=\n    def |\nclass |\Z)",
        content,
        re.DOTALL,
    )
    assert m, "❌ 找不到 _apply_strong_filter body"
    body = m.group(0)

    for cond, key in [
        ("營收YoY", "strong_revenue_yoy"),
        ("EPS本期", "strong_revenue_yoy"),  # 用 strict > 0
        ("PE", "strong_pe_max"),
        ("股價", "strong_price_min"),
    ]:
        assert cond in body, f"❌ helper 缺少 {cond} 條件"
        assert key in body, f"❌ helper 缺少 {key} 參考"

    # EPS > 0 是字面 0（不是 cfg 參數）
    assert body.count("> 0") >= 1, "❌ helper 沒寫 EPS > 0"

    print("✅ helper 過濾 4 個條件：營收YoY / EPS>0 / PE / 股價")


def test_strong_filter_called_in_top10_path():
    """use_top10_backtest 路徑必須呼叫 _apply_strong_filter"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # 找「if cfg.use_top10_backtest」區塊到下一個「return」
    m = re.search(
        r"if cfg\.use_top10_backtest:(.*?)\n        return\n",
        content,
        re.DOTALL,
    )
    assert m, "❌ 找不到 use_top10_backtest 區塊"
    body = m.group(1)

    assert "df_sel = _apply_strong_filter" in body, (
        "❌ use_top10_backtest 路徑沒套強勢股過濾！\n"
        "應在 sort 之後、head(10) 之前呼叫"
    )
    print("✅ use_top10_backtest 路徑套強勢股過濾")


def test_strong_filter_called_in_normal_path():
    """正常回測路徑必須呼叫 _apply_strong_filter"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # 找 use_top10_backtest 區塊之後的「正常回測模式」段
    # 第一個 return 在 use_top10_backtest 區塊內、第二段是正常回測
    # 找「logger.log(f"5) 抓取前」附近的代碼
    m = re.search(
        r'df_sel_temp\.sort_values\("Score".*?logger\.log\(f"5\) 抓取前',
        content,
        re.DOTALL,
    )
    assert m, "❌ 找不到正常回測路徑"
    body = m.group(0)

    assert "_apply_strong_filter(df_sel_temp" in body, (
        "❌ 正常回測路徑沒套強勢股過濾！\n"
        "應在 sort 之後、head(top_n_for_tech) 之前呼叫"
    )
    print("✅ 正常回測路徑套強勢股過濾")


def test_ui_label_changed():
    """UI label 必須從「💪 強勢股過濾 (報表用)」改為「💪 強勢股過濾」"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # 不應再有「(報表用)」
    assert "💪 強勢股過濾 (報表用)" not in content, (
        "❌ 還有「💪 強勢股過濾 (報表用)」標籤！\n"
        "Phase 3 B-2：強勢股過濾不再只是報表用、要實際生效"
    )

    # 必須有新 label
    assert "💪 強勢股過濾" in content, "❌ 找不到「💪 強勢股過濾」"

    print("✅ UI label 已改：「💪 強勢股過濾」")


def test_helper_logs_filter_counts():
    """helper 必須 log 過濾前/後筆數"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    m = re.search(
        r"def _apply_strong_filter\(.*?(?=\n    def |\nclass |\Z)",
        content,
        re.DOTALL,
    )
    assert m
    body = m.group(0)

    # 必須有 logger.log
    assert "logger.log" in body, "❌ helper 沒 log"
    # 必須提到 before / after 或過濾相關字
    assert "before" in body and "after" in body, (
        "❌ helper 沒 log before / after 筆數"
    )
    print("✅ helper log 過濾前/後筆數")