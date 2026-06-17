"""
test_ex_date_yield.py
驗證 V0.9.5+ Phase 10：去年現金殖利率算法改用「除息日收盤價」。

【William 2026-06-15 11:39 反映】
- 「去年現金殖利率」應該除以「去年除息日的價錢」、不是現價
- 原本：除以現價 → 譯導（殖利率看似高、實際上是用現價算的）
- 修正：除以「去年除息日收盤價」→ 真正表示「拿去年現金股利、除以當時除息日的股價」

【修法】
- DB schema 加 ex_date（除息日）、ex_date_close（除息日收盤價）
- _fetch_finmind_dividend 保留 date 寫入 DB
- 新增 _fetch_ex_date_close() 抓除息日附近股價
- 改寫 _run_manual_selection 內「去年現金殖利率」算法

【為什麼要這個 test】
- 守護「去年現金殖利率」算法改用 ex_date_close（不是現價）
- 守護 DB schema migration 不漏欄位
- 守護 _fetch_ex_date_close 在假日 ±3 天查找邏輯
"""
import os
import sys
import sqlite3
import tempfile
from datetime import datetime
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402


CY = datetime.now().year  # 2026


# ==========================================================
# 【DB schema migration】守護新欄位加得進去
# ==========================================================

def test_db_init_加ex_date欄位(tmp_path):
    """【核心】DB schema 應含 ex_date 跟 ex_date_close 欄位"""
    db_path = str(tmp_path / "test_div.db")
    st._init_div_history_db(db_path)
    with sqlite3.connect(db_path) as conn:
        cols = [row[1] for row in conn.execute("PRAGMA table_info(dividend_history)").fetchall()]
    assert "ex_date" in cols, f"DB 應有 ex_date 欄位，實際: {cols}"
    assert "ex_date_close" in cols, f"DB 應有 ex_date_close 欄位，實際: {cols}"


def test_db_init_重複跑不爆(tmp_path):
    """重複 init 同一個 DB 不會爆（migration 安全）"""
    db_path = str(tmp_path / "test_div.db")
    st._init_div_history_db(db_path)
    st._init_div_history_db(db_path)  # 第二次、ALTER TABLE 會失敗但不應爆
    # 欄位仍存在
    with sqlite3.connect(db_path) as conn:
        cols = [row[1] for row in conn.execute("PRAGMA table_info(dividend_history)").fetchall()]
    assert "ex_date" in cols
    assert "ex_date_close" in cols


# ==========================================================
# 【_upsert_div_history】支援 7-tuple 跟向後相容 5-tuple
# ==========================================================

def test_upsert_7tuple_含ex_date寫入(tmp_path):
    """【核心】7-tuple 寫入應包含 ex_date / ex_date_close"""
    db_path = str(tmp_path / "test_div.db")
    st._init_div_history_db(db_path)
    rows = [("2330", 2025, 2.5, 0.5, "finmind", "2025-08-15", 620.0)]
    st._upsert_div_history(db_path, rows)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT cash, stock, ex_date, ex_date_close FROM dividend_history WHERE stock_id='2330' AND year=2025"
        ).fetchone()
    assert row[0] == 2.5
    assert row[1] == 0.5
    assert row[2] == "2025-08-15"
    assert row[3] == 620.0


def test_upsert_5tuple向後相容(tmp_path):
    """5-tuple（舊 code）應仍能寫入、ex_date / ex_date_close 設 NULL"""
    db_path = str(tmp_path / "test_div.db")
    st._init_div_history_db(db_path)
    rows = [("2330", 2025, 2.5, 0.5, "finmind")]
    st._upsert_div_history(db_path, rows)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT cash, stock, ex_date, ex_date_close FROM dividend_history WHERE stock_id='2330' AND year=2025"
        ).fetchone()
    assert row[0] == 2.5
    assert row[1] == 0.5
    assert row[2] is None  # ex_date 自動補 NULL
    assert row[3] is None  # ex_date_close 自動補 NULL


# ==========================================================
# 【_update_ex_date_close】寫入緩存
# ==========================================================

