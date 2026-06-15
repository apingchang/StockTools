"""
test_market_hours.py
驗證 V0.9.5+ Phase 7：_is_market_hours() 判斷台股盤中時段邏輯。

【V0.9.5+ Phase 7 規則】William 2026-06-15 09:56 設定
- 每天 09:00 後執行 App、任何需要股票現價 → 應該 refresh 所有股價
- 收盤（13:30）後 → 只要 refresh 一次（一天一次）
- 週末 → 用上週五收盤價、不 refresh

【為什麼要獨立 test 守護】
- _is_market_hours 邏輯很簡單但邊界很多（盤中、盤後、凌晨、週末、跨日）
- 影響 get_or_fetch 行為：盤中走「強制 refresh」路徑、盤後走「cache 優先」路徑
- 萬一未來改時間（例如改 13:00 收盤）、這層 test 會第一時間跳出來

【台股交易時間】
- 平日 09:00 ~ 13:30
- 不含早盤 09:00 前的「盤前撮合」
- 不含夜盤（台股沒有夜盤）
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402


# ==========================================================
# 【盤中】平日 09:00 ~ 13:30
# ==========================================================

def test_平日_開盤瞬間_算盤中():
    """09:00:00 整點算盤中（開盤第一秒）"""
    now = datetime(2026, 6, 15, 9, 0, 0)  # 週一 09:00:00
    assert st._is_market_hours(now) is True, "09:00:00 應算盤中"


def test_平日_中午_算盤中():
    """12:00 算盤中（盤中中間點）"""
    now = datetime(2026, 6, 15, 12, 0, 0)  # 週一 12:00
    assert st._is_market_hours(now) is True, "12:00 應算盤中"


def test_平日_收盤前一分鐘_算盤中():
    """13:29:00 算盤中（收盤前 1 分鐘）"""
    now = datetime(2026, 6, 15, 13, 29, 0)  # 週一 13:29
    assert st._is_market_hours(now) is True, "13:29 應算盤中"


def test_平日_收盤瞬間_算盤中():
    """13:30:00 整點算盤中（盤中最後一秒）"""
    now = datetime(2026, 6, 15, 13, 30, 0)  # 週一 13:30:00
    assert st._is_market_hours(now) is True, "13:30:00 應算盤中（收盤整點）"


# ==========================================================
# 【盤後】13:30 後到當日結束
# ==========================================================

def test_平日_收盤後1秒_不算盤中():
    """13:30:01 起算盤後（收盤後 1 秒）"""
    now = datetime(2026, 6, 15, 13, 30, 1)  # 週一 13:30:01
    assert st._is_market_hours(now) is False, "13:30:01 應算盤後"


def test_平日_下午3點_不算盤中():
    """15:00 不算盤中（盤後）"""
    now = datetime(2026, 6, 15, 15, 0, 0)  # 週一 15:00
    assert st._is_market_hours(now) is False, "15:00 應算盤後"


def test_平日_晚上10點_不算盤中():
    """22:00 不算盤中（盤後、收盤很久後）"""
    now = datetime(2026, 6, 15, 22, 0, 0)  # 週一 22:00
    assert st._is_market_hours(now) is False, "22:00 應算盤後"


def test_平日_凌晨_不算盤中():
    """00:00 不算盤中（凌晨）"""
    now = datetime(2026, 6, 15, 0, 0, 0)  # 週一 00:00
    assert st._is_market_hours(now) is False, "00:00 應算盤後"


# ==========================================================
# 【盤前】00:00 ~ 09:00
# ==========================================================

def test_平日_早上8點59_不算盤中():
    """08:59 不算盤中（盤前）"""
    now = datetime(2026, 6, 15, 8, 59, 0)  # 週一 08:59
    assert st._is_market_hours(now) is False, "08:59 應算盤前"


def test_平日_凌晨1點_不算盤中():
    """01:00 不算盤中（凌晨、盤前）"""
    now = datetime(2026, 6, 15, 1, 0, 0)  # 週一 01:00
    assert st._is_market_hours(now) is False, "01:00 應算盤前"


# ==========================================================
# 【週末】週六、週日
# ==========================================================

def test_週六_中午_不算盤中():
    """週六 12:00 不算盤中（週末、不開盤）"""
    now = datetime(2026, 6, 20, 12, 0, 0)  # 週六 12:00
    assert st._is_market_hours(now) is False, "週六 12:00 應算週末（不開盤）"


def test_週日_下午3點_不算盤中():
    """週日 15:00 不算盤中（週末、不開盤）"""
    now = datetime(2026, 6, 21, 15, 0, 0)  # 週日 15:00
    assert st._is_market_hours(now) is False, "週日 15:00 應算週末（不開盤）"


def test_週五_下午3點_不算盤中():
    """週五 15:00 不算盤中（盤後）"""
    now = datetime(2026, 6, 19, 15, 0, 0)  # 週五 15:00
    assert st._is_market_hours(now) is False, "週五 15:00 應算盤後（雖是平日但已收盤）"


def test_週五_中午12點_算盤中():
    """週五 12:00 算盤中（平日盤中）"""
    now = datetime(2026, 6, 19, 12, 0, 0)  # 週五 12:00
    assert st._is_market_hours(now) is True, "週五 12:00 應算盤中"


# ==========================================================
# 【實戰情境】William 2026-06-15 09:56 提到
# ==========================================================

def test_William情境_早上9點01分_算盤中():
    """【實戰】William 09:56 說「09:00 後執行 App 要 refresh」
    09:01 開 App → 應觸發 refresh"""
    now = datetime(2026, 6, 15, 9, 1, 0)  # 週一 09:01
    assert st._is_market_hours(now) is True, "09:01 應算盤中（要 refresh）"


def test_William情境_下午2點_算盤後():
    """【實戰】下午 2:00 已收盤 30 分鐘 → 走「一天一次」路徑
    William 09:56 規則：「收盤（13:30）後只要 refresh 一次」
    → 14:00 開 App → 用今日 cache、不重抓
    """
    now = datetime(2026, 6, 15, 14, 0, 0)  # 週一 14:00
    assert st._is_market_hours(now) is False, "14:00 應算盤後（已收盤 30 分鐘）"
