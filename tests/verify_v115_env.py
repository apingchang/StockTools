"""verify_v115_env.py — 5 秒驗證當前 PyCharm 載入的 stocktool 版本

不需關 App、不需重啟 GUI — 直接在 PyCharm Terminal 跑：
    python tests/verify_v115_env.py

跑完看 ✓ / ✗ 列表、就知道 v1.1.5 是不是真的生效了
"""
import os
import sys

# 確保從 source/ import（跟 StockTool.py 同一個 __init__ 路徑）
SOURCE_DIR = os.path.join(os.path.dirname(__file__), "..", "source")
if SOURCE_DIR not in sys.path:
    sys.path.insert(0, SOURCE_DIR)

print("=" * 70)
print("🔍 驗證當前 PyCharm import 的 stocktool 是不是 v1.1.5")
print("=" * 70)

# 1. VERSION 檢查
print("\n【1】VERSION 檢查（stocktool/config.py）")
try:
    from stocktool.config import VERSION, _HOLIDAY_DATES, _HALF_DAY_DATES
    if VERSION == "v1.1.5-holiday-console-log":
        print(f"  ✅ VERSION = {VERSION}（正確）")
    else:
        print(f"  ❌ VERSION = {VERSION}（應為 v1.1.5-holiday-console-log）")
        print(f"     → 你 PyCharm 還沒重啟 App、還是舊版")
        sys.exit(1)
except Exception as e:
    print(f"  ❌ import 失敗：{e}")
    sys.exit(1)

# 2. _HOLIDAY_DATES 檢查
print("\n【2】_HOLIDAY_DATES 國定假日清單檢查")
holidays = _HOLIDAY_DATES
print(f"  找到 {len(holidays)} 個國定假日:")
for h in sorted(holidays):
    if "2026" in h:
        print(f"    {h}")
if "2026-06-19" in holidays and "2026-01-01" in holidays:
    print(f"  ✅ 端午節 + 元旦都在清單")
else:
    print(f"  ❌ 端午節或元旦不在清單")

# 3. _is_market_hours 測試
print("\n【3】_is_market_hours() 端午節判斷")
from datetime import datetime
from stocktool.config import _is_market_hours
result = _is_market_hours(datetime(2026, 6, 19, 10, 0, 0))
if result is False:
    print(f"  ✅ 2026-06-19 (週五端午節) 10:00 → False（全日休市）")
else:
    print(f"  ❌ 應為 False、但回 True（沒生效）")

# 4. console log file 機制檢查
print("\n【4】console log file 機制檢查")
import inspect
from stocktool import config
src_path = inspect.getsourcefile(config)
print(f"  config.py 路徑：{src_path}")

# 找 StockTool.py 並檢查有沒有 console log file 邏輯
stocktool_pys = []
for root, dirs, files in os.walk(SOURCE_DIR):
    for f in files:
        if f == "StockTool.py":
            stocktool_pys.append(os.path.join(root, f))

if stocktool_pys:
    with open(stocktool_pys[0], "r", encoding="utf-8") as fp:
        content = fp.read()
    if "_console_log_path" in content and "cache/console" in content:
        print(f"  ✅ console log file 機制存在於 {os.path.basename(stocktool_pys[0])}")
    else:
        print(f"  ❌ 沒看到 console log file 機制")

# 5. Working dir 的 cache/console 檢查
print("\n【5】cache/console/ 目錄檢查")
cwd = os.getcwd()
cache_dir = os.path.join(cwd, "cache", "console")
exists = os.path.exists(cache_dir)
if exists:
    files = os.listdir(cache_dir)
    print(f"  ✅ 目錄存在：{cache_dir}")
    print(f"     內含 {len(files)} 個檔:")
    for f in files[:10]:
        full = os.path.join(cache_dir, f)
        size = os.path.getsize(full)
        print(f"       {f} ({size:,} bytes)")
else:
    print(f"  ⚠️  目錄不存在：{cache_dir}")
    print(f"     → **App 從未以 v1.1.5 啟動過**")
    print(f"     → 你 PyCharm 還在跑舊版（v1.1.4c 之前、訊息走 print() 進 PyCharm Run 視窗）")

print("\n" + "=" * 70)
print("【結論】")
if exists and "v1.1.5-holiday-console-log" in VERSION:
    print("✅ v1.1.5 已正確生效、你 App console 沒看到整批失敗 = GUI widget 問題")
    print("   點 App 主畫面左邊「📄 開啟 console log 檔」按鈕看完整 log")
else:
    print("❌ v1.1.5 還沒生效、你看到的訊息是 print() 進 PyCharm Run 視窗")
    print("   動作：完全關掉 PyCharm App → 重新開啟")
    print("   視窗標題應該出現「StockTool v1.1.5-holiday-console-log ...」")
print("=" * 70)