def test_update_ex_date_close寫入緩存(tmp_path):
    """【核心】新抓的 ex_date_close 應寫入 DB、下次不用重抓"""
    db_path = str(tmp_path / "test_div.db")
    st._init_div_history_db(db_path)
    # 先插一筆
    st._upsert_div_history(db_path, [("2330", 2025, 2.5, 0.5, "finmind", "2025-08-15", None)])
    # 更新 ex_date_close
    st._update_ex_date_close(db_path, "2330", 2025, "2025-08-15", 620.0)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT ex_date, ex_date_close FROM dividend_history WHERE stock_id='2330' AND year=2025"
        ).fetchone()
    assert row[0] == "2025-08-15"
    assert row[1] == 620.0


# ==========================================================
# 【_fetch_ex_date_close】抓除息日附近股價
# ==========================================================

def test_fetch_ex_date_close_正常抓到():
    """【核心】除息日當天有資料 → 抓該日 close"""
    with patch.object(st, "_finmind_get") as mock_fm:
        mock_fm.return_value = [
            {"date": "2025-08-13", "close": 618.0},
            {"date": "2025-08-14", "close": 620.0},
            {"date": "2025-08-15", "close": 622.0},  # ex_date 當天
            {"date": "2025-08-16", "close": 624.0},
        ]
        close = st._fetch_ex_date_close("2330", "2025-08-15")
    assert close == 622.0  # ex_date 當天的 close


def test_fetch_ex_date_close_除息日是假日找最近():
    """【邊界】除息日是週末（沒資料）→ 找 ±3 天內最近交易日"""
    with patch.object(st, "_finmind_get") as mock_fm:
        mock_fm.return_value = [
            {"date": "2025-08-14", "close": 620.0},  # 最近交易日
            {"date": "2025-08-18", "close": 625.0},
        ]
        close = st._fetch_ex_date_close("2330", "2025-08-16")  # 週六
    # 8/16 距 8/14 = 2 天、距 8/18 = 2 天 → 兩個一樣近、取第一個
    assert close == 620.0


def test_fetch_ex_date_close_空字串回傳None():
    """ex_date 空字串 → 不打 API、回 None"""
    assert st._fetch_ex_date_close("2330", "") is None
    assert st._fetch_ex_date_close("2330", None) is None


def test_fetch_ex_date_close_額度用完回傳None():
    """FinMind 額度用完（raise RuntimeError）→ 不爆、silently 回 None"""
    with patch.object(st, "_finmind_get", side_effect=RuntimeError("402")):
        close = st._fetch_ex_date_close("2330", "2025-08-15")
    assert close is None


def test_fetch_ex_date_close_沒資料回傳None():
    """API 回空 list → 回 None"""
    with patch.object(st, "_finmind_get", return_value=[]):
        close = st._fetch_ex_date_close("2330", "2025-08-15")
    assert close is None


def test_fetch_ex_date_close_close為0回傳None():
    """close = 0（不合理）→ 回 None"""
    with patch.object(st, "_finmind_get") as mock_fm:
        mock_fm.return_value = [{"date": "2025-08-15", "close": 0}]
        close = st._fetch_ex_date_close("2330", "2025-08-15")
    assert close is None


# ==========================================================
# 【_run_manual_selection 整合】去年現金殖利率新算法
# ==========================================================

def _make_div_df_with_ex_date() -> pd.DataFrame:
    """模擬 _fetch_finmind_dividend 回傳含 ex_date / ex_date_close 的 df
    V0.9.5-goodinfo3：殖利率 100% 用 goodinfo、加 cash_yield_pct 欄位

    原本設 ex_date/ex_date_close 是給 V0.9.5+ Phase 10 fallback 用，
    V0.9.5-goodinfo3 拿掉 fallback、殖利率直接看 cash_yield_pct_goodinfo
    """
    rows = [
        {
            "股票代號": "2330",
            f"{CY}現金股利": None, f"{CY}股票股利": None,
            f"{CY - 1}現金股利": 3.0, f"{CY - 1}股票股利": 0.5,   # 今年
            f"{CY - 2}現金股利": 2.5, f"{CY - 2}股票股利": 0.0,   # 去年
            f"{CY - 1}除息日": "2025-08-15", f"{CY - 1}除息日收盤價": 620.0,
            # V0.9.5-goodinfo3：殖利率 100% 用 goodinfo
            f"{CY - 1}現金殖利率_goodinfo": 0.48,
            f"{CY - 1}股票殖利率_goodinfo": 0.08,
        },
        {
            "股票代號": "2317",
            f"{CY}現金股利": None, f"{CY}股票股利": None,
            f"{CY - 1}現金股利": 2.0, f"{CY - 1}股票股利": 0.0,   # 今年
            f"{CY - 2}現金股利": 1.5, f"{CY - 2}股票股利": 0.0,   # 去年
            f"{CY - 1}除息日": "2025-07-20", f"{CY - 1}除息日收盤價": None,
            # 2317 去年現金殖利率 goodinfo = 2.0%（不是用 ex_date_close fallback 算的）
            f"{CY - 1}現金殖利率_goodinfo": 2.0,
            f"{CY - 1}股票殖利率_goodinfo": 0.0,
        },
    ]
    return pd.DataFrame(rows)


