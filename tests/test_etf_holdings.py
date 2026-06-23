"""【V0.9.5-etf】主動式 ETF 持股抓取 + 合併邏輯

測試 4 個函式：
- fetch_active_etf_list：從 TWSE API 抓 18 檔 domestic 主動式 ETF
- fetch_etf_top10_holdings：從 etfinfo.tw 抓單檔 ETF 前 10 大
- build_etf_holdings_table：完整 long-format table
- aggregate_etf_holdings：合併去重 + 計算 etf_count + merge 收盤價
"""
import os
import sys
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402


# ==========================================================
# 工具：mock session
# ==========================================================

def _make_session(responses: dict):
    """responses = {url_substring: response_text/json}"""
    session = requests.Session()

    def fake_get(url, **kwargs):
        m = MagicMock()
        m.raise_for_status = lambda: None
        for key, value in responses.items():
            if key in url:
                if isinstance(value, (dict, list)):
                    m.json = lambda v=value: v
                else:
                    m.text = value
                break
        else:
            m.json = lambda: {"status": "error"}
            m.text = ""
        return m

    session.get = fake_get
    return session


def _mock_etf_list_response():
    """TWSE activeList 真實資料（截錄）"""
    return {
        "status": "ok",
        "fields": ["證券代號", "證券簡稱", "管理方式", "ETF分類"],
        "data": [
            ["00981A", "主動統一台股增長", "主動式交易所交易基金", "domestic"],
            ["00403A", "主動統一升級50", "主動式交易所交易基金", "domestic"],
            ["00988A", "主動統一全球創新", "主動式交易所交易基金", "foreign"],  # 過濾掉
            ["00982D", "主動富邦動態入息", "主動式交易所交易基金", "bfIncome"],  # 過濾掉
        ],
    }


def _mock_etfinfo_html(stocks):
    """模擬 etfinfo.tw 總覽頁 HTML（含前 10 大表格）"""
    rows_html = ""
    for code, name, weight in stocks:
        rows_html += (
            f'<tr><td><a href="/stock/{code}">{code}</a></td>'
            f'<td><span>{name}</span></td>'
            f'<td><strong>{weight}%</strong></td></tr>'
        )
    return f"<html><body><h2>前 10 大成分股</h2><table>{rows_html}</table></body></html>"


# ==========================================================
# fetch_active_etf_list
# ==========================================================

def test_fetch_active_etf_list_過濾只留domestic():
    """【核心守護】TWSE API 回傳混雜、只保留 domestic"""
    s = _make_session({
        "ETF/activeList": _mock_etf_list_response(),
    })
    df = st.fetch_active_etf_list(s, st.StrategyConfig())
    codes = df["etf_code"].tolist()
    assert codes == ["00981A", "00403A"], (
        f"應只保留 2 檔 domestic、實際: {codes}"
    )
    assert "etf_name" in df.columns
    assert df.iloc[0]["etf_name"] == "主動統一台股增長"


# ==========================================================
# fetch_etf_top10_holdings
# ==========================================================

def test_fetch_etf_top10_holdings_正常解析10檔():
    """【核心守護】parse HTML 表格、回傳 10 筆 (code, name, weight)"""
    stocks = [
        ("2330", "台積電", 9.68),
        ("2327", "國巨*", 8.67),
        ("2383", "台光電", 8.44),
    ]
    s = _make_session({
        "/etf/00981A": _mock_etfinfo_html(stocks),
    })
    result = st.fetch_etf_top10_holdings(s, st.StrategyConfig(), "00981A")
    assert len(result) == 3
    assert result[0]["stock_code"] == "2330"
    assert result[0]["stock_name"] == "台積電"
    assert result[0]["weight"] == 9.68


def test_fetch_etf_top10_holdings_找不到section_拋錯():
    """【邊界】HTML 沒「前 10 大成分股」section → RuntimeError"""
    s = _make_session({
        "/etf/BAD": "<html>no holdings here</html>",
    })
    with pytest.raises(RuntimeError, match="找不到"):
        st.fetch_etf_top10_holdings(s, st.StrategyConfig(), "BAD")


def test_fetch_etf_top10_holdings_解析失敗_拋錯():
    """【邊界】HTML 有 section 但沒符合格式的 row → RuntimeError"""
    s = _make_session({
        "/etf/EMPTY": "<html><h2>前 10 大成分股</h2><table></table></html>",
    })
    with pytest.raises(RuntimeError, match="解析前 10 大失敗"):
        st.fetch_etf_top10_holdings(s, st.StrategyConfig(), "EMPTY")


# ==========================================================
# build_etf_holdings_table
# ==========================================================

