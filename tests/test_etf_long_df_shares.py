"""
test_etf_long_df_shares.py
驗證 V0.9.5-tab-split-phase3-H FixA：
build_etf_holdings_table 必須把 shares 放進 long_df
→ _save_etf_holdings_to_db 才能正確寫入 DB → _compute_etf_changes 才算得出異動

【William 2026-06-23 09:55 反映】
- ETF 持股篩選結果「今日異動」欄位全是 --
- 根因：build_etf_holdings_table 漏放 shares 欄位
- 修法：shares 放進 long_df → DB shares > 0 → 異動計算正常

【守護】
- shares 欄位必須存在
- shares 必須是數值（int 或 float）
- 至少 1 檔 > 0（從 etfinfo.tw SSR 抓到）
"""
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402


# ==========================================================
# 【build_etf_holdings_table】回傳的 long_df 必須含 shares
# ==========================================================

def test_build_etf_holdings_table_包含shares欄位():
    """【V0.9.5-tab-split-phase3-H FixA 守護】
    build_etf_holdings_table 回傳的 DataFrame 必須有 shares 欄位
    """
    # mock fetch_etf_top10_holdings 回傳假資料（含 shares）
    fake_holdings_00400A = [
        {"stock_code": "2330", "stock_name": "台積電", "weight": 57.01, "shares": 519237994, "industry": "半導體"},
        {"stock_code": "2454", "stock_name": "聯發科", "weight": 6.28, "shares": 31410621, "industry": "半導體"},
    ]
    fake_holdings_00981A = [
        {"stock_code": "2330", "stock_name": "台積電", "weight": 25.0, "shares": 100000000, "industry": "半導體"},
    ]

    with patch.object(st, "fetch_active_etf_list") as mock_list, \
         patch.object(st, "fetch_etf_top10_holdings") as mock_top10:

        # mock ETF list
        mock_list.return_value = MagicMock()
        mock_list.return_value.iterrows.return_value = iter([
            (0, {"etf_code": "00400A", "etf_name": "主動野村臺灣"}),
            (1, {"etf_code": "00981A", "etf_name": "主動統一台股增長"}),
        ])

        # mock top10
        def _side_effect(session, cfg, etf_code):
            if etf_code == "00400A":
                return fake_holdings_00400A
            if etf_code == "00981A":
                return fake_holdings_00981A
            return []
        mock_top10.side_effect = _side_effect

        # mock logger
        logger = MagicMock()

        session = MagicMock()
        cfg = st.StrategyConfig()

        long_df = st.build_etf_holdings_table(session, cfg, logger)

        # 1. 必須有 shares 欄位
        assert "shares" in long_df.columns, (
            f"long_df 缺少 shares 欄位、實際欄位: {list(long_df.columns)}"
        )

        # 2. shares 必須都是正整數（不為 0）
        shares_values = long_df["shares"].tolist()
        assert all(s > 0 for s in shares_values), (
            f"shares 必須 > 0、實際: {shares_values}"
        )

        # 3. 2330 出現 2 次、shares 分別是 519237994 和 100000000
        rows_2330 = long_df[long_df["stock_code"] == "2330"]
        assert len(rows_2330) == 2, f"2330 應出現 2 次、實際 {len(rows_2330)}"
        assert 519237994 in rows_2330["shares"].tolist()
        assert 100000000 in rows_2330["shares"].tolist()

        print("PASS: test_build_etf_holdings_table_包含shares欄位")


