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

    # 手動覆寫某檔某年的配息（FinMind 抓錯、可以手動改）
    python ../scripts/fetch_dividend.py update 3546 2025 --cash 2.0
    python ../scripts/fetch_dividend.py update 3546 2025 --cash 2.0 --stock 0.5

    # 查某檔的歷史配息
    python ../scripts/fetch_dividend.py show 3546

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
import argparse
import sqlite3
from datetime import datetime

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


def cmd_update(stock_id: str, year: int, cash=None, stock=None):
    """手動覆寫某檔某年的配息（FinMind 抓錯的時用）"""
    db_path = "dividend_history.db"
    st._init_div_history_db(db_path)
    sid = str(stock_id).strip()

    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            "SELECT cash, stock, source FROM dividend_history WHERE stock_id = ? AND year = ?",
            (sid, year),
        )
        row = cur.fetchone()
        if not row:
            print(f"❌ {sid} {year} 不存在於 DB")
            print(f"   可以先用 `fetch {sid}` 補抓、或用 insert 子命令新增")
            return 1

        old_cash, old_stock, old_source = row
        new_cash = cash if cash is not None else old_cash
        new_stock = stock if stock is not None else old_stock

        if new_cash == old_cash and new_stock == old_stock:
            print(f"ℹ️  {sid} {year} 沒變動 (cash={old_cash}, stock={old_stock}, source={old_source})")
            return 0

        conn.execute(
            "UPDATE dividend_history SET cash = ?, stock = ?, source = ?, fetched_at = ? "
            "WHERE stock_id = ? AND year = ?",
            (new_cash, new_stock, "manual", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), sid, year),
        )
        conn.commit()
        print(f"✅ {sid} {year}:")
        print(f"   現金股利: {old_cash} → {new_cash}")
        if new_stock != old_stock:
            print(f"   股票股利: {old_stock} → {new_stock}")
        print(f"   來源: {old_source} → manual")
        print()
        # 自動計算殖利率說明
        if new_cash > 0:
            print(f"💡 重跑「開始選股」就會看到新殖利率（{new_cash}/現價*100%）")
            print(f"   範例：現價 82 → {new_cash}/82*100% = {new_cash/82*100:.2f}%")
    return 0


def cmd_show(stock_id: str):
    """查某檔在 DB 的歷史配息"""
    db_path = "dividend_history.db"
    st._init_div_history_db(db_path)
    sid = str(stock_id).strip()

    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            "SELECT year, cash, stock, source, fetched_at "
            "FROM dividend_history WHERE stock_id = ? ORDER BY year DESC",
            (sid,),
        )
        rows = cur.fetchall()

    if not rows:
        print(f"❌ {sid} 不存在於 DB")
        return 1

    print(f"📊 {sid} 股利歷史：")
    print(f"   {'年度':<6}{'現金股利':>10}{'股票股利':>10}  {'來源':<10}{'抓取時間'}")
    print(f"   {'─'*6}{'─'*10}{'─'*10}  {'─'*10}{'─'*19}")
    for year, cash, stock, source, fetched_at in rows:
        cash_str = f"{cash:.2f}" if cash is not None else "--"
        stock_str = f"{stock:.2f}" if stock is not None else "--"
        print(f"   {year:<6}{cash_str:>10}{stock_str:>10}  {source:<10}{fetched_at}")
    return 0


def cmd_reset_source(stock_id: str, year: int):
    """重設某筆資料的 source 為 finmind（手動改完想讓 FinMind 重新抓時用）
    例如：手動寫 cash=2.0、但之後想讓 FinMind 重新驗證 → reset 後下次重抓
    """
    db_path = "dividend_history.db"
    st._init_div_history_db(db_path)
    sid = str(stock_id).strip()

    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            "SELECT cash, stock, source FROM dividend_history WHERE stock_id = ? AND year = ?",
            (sid, year),
        )
        row = cur.fetchone()
        if not row:
            print(f"❌ {sid} {year} 不存在於 DB")
            return 1

        cash, stock, old_source = row
        if old_source == "finmind":
            print(f"ℹ️  {sid} {year} 已是 finmind 來源、無需重設")
            return 0

        conn.execute(
            "UPDATE dividend_history SET source = 'finmind' WHERE stock_id = ? AND year = ?",
            (sid, year),
        )
        conn.commit()
        print(f"✅ {sid} {year}: source {old_source} → finmind（下次重抓會用 FinMind 資料）")
    return 0


def main():
    if len(sys.argv) < 2:
        # 沒參數 → 顯示用法
        print("📋 用法：python fetch_dividend.py <股號1> <股號2> ...")
        print("          python fetch_dividend.py show <股號>")
        print("          python fetch_dividend.py update <股號> <年> [--cash X] [--stock Y]")
        print()
        print("範例：")
        print("  python fetch_dividend.py 3188 2330 2317")
        print("  python fetch_dividend.py 3188,2330,2317")
        print("  python fetch_dividend.py \"3188 2330 2317\"")
        print("  python fetch_dividend.py show 3546")
        print("  python fetch_dividend.py update 3546 2025 --cash 2.0")
        sys.exit(2)

    first = sys.argv[1]

    # 子命令 show
    if first == "show":
        if len(sys.argv) < 3:
            print("❌ 用法：python fetch_dividend.py show <股號>")
            sys.exit(2)
        sys.exit(cmd_show(sys.argv[2]))

    # 子命令 update
    if first == "update":
        parser = argparse.ArgumentParser(description="手動覆寫某檔某年的配息")
        parser.add_argument("stock_id", help="股號")
        parser.add_argument("year", type=int, help="年度（例如 2025）")
        parser.add_argument("--cash", type=float, help="現金股利（元）")
        parser.add_argument("--stock", type=float, help="股票股利（元）")
        args = parser.parse_args(sys.argv[2:])
        if args.cash is None and args.stock is None:
            print("❌ 至少要給 --cash 或 --stock 其中一個")
            sys.exit(2)
        sys.exit(cmd_update(args.stock_id, args.year, args.cash, args.stock))

    # 預設動作：補抓股號
    codes = parse_codes(sys.argv[1:])
    if not codes:
        print("❌ 沒有有效的股號")
        sys.exit(2)

    print(f"📋 收到 {len(codes)} 檔股號：{', '.join(codes)}")

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

    if added == -1:
        print("❌ 補抓中斷：FinMind 額度用完（status 402）")
        print("   請升級 plan 或等下月重置｜已寫入 DB 的資料已保存")
        sys.exit(1)

    print(f"✅ 補抓完成：{added} 檔寫入 {db_path}")
    print()
    print("💡 下次可用：")
    print(f"   python ../scripts/fetch_dividend.py <其他股號>")
    print(f"   或打開 App 看「🎯 指定股補抓」按鈕")
    print(f"   查詢歷史: python ../scripts/fetch_dividend.py show 3546")
    print(f"   手動覆寫: python ../scripts/fetch_dividend.py update 3546 2025 --cash 2.0")
    sys.exit(0)


if __name__ == "__main__":
    main()
