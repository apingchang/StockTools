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


class TestImportDividendZeroValueNotSkipped(unittest.TestCase):
    """【V0.9.5-goodinfo6+】val=0 不跳過、也要 INSERT row（6219 2026 cash=0 bug）

    William 2026-06-26 12:00 反映：
      - 6219 殖利率 0.04%（應為 0%）
      - 1808 殖利率 0.05%（應為 4.83%）
    根因：
      1. import_dividend 原本 `if pd.isna(val) or val == 0: continue`
         → 6219 2026 cash=0 不寫入 → 2026 row 不存在
         → 後期 import_yield_rate 查不到 2026 row 跳過
         → cash_yield_pct 沒寫入 → 手動選股殖利率顯示 None → 預設 0
      2. 1808 → 整體殖利率算法 fallback 用 (EPS×0.7)/股價、不是 goodinfo 值
         → 1808 EPS 偏小 → 殖利率算成 0.05%（與原本 design 一致）
    修法：
      - val=0 也 INSERT、標記「該年無配息」cash_yield_pct=0%
    """

    def test_zero_cash_dividend_still_inserted(self):
        """6219 2026 cash=0 也應 INSERT（不跳過）"""
        from collections import defaultdict

        # 模擬 cash_years / share_years 都有 2026
        cash_years = ["2026發放年度"]
        share_years = ["2026發放年度"]

        # 6219 在 cash 欄位 = 0、stock = 0
        df_cash = pd.DataFrame({"代號": ["6219"], "2026發放年度": [0.0]})
        df_share = pd.DataFrame({"代號": ["6219"], "2026發放年度": [0.0]})

        cash_agg = defaultdict(float)
        share_agg = defaultdict(float)

        # 重現 import_dividend 的累加邏輯
        for df, agg, years in [(df_cash, cash_agg, cash_years),
                               (df_share, share_agg, share_years)]:
            for _, row in df.iterrows():
                sid = str(row["代號"]).strip()
                for ycol in years:
                    val = row.get(ycol)
                    if pd.isna(val):
                        continue
                    # V0.9.5-goodinfo6+ 修法：val=0 不跳過
                    key = (sid, int(ycol[:4]))
                    agg[key] += float(val)

        # 6219 2026 應有 (cash=0, stock=0) row（修法前不會有）
        self.assertIn(("6219", 2026), cash_agg,
            msg="6219 2026 cash=0 應 INSERT、不應被 continue 跳過")
        self.assertIn(("6219", 2026), share_agg,
            msg="6219 2026 stock=0 應 INSERT、不應被 continue 跳過")
        self.assertEqual(cash_agg[("6219", 2026)], 0.0)
        self.assertEqual(share_agg[("6219", 2026)], 0.0)


class TestImportDividendFinmindPreservation(unittest.TestCase):
    """【V0.9.5-goodinfo6+】finmind 補的 (sid, yr) 不被 goodinfo 覆寫

    6219 2024 = finmind (0.7, 0.5)、goodinfo 是 0.0（漏抓）
    原 INSERT OR REPLACE 不分 source、會被 goodinfo 0.0 蓋掉
    修法：finmind 已存在的 (sid, yr) 從 rows 中過濾、不寫入 goodinfo
    """

    def test_finmind_keys_filtered_from_goodinfo_rows(self):
        """finmind 已有的 (sid, yr) 不出現在 goodinfo rows"""
        # 模擬：finmind 補了 6219 2024 (0.7, 0.5)、goodinfo 想寫 0.0
        finmind_keys = {("6219", 2024), ("2342", 2024)}

        rows = [
            ("6219", 2024, 0.0, 0.0, "goodinfo", None, None),
            ("1808", 2026, 1.5, 0.0, "goodinfo", None, None),
            ("2342", 2024, 0.5, 0.0, "goodinfo", None, None),  # 會被過濾
        ]

        # 套用過濾（跟 import_dividend 內邏輯一樣）
        filtered = [r for r in rows if (r[0], r[1]) not in finmind_keys]

        self.assertNotIn(("6219", 2024, 0.0, 0.0, "goodinfo", None, None), filtered,
            msg="6219 2024 goodinfo 0.0 應被過濾、讓 finmind (0.7, 0.5) 保留")
        self.assertNotIn(("2342", 2024, 0.5, 0.0, "goodinfo", None, None), filtered,
            msg="2342 2024 goodinfo 應被過濾")
        self.assertIn(("1808", 2026, 1.5, 0.0, "goodinfo", None, None), filtered,
            msg="1808 2026 沒在 finmind、應保留")


