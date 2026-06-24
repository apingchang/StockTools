"""
【v1.1.1+ Bug Fix】cache 大部分 NaN 時也要強制重抓

William 2026-06-24 22:24 反映：系統選股 EPSYoY 全是 "--"
- 根因：上次 cache 寫入時、Q1 fallback 已修、但 cache 還是舊的「全 NaN」狀態
- 原本 cache 驗證只檢查「全部 NaN」才重抓，沒涵蓋「大部分 NaN」的情況

【修法】cache 驗證加入 NaN 比例 > 50% → 強制重抓
（這樣下次 App 啟動遇到舊 cache、會自動重抓一次讓 GoodInfo 覆蓋）
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'source'))

import unittest
import tempfile
from datetime import datetime
from unittest.mock import patch, MagicMock

import pandas as pd

from stocktool import cache


class TestCacheEpsNanThreshold(unittest.TestCase):
    """【v1.1.1+】cache 大部分 NaN → 強制重抓"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._orig = cache.get_cache_file
        cache.get_cache_file = lambda name: os.path.join(self.tmpdir, f"{name}.xlsx")

    def tearDown(self):
        cache.get_cache_file = self._orig
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_cache(self, n_total, n_yoy):
        """寫入 cache：n_total 總筆數、n_yoy 筆有 YoY"""
        df = pd.DataFrame({
            '股票代號': [str(1000 + i) for i in range(n_total)],
            'EPS季別': ['2026Q1'] * n_total,
            'EPS本期': [1.0] * n_total,
            'EPSYoY_raw': [None] * n_total,
            'EPSYoY_顯示(%)': [None] * n_total,
        })
        # 設定前 n_yoy 筆有 YoY
        for i in range(n_yoy):
            df.at[i, 'EPSYoY_raw'] = 0.5
            df.at[i, 'EPSYoY_顯示(%)'] = 50.0

        path = os.path.join(self.tmpdir, 'eps.xlsx')
        today = datetime.now().strftime('%Y-%m-%d')
        time_str = datetime.now().strftime('%H:%M:%S')
        meta = pd.DataFrame({'last_update': [today], 'last_update_time': [time_str]})
        with pd.ExcelWriter(path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='data', index=False)
            meta.to_excel(writer, sheet_name='meta', index=False)
        return path

    def test_cache_全部NaN_強制重抓(self):
        """全 NaN → 強制重抓（既有行為）"""
        self._write_cache(n_total=10, n_yoy=0)

        logger = MagicMock()
        new_df = pd.DataFrame({
            '股票代號': ['1000'],
            'EPS季別': ['2026Q1'],
            'EPS本期': [1.0],
            'EPSYoY_raw': [0.5],
            'EPSYoY_顯示(%)': [50.0],
        })
        fetch_func = MagicMock(return_value=new_df)

        with patch.object(cache, 'save_cache'):
            result = cache.get_or_fetch('eps', fetch_func, logger)

        fetch_func.assert_called_once()
        self.assertEqual(result['EPSYoY_顯示(%)'].iloc[0], 50.0)

    def test_cache_大部分NaN_強制重抓(self):
        """60% NaN → 強制重抓（新行為、v1.1.1+）"""
        self._write_cache(n_total=10, n_yoy=4)  # 60% NaN

        logger = MagicMock()
        new_df = pd.DataFrame({
            '股票代號': ['1000'],
            'EPS季別': ['2026Q1'],
            'EPS本期': [1.0],
            'EPSYoY_raw': [0.5],
            'EPSYoY_顯示(%)': [50.0],
        })
        fetch_func = MagicMock(return_value=new_df)

        with patch.object(cache, 'save_cache'):
            result = cache.get_or_fetch('eps', fetch_func, logger)

        fetch_func.assert_called_once()
        self.assertEqual(result['EPSYoY_顯示(%)'].iloc[0], 50.0)

    def test_cache_正常NaN比例_不重抓(self):
        """30% NaN（合理、就是部分小股沒 GoodInfo）→ 不重抓"""
        self._write_cache(n_total=10, n_yoy=7)  # 30% NaN

        logger = MagicMock()
        fetch_func = MagicMock()

        with patch.object(cache, 'save_cache'):
            result = cache.get_or_fetch('eps', fetch_func, logger)

        fetch_func.assert_not_called()
        self.assertEqual(result['EPSYoY_顯示(%)'].iloc[0], 50.0)


if __name__ == '__main__':
    unittest.main()
