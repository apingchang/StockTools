"""
【v1.1.1+ Bug Fix】lxml 缺失時 GoodInfo 12QEPSRate 完全載入失敗測試

William 2026-06-24 22:35 反映：系統選股 EPSYoY 整欄全是 --
（即使已修 Q1 fallback 跟 cache 驗證）

【根因】
pd.read_html() 需要 lxml 才能解析 HTML 偽裝的 .xls 檔。
如果環境沒裝 lxml：
- pd.read_html() 對每個檔案 raise ImportError
- _load_goodinfo_12q_epsrate() 全部 fail → 回傳 0 檔
- GoodInfo 覆蓋邏輯沒資料可用
- 所有 EPSYoY 變 NaN → 顯示 --

【修法】
1. requirements.txt 加入 lxml>=4.9
2. _load_goodinfo_12q_epsrate() 開頭先 import lxml 檢查、
   缺 lxml 就印 friendly error message、提早 return {}
3. 加 test 守住「沒 lxml 時早退」+「有 lxml 時正常載入」
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'source'))

import unittest
from unittest.mock import patch

from stocktool import fetch_market


class TestLoadGoodinfoLxmlCheck(unittest.TestCase):
    """【v1.1.1+】lxml 缺失時、_load_goodinfo_12q_epsrate 早退"""

    def test_沒裝lxml_早退且不crash(self):
        """模擬 lxml 沒裝：函式應該早退 return {} 而不是 crash"""
        # Mock lxml import 失敗
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == 'lxml' or name.startswith('lxml.'):
                raise ImportError(f"No module named '{name}'")
            return real_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=mock_import):
            # 不傳 goodinfo_dir 讓它用預設路徑（存在的也 OK）
            result = fetch_market._load_goodinfo_12q_epsrate()

        self.assertEqual(result, {},
            msg="沒裝 lxml 時、應該早退 return {} 而不是 crash")

    def test_有裝lxml_正常載入(self):
        """lxml 存在時應該能正常載入（如果有 GoodInfo 檔的話）"""
        import os
        from pathlib import Path
        home = Path.home()
        goodinfo_dir = home / ".openclaw" / "workspace" / "股神" / ".tmp" / "goodinfo_export" / "eps"
        if not goodinfo_dir.exists():
            self.skipTest(f"找不到 GoodInfo 檔案目錄：{goodinfo_dir}")

        result = fetch_market._load_goodinfo_12q_epsrate()
        # 應該至少載入一些股票（有檔案的情況下）
        self.assertGreater(len(result), 0,
            msg=f"lxml 有裝 + 檔案存在 → 應該載入 >0 檔，實際: {len(result)}")


if __name__ == '__main__':
    unittest.main()