def test_build_etf_holdings_table_合併多檔ETF():
    """【整合測試】多檔 ETF → long-format table"""
    responses = {
        "ETF/activeList": _mock_etf_list_response(),
        "/etf/00981A": _mock_etfinfo_html([
            ("2330", "台積電", 9.68),
            ("2327", "國巨", 8.67),
        ]),
        "/etf/00403A": _mock_etfinfo_html([
            ("2330", "台積電", 18.29),  # 同檔被 2 個 ETF 持有
            ("2454", "聯發科", 7.17),
        ]),
    }
    s = _make_session(responses)
    logger = MagicMock()
    df = st.build_etf_holdings_table(s, st.StrategyConfig(), logger)
    assert len(df) == 4  # 2+2
    assert df.columns.tolist() == ["stock_code", "stock_name", "etf_code", "etf_name", "weight", "shares", "industry"]
    # 2330 出現 2 次（被 2 檔 ETF 持有）
    assert len(df[df["stock_code"] == "2330"]) == 2


def test_build_etf_holdings_table_單檔抓取失敗_繼續跑():
    """【邊界】一檔抓失敗、不影響其他檔"""
    responses = {
        "ETF/activeList": _mock_etf_list_response(),
        "/etf/00981A": _mock_etfinfo_html([("2330", "台積電", 9.68)]),
        "/etf/00403A": "<html>bad html</html>",  # 解析失敗
    }
    s = _make_session(responses)
    logger = MagicMock()
    df = st.build_etf_holdings_table(s, st.StrategyConfig(), logger)
    # 至少 00981A 的資料要進來
    assert len(df) == 1
    assert df.iloc[0]["stock_code"] == "2330"
    assert df.iloc[0]["etf_code"] == "00981A"


# ==========================================================
# aggregate_etf_holdings
# ==========================================================

def test_aggregate_etf_holdings_計算etf_count_並排序():
    """【核心守護】合併去重、計算 etf_count、排序由大到小"""
    holdings = pd.DataFrame({
        "stock_code": ["2330", "2327", "2330", "2454", "2330"],
        "stock_name": ["台積電", "國巨", "台積電", "聯發科", "台積電"],
        "etf_code": ["00981A", "00981A", "00403A", "00403A", "00991A"],
        "etf_name": ["主動統一台股增長", "主動統一台股增長", "主動統一升級50", "主動統一升級50", "主動復華未來50"],
        "weight": [9.68, 8.67, 18.29, 7.17, 12.73],
    })
    result = st.aggregate_etf_holdings(holdings, price_df=None)

    # 預期 3 檔個股 (2330 出現 3 次、2327 出現 1 次、2454 出現 1 次)
    assert len(result) == 3

    # 2330 應該排第一（etf_count=3）
    assert result.iloc[0]["股票代號"] == "2330"
    assert result.iloc[0]["etf_count"] == 3

    # 2327 和 2454 應該排後面（etf_count=1）
    assert set(result[result["etf_count"] == 1]["股票代號"]) == {"2327", "2454"}


def test_aggregate_etf_holdings_etf_list字串包含代號名稱權重():
    """【核心守護】etf_list 字串包含 ETF 代號 + 名稱 + 權重"""
    holdings = pd.DataFrame({
        "stock_code": ["2330", "2330"],
        "stock_name": ["台積電", "台積電"],
        "etf_code": ["00981A", "00403A"],
        "etf_name": ["主動統一台股增長", "主動統一升級50"],
        "weight": [9.68, 18.29],
    })
    result = st.aggregate_etf_holdings(holdings, price_df=None)
    s2330 = result.iloc[0]["etf_list"]
    assert "00981A" in s2330
    assert "主動統一台股增長" in s2330
    assert "9.68%" in s2330
    assert "00403A" in s2330
    assert "18.29%" in s2330


def test_aggregate_etf_holdings_merge收盤價():
    """【整合測試】merge price_df → 加上「收盤價」欄"""
    holdings = pd.DataFrame({
        "stock_code": ["2330", "2327"],
        "stock_name": ["台積電", "國巨"],
        "etf_code": ["00981A", "00981A"],
        "etf_name": ["主動統一台股增長", "主動統一台股增長"],
        "weight": [9.68, 8.67],
    })
    price_df = pd.DataFrame({
        "股票代號": ["2330", "2327", "9999"],  # 9999 不在 holdings
        "股價": [950.0, 580.0, 100.0],
    })
    result = st.aggregate_etf_holdings(holdings, price_df=price_df)
    assert "收盤價" in result.columns
    row_2330 = result[result["股票代號"] == "2330"].iloc[0]
    assert row_2330["收盤價"] == 950.0
    row_2327 = result[result["股票代號"] == "2327"].iloc[0]
    assert row_2327["收盤價"] == 580.0


def test_aggregate_etf_holdings_股價df空白仍可跑():
    """【邊界】price_df 是空的 → 收盤價欄位為 None"""
    holdings = pd.DataFrame({
        "stock_code": ["2330"],
        "stock_name": ["台積電"],
        "etf_code": ["00981A"],
        "etf_name": ["主動統一台股增長"],
        "weight": [9.68],
    })
    result = st.aggregate_etf_holdings(holdings, price_df=pd.DataFrame())
    assert "收盤價" in result.columns
    # 收盤價可能 NaN
    assert result.iloc[0]["收盤價"] is None or pd.isna(result.iloc[0]["收盤價"])