#!/usr/bin/env python3
"""
fetch_dividend.py — CLI 補抓指定股票股利到 dividend_history.db

【為什麼要這個】
V0.9.5-alpha 的「🎯 指定股補抓」按鈕在 App 內運作。
但有時使用者想從命令列或對話中直接跑（不開 App），
這個腳本就提供 CLI 介面。

【用法】
    # 在 source/ 內跑（要 import StockTool）：
    cd source
    python ../scripts/fetch_dividend.py 3188 2330 2317 2454

    # 或用 venv：
    cd source
    /path/to/.venv/bin/python ../scripts/fetch_dividend.py 3188 2330 2317

    # 多個股號（任何分隔都 OK）：
    python ../scripts/fetch_dividend.py 3188,2330,2317
    python ../scripts/fetch_dividend.py "3188 2330 2317"

【輸出】
    📋 需抓 3 檔（1 檔已在 DB 跳過）
    進度 1/3（33%）
    進度 2/3（66%）
    進度 3/3（100%）
    ✅ 補抓完成：3 檔寫入 dividend_history.db

【回傳值】
    0 = 全部完成
    1 = 部分完成（FinMind 402 額度用完）
    2 = 完全失敗
"""
import os
import re
import sys

# 確保能 import StockTool
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "source")
sys.path.insert(0, SOURCE_DIR)
os.chdir(SOURCE_DIR)  # 讓 DB 路徑（"dividend_history.db"）寫在 source/

import StockTool as st  # noqa: E402


def parse_codes(args: list) -> list:
    """解析命令列參數 → 股號清單
    支援：
      python fetch_dividend.py 3188 2330 2317
      python fetch_dividend.py 3188,2330,2317
      python fetch_dividend.py "3188 2330 2317"
    """
    raw = " ".join(args)
    codes = [c.strip() for c in re.split(r"[\s,，]+", raw) if c.strip()]
    return codes


def main():
    if len(sys.argv) < 2:
        print("📋 用法：python fetch_dividend.py 股號1 股號2 ...")
        print()
        print("範例：")
        print("  python ../scripts/fetch_dividend.py 3188 2330 2317")
        print("  python ../scripts/fetch_dividend.py 3188,2330,2317")
        print("  python ../scripts/fetch_dividend.py \"3188 2330 2317\"")
        sys.exit(2)

    codes = parse_codes(sys.argv[1:])
    if not codes:
        print("❌ 沒有有效的股號")
        sys.exit(2)

    print(f"📋 收到 {len(codes)} 檔股號：{', '.join(codes)}")

    # 初始化 DB + 查哪些已存在
    db_path = "dividend_history.db"
    st._init_div_history_db(db_path)
    cached = st._query_div_history(db_path, codes)
    to_fetch = [c for c in codes if c not in cached]
    skipped = [c for c in codes if c in cached]

    if skipped:
        print(f"⏭️  已在 DB 跳過 {len(skipped)} 檔：{', '.join(skipped)}")
    if not to_fetch:
        print("✅ 全部已在 DB、無需補抓")
        sys.exit(0)

    print(f"🔄 開始補抓 {len(to_fetch)} 檔（FinMind 額度 300-1000/月）...")

    # 跑
    try:
        added = st._background_fetch_all_dividend(
            to_fetch, db_path=db_path,
            progress_callback=lambda d, t: print(
                f"\r   進度 {d}/{t}（{int(d/t*100)}%）", end="", flush=True,
            ),
        )
        print()  # 進度列印結束後換行
    except Exception as e:
        print(f"\n❌ 補抓失敗：{e}")
        sys.exit(2)

    # 結果
    if added == -1:
        print("❌ 補抓中斷：FinMind 額度用完（status 402）")
        print("   請升級 plan 或等下月重置｜已寫入 DB 的資料已保存")
        sys.exit(1)

    print(f"✅ 補抓完成：{added} 檔寫入 {db_path}")
    print()
    print("💡 下次可用：")
    print(f"   python ../scripts/fetch_dividend.py <其他股號>")
    print(f"   或打開 App 看「🎯 指定股補抓」按鈕")
    sys.exit(0)


if __name__ == "__main__":
    main()
