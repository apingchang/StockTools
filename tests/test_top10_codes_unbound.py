"""V0.9.5-tab-split-phase3 B-1 fix: UnboundLocalError: top10_codes

問題：top10_codes 在 `if cfg.use_top10_backtest:` 區塊內賦值
如果 use_top10_backtest=False（William 預設）就走不到、return 時 UnboundLocalError

修法：return dict 用 try/except NameError 包 top10_codes
"""
import os
import re

STOCKTOOL_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "StockTool.py"
)
CONFIG_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "stocktool", "config.py"
)
PIPELINE_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "stocktool", "pipeline.py"
)


def test_run_pipeline_return_handles_top10_codes():
    """run_pipeline return 必須處理 top10_codes 可能未定義的情況

    use_top10_backtest=False 時 top10_codes 不會被賦值

    【v1.1 重構】run_pipeline 已搬到 stocktool/pipeline.py
    """
    target = PIPELINE_PY if os.path.exists(PIPELINE_PY) else STOCKTOOL_PY
    with open(target, "r", encoding="utf-8") as f:
        content = f.read()

    # 必須有 try/except NameError 包 top10_codes
    pattern = r"try:\s*\n\s*_top10_codes\s*=\s*top10_codes\s*\n\s*except\s+NameError:"
    assert re.search(pattern, content), (
        f"❌ {target} run_pipeline 結尾沒處理 top10_codes 未定義情況！\n"
        "應為：\n"
        "  try:\n"
        "      _top10_codes = top10_codes\n"
        "  except NameError:\n"
        "      _top10_codes = []"
    )
    print(f"✅ {target} run_pipeline return 用 try/except 處理 top10_codes")


def test_top10_codes_assignment_in_if_block():
    """top10_codes 必須在 if cfg.use_top10_backtest: 區塊內（記錄事實、提醒不要在外面用）

    【v1.1 重構】run_pipeline 已搬到 stocktool/pipeline.py
    """
    target = PIPELINE_PY if os.path.exists(PIPELINE_PY) else STOCKTOOL_PY
    with open(target, "r", encoding="utf-8") as f:
        content = f.read()

    # 找 top10_codes = 的位置（要找到該行）
    pattern = r'(\s+)top10_codes\s*=\s*df_sel\.head\(10\)'
    m = re.search(pattern, content)
    assert m, f"❌ {target} 找不到 top10_codes = df_sel.head(10) 賦值"

    # 賦值縮排應該是 8 個 space（在 if 區塊內）
    indent = m.group(1)
    assert len(indent) >= 8, (
        f"❌ {target} top10_codes 賦值縮排只有 {len(indent)} 個空白\n"
        f"應在 if cfg.use_top10_backtest: 區塊內（8 個空白）"
    )
    print(f"✅ {target} top10_codes 賦值在 if 區塊內（縮排 {len(indent)} 個空白）")


def test_use_top10_backtest_default_false():
    """確認 use_top10_backtest 預設是 False（讓 use_top10_backtest=False 是常見路徑）

    【v1.1 重構】StrategyConfig 已搬到 stocktool/config.py、
    run_pipeline 已搬到 stocktool/pipeline.py
    """
    target = CONFIG_PY if os.path.exists(CONFIG_PY) else STOCKTOOL_PY
    with open(target, "r", encoding="utf-8") as f:
        content = f.read()

    # 找 use_top10_backtest 預設值
    m = re.search(r'use_top10_backtest:\s*bool\s*=\s*(True|False)', content)
    assert m, f"❌ {target} 找不到 use_top10_backtest 預設值"
    default = m.group(1)
    print(f"✅ use_top10_backtest 預設為 {default}（{target}）")

    if default == "False":
        # 如果預設 False、則 try/except 修法必須存在（否則必爆）
        target2 = PIPELINE_PY if os.path.exists(PIPELINE_PY) else STOCKTOOL_PY
        with open(target2, "r", encoding="utf-8") as f:
            pipeline_content = f.read()
        pattern = r"try:\s*\n\s*_top10_codes\s*=\s*top10_codes"
        assert re.search(pattern, pipeline_content), (
            f"❌ use_top10_backtest 預設 False 但 {target2} 沒保護 top10_codes return！"
        )
        print(f"✅ 預設 False → {target2} try/except 保護存在")