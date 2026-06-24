"""
【v1.1.1+ Bug Fix】3490 EPSYoY 算成 4040% 的陷阱測試

William 2026-06-24 21:48 反映：
- 3490 系統選股結果顯示 EPSYoY = 4040%
- 實際 GoodInfo 12QEPSRate 是 476%
- 根因：本期是 Q1 (2026Q1)、但 DB 沒有 2025Q1、fallback 用 2025Q4 全年 EPS = 0.05
        (2.07 - 0.05) / 0.05 = 40.4 = 4040%
- Q1 vs 全年 是錯誤的比較、數字會爆炸

【修法】
1. fetch_eps_latest: Q1/Q2/Q3 不適用 Q4 全年 fallback（只有 Q4 才適用）
2. cache validation: 偵測可疑 YoY（>500% 或 <-99%）→ 強制重抓一次讓 GoodInfo 覆蓋
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'source'))

import pandas as pd
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from stocktool import fetch_market, cache


def _make_eps_history_db():
    """建立 mock eps_history.db：模擬 3490 沒有 2025Q1 但有 2025Q4 + 2024Q4"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute('''CREATE TABLE eps_history (
        stock_id TEXT, year INTEGER, quarter INTEGER, eps REAL, source TEXT,
        fetched_at TEXT DEFAULT (datetime('now','localtime')),
        PRIMARY KEY (stock_id, year, quarter)
    )''')
    # 3490: 只有 Q4 全年（沒 Q1）
    c.execute("INSERT INTO eps_history VALUES ('3490', 2025, 4, 0.05, 'goodinfo', '2026-06-16')")
    c.execute("INSERT INTO eps_history VALUES ('3490', 2026, 1, 2.07, 'twse_csv', '2026-06-24')")
    # 為了 Q4 fallback test
    c.execute("INSERT INTO eps_history VALUES ('3490', 2024, 4, 0.41, 'goodinfo', '2026-06-16')")
    conn.commit()
    conn.close()
    return path


class TestEpsYoYQ4FallbackBug(unittest.TestCase):
    """【v1.1.1+】Q1/Q2/Q3 不適用 Q4 全年 EPS fallback"""

    def test_本期q1不適用q4全年_fallback(self):
        """3490 本期 Q1：CSV 無 2025Q1 → 不該 fallback 用 2025Q4 → YoY 留空等 GoodInfo 覆蓋"""
        db_path = _make_eps_history_db()
        cfg = MagicMock()
        cfg.eps_history_db = db_path

        # Mock CSV 只有本期 2026Q1
        eps_csv = pd.DataFrame({
            '公司代號': ['3490'],
            '年度': [115],  # 民國年 115 = 西元 2026
            '季別': [1],
            '基本每股盈餘(元)': [2.07],
        })

        session = MagicMock()
        session.get.return_value.json.return_value = {
            "公司代號": "3490", "年度": "115", "季別": "1", "基本每股盈餘(元)": "2.07"
        }
        session.get.return_value.raise_for_status = MagicMock()

        with patch.object(fetch_market, 'fetch_csv_requests', return_value=eps_csv), \
             patch.object(fetch_market, '_load_goodinfo_12q_epsrate', return_value={}):  # 沒 GoodInfo
            result = fetch_market.fetch_eps_latest(session, cfg)

        # 3490 應該 YoY = NA（不該用 Q4 全年 fallback）
        row_3490 = result[result['股票代號'] == '3490']
        if not row_3490.empty:
            self.assertTrue(pd.isna(row_3490['EPSYoY_顯示(%)'].iloc[0]),
                            f"Q1 不該 fallback 到 Q4 全年，YoY 應為 NA，實際: {row_3490['EPSYoY_顯示(%)'].iloc[0]}")

    def test_本期q4適用q4全年_fallback(self):
        """3490 本期 Q4：CSV 無去年 Q4 → 可以 fallback 用去年 Q4 全年 → YoY 正常算"""
        db_path = _make_eps_history_db()
        cfg = MagicMock()
        cfg.eps_history_db = db_path

        # Mock CSV 有 2025Q4 (本期) 但沒有 2024Q4
        eps_csv = pd.DataFrame({
            '公司代號': ['3490'],
            '年度': [114],  # 民國年 114 = 西元 2025
            '季別': [4],
            '基本每股盈餘(元)': [0.94],  # 2025Q4 全年
        })

        session = MagicMock()
        session.get.return_value.json.return_value = {
            "公司代號": "3490", "年度": "114", "季別": "4", "基本每股盈餘(元)": "0.94"
        }
        session.get.return_value.raise_for_status = MagicMock()

        with patch.object(fetch_market, 'fetch_csv_requests', return_value=eps_csv), \
             patch.object(fetch_market, '_load_goodinfo_12q_epsrate', return_value={}):
            result = fetch_market.fetch_eps_latest(session, cfg)

        # 3490 應該 YoY = (0.94 - 0.41) / 0.41 = 1.29 = 129%
        # 去年 Q4 = 0.41（2024 Q4 全年）
        row_3490 = result[result['股票代號'] == '3490']
        if not row_3490.empty:
            self.assertFalse(pd.isna(row_3490['EPSYoY_顯示(%)'].iloc[0]),
                             f"Q4 應該可以 fallback 到去年 Q4 全年 EPS")


class TestCacheEpsYoYValidation(unittest.TestCase):
    """【v1.1.1+】cache 偵測可疑 YoY、強制重抓"""

    def setUp(self):
        """準備一個寫好可疑 cache 的 mock dir"""
        self.tmpdir = tempfile.mkdtemp()
        # patch 讓 cache.get_cache_file 回傳 tmpdir 下的路徑
        self._orig_get_cache_file = cache.get_cache_file
        cache.get_cache_file = lambda name: os.path.join(self.tmpdir, f"{name}.xlsx")

    def tearDown(self):
        cache.get_cache_file = self._orig_get_cache_file
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_cache(self, yoy_value: float):
        """寫一份 EPS cache、YoY 設定為指定值"""
        df = pd.DataFrame({
            '股票代號': ['3490'],
            'EPS季別': ['2026Q1'],
            'EPS本期': [2.07],
            'EPSYoY_raw': [yoy_value / 100],
            'EPSYoY_顯示(%)': [yoy_value],
        })
        path = os.path.join(self.tmpdir, 'eps.xlsx')
        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        time_str = datetime.now().strftime('%H:%M:%S')
        meta = pd.DataFrame({'last_update': [today], 'last_update_time': [time_str]})
        with pd.ExcelWriter(path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='data', index=False)
            meta.to_excel(writer, sheet_name='meta', index=False)
        return path

    def test_cache_可疑yoy太高_強制重抓(self):
        """cache 裡 YoY > 500% → 應該觸發強制重抓"""
        self._write_cache(4040.0)

        logger = MagicMock()
        new_df = pd.DataFrame({
            '股票代號': ['3490'],
            'EPS季別': ['2026Q1'],
            'EPS本期': [2.07],
            'EPSYoY_raw': [4.76],
            'EPSYoY_顯示(%)': [476.0],
        })
        fetch_func = MagicMock(return_value=new_df)

        with patch.object(cache, 'save_cache'):
            result = cache.get_or_fetch('eps', fetch_func, logger)

        fetch_func.assert_called_once()
        self.assertEqual(result['EPSYoY_顯示(%)'].iloc[0], 476.0,
                         f"應該被重抓為 476，實際: {result['EPSYoY_顯示(%)'].iloc[0]}")

    def test_cache_正常yoy_不重抓(self):
        """cache 裡 YoY 在合理範圍 → 不重抓"""
        self._write_cache(58.3)

        logger = MagicMock()
        fetch_func = MagicMock()

        with patch.object(cache, 'save_cache'):
            result = cache.get_or_fetch('eps', fetch_func, logger)

        fetch_func.assert_not_called()
        self.assertEqual(result['EPSYoY_顯示(%)'].iloc[0], 58.3)

    def test_cache_負yoy太小_強制重抓(self):
        """cache 裡 YoY < -99% → 應該觸發強制重抓"""
        self._write_cache(-150.0)

        logger = MagicMock()
        new_df = pd.DataFrame({
            '股票代號': ['3490'],
            'EPS季別': ['2026Q1'],
            'EPS本期': [2.07],
            'EPSYoY_raw': [-1.29],
            'EPSYoY_顯示(%)': [-129.0],
        })
        fetch_func = MagicMock(return_value=new_df)

        with patch.object(cache, 'save_cache'):
            result = cache.get_or_fetch('eps', fetch_func, logger)

        fetch_func.assert_called_once()
        self.assertEqual(result['EPSYoY_顯示(%)'].iloc[0], -129.0)


if __name__ == '__main__':
    unittest.main()