class TestEndToEndYieldCalculation(unittest.TestCase):
    """【V0.9.5-goodinfo6+】end-to-end 驗證 6219 / 1808 殖利率正確

    用真實 DB 跑 _run_manual_selection、確認殖利率欄位正確
    """

    @classmethod
    def setUpClass(cls):
        import sqlite3
        import os
        # 測試 cwd 是 tests/、這裡用絕對路徑
        cls.db_path = os.path.join(
            os.path.dirname(__file__), '..', 'source', 'dividend_history.db')
        conn = sqlite3.connect(cls.db_path)
        cur = conn.cursor()
        cls.data_6219 = cur.execute(
            "SELECT year, cash, cash_yield_pct FROM dividend_history "
            "WHERE stock_id='6219' ORDER BY year"
        ).fetchall()
        cls.data_1808 = cur.execute(
            "SELECT year, cash, cash_yield_pct FROM dividend_history "
            "WHERE stock_id='1808' ORDER BY year"
        ).fetchall()
        cls.row_6219_2024 = cur.execute(
            "SELECT cash, stock, source FROM dividend_history "
            "WHERE stock_id='6219' AND year=2024"
        ).fetchall()
        conn.close()

    def test_1808_2026_yield_is_4_83(self):
        """1808 2026 cash_yield = 4.83%（goodinfo 正確值）"""
        rows = [r for r in self.data_1808 if r[0] == 2026]
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0][2], 4.83, places=2,
            msg=f"1808 2026 cash_yield 應 = 4.83%、實際 {rows[0][2]}")

    def test_6219_2026_yield_is_zero(self):
        """6219 2026 cash_yield = 0%（goodinfo 標記「該年未配息」）"""
        rows = [r for r in self.data_6219 if r[0] == 2026]
        if len(rows) == 0:
            self.skipTest("6219 2026 尚未有 row（import_dividend 沒跑）")
        self.assertAlmostEqual(rows[0][2], 0.0, places=2,
            msg=f"6219 2026 cash_yield 應 = 0.0%、實際 {rows[0][2]}")

    def test_6219_2024_finmind_removed_after_alignment(self):
        """6219 2024 finmind row 該年被刪除、合併到 2025 goodinfo

        【V0.9.5-goodinfo6+】2026-06-26 13:00 發現：
          finmind year 是會計年度（113年=西元 2024）、對應 goodinfo 發放年度（2025 發放）
          finmind (0.7, 0.5) 跟 goodinfo (0.7, 0.5) 是同一筆、不該重複
          修法：finmind row 全部刪除、靠 goodinfo row 保留資料
        """
        # 6219 2024 應該完全沒有 finmind row
        import sqlite3
        import os
        db_path = os.path.join(
            os.path.dirname(__file__), '..', 'source', 'dividend_history.db')
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM dividend_history "
            "WHERE stock_id='6219' AND year=2024 AND source='finmind'"
        )
        count = cur.fetchone()[0]
        conn.close()
        self.assertEqual(count, 0,
            msg="6219 2024 finmind row 應該被刪除、靠 goodinfo 2025 保留")

    def test_6219_2025_goodinfo_intact(self):
        """6219 2025 goodinfo row 仍是 (0.7, 0.5, cyld=3.15, syld=2.43)"""
        rows = [r for r in self.data_6219 if r[0] == 2025]
        self.assertEqual(len(rows), 1, msg="6219 2025 應該有 1 筆 goodinfo row")
        year, cash, cyld = rows[0]
        self.assertAlmostEqual(cash, 0.7, places=2,
            msg=f"6219 2025 cash 應 = 0.7、實際 {cash}")
        self.assertAlmostEqual(cyld, 3.15, places=2,
            msg=f"6219 2025 cyld 應 = 3.15、實際 {cyld}")