def test_build_etf_holdings_table_shares為0_也要帶欄位():
    """【V0.9.5-tab-split-phase3-H FixA 守護】
    即使 SSR parse 失敗（shares=0）、欄位還是要存在（不能 drop）
    → _save_etf_holdings_to_db 用 r.get("shares", 0) 才不會爆 KeyError
    """
    fake_holdings = [
        {"stock_code": "2330", "stock_name": "台積電", "weight": 57.01, "shares": 0, "industry": ""},
    ]

    with patch.object(st, "fetch_active_etf_list") as mock_list, \
         patch.object(st, "fetch_etf_top10_holdings") as mock_top10:

        mock_list.return_value = MagicMock()
        mock_list.return_value.iterrows.return_value = iter([
            (0, {"etf_code": "00400A", "etf_name": "測試"}),
        ])
        mock_top10.return_value = fake_holdings
        logger = MagicMock()
        long_df = st.build_etf_holdings_table(MagicMock(), st.StrategyConfig(), logger)

        # 欄位還是要有
        assert "shares" in long_df.columns
        assert long_df.iloc[0]["shares"] == 0

        print("PASS: test_build_etf_holdings_table_shares為0_也要帶欄位")


def test_build_etf_holdings_table_包含industry欄位():
    """【V0.9.5-tab-split-phase3-H FixA 附帶守護】
    industry 也一起補進 long_df（雖然現在 etfinfo.tw SSR 拿不到、未來可以從別處補）
    """
    fake_holdings = [
        {"stock_code": "2330", "stock_name": "台積電", "weight": 57.01, "shares": 100, "industry": "半導體"},
    ]

    with patch.object(st, "fetch_active_etf_list") as mock_list, \
         patch.object(st, "fetch_etf_top10_holdings") as mock_top10:

        mock_list.return_value = MagicMock()
        mock_list.return_value.iterrows.return_value = iter([
            (0, {"etf_code": "00400A", "etf_name": "測試"}),
        ])
        mock_top10.return_value = fake_holdings
        long_df = st.build_etf_holdings_table(MagicMock(), st.StrategyConfig(), MagicMock())

        assert "industry" in long_df.columns, (
            f"long_df 缺少 industry 欄位、實際欄位: {list(long_df.columns)}"
        )

        print("PASS: test_build_etf_holdings_table_包含industry欄位")


# ==========================================================
# 【_save_etf_holdings_to_db】從 long_df 抓 shares 正確
# ==========================================================

def test_save_etf_holdings_to_db_從long_df抓shares():
    """【V0.9.5-tab-split-phase3-H FixA 守護】
    _save_etf_holdings_to_db 從 long_df 的 shares 欄位正確寫入 DB
    """
    import sqlite3
    import tempfile

    # 準備測試用 DB
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # 初始化 DB schema
        st._init_etf_history_db(tmp_path)

        # 模擬 long_df
        long_df = st.pd.DataFrame([
            {
                "stock_code": "2330",
                "stock_name": "台積電",
                "etf_code": "00400A",
                "etf_name": "主動野村臺灣",
                "weight": 57.01,
                "shares": 519237994,
                "industry": "半導體",
            },
        ])

        # 建一個最小 mock self
        app = MagicMock()
        app._etf_history_db = tmp_path
        app.logger = MagicMock()
        st.StrategyGUI._save_etf_holdings_to_db(app, long_df)

        # 驗證 DB shares
        with sqlite3.connect(tmp_path) as conn:
            row = conn.execute(
                "SELECT shares, shares_lots FROM etf_holding_history WHERE stock_code = ?",
                ("2330",),
            ).fetchone()
            assert row is not None, "DB 沒寫入"
            assert row[0] == 519237994, f"shares 應為 519237994、實際 {row[0]}"
            assert row[1] == 519237.994, f"shares_lots 應為 519237.994、實際 {row[1]}"

        print("PASS: test_save_etf_holdings_to_db_從long_df抓shares")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


if __name__ == "__main__":
    test_build_etf_holdings_table_包含shares欄位()
    test_build_etf_holdings_table_shares為0_也要帶欄位()
    test_build_etf_holdings_table_包含industry欄位()
    test_save_etf_holdings_to_db_從long_df抓shares()
    print("\nAll V0.9.5-tab-split-phase3-H FixA tests passed!")