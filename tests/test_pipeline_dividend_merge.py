"""
【v1.1.1+ Bug Fix】系統選股殖利率改用實際現金殖利率測試

William 2026-06-24 21:48 反映：
- 系統選股殖利率欄顯示 0.04%（估算：EPS × 0.7 / 股價）
- 應該顯示 1.54%（實際 GoodInfo 現金殖利率）
- 修法：run_pipeline 跟 manual 一樣合併 FinMind 股利資料、殖利率優先用 GoodInfo
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'source'))

import pandas as pd
import unittest
from unittest.mock import patch

from stocktool import pipeline
from stocktool.config import StrategyConfig


def _price_df():
    return pd.DataFrame({
        '股票代號': ['3490', '2330'],
        '公司名稱_來源': ['單井', '台積電'],
        '股價': [32.5, 600.0],
        '漲跌': [-0.9, 5.0],
        'data_date': ['2026-06-23', '2026-06-23'],
        '成交量_張': [675.0, 30000.0],
    })


def _rev_df():
    return pd.DataFrame({
        '股票代號': ['3490', '2330'],
        '營收YoY(%)': [50.0, 30.0],
    })


def _eps_df():
    return pd.DataFrame({
        '股票代號': ['3490', '2330'],
        'EPS季別': ['2026Q1', '2026Q1'],
        'EPS本期': [2.07, 10.0],
        'EPSYoY_raw': [4.76, 0.583],
        'EPSYoY_顯示(%)': [476.0, 58.3],
    })


class _MockLogger:
    def log(self, msg):
        pass


def _make_get_or_fetch_mock(price_df, rev_df, eps_df):
    """建立一個 get_or_fetch mock 根據 name 回傳對應 df"""
    def side_effect(name, fetch_func, logger):
        if name == 'price':
            return price_df
        if name == 'revenue':
            return rev_df
        if name == 'eps':
            return eps_df
        return fetch_func()
    return side_effect


class TestPipelineDividendMerge(unittest.TestCase):
    """【v1.1.1+】run_pipeline 合併 FinMind 股利資料"""

    def test_合併股利_殖利率用goodinfo(self):
        """run_pipeline 應該合併 FinMind 股利資料、殖利率優先用 GoodInfo"""
        cfg = StrategyConfig()
        cfg.use_enhanced_score = True

        price_df = _price_df()
        rev_df = _rev_df()
        eps_df = _eps_df()
        div_df = pd.DataFrame({
            '股票代號': ['3490'],
            f'{pd.Timestamp.now().year}現金殖利率_goodinfo': [1.54],
            f'{pd.Timestamp.now().year - 1}現金殖利率_goodinfo': [0.5],
        })

        with patch.object(pipeline, 'get_or_fetch',
                          side_effect=_make_get_or_fetch_mock(price_df, rev_df, eps_df)), \
             patch.object(pipeline, '_fetch_finmind_dividend', return_value=div_df), \
             patch.object(pipeline, 'calculate_multi_factor_score',
                          side_effect=lambda x, cfg: x.assign(Score=1.0)), \
             patch.object(pipeline, '_apply_strong_filter', side_effect=lambda x, cfg, logger: x):
            result = pipeline._run_selection_only(cfg, _MockLogger())

        row_3490 = result[result['股票代號'].astype(str) == '3490']
        self.assertFalse(row_3490.empty, "Should have 3490 row")
        yld = row_3490['殖利率(估)'].iloc[0]
        # GoodInfo 1.54% = 0.0154（小數）
        self.assertAlmostEqual(float(yld), 0.0154, places=4,
            msg=f"3490 殖利率應該用 GoodInfo 1.54% = 0.0154，實際: {yld}")

    def test_沒股利資料_走估算(self):
        """FinMind DB 沒資料時、殖利率走估算（EPS × 0.7 / 股價）"""
        cfg = StrategyConfig()
        cfg.use_enhanced_score = True

        price_df = _price_df()
        rev_df = _rev_df()
        eps_df = _eps_df()

        with patch.object(pipeline, 'get_or_fetch',
                          side_effect=_make_get_or_fetch_mock(price_df, rev_df, eps_df)), \
             patch.object(pipeline, '_fetch_finmind_dividend', return_value=pd.DataFrame()), \
             patch.object(pipeline, 'calculate_multi_factor_score',
                          side_effect=lambda x, cfg: x.assign(Score=1.0)), \
             patch.object(pipeline, '_apply_strong_filter', side_effect=lambda x, cfg, logger: x):
            result = pipeline._run_selection_only(cfg, _MockLogger())

        row_3490 = result[result['股票代號'].astype(str) == '3490']
        self.assertFalse(row_3490.empty)
        yld = row_3490['殖利率(估)'].iloc[0]
        # 估算 = 2.07 × 0.7 / 32.5 = 0.04458
        expected = 2.07 * 0.7 / 32.5
        self.assertAlmostEqual(float(yld), expected, places=4,
            msg=f"3490 殖利率應該走估算 {expected}，實際: {yld}")


if __name__ == '__main__':
    unittest.main()