def test_去年現金殖利率_用ex_date_close_不是現價():
    """【V0.9.5+ Phase 10 核心】2330 的 ex_date_close=620、去年現金=2.5
    → 殖利率 = 3.0/620*100 = 0.48%
    若誤用現價（60.0）算 → 5.0%（差 10 倍）"""
    st._fetch_finmind_dividend = lambda codes, **kw: _make_div_df_with_ex_date()
    # _fetch_ex_date_close 對 2317（沒緩存）回 100
    st._fetch_ex_date_close = lambda code, ex_date: 100.0 if code == "2317" else None

    price_df = pd.DataFrame([
        {"股票代號": "2330", "股票名稱": "台積電", "現價": 60.0,
         "營收YoY(%)": 25.0, "成交量_張": 5000.0, "PE": 15.0, "EPS本期": 4.0},
        {"股票代號": "2317", "股票名稱": "鴻海", "現價": 50.0,
         "營收YoY(%)": 15.0, "成交量_張": 3000.0, "PE": 12.0, "EPS本期": 4.2},
    ])

    result = st._run_manual_selection(price_df, pd.DataFrame(), pd.DataFrame(), {}, top_n=10)

    row_2330 = result[result["股票代號"] == "2330"].iloc[0]
    row_2317 = result[result["股票代號"] == "2317"].iloc[0]

    # 2330: 殖利率應該用 620（ex_date_close）算 → 3.0/620 = 0.48%
    assert abs(row_2330["去年現金殖利率(%)"] - 0.48) < 0.01, \
        f"2330 去年殖利率應為 0.48%（3.0/620），實際: {row_2330['去年現金殖利率(%)']}"
    # 不是用現價 60 算的 5.0%
    assert row_2330["去年現金殖利率(%)"] != 5.0, \
        "不應誤用現價算（5.0% 是用現價 60 算出來的）"

    # 2317: 殖利率 2.0/100*100 = 2.0%
    assert abs(row_2317["去年現金殖利率(%)"] - 2.0) < 0.01, \
        f"2317 去年殖利率應為 2.0%（2.0/100），實際: {row_2317['去年現金殖利率(%)']}"


def test_去年現金殖利率_沒goodinfo_殖利率為None():
    """【邊界】V0.9.5-goodinfo3：沒 goodinfo 殖利率 → 殖利率 None

    原本（V0.9.5+ Phase 10）：ex_date 空且 fetch 失敗 → fallback 用現價 = 2.0%
    V0.9.5-goodinfo3：拿掉所有 fallback → 沒 goodinfo = None
    """
    st._fetch_finmind_dividend = lambda codes, **kw: pd.DataFrame([
        {
            "股票代號": "9999",
            f"{CY}現金股利": None, f"{CY}股票股利": None,
            f"{CY - 1}現金股利": 1.0, f"{CY - 1}股票股利": [0.0][0],
            f"{CY - 2}現金股利": 0.0, f"{CY - 2}股票股利": 0.0,
            f"{CY - 1}除息日": "",  # ← 空字串
            f"{CY - 1}除息日收盤價": None,
            # V0.9.5-goodinfo3：故意不給殖利率（沒 goodinfo 資料）
        }
    ])
    # fetch 也回 None
    st._fetch_ex_date_close = lambda code, ex_date: None

    price_df = pd.DataFrame([
        {"股票代號": "9999", "股票名稱": "測試", "現價": 50.0,
         "營收YoY(%)": 10.0, "成交量_張": 1000.0, "PE": 20.0, "EPS本期": 2.5},
    ])

    result = st._run_manual_selection(price_df, pd.DataFrame(), pd.DataFrame(), {}, top_n=10)
    row = result.iloc[0]
    # V0.9.5-goodinfo3：沒 fallback、殖利率 = None
    assert pd.isna(row["去年現金殖利率(%)"]), \
        f"沒 goodinfo 殖利率應為 None，實際: {row['去年現金殖利率(%)']}"