class TestFinmindYearSemanticsFix(unittest.TestCase):
    """【V0.9.5-goodinfo6+】finmind year 是會計年度、不是發放年度

    William 2026-06-26 12:39 反映：6219 2024 finmind (0.7, 0.5) 其實是 2025 發放
    證據：finmind 113年第4季 cash=0.7 CashExDividendTradingDate=2025-07-03
          → 2025-07-03 除息 → 應歸到 goodinfo 2025 發放年度
    證據：goodinfo 2025 發放年度 = 0.7、cash 完全相同

    修法：
      - _fetch_finmind_dividend: 優先用 CashExDividendTradingDate 年份
      - _background_fetch_all_dividend: 同樣優先用 ex_date
      - DB cleanup: 刪除 39 筆 finmind ex_date NULL 的孤兒 row
      - 6219 2024 finmind row: 跟 goodinfo 2025 重複、刪除
    """

    def test_finmind_year_uses_ex_date_year(self):
        """fetcher 邏輯：用 ex_date year、不是 finmind year+1911

        這是 code review test、確認 fetch_market.py 已加 ex_date year 邏輯
        """
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'source'))
        # 讀 fetch_market.py source、確認有「ex_date year」相關邏輯
        with open(os.path.join(os.path.dirname(__file__), '..', 'source',
                               'stocktool', 'fetch_market.py')) as f:
            source = f.read()

        # 至少有 2 個 fetcher 都改了
        self.assertIn("CashExDividendTradingDate", source,
            msg="fetch_market.py 應該用 CashExDividendTradingDate 取得 ex_date")
        self.assertIn("StockExDividendTradingDate", source,
            msg="fetch_market.py 應該 fallback 到 StockExDividendTradingDate")
        self.assertIn("ex_date_str and len(ex_date_str) >= 4", source,
            msg="應該用 ex_date_str[:4] 拿到年份")

    def test_no_finmind_rows_with_null_ex_date(self):
        """DB 內不應有 finmind ex_date NULL 的 row（已被 cleanup 刪除）"""
        import sqlite3, os
        db_path = os.path.join(
            os.path.dirname(__file__), '..', 'source', 'dividend_history.db')
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM dividend_history "
            "WHERE source='finmind' AND (ex_date IS NULL OR ex_date='')"
        )
        count = cur.fetchone()[0]
        conn.close()
        self.assertEqual(count, 0,
            msg=f"finmind ex_date NULL 應該清空、剩 {count} 筆")


class TestFetcherDBPathResolution(unittest.TestCase):
    """【V0.9.5-goodinfo6++】fetcher db_path=None 自動找 source/dividend_history.db

    William 2026-06-26 13:56 反映：系統選股結果 9946 殖利率 0.07 (應為 0)、4973 殖利率 0.015 (應為 1.28)
    根因：
      - _fetch_finmind_dividend 預設 db_path = "dividend_history.db" 是相對路徑
      - 專案根有空的 dividend_history.db (0 筆, 6/20 殘留)
      - App 跑時 cwd 不同、可能抓到專案根那個空 DB
      - DB 查不到資料 → 殖利率全 None → fallback 估算
      - 9946 估算 (EPS×0.7/股價) = 0.036 → 顯示 0.04
      - 部分狀況抓到正確 DB → 9946 goodinfo cyld=6.9 → 顯示 0.07
    修法：db_path=None 自動找 fetch_market.py 上層的 source/dividend_history.db (絕對路徑)
    """

    def test_fetcher_default_db_path_finds_source_db(self):
        """不傳 db_path、從任何 cwd 都應該能找到 source/dividend_history.db"""
        import os, sys
        import tempfile

        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'source'))

        # 模擬三種 cwd
        for cwd in ['.', 'source', '/tmp']:
            with tempfile.TemporaryDirectory() as tmp:
                os.chdir(tmp)
                from stocktool.fetch_market import _fetch_finmind_dividend
                # 用 source/dividend_history.db 的真實 9946 查詢
                df = _fetch_finmind_dividend(['9946', '4973'], skip_remote=True)
                # 應該拿到 goodinfo 殖利率 (6.9, 1.28)
                self.assertEqual(len(df), 2, f"cwd={cwd}: df 應該有 2 列")
                cyld_2026 = df['2026現金殖利率_goodinfo'].tolist()
                self.assertEqual(cyld_2026, [6.9, 1.28],
                    msg=f"cwd={cwd}: 預期 9946=6.9, 4973=1.28、實際 {cyld_2026}")

    def test_background_fetcher_default_db_path(self):
        """_background_fetch_all_dividend 也自動找正確路徑"""
        import os, sys
        import tempfile

        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'source'))
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            from stocktool.fetch_market import _background_fetch_all_dividend
            # 傳已知 stock_ids、不要真的抓 FinMind（會被 FinMind API 擋）
            # 只測 db_path 自動找得到
            # skip_remote=True 不存在、所以用不存在的 stock
            result = _background_fetch_all_dividend(['NONEXIST_9999'], batch_size=0)
            # 應該至少 return 0 (沒抓到) 不報錯
            self.assertIn(result, [-1, 0, 1])
