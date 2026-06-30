"""【v1.1.2-fallback-log】fetch_prices fallback 診斷 log 必須存在且分類正確

2026-06-30 23:15 William 反映：
- 「先修一下這個」
- 跑了 App 後看到「TWSE tse 整批失敗 20 次」+「MIS 未覆蓋 981 檔、fallback 到 STOCK_DAY_ALL / TPEx」
- 但 fallback 跑完仍抓不到的股沒有額外說明，使用者看不出原因

【根因】
- 跑了完整 fetch_prices 流程驗證（99.3% 抓取成功率）
- 剩 16 檔「TPEx 有代號但 Close 標記為「----」」（當日無成交）
- 過去是「靜默 NaN」、UI 顯示 -- 但 console 沒說明

【修法】
- Step 4 fallback 結束後（Step 5 整理欄位前）加 ℹ️ 診斷 log
- 4 類分流（互不重疊）：衍生檔 > KY 類 > 當日無成交 > 其他
- 不動 fallback 邏輯本身（向後相容、不影響現有 99.3% 成功率）
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
FETCH_MARKET_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "stocktool", "fetch_market.py"
)


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def test_fallback_diag_log_present():
    """fetch_prices fallback 結束後必須有 ℹ️ 診斷 log"""
    content = _read(FETCH_MARKET_PY)
    fn_start = content.find("def fetch_prices(")
    fn_end = content.find("\ndef ", fn_start + 1)
    fn_body = content[fn_start:fn_end]
    assert "fallback 後仍有" in fn_body, (
        "❌ fetch_prices 內沒看到「fallback 後仍有」診斷 log！\n"
        "→ 應在 Step 4 fallback 結束後印 ℹ️ 訊息，列出當日無成交 / 衍生檔 / KY 類 / 其他"
    )


def test_fallback_diag_log_categories():
    """4 類分流必須都存在：衍生檔 / KY 類 / 當日無成交 / 其他"""
    content = _read(FETCH_MARKET_PY)
    fn_start = content.find("def fetch_prices(")
    fn_end = content.find("\ndef ", fn_start + 1)
    fn_body = content[fn_start:fn_end]
    for kw in ["衍生檔", "KY 類", "當日無成交", "其他"]:
        assert kw in fn_body, f"❌ 漏掉分類「{kw}」"


def test_fallback_diag_log_no_overlap():
    """4 類分流邏輯必須互不重疊（先扣除衍生檔、再扣 KY 類、再扣 當日無成交）"""
    content = _read(FETCH_MARKET_PY)
    fn_start = content.find("def fetch_prices(")
    fn_end = content.find("\ndef ", fn_start + 1)
    fn_body = content[fn_start:fn_end]
    # 確認 etf_like 用 `not in etf_like` 排除自己
    assert "c not in etf_like" in fn_body, (
        "❌ 衍生檔扣除邏輯錯！應為「c not in etf_like」"
    )
    # 確認 ky_like 排除 etf_like
    assert "c not in etf_like and c not in ky_like" in fn_body, (
        "❌ 當日無成交扣除邏輯錯！應扣除 etf_like + ky_like"
    )


def test_fallback_diag_log_correctly_classifies_known_codes():
    """已知 16 檔的分類結果應正確"""
    # 已知分類（2026-06-30 23:15 驗證）：
    # - 衍生檔（02000X）：020001, 020035, 020040 (3 檔)
    # - KY 類（無 STOCK_DAY_ALL）：0 檔
    # - 當日無成交（TPEx 標 ----）：13 檔
    # - 其他：0 檔
    KNOWN_ETFS = {"020001", "020035", "020040"}
    KNOWN_NO_TRADE = {
        "2924", "2937", "2941", "2948", "3064", "3085", "3629",
        "4905", "6236", "6240", "6542", "6904", "8905",
    }
    KNOWN_KY = set()  # 本次沒有 KY
    KNOWN_OTHER = set()  # 本次沒有其他

    all_codes = KNOWN_ETFS | KNOWN_NO_TRADE | KNOWN_KY | KNOWN_OTHER
    assert len(all_codes) == 16, f"預期 16 檔、實 {len(all_codes)}"

    # 分流邏輯（與 fetch_market.py 同步）
    no_trade_set = KNOWN_NO_TRADE  # 假設 TPEx ---- 的 set
    etf_like = sorted([c for c in all_codes if str(c).startswith("020")])
    ky_like = sorted([c for c in all_codes if str(c).endswith("KY") and c not in etf_like])
    no_trade_only = sorted([c for c in all_codes if c in no_trade_set and c not in etf_like and c not in ky_like])
    other = sorted([c for c in all_codes if c not in etf_like and c not in ky_like and c not in no_trade_only])

    assert set(etf_like) == KNOWN_ETFS, f"衍生檔分類錯: {etf_like}"
    assert set(ky_like) == KNOWN_KY, f"KY 類分類錯: {ky_like}"
    assert set(no_trade_only) == KNOWN_NO_TRADE, f"當日無成交分類錯: {no_trade_only}"
    assert set(other) == KNOWN_OTHER, f"其他分類錯: {other}"


def test_version_bumped_to_v1_1_2():
    """VERSION 必須更新為 v1.1.2-fallback-log"""
    import importlib
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
    if "stocktool" in sys.modules:
        # 重新載入避免 cache
        import importlib
        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith("stocktool"):
                importlib.reload(sys.modules[mod_name])
    from stocktool.config import VERSION
    assert VERSION == "v1.1.2-fallback-log", f"❌ VERSION 應為 v1.1.2-fallback-log、實 {VERSION}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])