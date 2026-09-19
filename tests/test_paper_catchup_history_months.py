"""
【V1.2.0-paper-trading-kb-focus-v26 + 2026-08-20 bug fix】
Regression test for paper_catchup._get_historical_prices history_months mismatch

背景：
- cache/history/ 裡只放 *_60m.xlsx（config.py history_months=60）
- 但 paper_catchup._get_historical_prices 寫死 history_months=12
- → 找不到 *_12m.xlsx → 整個 stock_data 空 → 每天都被 skip → 永遠不交易
- William 2026-08-20 15:05 反映：「為什麼模擬買賣都沒有買賣紀錄？」

期望：_get_historical_prices 應該用 cache 實際有的月份 (60)、
或具備 fallback 行為 (12 → 60)
"""

import os
import sys
import tempfile

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))


def _write_history_xlsx(path: str, df: pd.DataFrame) -> None:
    """直接寫 xlsx、不經 save_cache (避免 cwd 污染)"""
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="data", index=False)
        meta = pd.DataFrame({"last_update": ["2026-08-20"], "last_update_time": ["07:00:00"]})
        meta.to_excel(writer, sheet_name="meta", index=False)


# ==========================================================
# Test 1：cache 只有 *_60m.xlsx 時，_get_historical_prices 應能找到資料
# ==========================================================
def test_get_historical_prices_finds_60m_cache():
    """模擬 cache 只有 *_60m.xlsx 時，補跑不應該全部 skip"""
    from stocktool import paper_catchup
    from stocktool import export_excel

    with tempfile.TemporaryDirectory() as tmpdir:
        # 把 HISTORY_DIR 換成 tmpdir
        orig = export_excel.HISTORY_DIR
        export_excel.HISTORY_DIR = tmpdir
        try:
            # 寫一份真實格式的 *_60m.xlsx 進 tmpdir
            code = "2330"
            df = pd.DataFrame({
                "Date": pd.to_datetime([
                    "2026-07-10", "2026-07-13", "2026-07-14",
                    "2026-07-15", "2026-07-16", "2026-07-17",
                ]).strftime("%Y-%m-%d"),
                "股票代號": [code] * 6,
                "Close": [2400.0, 2410.0, 2420.0, 2450.0, 2470.0, 2290.0],
                "Volume": [10000] * 6,
            })
            fp = os.path.join(tmpdir, f"{code}_60m.xlsx")
            _write_history_xlsx(fp, df)

            # 跑 _get_historical_prices
            result = paper_catchup._get_historical_prices(
                session=None, cfg=None, codes=[code],
                trade_date="2026-07-14",
            )

            # ✅ 應該抓到資料
            assert code in result, (
                f"❌ _get_historical_prices 沒從 *_60m.xlsx 抓到 {code}\n"
                f"   got={result}\n"
                f"   cache dir={tmpdir}\n"
                f"   → 這就是為什麼補跑永遠 0 交易 (history_months mismatch bug)"
            )
            assert result[code]["price"] == 2420.0
        finally:
            export_excel.HISTORY_DIR = orig


# ==========================================================
# Test 2：cache 只有 *_12m.xlsx 時也要能讀
# ==========================================================
def test_get_historical_prices_finds_12m_cache():
    """cache 只有 12m 時也要能讀 (確保函式通用)"""
    from stocktool import paper_catchup
    from stocktool import export_excel

    with tempfile.TemporaryDirectory() as tmpdir:
        orig = export_excel.HISTORY_DIR
        export_excel.HISTORY_DIR = tmpdir
        try:
            code = "2330"
            df = pd.DataFrame({
                "Date": pd.to_datetime(["2026-07-14"]).strftime("%Y-%m-%d"),
                "股票代號": [code],
                "Close": [2420.0],
                "Volume": [10000],
            })
            fp = os.path.join(tmpdir, f"{code}_12m.xlsx")
            _write_history_xlsx(fp, df)

            result = paper_catchup._get_historical_prices(
                session=None, cfg=None, codes=[code],
                trade_date="2026-07-14",
            )

            assert code in result, (
                f"❌ 連 *_12m.xlsx 都沒抓到\n"
                f"   got={result}"
            )
        finally:
            export_excel.HISTORY_DIR = orig


# ==========================================================
# Test 3：完整 catch_up_portfolio 補跑一天不應該 skip
# ==========================================================
def test_catch_up_portfolio_one_day_no_skip():
    """完整補跑一天、不是 28 天全部 skip

    這個測試會：
    1. 建一個 test portfolio (ai_meta, pool=[2330])
    2. 寫一份 60m history
    3. 跑 catch_up_portfolio (end_date=2026-07-14)
    4. 期望 skipped_dates 為空 (不應 skip)
    """
    from stocktool import paper_catchup
    from stocktool import paper_trading as pt
    from stocktool.paper_trading import init_paper_trading_db
    from stocktool import export_excel

    with tempfile.TemporaryDirectory() as tmpdir:
        # mock HISTORY_DIR
        orig_hist = export_excel.HISTORY_DIR
        export_excel.HISTORY_DIR = tmpdir
        # mock DB path
        db_path = os.path.join(tmpdir, "test_portfolio.db")
        init_paper_trading_db(db_path)

        try:
            # 建一份 pool 只有 2330 的 portfolio
            from stocktool.paper_trading import PaperPortfolio
            p_obj = PaperPortfolio(
                name="test_60m",
                stock_pool=["2330"],
                initial_cash=1000000.0,
                strategy_mode="ai_meta",
                ai_threshold=70.0,
            )
            pid = pt.create_portfolio(db_path, p_obj)
            # backdate started_at so catchup will run for 2026-07-14
            import sqlite3 as _sq
            with _sq.connect(db_path) as _c:
                _c.execute("UPDATE sim_portfolios SET started_at='2026-07-13 14:00:00' WHERE id=?", (pid,))
                _c.commit()

            # 寫一份 *_60m.xlsx 進 tmpdir (cache)
            df = pd.DataFrame({
                "Date": pd.to_datetime(["2026-07-13", "2026-07-14"]).strftime("%Y-%m-%d"),
                "股票代號": ["2330"] * 2,
                "Close": [2400.0, 2420.0],
                "Volume": [10000] * 2,
            })
            _write_history_xlsx(os.path.join(tmpdir, "2330_60m.xlsx"), df)

            # 跑補跑 (從 2026-07-14 起一天)
            result = paper_catchup.catch_up_portfolio(
                db_path, pid, end_date="2026-07-14",
            )

            # ✅ 不應 skip (因為 cache 有資料)
            assert result.skipped_dates == [], (
                f"❌ 補跑 1 天卻被 skip\n"
                f"   skipped={result.skipped_dates}\n"
                f"   errors={result.errors}\n"
                f"   → history_months 沒對應到 cache (12 vs 60)"
            )

            # 沒交易也 OK，但 last_run_date 應該推進
            p2 = pt.get_portfolio(db_path, pid)
            assert p2.last_run_date == "2026-07-14", (
                f"❌ last_run_date 沒推進 → 補跑沒跑成\n"
                f"   got={p2.last_run_date}"
            )
        finally:
            export_excel.HISTORY_DIR = orig_hist
            try:
                os.remove(db_path)
            except OSError:
                pass