def test_去年現金殖利率_現金股利為0_殖利率為None():
    """【邊界】去年現金股利=0 → 殖利率 None（跟原本行為一致）"""
    st._fetch_finmind_dividend = lambda codes, **kw: pd.DataFrame([
        {
            "股票代號": "9999",
            f"{CY}現金股利": None, f"{CY}股票股利": None,
            f"{CY - 1}現金股利": 0.0,  # 不配息
            f"{CY - 1}股票股利": 0.0,
            f"{CY - 2}現金股利": 0.0, f"{CY - 2}股票股利": 0.0,
            f"{CY - 1}除息日": "2025-08-15",
            f"{CY - 1}除息日收盤價": 100.0,
        }
    ])

    price_df = pd.DataFrame([
        {"股票代號": "9999", "股票名稱": "測試", "現價": 50.0,
         "營收YoY(%)": 10.0, "成交量_張": 1000.0, "PE": 20.0, "EPS本期": 2.5},
    ])

    result = st._run_manual_selection(price_df, pd.DataFrame(), pd.DataFrame(), {}, top_n=10)
    row = result.iloc[0]
    assert pd.isna(row["去年現金殖利率(%)"]), \
        f"現金股利 0 應為 None，實際: {row['去年現金殖利率(%)']}"


def test_去年現金殖利率_殖利率100用goodinfo_不走fetch():
    """【V0.9.5-goodinfo3】殖利率 100% 用 goodinfo、不呼叫 _fetch_ex_date_close

    原本（V0.9.5+ Phase 10）：DB 沒 ex_date_close → 自動 fetch → 寫入緩存 → 用 1.36%
    V0.9.5-goodinfo3：直接用 goodinfo 提供的殖利率、不需 fetch
    """
    st._fetch_finmind_dividend = lambda codes, **kw: pd.DataFrame([
        {
            "股票代號": "9999",
            f"{CY}現金股利": None, f"{CY}股票股利": None,
            f"{CY - 1}現金股利": 1.5, f"{CY - 1}股票股利": 0.0,
            f"{CY - 2}現金股利": 0.0, f"{CY - 2}股票股利": 0.0,
            f"{CY - 1}除息日": "2025-08-15",
            f"{CY - 1}除息日收盤價": None,  # 沒緩存
            # V0.9.5-goodinfo3：殖利率 100% 用 goodinfo
            f"{CY - 1}現金殖利率_goodinfo": 1.36,   # goodinfo 提供
            f"{CY - 1}股票殖利率_goodinfo": 0.0,
        }
    ])
    # 不應被呼叫：殖利率不走 fetch 路徑
    st._fetch_ex_date_close = lambda code, ex_date: 110.0  # 故意設錯、避免誤用

    # 抓 _update_ex_date_close 不應被呼叫
    with patch.object(st, "_update_ex_date_close") as mock_update:
        price_df = pd.DataFrame([
            {"股票代號": "9999", "股票名稱": "測試", "現價": 50.0,
             "營收YoY(%)": 10.0, "成交量_張": 1000.0, "PE": 20.0, "EPS本期": 2.5},
        ])
        result = st._run_manual_selection(price_df, pd.DataFrame(), pd.DataFrame(), {}, top_n=10)
        # V0.9.5-goodinfo3：殖利率 100% 用 goodinfo、不會走 fetch 路徑
        assert not mock_update.called, "V0.9.5-goodinfo3 不該呼叫 _update_ex_date_close"

    row = result.iloc[0]
    # 直接用 goodinfo 1.36%，不是 fetch 算出來的 1.36（巧合一樣）
    assert abs(row["去年現金殖利率(%)"] - 1.36) < 0.01, \
        f"殖利率應用 goodinfo 1.36%，實際: {row['去年現金殖利率(%)']}"
