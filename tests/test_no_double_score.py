"""V1.1-no-double-score: 修 P0 統一評分呼叫、避免重複計算

驗證：
- run_pipeline 正常回測路徑只呼叫一次 calculate_multi_factor_score 或 calculate_simple_score
- 不再有「df_sel 算一次、df_sel_temp 又算一次」的情況
- 刪掉的「line 415 重複評分」不應回來

背景（v1.0 改版 TODO 2026-06-09 列的 P0）：
- 原本 StockTool.py line 1620 區塊在 v1.1 重構後變成 pipeline.py
- 修法：line 367 算 df_sel（不再算 df_sel_temp）、line 415 拿掉重複計算
"""
import os
import re

PIPELINE_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "stocktool", "pipeline.py"
)


def _read_pipeline():
    assert os.path.exists(PIPELINE_PY), f"❌ 找不到 {PIPELINE_PY}"
    with open(PIPELINE_PY, "r", encoding="utf-8") as f:
        return f.read()


def test_no_duplicate_score_after_tech():
    """line 415（技術分析跑完後）不能再算一次評分

    原本的「重複評分」位置在「run_tech 呼叫之後」
    修完後 run_tech 之後不應再有 calculate_*(df_sel, ...)
    """
    content = _read_pipeline()

    # 找 use_top10_backtest return 之後的「正常回測」段
    # 找「run_tech(cfg, s, tech_codes...」之後的程式碼
    m = re.search(
        r"tech_all\s*,\s*tech_today\s*,\s*buy_today\s*=\s*run_tech\([^)]+\)(.*?)$",
        content,
        re.DOTALL,
    )
    assert m, "❌ 找不到 run_tech 呼叫"
    after_tech = m.group(1)

    # run_tech 之後不應再出現 calculate_*_score(df_sel, ...) 的呼叫
    dup_calls = re.findall(
        r"calculate_(?:multi_factor|simple|enhanced)_score\(df_sel",
        after_tech,
    )

    assert len(dup_calls) == 0, (
        f"❌ run_tech 之後還有 {len(dup_calls)} 個重複評分呼叫！\n"
        f"找到：{dup_calls}\n"
        f"V1.1-no-double-score 修法：line 415 拿掉重複計算"
    )
    print(f"✅ run_tech 之後沒有重複評分（0 個）")


def test_df_sel_temp_after_strong_filter():
    """df_sel_temp 應該是 _apply_strong_filter 的結果、不是 calculate_*_score 的結果

    原本 df_sel_temp = calculate_*(df_sel, cfg)（重複計算）
    修完後 df_sel_temp = _apply_strong_filter(df_sel, ...)
    """
    content = _read_pipeline()

    # 在 run_pipeline 主體內找「df_sel_temp = _apply_strong_filter」
    m = re.search(
        r"def run_pipeline\([^)]*\):(.*?)(?=\n\ndef |\nclass |\Z)",
        content,
        re.DOTALL,
    )
    assert m, "❌ 找不到 run_pipeline 函式"
    body = m.group(0)

    # df_sel_temp 第一次被賦值（過濾版本）必須是 _apply_strong_filter
    # 排除 use_top10_backtest 區塊內的（先抓第一個 df_sel_temp = _apply_strong_filter 的位置）
    m_filter = re.search(
        r"df_sel_temp\s*=\s*_apply_strong_filter\(df_sel",
        body,
    )
    assert m_filter, (
        "❌ 正常回測路徑沒看到「df_sel_temp = _apply_strong_filter(df_sel, ...)」！\n"
        "V1.1-no-double-score 修法：df_sel_temp 應是 strong_filter 的結果"
    )
    print("✅ df_sel_temp = _apply_strong_filter(df_sel, ...) 存在")
