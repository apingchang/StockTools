"""
【V0.9.5-goodinfo6】2026/06/26 重新抓 GoodInfo 檔案、新版檔名 + Divided10Y 是純現金

William 2026-06-26 11:22 重新抓了 goodinfo 歷史股利/殖利率檔、放到：
  /home/aping/.openclaw/workspace/股神/.tmp/goodinfo_export/dividend/

新版 vs 舊版差異：
  1. 價位帶擴大：P50U → P55U (923 檔)、P20-50 → P20-55 (836 檔)
  2. 檔名怪：P55U 用 Dividend10Y、P20-55/P20L 用 Divided10Y（e 跟 i 顛倒）
  3. Divided10Y 已經是「純現金股利」（不是合計）、cash 直接拿
  4. P55U/P20-55 的 ShareRate 內容跟 DividendRate 一模一樣（GoodInfo bug）
     → 跳過、不寫入 share_yield_pct

這個 test 守住：
  - import_dividend 知道 Divided10Y 是純現金（cash 直接拿、不扣 stock）
  - import_yield_rate 知道 P55U/P20-55 的 ShareRate 是 bug、要跳過
  - load_goodinfo 知道新檔名前綴
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'source'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import unittest
from unittest.mock import patch, MagicMock
import pandas as pd

import import_goodinfo_history as ig


class TestLoadGoodinfoV095g6NewFilenames(unittest.TestCase):
    """【V0.9.5-goodinfo6】新檔名 P55U/P20-55 + Divided10Y 支援"""

    def test_FILE_PREFIX_MAP_P55U_uses_Dividend10Y(self):
        """P55U 的現金股利檔用 Dividend10Y（注意沒 p、不是 P50Up）"""
        # 搜尋所有以 P55U 為 prefix 的 key、應該至少有 Dividend10Y
        p55u_keys = [k for k in ig.FILE_PREFIX_MAP.keys() if k[1] == "P55U"]
        dividends = [k for k in p55u_keys if "Dividend" in k[2]]
        self.assertGreater(len(dividends), 0,
            msg=f"P55U 應該至少有 Dividend10Y 對應、實際: {p55u_keys}")
        # 確認 Dividend10Y（不是 Divided10Y）
        self.assertIn(("dividend", "P55U", "Dividend10Y"), ig.FILE_PREFIX_MAP,
            msg="P55U 應該用 Dividend10Y（不是 P55Up）")

    def test_FILE_PREFIX_MAP_P20_55_uses_Divided10Y(self):
        """P20-55 跟 P20L 用 Divided10Y（注意 e 跟 i 顛倒）"""
        self.assertIn(("dividend", "P20-55", "Divided10Y"), ig.FILE_PREFIX_MAP,
            msg="P20-55 應該用 Divided10Y（注意 e 跟 i 顛倒）")
        self.assertIn(("dividend", "P20L", "Divided10Y"), ig.FILE_PREFIX_MAP,
            msg="P20L 應該用 Divided10Y")

    def test_old_P50U_and_P20_50_should_not_be_in_map(self):
        """舊版 P50U / P20-50 應該已經從 FILE_PREFIX_MAP 拿掉"""
        for old_key in [("dividend", "P50U", "Dividend10Y"),
                        ("dividend", "P20-50", "Dividend10Y")]:
            self.assertNotIn(old_key, ig.FILE_PREFIX_MAP,
                msg=f"舊版前綴 {old_key} 應該從 FILE_PREFIX_MAP 拿掉")


class TestImportDividendV095g6CashIsPure(unittest.TestCase):
    """【V0.9.5-goodinfo6】Divided10Y 是純現金、cash 直接拿（不扣 stock）"""

    def test_dividend_cash_equals_divided10y_directly(self):
        """驗證 import_dividend 把 Divided10Y 值直接寫入 cash、不扣 stock

        證據：2442 2025 Divided10Y=0.079、Share10Y=0.158
              預期 cash=0.079（純現金）、stock=0.158（股票股利）
              舊版錯誤算法 cash = 0.079 - 0.158 = -0.079（負）
        """
        # 模擬 load_goodinfo 回傳固定的 DataFrame
        mock_divided = pd.DataFrame({
            "代號": ["2442", "3490"],
            "2017發放年度": [0.0, 0.25],
            "2018發放年度": [0.0, 0.5],
            "2025發放年度": [0.079, 1.0],   # 重點測試
            "2026發放年度": [2.0, 0.5],
        })
        mock_share = pd.DataFrame({
            "代號": ["2442", "3490"],
            "2017發放年度": [0.0, 0.25],
            "2018發放年度": [0.0, 0.0],
            "2025發放年度": [0.158, 0.0],   # 2442 2025 股票 0.158
            "2026發放年度": [0.7, 0.0],
        })

        with patch.object(ig, "load_goodinfo") as mock_load:
            mock_load.side_effect = lambda folder, sm: (
                mock_divided if folder == "dividend" and "Divided" in str(sm)
                else mock_share
            )
            # 讓 load_goodinfo 看 suffix_map 內容決定回傳哪個
            def smart_load(folder, sm):
                # sm 的 value 是 "_Divided10Y" 還是 "_Share10Y"
                if "_Divided10Y" in str(sm):
                    return mock_divided
                return mock_share
            mock_load.side_effect = smart_load

            # 用一個 spy 收集 import 結果（drill into import_dividend）
            # 因為 import_dividend 內部不暴露結果、只寫 DB、所以用 dry=True 預覽
            import io
            from contextlib import redirect_stdout
            f = io.StringIO()
            with redirect_stdout(f):
                ig.import_dividend(dry=True)
            output = f.getvalue()

        # 預覽輸出應該有 2442 2025 cash≈0.08（純現金、0.079 四捨五入顯示 0.08）
        # 不該有負 cash
        import re
        m = re.search(r'2442 2025:\s+cash=([-\d.]+),\s+stock=([-\d.]+)', output)
        self.assertIsNotNone(m,
            msg=f"找不到 2442 2025 預覽：\n{output[:2000]}")
        cash = float(m.group(1))
        stock = float(m.group(2))
        self.assertAlmostEqual(cash, 0.08, places=2,
            msg=f"2442 2025 cash 應該 ≈0.08 (純現金 0.079)、實際 {cash}")
        self.assertAlmostEqual(stock, 0.16, places=2,
            msg=f"2442 2025 stock 應該 ≈0.16、實際 {stock}")
        self.assertGreaterEqual(cash, 0,
            msg=f"2442 2025 cash 不該是負的、實際 {cash}")


class TestImportYieldRateV095g6SkipBadShareRate(unittest.TestCase):
    """【V0.9.5-goodinfo6】跳過 P55U/P20-55 的 bug ShareRate"""

    def test_BAD_SHARE_RATE_GROUPS_包含_P55U_跟_P20_55(self):
        """哪些 ShareRate 是 GoodInfo bug 應該被跳過"""
        self.assertIn("P55U", ig.BAD_SHARE_RATE_GROUPS)
        self.assertIn("P20-55", ig.BAD_SHARE_RATE_GROUPS)
        # P20L 是好的、不能跳過
        self.assertNotIn("P20L", ig.BAD_SHARE_RATE_GROUPS)

    def test_import_yield_rate跳過P55U_P20_55_ShareRate(self):
        """import_yield_rate 應該印出跳過 P55U_ShareRate / P20-55_ShareRate 警告"""
        # 製造假的 .xls 路徑指向 P55U/P20-55 ShareRate → 確認被跳過
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            # 製造假的 ShareRate 檔給 P55U/P20-55
            for prefix in ["P55U", "P20-55"]:
                bad_path = os.path.join(tmp, f"{prefix}_ShareRate.xls")
                with open(bad_path, "w") as f:
                    f.write("<html><body>fake</body></html>")

            # mock EXPORT_DIR 指向 tmp
            with patch.object(ig, "EXPORT_DIR", type(ig.EXPORT_DIR)(tmp)):
                import io
                from contextlib import redirect_stdout
                f = io.StringIO()
                with redirect_stdout(f):
                    try:
                        ig.import_yield_rate(dry=True)
                    except Exception:
                        pass  # 假檔可能 pandas 讀失敗、無所謂
                output = f.getvalue()

        # 應該印「跳過 P55U_ShareRate」「跳過 P20-55_ShareRate」
        self.assertIn("P55U_ShareRate", output,
            msg=f"應該印跳過 P55U_ShareRate 警告：\n{output[:2000]}")
        self.assertIn("P20-55_ShareRate", output,
            msg=f"應該印跳過 P20-55_ShareRate 警告：\n{output[:2000]}")


class TestDividendDBAfterReimport(unittest.TestCase):
    """【V0.9.5-goodinfo6】DB 內 2442 2025 cash 應該是 0.079（純現金）、stock 0.158"""

    @classmethod
    def setUpClass(cls):
        cls.db_path = os.path.join(
            os.path.dirname(__file__), '..', 'source', 'dividend_history.db'
        )
        if not os.path.exists(cls.db_path):
            raise unittest.SkipTest("找不到 dividend_history.db")

    def test_2442_2025_cash_0_079_stock_0_158(self):
        """2442 2025 cash=0.079、stock=0.158、不是負的"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""SELECT cash, stock FROM dividend_history
                       WHERE stock_id='2442' AND year=2025""")
        row = cur.fetchone()
        conn.close()
        if row is None:
            self.skipTest("2442 2025 沒資料")
        cash, stock = row
        self.assertAlmostEqual(cash, 0.079, places=3,
            msg=f"2442 2025 cash 應該 ≈0.079、實際 {cash}")
        self.assertAlmostEqual(stock, 0.158, places=3,
            msg=f"2442 2025 stock 應該 ≈0.158、實際 {stock}")
        self.assertGreaterEqual(cash, 0,
            msg=f"2442 2025 cash 不該是負的、實際 {cash}")


if __name__ == '__main__':
    unittest.main()
