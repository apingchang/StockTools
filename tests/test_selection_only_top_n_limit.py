"""
【V1.2.0-system-select-topn】系統選股結果套用 TopN 限制

William 2026-07-06 14:54 反映：
- 系統選股 UI 設定「選股檔數 (TopN)」= 20、但結果顯示約 50 檔
- 原本只跑強勢股過濾、沒套用 TopN 限制 → TopN 參數形同虛設
- 修法：在 _apply_strong_filter 之後 head(cfg.top_n_for_tech)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

import pandas as pd
import pytest
from unittest.mock import patch

from stocktool import pipeline
from stocktool.config import StrategyConfig


class _MockLogger:
    def __init__(self):
        self.messages = []

    def log(self, msg):
        self.messages.append(msg)


def _make_price_df(n: int) -> pd.DataFrame:
    """產生 n 筆假股價資料"""
    return pd.DataFrame(
        {
            "股票代號": [str(1000 + i) for i in range(n)],
            "公司名稱_來源": [f"測試股{i}" for i in range(n)],
            "股價": [50.0] * n,
            "漲跌": [0.0] * n,
            "data_date": ["2026-07-06"] * n,
            "成交量_張": [100.0] * n,
        }
    )


def _make_rev_eps_df(n: int) -> pd.DataFrame:
    """產生 n 筆假營收 + EPS 資料"""
    return (
        pd.DataFrame(
            {
                "股票代號": [str(1000 + i) for i in range(n)],
                "營收YoY(%)": [50.0] * n,
                "EPS季別": ["2026Q1"] * n,
                "EPS本期": [2.0] * n,
                "EPSYoY_raw": [0.5] * n,
                "EPSYoY_顯示(%)": [50.0] * n,
            }
        ),
        pd.DataFrame(
            {
                "股票代號": [str(1000 + i) for i in range(n)],
                "營收YoY(%)": [50.0] * n,
            }
        ),
    )


def _make_get_or_fetch_mock(price_df, rev_df, eps_df):
    def side_effect(name, fetch_func, logger):
        if name == "price":
            return price_df
        if name == "revenue":
            return rev_df
        if name == "eps":
            return eps_df
        return pd.DataFrame()

    return side_effect


def _run_with_filter(strong_filter_result: pd.DataFrame, top_n: int, n_input: int = 50) -> pd.DataFrame:
    """跑一次 _run_selection_only、套用指定的 strong_filter 結果 + top_n"""
    cfg = StrategyConfig()
    cfg.top_n_for_tech = top_n
    cfg.use_enhanced_score = True

    price_df = _make_price_df(n_input)
    eps_df, rev_df = _make_rev_eps_df(n_input)

    logger = _MockLogger()
    with patch.object(
        pipeline,
        "get_or_fetch",
        side_effect=_make_get_or_fetch_mock(price_df, rev_df, eps_df),
    ), patch.object(
        pipeline, "_fetch_finmind_dividend", return_value=pd.DataFrame()
    ), patch.object(
        pipeline,
        "calculate_multi_factor_score",
        side_effect=lambda x, cfg: x.assign(Score=1.0),
    ), patch.object(
        pipeline,
        "_apply_strong_filter",
        return_value=strong_filter_result,
    ):
        return pipeline._run_selection_only(cfg, logger), logger


# ==========================================================
# 主測試
# ==========================================================


def test_強勢股過濾後大於_topn_會被限縮():
    """【核心 bug 修正】50 檔過濾後 + top_n=20 → 結果應該只剩 20 檔"""
    strong_result = _make_price_df(50)
    result, logger = _run_with_filter(strong_result, top_n=20, n_input=50)

    assert len(result) == 20, f"應被限縮到 20 檔、實際 {len(result)} 檔"
    # log 應該有「TopN 限縮」訊息
    assert any("TopN 限縮" in m for m in logger.messages), "應 log TopN 限縮訊息"


def test_強勢股過濾後小於_topn_不變():
    """10 檔過濾後 + top_n=20 → 結果仍是 10 檔（沒有 top_n 限制效果）"""
    strong_result = _make_price_df(10)
    result, logger = _run_with_filter(strong_result, top_n=20, n_input=50)

    assert len(result) == 10, f"應保持 10 檔、實際 {len(result)} 檔"
    # 不應該 log TopN 限縮
    assert not any("TopN 限縮" in m for m in logger.messages), "不該 log TopN 限縮"


def test_強勢股過濾後等於_topn_不變():
    """20 檔過濾後 + top_n=20 → 結果 20 檔、不 log 限縮"""
    strong_result = _make_price_df(20)
    result, logger = _run_with_filter(strong_result, top_n=20, n_input=50)

    assert len(result) == 20, f"應保持 20 檔、實際 {len(result)} 檔"
    assert not any("TopN 限縮" in m for m in logger.messages)


def test_強勢股過濾後無股票_fallback_仍套用_topn():
    """_apply_strong_filter fallback 回全部 50 檔 + top_n=20 → 結果仍是 20 檔"""
    # fallback 情境：_apply_strong_filter 過濾後 0 檔、return 原 df（50 檔）
    full_input = _make_price_df(50)
    result, logger = _run_with_filter(full_input, top_n=20, n_input=50)

    assert len(result) == 20, f"fallback 仍應被限縮到 20 檔、實際 {len(result)} 檔"


def test_topn_1_只留_1_檔():
    """極端值：top_n=1 → 結果只留 1 檔"""
    strong_result = _make_price_df(50)
    result, _ = _run_with_filter(strong_result, top_n=1, n_input=50)

    assert len(result) == 1, f"top_n=1 應只剩 1 檔、實際 {len(result)} 檔"


def test_結果維持_score_降序():
    """TopN 限縮後、應維持原本 Score 降序（前 N 高的保留）"""
    # 製造分數遞減的 50 檔
    strong_result = _make_price_df(50).assign(Score=[100 - i for i in range(50)])
    result, _ = _run_with_filter(strong_result, top_n=10, n_input=50)

    scores = result["Score"].tolist()
    # 應該是前 10 高的 = [100, 99, 98, ..., 91]
    assert scores == [100 - i for i in range(10)], f"應保留前 10 高分、實際 {scores}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])