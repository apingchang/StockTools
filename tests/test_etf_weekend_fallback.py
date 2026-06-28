"""
test_etf_weekend_fallback.py
驗證 V0.9.5-etf-weekend-fix：
- 沒開盤的日子（週六/週日/假日）打開 App、「今日異動」要保持上個交易日的結果
- 不能因為週末抓的 stale shares_lots 跟前一天完全一樣、就全顯示 "--"

【William 2026-06-28 08:42 反映】
- 截圖：主動式 ETF 分頁、「今日異動」全 "--"
- 今天 2026-06-28 是週日、沒開盤
- 預期：應該顯示 6/27 (週六) vs 6/26 (週五) 的異動
  - 但實際：6/28 (週日) vs 6/27 (週六) → 0 row 變動 → 全 "--"
- 因為：App 週日早上抓 ETF 持股網頁、shares_lots 跟週六完全一樣（網頁週末沒更新）
- 原本 _compute_etf_changes 用 dates[0] 當 today → 算 dates[0] vs dates[1] = 6/28 vs 6/27 → 全 0

【根因】
- _compute_etf_changes 直接用 dates[0] (DB 最新日期) 當 today
- 沒考慮「dates[0] 可能是週末/假日抓的 stale duplicate」

【修法】
- 加 _etf_dates_have_changes() 判斷兩天 shares_lots 是否有差異
- 加 _find_latest_changed_etf_pair() 從 dates DESC 找「最後一個有實質變動的對」
- _compute_etf_changes() 偵測到 dates[0] 跟 dates[1] 完全相同時、往前找

【守護】
- 週末/假日場景：寫入 4 天 (週五~週一)、其中週六週日 shares 跟前一天完全一樣 → 結果應 = 週五 vs 週四
- 平日場景（向後相容）：週二 vs 週一有差異 → 結果應 = 週二 vs 週一
- 全部都一樣：只有 1 天資料 → 結果空
- DB 沒資料：空 DataFrame
- caller 明確指定 today_str 且無 weekend issue：用 caller 的
"""
import os
import sys
import sqlite3
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import pandas as pd
import StockTool as st  # noqa: E402


# ==========================================================
# 【主場景】週末/假日 fallback
# ==========================================================

def test_weekend_fallback_取最後有變動的交易日():
    """【V0.9.5-etf-weekend-fix 主場景】

    模擬：今天 2026-06-28 (週日)
    DB dates = [2026-06-28, 2026-06-27, 2026-06-26, 2026-06-25]
    - 6/28 (週日) shares 完全 = 6/27 (週六) → stale
    - 6/27 (週六) shares 完全 = 6/26 (週五) → 也 stale
    - 6/26 (週五) shares 跟 6/25 不同 → 真的有變動

    預期：_compute_etf_changes(2026-06-28) 應跳過 6/28、6/27、用 6/26 vs 6/25 算
    """
    from datetime import datetime
    # 用「today=2026-06-28 (週日)」呼叫
    # 但需要 mock datetime.now() → 直接傳 today_str 比較不容易、看一下函式簽名
    # _compute_etf_changes(today_str=None, yesterday_str=None)
    # 如果 today_str=None → 用 datetime.now()、但今天是 2026-06-28 剛好等於 caller 想測試的
    today_str = "2026-06-28"  # 週日

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        st._init_etf_history_db(tmp_path)

        # 6/25 (週四): 2330 有 500 股
        st._save_etf_holding_snapshot(tmp_path, "00400A", [
            {"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 500, "industry": ""},
        ], date_str="2026-06-25")

        # 6/26 (週五): 2330 增加到 1000 股 ← 真的有變動
        st._save_etf_holding_snapshot(tmp_path, "00400A", [
            {"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 1000, "industry": ""},
        ], date_str="2026-06-26")

        # 6/27 (週六): shares 完全跟 6/26 一樣 → stale
        st._save_etf_holding_snapshot(tmp_path, "00400A", [
            {"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 1000, "industry": ""},
        ], date_str="2026-06-27")

        # 6/28 (週日): shares 也完全跟 6/27 一樣 → stale
        st._save_etf_holding_snapshot(tmp_path, "00400A", [
            {"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 1000, "industry": ""},
        ], date_str="2026-06-28")

        # 呼叫：模擬週日打開 App
        result = st._compute_etf_changes(tmp_path, today_str=today_str)

        # 預期：跳過 6/28、6/27（都是 stale）、用 6/26 (週五) vs 6/25 (週四) 算
        # 1000 - 500 = 500 股 = 0.5 張
        assert not result.empty, (
            "週末 fallback 應跳過 stale dates、找出 6/26 vs 6/25 的異動、不應回傳空"
        )
        assert "today_change_lots" in result.columns
        row = result[result["stock_code"] == "2330"]
        assert not row.empty, "應有 2330 的異動 row"
        actual = row.iloc[0]["today_change_lots"]
        assert actual == 0.5, (
            f"週末 fallback 應抓到 6/26 vs 6/25 的異動 = +0.5 張、實際: {actual}"
        )
        print(f"PASS: test_weekend_fallback_取最後有變動的交易日 (today_change_lots = {actual})")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_weekday_no_fallback_保留原本行為():
    """【V0.9.5-etf-weekend-fix 向後相容】

    模擬：今天 2026-06-23 (週二) 正常交易日
    DB dates = [2026-06-23, 2026-06-22]
    - 6/23 shares 跟 6/22 不同 → 正常算 today vs yesterday

    預期：用 6/23 vs 6/22 算、不 fallback
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        st._init_etf_history_db(tmp_path)

        st._save_etf_holding_snapshot(tmp_path, "00400A", [
            {"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 500, "industry": ""},
        ], date_str="2026-06-22")
        st._save_etf_holding_snapshot(tmp_path, "00400A", [
            {"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 1000, "industry": ""},
        ], date_str="2026-06-23")

        result = st._compute_etf_changes(tmp_path, today_str="2026-06-23")

        assert not result.empty
        row = result[result["stock_code"] == "2330"].iloc[0]
        assert row["today_change_lots"] == 0.5, (
            f"平日 6/23 vs 6/22 應 = +0.5 張、實際: {row['today_change_lots']}"
        )
        print(f"PASS: test_weekday_no_fallback_保留原本行為 (today_change_lots = {row['today_change_lots']})")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ==========================================================
# 【邊界】helper 函數
# ==========================================================

def test_helper_dates_have_changes_兩天完全一樣():
    """【V0.9.5-etf-weekend-fix】_etf_dates_have_changes: 兩天完全一樣 → False"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        st._init_etf_history_db(tmp_path)
        for d in ["2026-06-26", "2026-06-27"]:
            st._save_etf_holding_snapshot(tmp_path, "00400A", [
                {"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 1000, "industry": ""},
            ], date_str=d)

        result = st._etf_dates_have_changes(tmp_path, "2026-06-27", "2026-06-26")
        assert result is False, f"兩天完全一樣應回 False、實際: {result}"
        print("PASS: test_helper_dates_have_changes_兩天完全一樣")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_helper_dates_have_changes_shares不同():
    """【V0.9.5-etf-weekend-fix】_etf_dates_have_changes: shares 不同 → True"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        st._init_etf_history_db(tmp_path)
        st._save_etf_holding_snapshot(tmp_path, "00400A", [
            {"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 500, "industry": ""},
        ], date_str="2026-06-26")
        st._save_etf_holding_snapshot(tmp_path, "00400A", [
            {"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 1000, "industry": ""},
        ], date_str="2026-06-27")

        result = st._etf_dates_have_changes(tmp_path, "2026-06-27", "2026-06-26")
        assert result is True, f"shares 不同應回 True、實際: {result}"
        print("PASS: test_helper_dates_have_changes_shares不同")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_helper_dates_have_changes_一邊全空():
    """【V0.9.5-etf-weekend-fix】_etf_dates_have_changes: 一邊全空 → True（大變動）"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        st._init_etf_history_db(tmp_path)
        st._save_etf_holding_snapshot(tmp_path, "00400A", [
            {"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 1000, "industry": ""},
        ], date_str="2026-06-26")
        # 6/27 完全沒寫 → 全清倉

        result = st._etf_dates_have_changes(tmp_path, "2026-06-27", "2026-06-26")
        assert result is True, f"一邊全空（清倉）應回 True、實際: {result}"
        print("PASS: test_helper_dates_have_changes_一邊全空")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_helper_dates_have_changes_新增股票():
    """【V0.9.5-etf-weekend-fix】_etf_dates_have_changes: B 沒有的股票 A 新增 → True"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        st._init_etf_history_db(tmp_path)
        st._save_etf_holding_snapshot(tmp_path, "00400A", [
            {"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 1000, "industry": ""},
        ], date_str="2026-06-26")
        st._save_etf_holding_snapshot(tmp_path, "00400A", [
            {"stock_code": "2330", "stock_name": "台積電", "weight": 40.0, "shares": 800, "industry": ""},
            {"stock_code": "2454", "stock_name": "聯發科", "weight": 10.0, "shares": 500, "industry": ""},
        ], date_str="2026-06-27")

        result = st._etf_dates_have_changes(tmp_path, "2026-06-27", "2026-06-26")
        assert result is True, f"新增 2454 + 2330 shares 變 → True、實際: {result}"
        print("PASS: test_helper_dates_have_changes_新增股票")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_helper_find_latest_changed_pair_跳過stale():
    """【V0.9.5-etf-weekend-fix】_find_latest_changed_etf_pair: 跳過 stale dates、找有變動的"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        st._init_etf_history_db(tmp_path)

        # 4 天、其中前兩天 stale、最後一對有變動
        st._save_etf_holding_snapshot(tmp_path, "00400A", [
            {"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 500, "industry": ""},
        ], date_str="2026-06-25")
        st._save_etf_holding_snapshot(tmp_path, "00400A", [
            {"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 1000, "industry": ""},
        ], date_str="2026-06-26")
        # 6/27, 6/28 都跟 6/26 一樣 → stale
        for d in ["2026-06-27", "2026-06-28"]:
            st._save_etf_holding_snapshot(tmp_path, "00400A", [
                {"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 1000, "industry": ""},
            ], date_str=d)

        result = st._find_latest_changed_etf_pair(tmp_path, ["2026-06-28", "2026-06-27", "2026-06-26", "2026-06-25"])
        assert result == ("2026-06-26", "2026-06-25"), (
            f"應跳過 6/28, 6/27 找到 6/26 vs 6/25、實際: {result}"
        )
        print(f"PASS: test_helper_find_latest_changed_pair_跳過stale ({result})")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_helper_find_latest_changed_pair_找不到():
    """【V0.9.5-etf-weekend-fix】_find_latest_changed_etf_pair: 全部都一樣 → None"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        st._init_etf_history_db(tmp_path)
        for d in ["2026-06-26", "2026-06-27", "2026-06-28"]:
            st._save_etf_holding_snapshot(tmp_path, "00400A", [
                {"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 1000, "industry": ""},
            ], date_str=d)

        result = st._find_latest_changed_etf_pair(tmp_path, ["2026-06-28", "2026-06-27", "2026-06-26"])
        assert result is None, f"全部都一樣應回 None、實際: {result}"
        print("PASS: test_helper_find_latest_changed_pair_找不到")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ==========================================================
# 【邊界】今天 DB 完全沒資料
# ==========================================================

def test_today_str不在DB_且DB只有1天資料():
    """【V0.9.5-etf-weekend-fix】today_str 不在 DB、DB 只有 1 天資料 → 空 DataFrame"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        st._init_etf_history_db(tmp_path)
        st._save_etf_holding_snapshot(tmp_path, "00400A", [
            {"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 1000, "industry": ""},
        ], date_str="2026-06-20")

        result = st._compute_etf_changes(tmp_path, today_str="2099-12-31")
        assert result.empty, f"DB 只有 1 天、無 yesterday → 應回傳空、實際 shape: {result.shape}"
        print("PASS: test_today_str不在DB_且DB只有1天資料")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_today_str不在DB_且DB全stale():
    """【V0.9.5-etf-weekend-fix】today_str 不在 DB、DB 全部 shares 一樣 → 空 DataFrame"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        st._init_etf_history_db(tmp_path)
        for d in ["2026-06-25", "2026-06-26", "2026-06-27"]:
            st._save_etf_holding_snapshot(tmp_path, "00400A", [
                {"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 1000, "industry": ""},
            ], date_str=d)

        # 傳一個 DB 沒有的日期
        result = st._compute_etf_changes(tmp_path, today_str="2099-12-31")
        # DB 內 6/27, 6/26, 6/25 全部 shares 一樣 → 找不到變動 → 空
        assert result.empty, f"全 stale 應回傳空、實際 shape: {result.shape}"
        print("PASS: test_today_str不在DB_且DB全stale")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_today_str不在DB_取最後有變動的對():
    """【V0.9.5-etf-weekend-fix】today_str 不在 DB、但 DB 內有實質變動 → 取最後變動對"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        st._init_etf_history_db(tmp_path)
        st._save_etf_holding_snapshot(tmp_path, "00400A", [
            {"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 500, "industry": ""},
        ], date_str="2026-06-25")
        st._save_etf_holding_snapshot(tmp_path, "00400A", [
            {"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 1000, "industry": ""},
        ], date_str="2026-06-26")

        # today_str = 2099-12-31 → 不在 DB → 用 DB 內最後有變動的對
        result = st._compute_etf_changes(tmp_path, today_str="2099-12-31")

        assert not result.empty, "DB 內有變動應有結果"
        row = result[result["stock_code"] == "2330"].iloc[0]
        assert row["today_change_lots"] == 0.5, (
            f"應 = 6/26 vs 6/25 = +0.5 張、實際: {row['today_change_lots']}"
        )
        print(f"PASS: test_today_str不在DB_取最後有變動的對 (today_change_lots = {row['today_change_lots']})")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ==========================================================
# 【真實 DB】在 production etf_history.db 上跑
# ==========================================================

def test_real_db_2026_06_28_周日():
    """【V0.9.5-etf-weekend-fix 真實 DB】2026-06-28 (週日) 應回傳 6/27 vs 6/26 的異動"""
    db_path = "etf_history.db"
    if not os.path.exists(db_path):
        print(f"SKIP: {db_path} 不存在、跳過真實 DB 測試")
        return

    # 直接呼叫 today_str=None（用 datetime.now() = 2026-06-28）
    # 但系統時間可能不是 6/28、所以手動傳
    result = st._compute_etf_changes(db_path, today_str="2026-06-28")

    # 預期：有資料（原本是空）
    # 具體 row 數可能隨 DB 內容變動、不嚴格斷
    assert not result.empty, (
        f"真實 DB 6/28 週日、原本是空 DataFrame、應該 fallback 到 6/27 vs 6/26、實際空"
    )

    # 至少要有台積電（2330）、因為 6/27 vs 6/26 有變動
    assert "2330" in result["stock_code"].values, "應有 2330 (台積電) 的異動 row"
    row = result[result["stock_code"] == "2330"].iloc[0]
    # 6/27 vs 6/26 2330 增持 +249 張（從之前 console 輸出確認）
    assert row["today_change_lots"] == 249.0, (
        f"2330 應為 +249.0 張（6/27 vs 6/26）、實際: {row['today_change_lots']}"
    )
    print(f"PASS: test_real_db_2026_06_28_周日 (2330 today_change_lots = {row['today_change_lots']})")


if __name__ == "__main__":
    test_weekend_fallback_取最後有變動的交易日()
    test_weekday_no_fallback_保留原本行為()
    test_helper_dates_have_changes_兩天完全一樣()
    test_helper_dates_have_changes_shares不同()
    test_helper_dates_have_changes_一邊全空()
    test_helper_dates_have_changes_新增股票()
    test_helper_find_latest_changed_pair_跳過stale()
    test_helper_find_latest_changed_pair_找不到()
    test_today_str不在DB_且DB只有1天資料()
    test_today_str不在DB_且DB全stale()
    test_today_str不在DB_取最後有變動的對()
    test_real_db_2026_06_28_周日()
    print("\nAll V0.9.5-etf-weekend-fix tests passed!")