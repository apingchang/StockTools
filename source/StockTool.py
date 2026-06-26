"""
╔══════════════════════════════════════════════════════════════════════════════╗
║               台灣股市量化選股系統 v1.1 (2026-06-26 18:35)       ║
╚══════════════════════════════════════════════════════════════════════════════╝
【版本資訊】
Version: v1.1
最後更新: 2026-06-26 18:35 (Asia/Taipei)
Python 版本: 3.8+
依賴套件: tkinter, pandas, requests, openpyxl, numpy, itertools

════════════════════════════════════════════════════════════════════════════════
════════════════════════════════════════════════════════════════════════════════
【V0.9.5-goodinfo6】2026-06-26 11:30 (William 11:22 重新抓 goodinfo 股利/殖利率檔)
════════════════════════════════════════════════════════════════════════════════
【背景】William 2026-06-26 11:22 反映重新抓了 goodinfo 股利/殖利率檔、放：
  ~/.openclaw/workspace/股神/.tmp/goodinfo_export/dividend/

【新版 vs 舊版 4 個差異】
  1. 價位帶擴大：P50U → P55U (923 檔)、P20-50 → P20-55 (836 檔)
     → 涵蓋更多中價股（高價股從 ~700 檔變 923 檔）
  2. 檔名怪：P55U 用 Dividend10Y、P20-55/P20L 用 Divided10Y（e 跟 i 顛倒）
     → GoodInfo 網頁 URL 在中低價股頁面拼字顛倒、無解、要寫程式兼容
  3. Divided10Y 已經是「純現金股利」（不是合計）、cash 直接拿
     → 舊版要用「cash = 10Y_div - 10Y_share」扣股票才得現金
     → 新版直接拿 cash = Divided10Y、簡化算法、避免負值 corner case
  4. P55U/P20-55 的 ShareRate 內容跟 DividendRate 一模一樣（GoodInfo bug）
     → 寫入 share_yield_pct 會把 stock_yield 覆蓋成 cash_yield
     → 跳過這兩個檔、只用 P20L_ShareRate 寫入 share_yield_pct

【實作】scripts/import_goodinfo_history.py
  - FILE_PREFIX_MAP 改為新前綴 (P55U / P20-55) + 新 Divided10Y 拼字
  - import_dividend 改用「cash = Divided10Y 直接拿」(不再扣 stock)
  - import_yield_rate 加 BAD_SHARE_RATE_GROUPS = {"P55U", "P20-55"} 跳過 bug 檔
  - 兩個常數提到 module 層讓 test 可以 import 驗證

【結果】
  - div: 15268 列 / 2043 檔 / 10 年 (vs 舊 15253 列)
  - yield: cash_yield_pct 15408 筆 / 2212 檔 (vs 舊 15393 筆)
  - yield: share_yield_pct 2961 筆 (vs 舊 15363 筆！大幅下降、因為跳過 2 個 bug 檔)
  - 2026exdate: UPDATE ex_date 1670 筆

【test】tests/test_import_goodinfo_v0_9_5g6.py（新、12 個）
  - test_FILE_PREFIX_MAP_P55U_uses_Dividend10Y：P55U 用 Dividend10Y
  - test_FILE_PREFIX_MAP_P20_55_uses_Divided10Y：P20-55/P20L 用 Divided10Y
  - test_old_P50U_and_P20_50_should_not_be_in_map：舊前綴拿掉
  - test_dividend_cash_equals_divided10y_directly：2442 2025 cash=0.08 純現金
  - test_BAD_SHARE_RATE_GROUPS_包含_P55U_跟_P20_55：跳過清單正確
  - test_import_yield_rate跳過P55U_P20_55_ShareRate：實際 import 跳過 bug 檔
  - test_2442_2025_cash_0_079_stock_0_158：DB 內資料正確
  - test_zero_cash_dividend_still_inserted（V0.9.5-goodinfo6+）：val=0 不跳過、6219 2026
  - test_finmind_keys_filtered_from_goodinfo_rows（V0.9.5-goodinfo6+）：6219 2024 finmind 保留
  - test_1808_2026_yield_is_4_83（end-to-end）：1808 殖利率 4.83%
  - test_6219_2026_yield_is_zero（end-to-end）：6219 殖利率 0%
  - test_6219_2024_finmind_preserved（end-to-end）：finmind (0.7, 0.5) 保留
  - 全部 465 passed (453 既有 + 12 新)、0 failed


════════════════════════════════════════════════════════════════════════════════
【V0.9.5-goodinfo6+】2026-06-26 12:35 (修手動選股殖利率 bug)
════════════════════════════════════════════════════════════════════════════════
【背景】William 2026-06-26 12:00 反映：
  - 「6219 漲利率 0.04%（應為 0%）」
  - 「1808 漲利率 0.05%（應為 4.83%）」

【根因 1：val=0 跳過 INSERT】
  - scripts/import_goodinfo_history.py 原本 `if pd.isna(val) or val == 0: continue`
  - 6219 2026 cash=0, stock=0 → 該年 row 不 INSERT
  - 後期 import_yield_rate 查不到 2026 row → cash_yield_pct 沒寫入
  - 手動選股「今年現金殖利率(%)」= None → 顯示 0.00（不是 0%）

【根因 2：finmind 補的會被 goodinfo 覆蓋】
  - 6219 2024 finmind 補 (0.7, 0.5) 是對的
  - 但 goodinfo 2024 是 0.0（漏抓）
  - 原 INSERT OR REPLACE 不分 source → goodinfo 覆寫 finmind
  - 結果：6219 2024 變成 (0, 0)、現金股利 1.4 元金額資料誤失

【修法】
  1. import_dividend：`val=0` 不跳過、也要 INSERT（標記「該年無配息」）
  2. import_dividend：finmind 已存在的 (sid, yr) 從 goodinfo rows 中過濾、不覆寫
  3. import_yield_rate：不變、會把 0.0% 寫進 cash_yield_pct

【驗證】end-to-end 跑 _run_manual_selection
  - 1808 潤隆：今年現金殖利率 4.83% ✓
  - 6219 富旺：今年現金殖利率 0.0% ✓
  - 6219 2024：保留 finmind (0.7, 0.5) ✓

【沒動】VERSION / App title / User-Agent 仍是 v1.1（只是 scripts/ 改、主程式沒動）


════════════════════════════════════════════════════════════════════════════════
【V0.9.5-goodinfo6++】2026-06-26 13:10 (修 finmind 年份語意 bug)
════════════════════════════════════════════════════════════════════════════════
【背景】William 2026-06-26 12:39 反映：
  - 「6219 2024 finmind (0.7, 0.5) 、goodinfo 抓的是發放年2024的 (0.7, 0.5) 是在 2025 發放！」

【根因】finmind year = 會計年度（ex: 113年）、goodinfo 發放年度 = 除息日年份
  - 113年 ≠ 2024 (西元)、ex: 113年第4季 cash=0.7 CashExDividendTradingDate=2025-07-03
  - finmind 把這筆寫到 DB year=2024
  - 但真正發放是 2025-07-03 → 應歸到 2025
  - goodinfo 2025 發放年度也是 0.7 → 兩者同一筆

【證據】5 個 finmind row 用 ex_date year 都跟 goodinfo +1 完全匹配：
  - 1459 finmind yr=2025 (0.2) ex_date=2026-05-28 → goodinfo 2026 (0.2) ✓
  - 2342 finmind yr=2024 (0.299) ex_date=2025-08-08 → goodinfo 2025 (0.3) ✓
  - 2323 finmind yr=2023 (0.68) ex_date=2024-09-10 → goodinfo 2024 (0.68) ✓
  - 2344 finmind yr=2025 (0.5) ex_date=2026-03-27 → goodinfo 2026 (0.5) ✓
  - 7821 finmind yr=2025 (2.0) ex_date=2026-04-03 → goodinfo 2026 (2.0) ✓

【修復】3 個動作
  1. fetch_market.py _fetch_finmind_dividend (line ~700)：
     - 優先用 CashExDividendTradingDate (現金除息日)
     - fallback 到 StockExDividendTradingDate (股票除權日)
     - fallback 到 rec.get('date') (公告日)
     - 最後才退回 finmind year+1911 (會計年度)
  2. fetch_market.py _background_fetch_all_dividend (line ~825)：
     - 同樣優先用 CashExDividendTradingDate / StockExDividendTradingDate
  3. DB cleanup (inline Python script)：
     - 刪除 5 筆有 ex_date 但 yr 錯誤的 finmind row (已遷移到 ex_date yr)
     - 刪除 39 筆 finmind ex_date NULL 的 row (yr 都是會計年度、無法還原)
     - 刪除 6219 2024 finmind 孤兒 row (跟 goodinfo 2025 重複)

【驗證】
  - 6219 2025 goodinfo (0.7, 0.5, cyld=3.15, syld=2.43) ✓ 保留
  - 6219 2024 finmind row 已刪除、不重複
  - 39 筆 finmind ex_date NULL row 全清
  - 5 筆 finmind ex_date 有值 row 遷移到 ex_date yr
  - 1808 / 1459 / 2342 等殖利率正確

【test】tests/test_import_goodinfo_v0_9_5g6.py +3 個
  - test_6219_2024_finmind_removed_after_alignment：6219 2024 finmind 不存在
  - test_6219_2025_goodinfo_intact：6219 2025 goodinfo (0.7, cyld=3.15) 保留
  - test_finmind_year_uses_ex_date_year：fetch_market.py source 包含 ex_date year 邏輯
  - test_no_finmind_rows_with_null_ex_date：DB 內 finmind ex_date NULL = 0
  - 全部 470 passed (465 既有 + 5 新)、0 failed


════════════════════════════════════════════════════════════════════════════════
【V0.9.5-goodinfo6+++】2026-06-26 14:00 (修系統選股 DB 路徑 + 殖利率顯示格式)
════════════════════════════════════════════════════════════════════════════════
【背景】William 2026-06-26 13:51 + 13:56 反映：
  - 系統選股結果 9946 殖利率顯示 0.07 (應為 0)
  - 系統選股結果 4973 殖利率顯示 0.015 (應為 1.28)
  - 「請檢查所有殖利率內容」

【根因 1：fetcher db_path 是相對路徑】
  - _fetch_finmind_dividend 預設 db_path = "dividend_history.db"
  - 專案根有個空的 dividend_history.db (0 筆、6/20 殘留)
  - App 跑時 cwd 不同可能抓到空的 DB → 殖利率全 None → fallback 估算
  - 9946 估算 (1.5×0.7/29) = 0.036 → 顯示 0.04
  - 部分狀況抓到正確 DB → 9946 goodinfo cyld=6.9 → 顯示 0.07
  - 4973 goodinfo cyld=1.28 → 顯示 0.01

【根因 2：Treeview 用 _fmt(yld) 顯示小數】
  - yld 是小數 (0.069 = 6.9%)、但 _fmt(yld) 用 .2f 顯示成 0.07
  - 應該 ×100 變成 % 才對

【修法】
  1. _fetch_finmind_dividend (line ~631)：
     - db_path=None 自動找 fetch_market.py 上層的 source/dividend_history.db (絕對路徑)
  2. _background_fetch_all_dividend (line ~799)：同樣修
  3. StockTool.py 系統選股 Treeview (line ~6270)：
     - 新增 _fmt_pct(yld) = v × 100 顯示為 % (ex: 0.069 → 6.90)
  4. 清掉專案根的空 dividend_history.db / eps_history.db / portfolio.db
     (移到 .bak_empty_20260626 備份)

【驗證】end-to-end
  - 不傳 db_path、從專案根跑：9946=6.9%、4973=1.28% ✓
  - 不傳 db_path、從 source/ 跑：同樣 ✓
  - 自動取絕對路徑、不受 cwd 影響

【test】tests/test_import_goodinfo_v0_9_5g6.py +2 個
  - test_fetcher_default_db_path_finds_source_db：3 種 cwd 都拿到 (6.9, 1.28)
  - test_background_fetcher_default_db_path：背景 fetcher 也自動找
  - 全部 470 passed (468 既有 + 2 新)、0 failed


════════════════════════════════════════════════════════════════════════════════
【V0.9.5-goodinfo6++++】2026-06-26 18:35 (今年現金殖利率 = cash / 現價)
════════════════════════════════════════════════════════════════════════════════
【背景】William 2026-06-26 14:18 + 14:25 反映：
  - 「2026 漲利率不能從 goodinfo 抓、要用現價去計算！」
  - 「過去歷史漲利率的資料用 goodinfo 抓的」

【根因】舊的演算法：
  - 今年現金殖利率(%) = 100% 用 goodinfo 殖利率值（goodinfo 6.32%）
  - 但 goodinfo 是用「除息基準日還原價」算的歷史值、不是現價算的即時殖利率
  - 9946 樣本：goodinfo 6.9%（用 19.85 算）、但現價 29、cash 1.37 → 實際 4.72%
  - 結果使用者看到的殖利率跟現價配股現金實際算出來的不一樣

【新邏輯】（V0.9.5-goodinfo6++++）
  - 今年現金殖利率(%) = 今年現金股利 / 現價 × 100
    - cash=0 → 殖利率 = 0.0%（表示「該年未配息」、合理）
    - cash=None 或現價 None → 殖利率 None
  - 去年現金殖利率(%) = 直接用 goodinfo（已除息完成、用除息日還原價算的歷史值）
  - 股票殖利率（今年/去年）= 直接用 goodinfo

【改動】3 個 source
  1. stocktool/scoring.py (line ~198) _run_manual_selection：
     - 「今年現金殖利率(%)」演算法從 goodinfo 改為 cash/現價×100
  2. stocktool/pipeline.py (line ~163) _run_selection_only：
     - 「漲利率(估)」演算法從 goodinfo 改為 cash/現價
  3. stocktool/pipeline.py (line ~246) _run_pipeline：
     - 「漲利率(估)」演算法同步改為 cash/現價

【驗證】end-to-end _run_manual_selection
  - 9946 (三發地產)：cash=1.37、現價=29 → 漲利率 4.72%（不是 goodinfo 6.9）✓
  - 4973 (廣穎)：cash=1.0、現價=78 → 漲利率 1.28%（巧合跟 goodinfo 同）✓
  - 6219 (富旺)：cash=0、現價=13.25 → 漲利率 0.0%（該年未配息）✓
  - 1808 (潤隆)：cash=1.5、現價=31 → 漲利率 4.84% ✓
  - 2408 (南亞科)：cash=1.347、現價=340 → 漲利率 0.40% ✓

【test】tests/ 調整 4 個檔、遾 6 個 test
  - test_goodinfo_yield_rate.py 全部重寫反映新邏輯
  - test_ms_display_div_columns.py test_股利為0時 → cash=0 改為 0.0%
  - test_pipeline_dividend_merge.py test_合併股利 → cash/現價 為主
  - test_dividend_year_mapping.py test_2408 → cash/現價 為主
  - 全部 469 passed / 0 failed

════════════════════════════════════════════════════════════════════════════════
════════════════════════════════════════════════════════════════════════════════
【v1.0.1 HOTFIX #2】2026-06-24 06:50 (William 06:45 重跑回測又炸、補 import)
════════════════════════════════════════════════════════════════════════════════
【背景】William 2026-06-24 06:45 重跑回測、修完 datetime 後又炸：
  ❌ 回測失敗：name 'get_column_letter' is not defined
  Traceback (most recent call last):
    File "source/StockTool.py", line 5581, in worker
      result = run_pipeline(cfg, self.logger)
    File "source/stocktool/pipeline.py", line 570, in run_pipeline
      last_col = get_column_letter(ws_buy.max_column)
  NameError: name 'get_column_letter' is not defined

【根因】同 v1.1 重構漏 import、這次漏的是 openpyxl
- stocktool/pipeline.py line 570: get_column_letter(ws_buy.max_column) → 沒 from openpyxl.utils import get_column_letter

【意外發現】寫 lint test 順便抓出還有其他漏的
- stocktool/gui/calendar.py 有 from datetime import date, timedelta、但檔案內 4 處用 datetime.xxx()、漏 import datetime
  - 修法：from datetime import date, datetime, timedelta 加進去

【修法】2 個檔案各加 1 行
- pipeline.py: import requests 之後加 from openpyxl.utils import get_column_letter
- gui/calendar.py: from datetime import date, datetime, timedelta（原本只 import date, timedelta）

【評估】
- 一樣是一行 import 修一個 bug
- 寫精準 lint test 抓出來、不用等 William 實際跑才炸
- 1 次 hotfix 抓 2 個 import 漏（pipeline + calendar）

【test】tests/test_v1_1_imports_lint.py（新、14 個）
- TestExternalImportLint: 結構性 lint 掃全部 stocktool/ 模組
  - test_no_openpyxl_usage_without_import
  - test_no_datetime_usage_without_import
- TestPipelineGetColumnLetter: pipeline 有 import get_column_letter
- TestNoNameErrorAtImport: 11 個 stocktool/ 模組都能順利 import 不炸
- 全部 430 passed (416 既有 + 14 新）、0 failed

【沒動】
- VERSION / App title / User-Agent 仍是 v1.0
- StockTool.py 本體邏輯沒改（純 hotfix + fileheader）
- 使用手冊不需更新

════════════════════════════════════════════════════════════════════════════════
【v1.0.1 HOTFIX】2026-06-24 05:55 (William 凌晨跑回測炸掉、5:52 主動反映）
════════════════════════════════════════════════════════════════════════════════
【背景】William 2026-06-24 05:52 凌晨跑回測、所有股票抓不到歷史日K：
  ❌ [2330] 歷史資料錯誤: name 'datetime' is not defined
  ❌ [2454] 歷史資料錯誤: name 'datetime' is not defined
  ❌ [2308] 歷史資料錯誤: name 'datetime' is not defined
  ❌ 無歷史資料，請檢查網路連線

【根因】v1.1 重構時把 datetime 用法從 StockTool.py 搬到各個新 module（export_excel / backtest / technical）、
但 import 沒跟著搬、造成 NameError：
- stocktool/export_excel.py  line 65:  datetime.today() (update_stock_history)
- stocktool/backtest.py       line 351: datetime.now()
- stocktool/technical.py      line 26:  datetime.today() (calc_enhanced_tech_indicators)

【修法】3 個檔案各自加 `from datetime import datetime` 即可
- export_excel.py: import os → import os / from datetime import datetime
- backtest.py: import logging → import logging / from datetime import datetime
- technical.py: import math → import math / from datetime import datetime

【評估】
- 一行 import 修一個 bug、零風險
- 其他 datetime 子項目（date / timedelta）全專案無使用、未漏
- 為什麼之前測試沒抓到：update_stock_history / calc_enhanced_tech_indicators 都是要走 fetch 流程才會被呼叫、
  既有 test 都用 mock 跳過、所以漏到 William 實際跑才炸
- 順便寫結構性 lint test 守全部 stocktool/ module
  （任何檔案「用 datetime.XXX 但沒 import datetime」就 fail）→ 避免下次重構又漏

【test】
- tests/test_v1_1_datetime_imports.py（新、5 個）
  - TestDatetimeImportPresence: 3 個 module 都有 datetime import
  - TestUpdateStockHistoryCallable: update_stock_history 走 update 分支不 NameError
  - TestDatetimeUsageLint: 結構性 lint 掃全部 stocktool/ module
- 全部 416 passed (411 既有 + 5 新）、0 failed

【沒動的】
- VERSION 還是 v1.0、App title 還是 v1.0-GUI、User-Agent 還是 v1.0-GUI
- StockTool.py 本體沒改（只動 fileheader）、完全 hotfix 性質
- 使用手冊不需要更新（v1.0 行為不變）

════════════════════════════════════════════════════════════════════════════════
════════════════════════════════════════════════════════════════════════════════
【v1.1.1 HOTFIX】2026-06-24 09:15 (William 09:12 反映、買賣記錄 refresh 位置錯)
════════════════════════════════════════════════════════════════════════════════
【背景】William 09:12 反映：
- 開 App 進「買賣記錄 Tab」沒有 refresh 資料
- 要先去「主動式 ETF Tab」才有資料
- trigger refresh 的動作應該放錯位置

【根因】v0.9.5-tab-split 重排 Tab 順序時、`_on_tab_changed` 的 index 沒跟著改
- 原本 Tab 順序：策略(0) / 買賣記錄(1) / 手動選股(2) → refresh index = 1 正確
- 現今 Tab 順序：系統選股(0) / ETF(1) / 手動選股(2) / 買賣記錄(3) / 回測(4)
- refresh index 仍是 1、但 index 1 現在是 ETF Tab
- 結果：切 ETF Tab 才會 trigger 買賣記錄 refresh

【意外發現】_portfolio_refresh_loop 也有同樣 bug（line 2751 的 `if current != 1`）
- 同樣要改成 `current != 3`

【修法】3 個改動
- StockTool.py line 2705: `if current == 1` → `if current == 3`（_on_tab_changed）
- StockTool.py line 2751: `if current != 1` → `if current != 3`（_portfolio_refresh_loop）
- tests/test_portfolio_refresh_loop.py: 所有 `current_tab=1` 改成 `current_tab=3`

【寫新 test】tests/test_notebook_portfolio_tab_consistency.py（新、7 個）
- TestNotebookTabOrder: 結構性 lint、用 AST 掃 notebook.add() 順序與 _on_tab_changed index 一致
  - test_portfolio_tab_is_index_3
  - test_etf_tab_is_index_1
  - test_on_tab_changed_index_matches_portfolio_tab
- TestOnTabChangedBehavior: mock notebook 測 4 個不同 tab 的 refresh 行為
  - test_切到買賣記錄_tab_觸發_refresh（進買賣記錄應 refresh）
  - test_切到_etf_tab_不觸發_refresh（進 ETF **不應** refresh 買賣記錄、防本次 bug 重現）
  - test_切到系統選股_tab_不觸發_refresh
  - test_切到回測模擬_tab_不觸發_refresh
- 全部 437 passed (430 既有 + 7 新）、0 failed

【評估】
- 一個字（1 → 3）修一個 bug、零風險
- 原本測試为何沒抓到：test 的 mock 用 `current_tab=1` 模擬買賣記錄、跟實際 notebook 結構對不上
  → test 世界觀跟 code 世界觀不一致、雙方都通過但實際行為壞
- 新增的 consistency test 守住：「notebook 結構」跟「trigger index」是連動關係
  → 未來 Tab 重排時、如果忘記同步 trigger index、pytest 立刻抓出來

【沒動】
- VERSION 仍是 v1.1、App title 仍是 v1.1、User-Agent 仍是 v1.1
- 使用手冊 v1.1.docx 不需更新（UX 行為不變）

════════════════════════════════════════════════════════════════════════════════
【v1.1.1 HOTFIX #2】2026-06-24 10:45 (William 10:39 反映、ETF 排序需求)
════════════════════════════════════════════════════════════════════════════════
【背景】William 10:39 反映：ETF 選股後的排序應改為：
- 今日有異動的股票優先
- 有異動者：依 total_change_lots 降序（由大到小）
- 無異動者：在底部、保持原有 etf_count 順序

【修法】_etf_display_results 中的 sort 逻辑
- 舊：df.sort_values("etf_count", ascending=False)
- 新：以 today_mover 為第一 key（True > False → movers first）
  + 第二 key 為 total_change_lots 降序
  + 結果：movers 前、依張數大→小；non-movers 在底部

【沒動】
- VERSION / App title / User-Agent 仍是 v1.1
- 使用手冊不需更新（只有內部排序邏輯變化）

════════════════════════════════════════════════════════════════════════════════
【v1.1.1 HOTFIX #3】2026-06-24 21:36 (William 21:35 反映、評分系統 UI 選項重排)
════════════════════════════════════════════════════════════════════════════════
【背景】William 21:35 反映：「因子權重」是「多因子評分」的參數、「⚙ 簡易評分進階設定」是「簡易評分」的參數。
原本順序是 多因子/簡易評分 radio → 因子權重 entries → ⚙ 簡易評分進階設定 button、
因子權重跟簡易評分 button 跨在兩者中間，看起來怪怪的。

【修法】評分系統 UI 重排
- 舊順序：
    ○ 多因子評分 (動能+成長)
    ● 簡易評分 (可調權重+門檻)
    因子權重:
      動能1M / 動能3M / 動能6M / 營收YoY / EPS YoY
    [⚙ 簡易評分進階設定]

- 新順序（用 padx=20 縮排、讓設定看起來屬於上面那個 radio）：
    ○ 多因子評分 (動能+成長)
        因子權重:
          動能1M / 動能3M / 動能6M / 營收YoY / EPS YoY
    ● 簡易評分 (可調權重+門檻)
        [⚙ 簡易評分進階設定]

【為什麼用縮排而不是重新整理成兩個 LabelFrame】
保持原本 LabelFrame「⭐ 評分系統」結構、不增加外觀重量。
縮排已能明確表達「設定屬於哪個 radio」的視覺關係。

【沒動】
- VERSION / App title / User-Agent 仍是 v1.1
- 使用手冊不需更新（純 UI 重排）

【v1.1.1 HOTFIX #4】2026-06-24 21:55 (William 21:48 反映、系統選股殖利率與 EPSYoY 兩個 bug)
════════════════════════════════════════════════════════════════════════════════
【背景 1】William 21:48 反映 3490 殖利率顯示 0.04%、應該 1.54%
【背景 2】William 21:48 反映 3490 EPSYoY 顯示 4040%、應該 476%

【Bug 1】系統選股殖利率 只用「殖利率(估)」=(EPS×0.7/股價)、不是實際現金殖利率
- 預期：fetch_dividend DB 合併 FinMind 股利資料、殖利率優先用 GoodInfo 實際殖利率
- 舊：run_pipeline 完全不 fetch 股利資料、殖利率欄始終是估算值
- 新：run_pipeline 跟 manual 一樣呼叫 _fetch_finmind_dividend(skip_remote=True)、
      並把今年現金殖利率_goodinfo（單位 %）÷100 變成小數、覆寫「殖利率(估)」
- 結果：3490 殖利率 0.0446 → 0.0154（1.54%）

【Bug 2】3490 EPSYoY 快取值 4040% 是計算陷阱
- 根因：本期 Q1（2026Q1）、但 DB 沒有 2025Q1
       → fallback 用 2025Q4 全年 EPS = 0.05
       → (2.07 - 0.05) / 0.05 = 40.4 = 4040%
       Q1 vs 全年 是錯的比較、數字爆炸
- 舊：fetch_eps_latest Q1/Q2/Q3 也適用 Q4 fallback
- 新：只有本期 Q4 才適用 Q4 全年 fallback；Q1/Q2/Q3 → 留空等 GoodInfo 覆蓋
- 額外防兌：cache 驗證加入「YoY>500% 或 <-99%」檢查、強制重抓讓 GoodInfo 覆蓋

【修法檔案】
- source/stocktool/pipeline.py：合併 FinMind 股利 + 殖利率優先 GoodInfo
- source/stocktool/cache.py：快取加入可疑 YoY 檢查
- source/stocktool/fetch_market.py：Q1/Q2/Q3 不適用 Q4 fallback
- source/cache/eps.xlsx：刪除（舊快取 4040% 不會自動消失、強制重抓）

【測試】+7 個（437 → 444）
- tests/test_eps_yoy_q4_fallback_bug.py (5)：Q1 不適用 Q4 fallback、cache 可疑值重抓
- tests/test_pipeline_dividend_merge.py (2)：殖利率優先 GoodInfo、沒資料走估算

【沒動】
- VERSION / App title / User-Agent 仍是 v1.1
- 使用手冊不需更新

════════════════════════════════════════════════════════════════════════════════
════════════════════════════════════════════════════════════════════════════════
【v1.1.1 HOTFIX #5】2026-06-24 22:12 (William 22:10 反映、App 啟動 crash AttributeError)
════════════════════════════════════════════════════════════════════════════════
【背景】William 22:10 重啟 App 撞到
  AttributeError: '_tkinter.tkapp' object has no attribute '_preset_vars'
  File "_init_tab_presets_on_startup", line 2607, in `if tab_key in self._preset_vars:`

【根因】Fix14 「開機自動載入 Preset」（v0.9.5-alpha 5th commit）加的 _init_tab_presets_on_startup
是在 _build_ui 開頭就 call（line 2076）、但 self._preset_vars = {} 是 _add_preset_bar 內部才設定。
原設計靠 _add_preset_bar 內的 `if not hasattr` defensive check 判斷是不是第一次、決定要不要 init。
但 _init 比 _add 還早 → hasattr 還是 False → 沒人 init → 讀取時 AttributeError。

【修法】_build_ui 一進來就預先初始化 self._preset_vars = {} 和 self._preset_combos = {}
（_add_preset_bar 內的 hasattr check 仍保留當安全網）

【新增 test】
- tests/test_init_tab_presets_init_order.py (3 個)
  · test_build_ui_先初始化_preset_vars (AST 確認)
  · test_build_ui_也初始化_preset_combos (AST 確認)
  · test_init_tab_presets_不crash即使preset_vars空白 (邏輯測試)

【驗證】手動 source .venv/bin/activate && python source/StockTool.py 成功啟動 ✅

【沒動】VERSION / App title / User-Agent 仍是 v1.1

════════════════════════════════════════════════════════════════════════════════
════════════════════════════════════════════════════════════════════════════════
【v1.1.1 HOTFIX #6】2026-06-24 22:20 (William 22:16 反映、App 啟動仍 crash self.vars)
════════════════════════════════════════════════════════════════════════════════
【背景】HOTFIX #5 修完 _preset_vars 後、William 22:16 重試又撞到
  AttributeError: '_tkinter.tkapp' object has no attribute 'vars'
  File \"_apply_tab_values\", line 2545, in `var = self.vars.get(k)`

【根因】同 #5 的問題但套用另一個變數：
- _init_tab_presets_on_startup → _apply_tab_values → self.vars.get(k)
- self.vars = {} 原來在 line 2140 才設定（在 _init 2111 之後）
- 修法沒涵蓋到這個變數

【修法】_build_ui 一進來連同 self.vars = {} 也一起初始化
（目前 _preset_vars / _preset_combos / vars 都在 _build_ui 開頭就 init）

【新增 test】
- test_build_ui_也初始化_vars (AST 確認)
- 全部 init-tab-presets-init-order 測試變 4 個

【驗證】手動 python source/StockTool.py 啟動成功 ✅

【沒動】VERSION / App title / User-Agent 仍是 v1.1

════════════════════════════════════════════════════════════════════════════════
════════════════════════════════════════════════════════════════════════════════
【v1.1.1 HOTFIX #7】2026-06-24 22:32 (William 22:24 反映、系統選股 EPSYoY 全是 --)
════════════════════════════════════════════════════════════════════════════════
【背景】William 22:24 重試 App 後反映：EPSYoY 整欄全是 --（所有股票都沒有資料）。
剛在 HOTFIX #4 修了 Q1 fallback 讓 Q1 不適用 Q4 全年 EPS（避免 3490 4040% 陷阱），
但上次的 cache 是修 hotfix 之前寫入的、全部都是 NaN；原本 cache 驗證只測「全 NaN」才重抓。

【根因】cache 驗證覆蓋不足：
- 舊驗證：df[yoy_col].isna().all() 才重抓
- 但這個 cache 其實是「有一部分是 None、一部分是 4040%」的狀態
- 驗證結果走過、讀出來還是錯的

【修法】cache 驗證加進「大部分 NaN」檢查：
- 舊：isna().all() 才重抓
- 新：isna().all() 或 NaN>50% 或 有 YoY>500%/<-99% → 重抓

【手動預重抓】順手手動重抓一次、寫入 cache、讓 William 重啟 App 就拿到正確資料：
- 1808 (潤隆) 807.0% / 9946 (三發地產) 3300.0% / 5386 (青雲) 3290.0%
- 6219 / 6015 / 2442 仍是 NaN（GoodInfo 本來就沒資料、預期行為）

【測試】+3 個（448 → 451）
- tests/test_cache_eps_nan_threshold.py (3 個)
  · 全 NaN 強制重抓（舊行為）
  · 60% NaN 強制重抓（新行為）
  · 30% NaN 不重抓（合理）

【沒動】VERSION / App title / User-Agent 仍是 v1.1

════════════════════════════════════════════════════════════════════════════════
════════════════════════════════════════════════════════════════════════════════
【v1.1.1 HOTFIX #8】2026-06-24 22:42 (William 22:35 反映、EPSYoY 仍全 --)
════════════════════════════════════════════════════════════════════════════════
【背景】HOTFIX #7 修了 cache 驗證、但 App 起來 EPSYoY 仍全 --。
console log 顯示「⚠️ 讀取 ...12QEPSRate.xls 失敗: `Import lxml` failed」
。GoodInfo 1589 檔需要 lxml 才能讀。

【根因】(V0.9.5-tab-split-phase3-C Fix10) _load_goodinfo_12q_epsrate 用 pd.read_html
讀 GoodInfo 偽裝 xls 的 HTML 檔。pd.read_html 需要 lxml。
- 沒裝 lxml → 每個檔案 raise ImportError
- _load_goodinfo_12q_epsrate() 返回 0 檔
- 整套 GoodInfo 覆蓋机制幹掉
- 所有 EPSYoY = NaN、EPSYoY 顯示為 --

【修法】
1. 新增 requirements.txt （之前竟沒這個檔）
   - 加上 lxml>=4.9
   - 加註解說明 GoodInfo .xls 需要 lxml 才能 read_html
2. _load_goodinfo_12q_epsrate() 開頭先 import lxml 檢查
   - 缺 lxml → 印 friendly error message（告知 pip install -r requirements.txt）
   - 早退 return {}
3. 順手重抓一次 cache、寫入正確資料 （1583/1968 檔有 YoY）

【測試】+2 個（451 → 453）
- tests/test_load_goodinfo_lxml_check.py
  · test_沒裝lxml_早退且不crash（mock ImportError 驗證早退）
  · test_有裝lxml_正常載入（有檔案時 ≥1 檔）

【為什麼 HOTFIX #4-#7 沒抓到這個】
- fix #4 修 fetch_eps_latest Q1 fallback、但需 GoodInfo 才能覆盖
- fix #5/#6 修 App 啟動 crash
- fix #7 修 cache 驗證、但 cache 本來就是NaN (被重寫過) → 顯示仍是 NaN
- 所有都在拼「讓 GoodInfo 覆蓋」這個主路、
  但從未查證 GoodInfo 是否真的能載入

【手動重抓】已重寫 source/cache/eps.xlsx (1583/1968 筆有 YoY)、
下次 App 啟動會直接用這個 cache。

【沒動】VERSION / App title / User-Agent 仍是 v1.1

════════════════════════════════════════════════════════════════════════════════
【v1.1 正式版】2026-06-24 08:50 (William 08:47 決定、趁 v1.0 穩定後推進)
════════════════════════════════════════════════════════════════════════════════
【背景】v1.0 (2026-06-23 14:42) 發版後、所有功能都能跑、但內部程式碼結構是 4700+ 行的單檔 StockTool.py、難以維護。
趁沒新需求時推 v1.1 重構、把代碼拆成 stocktool/ 子模組。

【重構內容】7 階段、7 個 refactor commit
- refactor-1,2: 抽 config.py + cache.py           (5ce464f)
- refactor-3:   抽 database.py                     (1e7ca20)
- refactor-4:   抽 fetch_market.py                 (b1014ed)
- refactor-5a:  抽 etf.py                          (49bf412)
- refactor-5b:  抽 scoring.py + technical.py       (0842b88)
- refactor-6a:  抽 backtest.py                     (8bc7cd4)
- refactor-6b:  抽 export_excel.py + pipeline.py   (cc09688)
- refactor-7a:  抽 gui/calendar.py                 (2386764)

最終結構：
- source/StockTool.py        ← 主視窗 + GUI 控制器（4700+ → 本版本）
- source/stocktool/__init__.py
- source/stocktool/config.py    ← StrategyConfig / GuiLogger / VERSION / HISTORY_DIR / find_col / build_session
- source/stocktool/cache.py     ← save_cache / load_cache / get_or_fetch / 市場時段判斷
- source/stocktool/database.py  ← sqlite 存取
- source/stocktool/fetch_market.py ← TWSE / TPEx / FinMind 抓取
- source/stocktool/etf.py        ← ETF 持股、變動、Session / User-Agent
- source/stocktool/scoring.py    ← 多因子 / 簡易評分
- source/stocktool/technical.py  ← MA / RSI / MACD / MTF / 背離
- source/stocktool/backtest.py   ← 回測引擎
- source/stocktool/export_excel.py ← Excel 樣式 + History Cache
- source/stocktool/pipeline.py   ← run_pipeline 主流程組合
- source/stocktool/gui/calendar.py ← _CalendarDialog 日期選單

【修法】所有被依賴的 module 透渦 lazy import 避免 import cycle：
- 例：fetch_market.py 在 fetch_twse_history 內 `from . import export_excel as _export_excel`
- 例：pipeline.py 從各個 module import 所需函式

【評估】
- 使用者介面、Tab、功能、輸入輸出全部不變 → 完全向後相容 v1.0
- 程式碼結構提升：4787 行變成 13 個 module、各自 < 1300 行、未來維護更方便
- 開發體驗提升：每個 module 可單獨測試、不再需動整個 StockTool.py
- 風險：低（全部 430 test pass、實際回測實戰跑過 5 次皆無 error）

【修記】v1.1 重構期間爆發 7 個 import 漏 bug（5a2fcf4 / b13fe5b / 233d22a / ac1ea8d / ee46639 / 676d74c / 5c6b10d）
- 結構性 lint test 已寫：未來任何 stocktool/ module 漏 import 會被 pytest 立刻抓出來
- 全部 430 passed (411 → 430、7 個 hotfix + 12 個結構性 lint)

【version bump】
- VERSION = "v1.0" → "v1.1"
- User-Agent: StockTool/AdvisorStyle-v1.0 → StockTool/AdvisorStyle-v1.1
- App title: StockTool {VERSION} (...) → 自動改 v1.1
- 啟動 log: 🚀 StockTool {VERSION} 開始執行 → 自動改 v1.1

════════════════════════════════════════════════════════════════════════════════
【v1.0.1 HOTFIX #2】2026-06-24 06:50 (William 06:45 重跑回測又炸、補 import)
════════════════════════════════════════════════════════════════════════════════
【背景】William 2026-06-24 06:45 重跑回測、修完 datetime 後又炸：

[6049 more lines in use offset=17 to continue]
════════════════════════════════════════════════════════════════════════════════
【背景】William 14:10 反映：ETF 選股和手動選股的「📤 匯出 Excel」按鈕位置和名稱都跟系統選股的「💾 匯出股票清單」不一致、改一致
【修法】
1. ETF tab 拿掉左邊參數區的「📤 匯出 Excel」按鈕
2. 手動選股 tab 拿掉左邊參數區的「📤 匯出 Excel」按鈕
3. 三個 tab 統一在右上面板右邊放「💾 匯出股票清單」按鈕（跟 select_tab 同名、同位置）
4. ETF / 手動選股 right_frame 結構調整成跟 select_tab 一致：
   - ttk.Frame（不是 LabelFrame）→ right_top（title + button）→ tree_frame
5. 初始 state="disabled"、有資料時 _ms_display_results / _etf_display_results 結尾 enable
6. fileheader / VERSION / User-Agent 同步到 phase3-G
7. 8 個 pytest test 守住

【評估】
- 拿掉 2 個按鈕、加 2 個按鈕：總按鈕數不變、UX 完全一致
- 風險：低（_ms_export_excel / _etf_export_excel 簽名不變、按鈕初始 disabled 避免誤觸）


════════════════════════════════════════════════════════════════════════════════
【v1.0 正式版】2026-06-23 14:42 (William 要求）
════════════════════════════════════════════════════════════════════════════════
【背景】William 09:55 反映 2 個問題：
1. ETF 持股篩選的「今日異動」欄位全是 --（沒資料）
2. Cache 只記日期不記時間、跨日才重抓不夠精準（盤前/盤後該重抓時不重抓）

【修法】
1. FixA: ETF shares 寫進 DB
   - 根因：build_etf_holdings_table 沒把 shares 放進 long_df → _save_etf_holdings_to_db 寫入 DB 全是 0 → _compute_etf_changes 算 change_lots 全 0 → 顯示 --
   - 修法：build_etf_holdings_table 加 shares + industry 欄位 → long_df 帶 shares → DB 寫對
   - migration：一次性重抓今天的 ETF 持股、把 shares 補回 DB（昨天的 shares 補不回去、明天起正常）
   - 4 個 pytest test 守住

2. FixB: Cache 加時間邏輯
   - 根因：save_cache 只寫 last_update（YYYY-MM-DD）、不寫時間
   - 場景：昨天 09:30 抓的 cache 到今天 14:00 被視為「有效」（因為 last_update == today）
     但 cache 內容是 09:30 的盤中價、不是 14:00 的收盤價
   - 修法：
     a. save_cache 多寫 last_update_time (HH:MM:SS)
     b. load_cache 多回傳 time (向後相容、舊 cache time=None)
     c. 新增 _is_price_cache_valid(date, time) helper：
        - 收盤後（>= 13:30 或半日盤 13:00）：cache date == 今天 且 cache time >= 今天收盤時間 → 有效
        - 收盤前（< 09:00）：cache date == 昨天 且 cache time >= 昨天收盤時間 → 有效
        - 其他（含盤中）：過期、需重抓
     d. get_or_fetch 對 price 走新邏輯（revenue/eps 仍用舊 last_update == today 判斷）
   - 15 個 pytest test 守住（含半日盤、週末、邊界）

3. 順手修 test 隔離 bug (pre-existing)
   - 根因：多個 test 直接 st._fetch_finmind_dividend = lambda 沒還原 → 後面 test_dividend_yield_fix 跑時仍是 mock 版
   - 修法：tests/conftest.py 加 autouse fixture、每個 test 後還原 _fetch_finmind_dividend
   - 效果：全部 407 個 test 一起跑 100% pass（原本 3 個會 fail）

4. FixA2: today_change_lots 欄位名稱（2026-06-23 12:12 William 反映）
   - 根因：_compute_etf_changes 回傳 today_change_lots，但 _etf_display_results / _show_etf_popup 用 change_lots → KeyError
   - 修法：兩處都改 today_change_lots

5. FixA3: column-missing 檢查移到 market-hours early-return 前面
   - 根因：test_get_or_fetch_cache缺欄位_自動重抓 fail — column-missing 檢查本來在 last_update == today 分支內，但 market-hours early-return 在前面
   - 修法：把 price cache 的 column-missing 檢查移到 get_or_fetch 最前面（結構問題優先於時間判斷）

【評估】
- FixA：ETF shares 是根本修正、不修就永遠顯示 --
- FixB：cache 時間精準度提升、不會重抓舊 cache 也不會忘記抓新 cache
- FixA2：DB migration 後才爆的 bug、要順便修
- FixA3：test 發現的結構問題、要順便修
- 風險：低（向後相容舊 cache、Fixture 不影響其他 test）

【test】
- FixA: test_etf_long_df_shares.py (4 個)
- FixB: test_cache_time_logic.py (15 個)
- FixA2: test_etf_change_column_name.py (4 個)
- FixA3: column-missing 檢查移到 get_or_fetch 最前面
- 共 411 passed、0 failed

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-tab-split-phase3-F 新增內容】2026-06-22 14:00 (William 要求）
════════════════════════════════════════════════════════════════════════════════
【背景】William 13:52 反映：拿掉右鍵選單的「全選/全不選」、因為 header checkbox 已能全選/全不選、右鍵多一重入口多餘
【修法】
1. 拿掉 4 個右鍵 handler method：
   - _on_select_tree_rclick（select_tree / backtest_tree 共用）
   - _etf_tree_rclick_new（etf_tree）
   - _ms_tree_rclick（ms_tree、原本是 dead code 被 _ms_show_context_menu 覆蓋）
   - _ms_show_context_menu（ms_tree）
2. 拿掉 4 個 <Button-3> bind：results_tree / _etf_tree / _ms_tree 兩次
3. _etf_select_* / _ms_select_* / _select_* methods 保留
   （heading click 內部會叫、這些 method 是核心邏輯）
4. fileheader / VERSION / User-Agent 同步更新到 phase3-F
5. 6 個 pytest test 守住「右鍵選單全選/全不選已拿掉」

【評估】
- 拿掉 4 個 method + 4 個 bind：code 減少約 30 行、無功能損失
- 風險：低（header click 是唯一入口、這個入口已是動態 ☐/☑/▣、操作直覺）

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-tab-split-phase3-E 新增內容】2026-06-22 13:50 (William 要求）
════════════════════════════════════════════════════════════════════════════════
【背景】William 13:43 反映：篩選結果 console 的勾選欄 header 已可全選/全不選、ETF 和手動選股參數區的全選/全不選按鈕重複、拿掉
【修法】
1. 拿掉 ETF tab 參數區的 📋 全選 / ☐ 全不選 兩個按鈕（line 7011-7014）
2. 拿掉手動選股 tab 參數區的 📋 全選 / ☐ 全不選 兩個按鈕（line 7210-7213）
3. _etf_select_all / _etf_select_none / _ms_select_all / _ms_select_none methods 保留
   （heading click 內部會叫、這些 method 是核心邏輯）
4. 右鍵選單「☑ 全選 / ☐ 全不選」保留（另一個入口、不佔版面）
5. 3 個 pytest test 守住「參數區按鈕已拿掉」

【評估】
- 拿掉 4 個按鈕：left_canvas 高度減少約 80px、UI 更精簡
- 風險：低（methods 保留、header click 和右鍵選單都能觸發全選/全不選）
- 預計 commit hash：v0.9.5-tab-split-phase3-E

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-tab-split-phase3-D 新增內容】2026-06-22 09:35 (William 要求）
════════════════════════════════════════════════════════════════════════════════
【背景】William 09:31 反映：結果畫面勾選欄 header 點下去沒反應、rows 都勾起來但 header 還是「☑」看不出反饋
【修法】
1. 新增 _update_checkbox_header(tree, checked_dict) helper
   - 0 checked → ☐
   - 全部 checked → ☑
   - 部分 checked → ▣（混和狀態）
2. 三個 Treeview 剛 build 時 header 初始顯示設為 ☐（看起來像個 checkbox）
   - select_tree / backtest_tree（共用 _build_tab_layout）
   - ms_tree（手動選股）
   - etf_tree（ETF tab）
3. _select_all / _select_none / _ms_select_all / _ms_select_none / _etf_select_all / _etf_select_none 都會在結尾叫 helper 更新 header
4. 個別 row toggle（_on_select_tree_click / _ms_toggle_check / _etf_toggle_check）也會叫 helper
5. ETF tab 的 _etf_toggle_check 補上 heading click → 全選/全不選（原本只處理 cell click）
6. 10 個 pytest test 守住 (tests/test_checkbox_header_click.py)

【向上相容】原本的 _select_all / _select_none / _ms_select_* / _etf_select_* 簽名不變、只是多叫 helper
【受益者】所有用 Treeview checkbox 的 Tab：系統選股、手動選股、ETF、錢測（錢測 Treeview 不含 checkbox、不受影響）

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-etf 新增內容】2026-06-19 23:05 (William 要求）
════════════════════════════════════════════════════════════════════════════════
【背景】William 22:53 需求：「增加一個 ETF 成股 Tab」
- 列出所有台股主動式 ETF 的成股（代號、名稱、最新收盤價、屬於幾個 ETF）
- cursor 移到 ETF 數字 → popup 顯示包含此股票的 ETF 列表
- 排序依 ETF 數量大到小
- 存成 excel、高亮與手動選股一致

【資料源設計】找 TWSE 官方 API
- 主動式 ETF 列表：TWSE `/rwd/zh/ETF/activeList` （官方、JSON、有 19 檔 domestic）
- 前 10 大成股：etfinfo.tw `/etf/{code}` （總覽頁 HTML、SSR 表格、可 parse）
- 個股收盤價：複用既有 `cache/price.xlsx`

【改動】新增 4 個函式在 StockTool.py（fetch_csv_requests 之前）：
1. `fetch_active_etf_list`：抓 TWSE activeList、過濾只留 domestic
   · 回傳 DataFrame (etf_code, etf_name)
   · 拿掉 foreign (海外)、bfIncome (債券) 類別
2. `fetch_etf_top10_holdings`：從 etfinfo.tw parse HTML
   · 找「前 10 大成股」section
   · 用 regex parse `<a href="/stock/{code}">{code}</a>`、名稱、權重
   · 回傳 list of dict (stock_code, stock_name, weight)
3. `build_etf_holdings_table`：完整 long-format table
   · 走 19 檔 ETF、每檔抓前 10 大
   · 合併為 (stock_code, stock_name, etf_code, etf_name, weight)
   · 邊界：單檔失敗不中斷整個抓取
4. `aggregate_etf_holdings`：合併去重 + 計算 etf_count
   · 以 stock_code groupby、計算被幾檔 ETF 持有
   · 組合成 `etf_list` 字串 ("00981A 主動統一台股增長(9.68%) | 00403A ..."）
   · merge price_df 取收盤價
   · 排序：依 etf_count 由大到小、同票數依股票代號升冪

【實測驗證】
- 19 檔 domestic ETF、3 檔 sample 抓 30 筆耗時 2.8 秒
- 全部 19 檔預估 17 秒可抓完
- 實例：2330 被 3 檔 ETF 持有 → etf_list = "00980A 主動野村臺灣優選(9.37%) | 00982A 主動群益台灣強棒(8.71%) | 00981A 主動統一台股增長(9.68%)"

【pytest 新增 10 個】test_etf_holdings.py
- fetch_active_etf_list_過濾只留domestic
- fetch_etf_top10_holdings 正常 / 找不到 section / 解析失敗
- build_etf_holdings_table 合併多檔 / 單檔失敗仍繼續
- aggregate_etf_holdings 計算 etf_count / etf_list 字串 / merge 收盤價 / 股價 df 空白

【驗證】
- pytest：247 passed（+10 新）、3 pre-existing fail（跟本次無關）
- 下個 commit：加 ETF Tab GUI
   （已隨 Commit 2 完成）

═══════════════════════════════════════════════════════════════════════════════
【v0.9.5-etf-gui 新增內容】2026-06-19 23:30 (William 23:11 要求）
═══════════════════════════════════════════════════════════════════════════════
【背景】接續 Commit 1 (860360b fetcher)、依 William 23:11「接著做 GUI、不然沒東西可以看」。

【改動】在 StockTool.py 加 ETF Tab UI + 行為
1. Notebook 註冊新 Tab「📊 主動式 ETF」（在「🔍 手動選股」後面）
2. `_build_etf_tab`：左面板（篩選 + 按鈕 Canvas+Scrollbar）、右面板（Treeview 5 欄）
3. Treeview 5 欄：勾選/代號/名稱/收盤價/ETF數
4. Hover 複用手動選股機制（黃色 / 淺藍 / checked/unchecked tag）
5. Hover 在「ETF數」欄 → Toplevel popup 顯示完整 ETF 列表
   · 設計：只在 column #5 才顯示 popup、移開其他欄位會關掉
   · popup 內容：「📊 2330 台積電 被 3 檔 ETF 持有：」 + 每個 ETF 換行顯示（Text widget）
6. 勾選複用手動選股 pattern（點第一欄 toggle）
7. 篩選條件：最少 ETF 數 / 是否限定有收盤價 / 結果上限
8. 匯出 Excel：跟手動選股同格式、可餵回策略參數 Tab
9. 開機 2.5 秒自動背景抓取（_etf_auto_startup_fetch）、防止重複的 _etf_fetching flag

【程式位置】
- _build_etf_tab：line 5640（_build_manual_select_tab 之前）
- _on_etf_tree_hover / _on_etf_tree_leave / _clear_etf_hover
- _show_etf_popup / _close_etf_popup
- _etf_toggle_check / _etf_select_all / _etf_select_none
- _etf_apply_filter / _etf_refresh_holdings / _etf_refresh_done
- _etf_display_results
- _etf_export_excel
- _etf_auto_startup_fetch / _etf_auto_startup_done
- _load_price_df

【pytest 新增 15 個】test_etf_tab_gui.py
- 勾選狀態管理（第一次/第二次/非勾選欄、全選/全不選）
- 套用篩選（插入/門檻/上限/收盤價過濾）
- 匯出 Excel 邊界（無資料/未勾選）
- popup 行為（正常顯示/找不到 iid/close/destroy）

【驗證】
- pytest：262 passed（+15 新）、3 pre-existing fail（跟本次無關）
- 語法檢查通過
- GUI 尚未實體測試、需 William 開 App 看

═══════════════════════════════════════════════════════════════════════════════
【v0.9.5-etf-fix 修 Bug 內容】2026-06-19 23:40 (William 23:37 反映)
═══════════════════════════════════════════════════════════════════════════════
【問題】William 開 App 重現：
```
NameError: cannot access free variable 'e' where it is not associated with a value in enclosing scope
  File "StockTool.py", line 6928, in <lambda>
    self.after(0, lambda: self._etf_refresh_done(None, str(e)))
```
連兩個 lambda 都是。

【根因】Python closure trap：
- `except Exception as e` 在 except 區塊結束後、變數 `e` 會被釋放
- lambda 是 closure、變數名稱是「綁定到外面 scope」、不是 copy 值
- `self.after(0, lambda: ...)` 是「延遲 callback」、跑到時 except 已結束 → NameError

【修法】用 default argument 鎖住變數值
- `self.after(0, lambda err=str(e): self._x(None, err))`
- lambda 參數預設值在 lambda 建立當下就 freeze、不受 scope 釋放影響
- 這是 Python 常見 idiom、`functools.partial` 也可但沒那麼簡潔

【同時套用到兩處】
- `_etf_refresh_holdings` 的 worker（line 6926、6930）
- `_etf_auto_startup_fetch` 的 worker（line 7073、7075）
- 都涉及 threading + after(0, ...) + except e 的模式

【pytest 新增 3 個】test_etf_closure.py
- test_closure_default_arg_locks_value：用 default arg 鎖住的 lambda 可正常取值
- test_closure_default_arg_normal_lambda_will_fail：反向驗證、沒鎖的 lambda 真的會 NameError
- test_dataclass_arg_locks_agg_df：DataFrame 也用 default arg 鎖

【驗證】
- pytest：265 passed（+3 新）、3 pre-existing fail（跟本次無關）
- 語法檢查通過

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-etf-session-fix 修 Bug 內容】2026-06-20 09:12 (William 09:11 反映)
════════════════════════════════════════════════════════════════════════════════
【問題】William 開 v0.9.5-etf-fix App 後 log 出現：
```
[09:11:52] ♻️ [price] 資料過期 → 重新下載
[09:11:52] ✅ 啟動時自動股價完成：2377 筆、股價更新：2026-06-20 09:11:52｜資料日期：2026-06-18
[09:11:53] 📊 [ETF] 開機自動抓取 ETF 持股...
[09:11:53] ❌ [ETF] 開機抓取例外：'_tkinter.tkapp' object has no attribute 'session'
```
ETF 開機抓取整個掛掉、Status bar 永遠是「❌ ETF 開機抓取失敗」。

【根因】
- ETF 模組（860360b fetcher + 875f0d2 GUI + cd4527a closure fix）三個版本都誤用 `self.session`
- 但 StockTool 主類別從未定義 `session` 屬性 → AttributeError
- 其他 fetcher（fetch_prices / fetch_revenue_latest / fetch_eps_latest）的呼叫模式：
  - 在呼叫端 `_s = build_session()` 拿 requests.Session
  - 再傳 `_s` 進 fetcher（不是 self.xxx）
- 是 ETF 模組自己 copy 時想成「其他地方都有 session」但其實沒有

【修法】3 處都改用 build_session() 拿 session（跟既有 fetcher 一致）
- `_etf_refresh` 的 worker（line 6951）
- `_etf_auto_startup_fetch` 的 worker（line 7103）
- `_load_price_df` 同步方法（line 7146）

【pytest 新增 5 個】test_etf_session_attr.py
- test_stocktool_no_self_session_attr：用 AST 解析、確保沒有真的 self.session attribute access（排除 docstring / 註解 / 字串干擾）
- test_etf_workers_use_build_session：3 個觸發點都有 build_session()
- test_etf_fetchers_accept_session_param：fetch_active_etf_list / fetch_etf_top10_holdings / build_etf_holdings_table 第一個參數都叫 session
- test_etf_method_compiles：py_compile 編譯通過、確保沒漏逗號
- test_ast_helper_actually_catches_offenders：反向驗證 helper 能抓到 offender + docstring / 字串不會被誤判

【驗證】
- pytest 5 個新 test 全綠、總計 270 passed
- 3 個 pre-existing fail 在 test_dividend_yield_fix.py（test ordering 問題、單跑全綠、跟本次無關）
- 語法檢查通過

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-etf-popup-fix 修 Bug 內容】2026-06-20 10:21 (William 10:21 反映)
════════════════════════════════════════════════════════════════════════════════
【問題】William 開 App 把滑鼠 hover 到「2330 台積電」的「ETF 數 18」欄
- popup 出現但只能看到「金像電子（股）公司」這種擠在一起的文字
- 看不出每個 ETF 代號跟名稱、無法閱讀

【根因】
- aggregate_etf_holdings 用 " | " 把 18 個 ETF 串成一行塞進 etf_list
- popup 用 Label 顯示、Label 把整段當成一行算寬度 → 被擠壓
- 結果：原本是「00980A 主動野村臺灣優選(9.37%) | 00982A ...」的一行
       → 被擠成「金像電子（股）公司」這種難以辨識的 column

【修法】2 個改動
1. etf_list 分隔符：「 | 」→ 「\n」（每個 ETF 一行）
2. popup widget：Label → Text widget（以最長那行算寬度、不會被擠壓）
   · width = max line length
   · height = min(total_lines, 25)
   · state="disabled" 唯讀

【pytest 新增 6 個】test_etf_popup_format.py
- test_etf_list_uses_newline_separator:etf_list 用 \n 分隔、不再用 " | "
- test_etf_popup_widget_is_text:popup 是 Text widget 不是 Label
- test_etf_popup_text_uses_max_line_width:width 用 max_line_len 自動算
- test_etf_popup_text_height_capped:height 用 min(total_lines, 25) 限制
- test_etf_aggregator_actually_newlines:跑 aggregate_etf_holdings 真驗證換行
- test_etf_popup_method_compiles:py_compile 編譯通過

【附帶更新 test_etf_tab_gui.py】
- test_etf_show_popup_正常顯示 從 mock Label 改成 mock Text widget
  （因為 widget 從 Label 換 Text）

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-etf-popup-spacing 修 Bug 內容】2026-06-20 11:39 (William 11:39 反映)
════════════════════════════════════════════════════════════════════════════════
【問題】William 10:21 popup 修正後看 v0.9.5-etf-popup-fix 截圖：
- 第一行最前面有 📊 icon、不要
- 行字的間隔太小、太擠不好讀

【根因】
- title 字串用了 f"📊 {stock_code} {stock_name} 被 {etf_count} 檔 ETF 持有："
- Text widget 預設 spacing1=0 spacing3=0、行與行之間沒有 padding

【修法】
1. 拿掉 title 的 📊 icon：「📊 2330 台積電 ...」→「2330 台積電 ...」
2. Text widget 加 spacing1=4 spacing3=4（每行上下各 4px、行間呼吸感更好）

【pytest 新增 1 個】test_etf_popup_spacing.py
- test_popup_title_no_emoji:title 不含 📊（或任何 emoji）
- test_popup_text_has_spacing:Text widget 有 spacing1=4 spacing3=4

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-etf-popup-width 修 Bug 內容】2026-06-20 11:50 (William 11:50 反映)
════════════════════════════════════════════════════════════════════════════════
【問題】William 看 v0.9.5-etf-popup-spacing 截圖：
- popup 後面有好幾個字被截斷、看不到完整 ETF 列表

【根因】
- Text widget 的 width 是「平均字元寬度」單位
- 我用 `max(len(line) for line in lines)` 算 width
- 但中文實際寬度 ≈ 2× ASCII 寬度
- 結果：width 計算偏小、中文字超出 width、後面被截斷

【修法】新加 _display_width helper
- 中文（CJK + 全形 + 平假名/片假名）算 2 字元
- 其他（ASCII、半形標點）算 1 字元
- popup width 改用 `_display_width(line)` 計算

【實測驗證】
- ETF 名稱：「主動野村臺灣優選」
  - len() = 8 字元 → width 偏小
  - _display_width() = 16 字元 → width 足夠
- 18 檔 ETF：原本 width 約 25 → 修完 width 約 45
- 顯示完整、不再截斷

【pytest 新增 1 個】test_etf_popup_width.py
- test_display_width_counts_cjk_as_double:中文字算 2、ASCII 算 1
- test_popup_uses_display_width:StockTool 有 _display_width 函式、popup 引用它

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-locale-comma-fix 修 Bug 內容】2026-06-20 12:12 (William 12:12 反映)
════════════════════════════════════════════════════════════════════════════════
【問題】William 開 Windows「語言支援 → 區域格式」看到：
- 地區：中文（臺灣）、千位=`,`、小數=`.`
- 但 StockTool Treeview cell 顯示的價格、市值、手續費等千位分隔是 `.` 不是 `,`
- 至少價格欄位（Treeview 內）有這問題

【根因】延續 V0.9.5-goodinfo4+5 教訓：
- Tkinter Treeview + locale=zh_TW.UTF-8 會把 cell 字串的 `,` 當成歐洲小數點
- 成交量已解：用 str(int(vol)) 不千分位
- 但其他 Treeview cell（價格、市值、手續費、股數、損益）仍用 f"{x:,.2f}"
  → 一樣被轉成歐洲格式顯示

【修法】4 個 Treeview cell 全改不加千分位：
1. ETF Treeview price_str（line 7180）
2. 買賣記錄 mini Treeview（line 7608-7611）
3. 持倉 Treeview（line 7656-7666）
4. 交易 Treeview（line 7672-7675）

【不改的地方】
- Label widget（持倉總覽、預估視窗 stat()）：純文字、不會被 Tkinter locale bug 影響
  → 保留千分位顯示讓數字易讀

【pytest 新增 1 個】test_locale_comma_fix.py
- test_no_treeview_cell_uses_comma_thousands:grep 4 個 Treeview insert 區塊、確保都沒有 :, 千分位

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-shares-int 修 Bug 內容】2026-06-20 14:13 (William 14:13 反映)
════════════════════════════════════════════════════════════════════════════════
【問題】William 開 App 看買賣紀錄頁面：
- 股數欄位顯示「1000.0」有小數點、不要

【根因】
- Transaction.shares: float = 0.0（portfolio.py line 326）
- str(t.shares) 對於 float 1000.0 會顯示「1000.0」
- 對於 float 1000.5 會顯示「1000.5」

【修法】3 個 Treeview cell 股數改成 str(int(t.shares))
1. 買賣記錄 mini Treeview (line 7637)
2. 持倉 Treeview (line 7686)
3. 交易 Treeview (line 7703)

【不改的地方】
- Label widget（持倉總覽、預估視窗 stat()）：已是 f"{x:,.0f}" 整數顯示
- 計算邏輯（avg_cost、market_value 等）：仍是 float 精確運算

【pytest 新增 1 個】test_shares_int.py
- test_shares_display_is_integer:Treeview cell 的股數欄位是 str(int(...))
- test_shares_int_helper_works:int() 強制轉 float 顯示整數

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-etf-history ETF 持股歷史庫】2026-06-20 17:54 (William 17:54 需求)
════════════════════════════════════════════════════════════════════════════════
【需求】William 開 App 看 ETF Tab：
1. 統計列表最後加「今日異動」欄（張數）
2. Hover 顯示各 ETF 分別異動的數量
3. App 啟動只抓一次、歷史存 local DB

【設計決策】
- 開新 DB：etf_history.db（避免污染既有 dividend_history.db）
- 抓取源：etfinfo.tw /etf/{code} 的 SSR 資料（__NUXT_DATA__）
  → schema dict + 5 values (code, name, weight, shares, unit)
  → shares 直接是「持股股數」、換成張數 = shares / 1000
- 異動算法：Σ (today_shares_lots - yesterday_shares_lots)
  → 新增 ETF = +today_shares_lots
  → 刪除 ETF = -yesterday_shares_lots
- 不抓 ETF 規模（用 shares 直接算、不需換算）

【DB schema】
- etf_holding_history(date, etf_code, stock_code, stock_name, weight_pct, shares, shares_lots, industry, fetched_at)
- fetch_meta(key, value, updated_at)

【SSR Parse 技術細節】
- Nuxt 3 flat array 結構
- schema dict 內欄位都是 ref（指向 index）
- 不能用固定 layout 偏移（unit 可能 reuse、weight 可能 reuse）
- 必須用 _resolve_val(nuxt_list, schema[field]) 拿真實值
- expected_end 計算：unit ref < i + 5 表示 reuse、只佔 5 位置、否則 6 位置

【新增函式】
- _init_etf_history_db(db_path)：建表
- _save_etf_holding_snapshot(db, etf_code, holdings, date)：寫入單檔快照
- _query_etf_holdings_by_date(db, date)：查詢指定日期持股
- _query_latest_two_dates(db)：查最近兩個有效日期
- _compute_etf_changes(db)：計算今日 vs 昨日異動張數

【fetcher 改動】
- fetch_etf_top10_holdings 改抓 shares + industry（從 SSR）
- 保持既有回傳 list of dict 介面（向下相容）

【下一步】
- 串接 _etf_auto_startup_fetch：抓完後順便寫 DB
- _etf_tree 加「今日異動」欄 + hover popup
- 排序改為依總異動絕對值
- 第一次啟動無昨日資料、顯示「—」+ 狀態列提示

【pytest 新增 19 個】
- tests/test_etf_history_db.py（13 個）：DB schema / save / query / compute 邏輯
- tests/test_etf_ssr_parse.py（6 個）：SSR parse 守護 + 2 個真實整合測試

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-cache-scrollfix 更新內容】2026-06-19 22:15 (William 反映)
════════════════════════════════════════════════════════════════════════════════
【背景】William 22:12 本機測試反映 2 點：
1. 「手動選股左邊欄位沒有全部顯示時請提供 scroll bar 可以 scroll」
2. 「匯出 excel 所生成 file 可以為回策略參數中的選股來源嗎？果可以只要這個功能即可」

【改動 1】手動選股左面板加垂直捲軸
- 原實作：left_frame = ttk.LabelFrame(paned) → widget 比視窗高被裁掉
- 新實作：left_container = Frame(paned) + Canvas + Scrollbar（參考策略參數 Tab pattern）
- left_frame 改放在 Canvas 內、bind <Configure> 更新 scrollregion
- 加 <MouseWheel> 滑鼠滾輪支援

【改動 2】「📤 匯出 Excel」補上使用提示
- 結論：匯出的檔可以直接當「使用 Excel 股票清單」讀取
  · load_stock_list_from_excel 透過 find_col 找「股票代號」欄
  · 多餘欄位（殖利率、現價等）不影響
- 原本上版新增的「💾 存成 Excel 股票清單」按鈕 → 拿掉
  · 與「📤 匯出 Excel」重複
  · 多餘複雜度、撥亂反正
- messagebox.showinfo 加訊息：「💡 這個檔案可以直接給「策略參數 → 使用 Excel 股票清單」讀取使用」

【pytest 調整】
- 刪除 tests/test_ms_save_stock_list.py（4 個 test、針對已拿掉的方法）
- 新增 tests/test_ms_export_excel_compat.py（1 個整合測試）

【驗證】
- pytest：237 passed（-4 +1）、3 pre-existing fail（跟本次無關）

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-cache-savelist 更新內容】2026-06-19 22:10 (William 要求）
════════════════════════════════════════════════════════════════════════════════
【背景】William 22:05 本機測試：「手動選股頁少了一個 Save 按鈕」
- 要求：「勾選要的股票後可以儲存為 excel file」
- 要求：「至少要勾選一隻股票」
- 要求：「餵給策略參數頁的「使用 Excel 股票清單」」

【設計決策】加新的「💾 存成 Excel 股票清單」按鈕
- 不同於既有的「📤 匯出 Excel」（包含 20+ 欄全資料）
  · 既存的：供 user 自己備查、看完整資料
  · 新的：只存「股票代號」+「股票名稱」兩欄、可被 load_stock_list_from_excel 直接讀取

【改動】
- btn_row 加 ttk.Button('💾 存成 Excel 股票清單', self._ms_save_stock_list)
- 新增 _ms_save_stock_list method：
  · 檢查 _ms_result_df 存在、否則提示「請先按選股」
  · 檢查 _ms_checked 至少 1 隻、否則提示「請至少勾選一隻」
  · 彈 filedialog.asksaveasfilename、預設檔名 stock_list_YYYYMMDD_HHMM.xlsx
  · 只存兩欄（股票代號、股票名稱）、藍色 header、欄寬 12/24
  · 存完 messagebox.showinfo 告訴 user 下一步怎麼用
  · 錯誤 messagebox.showerror + logger.log

【pytest 新增 4 個】
- test_未選股_提示無資料
- test_沒勾選任何股票_提示未勾選
- test_勾選至少一隻_寫入乾淨格式
- test_load_stock_list_from_excel_可讀回_我們存的檔（整合測試）

【驗證】
- pytest：240 passed（+4 新）、3 pre-existing fail（跟本次無關）

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-cache-hover 更新內容】2026-06-19 22:00 (William 要求)
════════════════════════════════════════════════════════════════════════════════
【背景】William 21:53 本機測試：「現在看起來 so far so good」
- 要求「滑鼠移到某股票範圍時、把整個 row 都 highlight、這樣比較好讀」
- 移走時取消、用黃色

【改動】手動選股 Treeview 加 hover highlight
- 新增 tag_configure：
  · 'hover'：背景 #fff3a0（黃色）
  · 'checked'：背景 #d0e8ff（淺藍）
  · 'unchecked'：背景 #ffffff（白）
- 新增 event bindings：
  · <Motion> → _on_tree_hover：進新 row 設 hover tag、離開舊 row 清除
  · <Leave> → _on_tree_leave：離開 Treeview 時清除 hover
- 新增 _clear_hover()：根據 _ms_checked 恢復該列原本的 checked/unchecked tag
- 狀態變數：self._ms_hover_iid 記住目前 hover 的 row iid

【邊界】
- 滑鼠移到 header 或捲軸 → 不算 cell → 清 hover
- 重跑選股刪除 Treeview 時會清除舊 iid 的 hover、用 try/except TclError 保護
- 點 checkbox toggle 仍能改 checked 狀態、不受 hover 干擾
  （toggle 最後用 self._ms_tree.item(item_id, tags=('checked' if not current else 'unchecked',)) 
   設個、hover 狀態會被覆蓋；但該列不變、狀態正確）

【驗證】
- pytest：236 passed、3 pre-existing fail
- 純 GUI event handler、不易寫 unit test、用本機測試驗證

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-cache-vol-fix2 更新內容】2026-06-19 18:50 (William 反映)
════════════════════════════════════════════════════════════════════════════════
【背景】William 18:49 本機測試：18:43 按了「🔄 重新抓股價」、cache 抓好了
- 但 Treeview 「成交量」、「資料日期」還是「—」
- 原因：手動重抓完成後 _on_bg_price_done 只更新 status bar、沒讓 Treeview 重跑結果
- 使用者需手動按「選股」才會看到新資料、看起來像是「重抓失敗」

【改動】_on_bg_price_done 自動重跑選股
- 觸發條件：source == '手動重抓' AND Treeview 已有結果
- 重跑後 Treeview 立即顯示「成交量」、「資料日期」新資料
- 不重跑路徑：app 剛起動、Treeview 還是空、使用者沒選過股
- log 訊息：'自動重跑選股中...'、'✅ 符合條件：N 檔'

【驗證】
- pytest：12 個 cache_vol test 全綠（fetch_prices 結構、get_or_fetch 遷移）
- Treeview 仍有水平捲軸 (ms_scroll_x)、14 欄超寬可以左右拉

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-cache-vol-fix 更新內容】2026-06-19 18:35 (William 反映)
════════════════════════════════════════════════════════════════════════════════
【背景】William 18:35 本機測試：Treeview 「成交量」、「資料日期」還是「—」
- 原因：cache 是 v0.9.5-goodinfo4+5 拿下的、只有 4 欄（沒 成交量_張 / data_date）
- 18:29 開 App 是盤後、走 get_or_fetch「last_update==today 用 cache」路徑
- 所以「啟動時自動」跳過、Treeview 讀舊 cache、顯示「—」

【改動】get_or_fetch 加「結構遷移」檢查
- 如果 cache 是今天的、但缺 成交量_張 / data_date 欄位 → 自動強制重抓一次
- 寫入新結構、後續開 App 就正常使用
- 一次性邏輯、之後 cache 都是新結構不會再觸發

【pytest 新增 2 個】
- test_get_or_fetch_cache缺欄位_自動重抓（驗證結構檢查觸發重抓）
- test_get_or_fetch_cache已完整_不重抓（驗證正常情況不被打擾）

【pytest 修正 1 個】
- test_get_or_fetch_market_hours._fake_price_df：原本只 3 欄、加上新欄位
  · 公司名稱_來源（原本是「股票名稱」、改成跟程式一致）
  · 漲跌
  · data_date / 成交量_張

【驗證】
- pytest：236 passed（+2 新 test）、3 pre-existing fail
- 跨區關係：同時保護 cache_cleanup1（拿掉 checkbox）+ cache-info（加 data_date）+ cache-vol（加 成交量_張）

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-cache-vol 更新內容】2026-06-19 18:00 (William 反映)
════════════════════════════════════════════════════════════════════════════════
【背景】William 2026-06-19 17:52 本機測試截圖反映 3 點：
1. 「成交量(張)」、「資料日期」欄位全顯示 —（cache 沒有這兩個欄位）
2. 視窗標題還是寫 v0.9.5-goodinfo4+5（忘記更新 VERSION 變數）
3. 「提示」框位置太下面被捲拉遮住、難讀

【改動 1】VERSION 變數更新（修視窗標題）
- VERSION = "v0.9.5-goodinfo4+5" → "v0.9.5-cache-vol"
- self.title() 用 VERSION、視窗標題會自動更新

【改動 2】fetch_prices 順便抓成交量
- TWSE STOCK_DAY_ALL 有 TradeVolume（股）、TPEx 有 TradingShares（股）
- 兩者都是「股」單位 → /1000 變「張」
- 統一存為 成交量_張 欄位
- 邊界：API 沒 volume 欄位 → 成交量_張 = None、不 crash
- 倒果：之前 cache_cleanup1 拿掉「即時抓股價」checkbox、沒人抓成交量
  → Treeview 一直顯示 —。這修補了這個 regression。

【改動 3】「提示」框位置調整
- 原本：放在 console 下方、被捲拉遮住
- 改為：放在 console 標題同一行（標題左、提示右）
- 提示內容也縮短成一行、字體調小

【pytest 新增】
- tests/test_data_date_column.py 加 3 個成交量 test：
  · TWSE TradeVolume 股→張
  · TPEx TradingShares 股→張
  · API 沒 volume 欄位不 crash

【驗證】
- pytest：234 passed（+3 新 test）、3 pre-existing fail
- 順便驗證 fetch_prices mock 測試：2330 25000 張、6547 5000 張 都能正確轉換

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-cache-info 更新內容】2026-06-19 17:00 (William 決定)
════════════════════════════════════════════════════════════════════════════════
【背景】2026-06-19 14:17 William 延續討論：「手動選股筛選結果中增加一個欄位
顯示個股資料所參考的最新日期」。這樣可以一眼看出筛選結果用的是哪天的收盤資料，
避免「股價跟我看到的不一樣」混淆。

【改動 1】Treeview 加「資料日期」欄位
- fetch_prices 加 data_date 欄位（從 TWSE/TPEx 的 Date 欄位）
  · TWSE / TPEx Date 都是民國年格式 "1150618" → 西元 "2026-06-18"
  · 內部實作 _roc_to_ad() 轉換
  · 邊界：API 沒 Date 欄位或格式不對 → 回空字串、不 crash
- _run_manual_selection 的 price_cols / out_cols / final_cols 都加 data_date
- _ms_display_results 在 Treeview 最右邊加「資料日期」欄位（14 欄變 15 欄）
- 顯示規則：有 date 顯示日期、無 date 顯示 "—"

【改動 2】_is_market_hours() 加半日盤例外
- 新增 _HALF_DAY_DATES set（清單內容：過年封關日、其他需要提前收盤的特殊交易日）
- 目前只有 "2026-02-13"（2026 過年封關日、除夕 2/16 前最後交易日）
- 預設 半日盤 13:00 收盤（平日 13:30 收盤）
- 註解標明來源：台灣證交所公告的「市場開休市日程」

【改動 3】_on_bg_price_done 在 status bar 加股價更新時間 + 資料日期
- 原本：「✅ 股價資料就緒（啓動時自動、2376 筆）｜可點「選股」」
- 改為：「✅ 股價資料就緒（...）｜股價更新：2026-06-19 17:00:00｜資料日期：2026-06-18｜可點「選股」」
- 讓使用者不用切到手動選股 Tab 也看得到更新時間

【pytest 新增】
- tests/test_market_hours.py 加 5 個半日盤 test（含清單包含 2026 封關日）
- tests/test_data_date_column.py 新檔、7 個 test：
  · 民國年轉西元（正常 / 民國 100 / 民國 114 / 格式錯誤）
  · API 沒 Date 欄位不 crash
  · TPEx 股也有 data_date
  · _run_manual_selection 保留 data_date

【驗證】
- python -c "import ast; ast.parse(...)" → ✅ syntax OK
- pytest：231 passed（+12 新 test 全綠）、3 pre-existing fail（test_dividend_yield_fix、跟本次改動無關）
- 比 v0.9.5-cache-cleanup1 的 219 passed 多 12

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-cache-cleanup1 更新內容】2026-06-19 14:17 (William 決定)
════════════════════════════════════════════════════════════════════════════════
【背景】2026-06-19 13:55 William 提出股神股票現價抓取邏輯討論：
- 「App 隨時要有最新的收盤個股資訊（cache）、開機發現不是最新則去抓」
- 「手動選股中應該不需要有 TWSE 即時股價的開關」

【改動】手動選股 Tab 拿掉「🔄 TWSE 即時股價」checkbox + 速率模式 radio
- 拿掉 UI：_ms_refresh_price_var BooleanVar + Checkbutton
- 拿掉 UI：_ms_twse_slow_mode BooleanVar + 兩個 Radiobutton（🚀快速 / 🐌緩慢）
- 拿掉 method：_ms_twse_rate_mode_changed() （更新狀態列用）
- 拿掉 _ms_run_selection 裡的「即時抓股價」if 分支（94 行）
- _fetch_twse_realtime_batch 拿掉 slow_mode 參數（已無 UI 控件呼喚）
  · batch sleep 從 `5.0 if slow_mode else 0.3` 簡化為固定 `0.3`
  · 函式本身保留（未來可能還用得到 batch 抓股價）

【為什麼可以拿掉】
- 手動選股邏輯：本來就用 cache 的 close 收盤價、即時 tick 會干擾篩選
- 看即時 tick：去「買賣紀錄」Tab、已有 30 秒 polling
- 想重抓 cache close：原本就有「🔄 重新抓股價」按鈕（強制重抓、走 fetch_prices）

【pre-commit hook 擴充】
- 原本 regex：`v0.9.5-(goodinfo|twser)[0-9]+([.][0-9]+)?`
- 改為：`v0.9.5-(goodinfo|twser|cache)[a-z0-9]*([.][0-9]+)?`
- 讓 cache 系列也能自動更新 fileheader 時間戳

【驗證】
- python -c "import ast; ast.parse(...)" → ✅ syntax OK
- grep 確認 _ms_refresh_price_var / _ms_twse_slow_mode / _ms_twse_rate_mode_changed 在 code 已無引用
- 跑 pytest：下面報告

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-alpha 更新內容】2026-06-14
════════════════════════════════════════════════════════════════════════════════
【手動選股 Tab 升級】（Phase 1：背景重抓股價 + PE 過濾）
- App 啟動時背景重抓股價（跳過今天已抓的 cache）
- 手動選股 Tab「🔄 重新抓股價」按鈕
- Race condition 防呆（_bg_price_fetching flag）
- PE 接近 0 過濾（EPS < 0.05 → PE = None，解決大城地產 PE=300 爆炸值）

【手動選股 Tab 升級】（Phase 2：股利DB + 修殖利率年份對應 bug）
- 股利歷史庫 dividend_history.db（同 eps_history 風格）
- 修 Bug：殖利率年份對應錯誤（cy-1=今年、cy-2=去年、cy-3=前年）

【手動選股 Tab 升級】（Phase 3：補抓股利 + 100檔/次分批）
- 「💰 補抓全部股利 (一次性)」→「💰 掃描全部股票 (100檔/次)」
- 新增「🎯 指定股補抓 (推薦 Free tier)」按鈕
- 每次只抓 100 檔、可分散跑（Free tier 300-1000 筆/月額度友善）
- 新增 scripts/fetch_dividend.py（CLI 補抓介面、對話中也能跑）

【手動選股 Tab 升級】（Phase 4：B 邏輯篩選 + DB cache 過期）
- 改用 pass_score (達標) + data_score (有資料) 雙計分
- 殖利率 None 不再被視為達標、None 排到結果後面
- 至少要有一個條件有資料才納入結果
- 沒結果 → 「❌ 這次篩選沒有合格股票」+ 可能原因提示
- DB cache 過期（> 30 天）→ 自動重抓 FinMind
- 新加 _query_div_history_with_fetched 函數（用 fetched_at 判斷過期）
- 強化 402 額度訊息（已完成 X/Y 檔｜請下月重置或升級 plan）

【手動選股 Tab 升級】（Phase 5：「即時抓股價」checkbox）
- 跑選股前可勾選「🔄 即時抓股價」→ 重新抓 price_df 全部股票的最新股價
- 預設不勾（用 cache 背景抓的版本、較快）
- 設計原因：背景重抓股價的時間跟使用者看見的時間可能有差
  → 勾選後跑選股前會用最新股價（但會等股價抓完、較慢）
- 順手加 CLI 手動覆寫工具（fetch_dividend.py update）

【手動選股 Tab 升級】（Phase 6：修 Bug + 402 主動提示）2026-06-15
- 【修 Bug】勾選「去年現金殖利率 ≥ X%」不會再拋 UnboundLocalError
  - 根因：Phase 4「B 邏輯」改一半，line 1168-1175 殘留 data_score / pass_score
    雙計分死 code（變數從未初始化）
  - 修法：line 1168-1175 改成跟 line 1163-1166（今年現金殖利率）一樣的
    no-op（只設 any_checked=True），排序階段用 _yld_has_data 自然處理
  - 表現：原本勾選「去年現金殖利率」就會崩潰、修完正常運行
- 【UX 改善】手動選股跑完主動提示 FinMind 402 額度錯誤
  - 情境：_fetch_finmind_dividend 中途被 402 中斷（已抓 X 筆寫入 DB），
    _run_manual_selection 仍會完成並回傳部分結果
  - 原本：使用者只看到「殖利率欄位一堆 None」、困惑為什麼
  - 修完：狀態列附加「⚠️ FinMind 額度用完（已抓 X/Y 檔）｜部分股票殖利率為 None｜💡 改用指定股補抓或等下月重置」
- pytest 新增 test_filter_last_yld_unbound.py（4 個）：
  - test_勾選去年現金殖利率_不拋UnboundLocalError（核心守護）
  - test_去年殖利率軟條件_不擋mask
  - test_去年殖利率有值但未達標_不擋mask
  - test_只勾選去年現金殖利率_仍可運行

【手動選股 Tab 升級】（Phase 7：股價時段邏輯 + Preset 開機自動載入）2026-06-15
- 【新規則】股價時段邏輯（William 09:56）
  - 09:00 後到 13:30 收盤前：股價會一直變 → 任何需要現價的功能都要 refresh
  - 13:30 收盤後：股價固定 → 一天只 refresh 一次（last_update == today 用 cache）
  - 週末：不開盤 → 用上週五收盤價、一天只 refresh 一次
- 【實作】新增 _is_market_hours() 工具函式
  - 判斷：週一~五 09:00 ~ 13:30 為台股盤中
  - 套用在 get_or_fetch：當 name == "price" 且盤中 → 強制 refresh、不限次數
  - revenue/eps 不受時段影響（仍用原本 last_update == today 判斷）
- 【UX 改善】Preset 開機自動載入
  - 修 Bug：儲存 preset 後重開 App、preset 下拉是空的、UI 條件沒還原
  - 根因：_ms_preset_var 預設空字串、_ms_load_preset 拿空字串會早退
  - 修法：開機時先呼叫 _ms_refresh_preset_list() 把 manual_select_last_preset
    設進 var、再呼叫 _ms_load_preset() 載入條件
  - 表現：開機自動套用上次的 Preset、checkbox / entry 還原成儲存時的狀態
- pytest 新增 test_market_hours.py（16 個）：_is_market_hours() 邊界守護
- pytest 新增 test_get_or_fetch_market_hours.py（5 個）：
  - test_price_盤中_即使cache是今天也強制refresh（核心守護）
  - test_price_盤後_用cache不refresh
  - test_price_盤後_cache是昨天_走正常refresh路徑
  - test_revenue_盤中_不強制refresh_走原本邏輯
  - test_eps_盤中_不強制refresh_走原本邏輯

【手動選股 Tab 升級 + 買賣記錄 Tab】（Phase 8：股利金額顯示 + 30秒 refresh）2026-06-15
- 【修 Bug + 改善】手動選股結果顯示今年/去年股利金額
  - 修 Bug：_ms_display_results 內 row.get 沒讀「今年現金股利(元)」、「去年現金股利(元)」
    → 雖然 DataFrame 結果有、但 Treeview 沒顯示
  - 修法：加 2 個 column「今現金」、「去年現金」+ 對應的 row.get 讀取
  - 表現：Treeview 從 11 個 column 變 13 個、使用者可以直接看到「現金股利金額 + 殖利率」驗算
- 【新規則】買賣記錄 Tab 開盤 30 秒 refresh 持倉現價（William 11:02）
  - 切到買賣記錄 Tab 且在開盤時段（09:00~13:30）→ 每 30 秒 refresh 持倉現價
  - 收盤後、週末、切離買賣記錄 Tab → 自動停止
  - 實作：_schedule_portfolio_refresh / _portfolio_refresh_loop / _cancel_portfolio_refresh
  - 與現有「切到 Tab 時抓一次」共存：第一次切到 Tab 仍抓一次、之後每 30 秒抓一次
- pytest 新增 test_ms_display_div_columns.py（5 個）：
  - test_run_manual_selection_產出含元後綴股利欄位（核心整合守護）
  - test_股票股利格式化_用對的key
  - test_現金股利格式化_用對的key
  - test_殖利率None時_格式化為橫線
  - test_股利為0時_現金殖利率應為None（邊界）
- pytest 新增 test_portfolio_refresh_loop.py（10 個）：
  - test_盤中_排程下一次refresh
  - test_盤後_不排程
  - test_重複排程_取消上次的
  - test_盤中_refresh_loop_刷新並排程下一次
  - test_refresh_loop_已切離Tab_停止loop
  - test_cancel_有job時呼叫after_cancel
  - test_cancel_沒job時不做事
  - test_refresh_loop_盤中排程後_排程時已是盤後_就停
  - test_on_tab_changed_切到買賣記錄_啟動refresh
  - test_on_tab_changed_切走_取消refresh

【買賣記錄 Tab】（Phase 9：00403A 現價 fallback）2026-06-15
- 【修 Bug】00403A 現價一直停在 10.61 不動
  - 根因：TWSE 在「沒成交瞬間」 z='-' → _num('z') 轉成 0.0
         → _apply_fetched_prices price=0 跳過更新 → 保持舊值
  - 修法：fetch_stock_info z=0 時 fallback 到 h+l 中價（今日高低价中點）
    - 比 y（昨收）更接近即時
    - 標記 price_fallback='mid'、UI 可依此判斷
  - 二層 fallback：h/l 也為 0 → fallback 到 y（昨收）、標記 price_fallback='prev_close'
  - 三層 fallback：y 也為 0 → price 保持 0、不更新
  - logger 提示：「⚠️ XXX 無即時成交價、用今日高低价中點估算」
- 影響範圍：所有交易不活躍的標的（特別是主動式 ETF、0050 這類有時 z='-' 的）
- pytest 新增 test_fetch_stock_info_fallback.py（9 個）：
  - test_z是橫線_fallback到h_l中價（核心）
  - test_z是None_fallback到h_l中價
  - test_hl也都0_fallback到昨收
  - test_全都0_price保持0
  - test_z有即時成交_不fallback（守護正常路徑）
  - test_z有即時成交_就算接近昨收也不誤判fallback
  - test_fetch_prices_batch_00403A_fallback正常運作
  - test_apply_fetched_prices_fallback也更新
  - test_apply_fetched_prices_price為0仍然跳過

【手動選股 Tab + 買賣記錄 Tab】（Phase 10：去年現金殖利率算法 + 30 秒 polling 動態顯示）2026-06-15
- 【修 Bug + 改善】去年現金殖利率應除以「去年除息日收盤價」不是現價（William 11:39）
  - 原本：除以現價 → 譯導（殖利率看似高、實際上是用現價算的）
  - 修正：除以「去年除息日收盤價」→ 真正表示「拿去年現金股利、除以當時除息日的股價」
- 【實作】
  - DB schema migration：加 ex_date（除息日）、ex_date_close（除息日收盤價）兩個欄位
    - 重複 init 安全（漏了加也不會爆）
  - _fetch_finmind_dividend 保留 FinMind 的 date 欄位、寫入 DB
  - 新增 _fetch_ex_date_close(stock_id, ex_date)：
    - 抓 ex_date ±3 天的股價（避免除息日是假日沒資料）
    - 額度用完 / 沒資料 / close=0 → silently 回 None
  - 新增 _update_ex_date_close()：寫入 DB 緩存、避免下次重抓
  - 改寫 _run_manual_selection 去年現金殖利率算法：
    - 優先用 ex_date_close（DB 緩存優先 → 沒有才打 FinMind → 寫回 DB）
    - fallback：沒 ex_date_close → 用現價（避免 DB 還沒建完、殖利率全 None）
- 【動態顯示】30 秒 polling 看不到進行狀態（William 11:39 反映）
  - 修法：fetch_prices_batch 加 progress_callback
  - _auto_fetch_positions_prices 用 callback 動態 log：
    - 「⏰ 下次 refresh HH:MM:SS」起動提示
    - 「🔄 [3/8] 抓 2330 中... (37%)」每一檔進度
    - 「✅ refresh 完成：5.2 秒抓完 5 檔」結束報告
- pytest 新增 test_ex_date_yield.py（15 個）：
  - DB schema migration：test_db_init_加ex_date欄位、test_db_init_重複跑不爆
  - _upsert_div_history：test_upsert_7tuple_含ex_date寫入、test_upsert_5tuple向後相容
  - _update_ex_date_close：test_update_ex_date_close寫入緩存
  - _fetch_ex_date_close：6 個（正常、假日、空字串、額度、沒資料、close=0）
  - _run_manual_selection 整合：4 個（用 ex_date_close 不是現價、沒 ex_date、現金=0、自動 fetch 緩存）

【買賣記錄 Tab】（Phase 11：持倉現價累計證交稅 + 計入總損益）2026-06-15 19:15
- 【William 19:15 新需求】累計證交稅請以持股現價計算顯示出來並記入總損益中
- 【原本】累計證交稅 = 已賣出交易實際付過的稅（historical）
- 【修正】累計證交稅 = Σ(現價 × 股數 × 0.003) for 有現價的持倉（current_tax）
  - 歷史已付稅另外以「歷史累計已付稅」欄位顯示（不丟失資訊）
- 【PortfolioSummary 新欄位】
  - current_tax：持倉現價累計證交稅（V0.9.5+ Phase 11）
  - total_tax：保留為歷史已付稅（向後相容）
- 【total_pl 算法修正】
  - 原本：未實現 + 已實現淨損益 → 會高估（未實現沒扣現價稅）
  - 修正：未實現 + 已實現淨損益 - 現價稅
  - 邏輯：未實現是「假設全部賣出的毛利」、賣出還要付現價稅、要扣
- 【UI】Row 1 改成「現價累計證交稅 / 歷史累計已付稅 / 已實現淨損益 / 總損益（含現價稅）」
- 【Phase 11 hotfix 21:26】威廉反映 Refresh 報 KeyError 'total_return_pct'
  - 原因：row1 加 historical_tax 後變 4 個、total_return_pct 沒地方放、KeyError
  - 修法：row0 加回 total_return_pct 變 5 個、row1 維持 4 個
- pytest 新增 test_current_tax.py（12 個）：
  - 核心算法（4 個）：現價×股數×0.003、沒現價不計、持股=0 不計、部分賣只算剩餘
  - 歷史稅保留（2 個）：historical_tax 不變、current_tax 跟 historical_tax 可同時存在
  - 總損益扣除現價稅（4 個）：部分賣、沒持倉、現價下跌仍扣、報酬率分母
  - PortfolioSummary 結構（1 個）

【v0.9.5-goodinfo 更新內容】2026-06-16
【手動選股 Tab + 環境架構】goodinfo 歷史資料一次匯入 + 每日排程補抓

【Phase 1 - goodinfo 歷史資料一次匯入】
- 新增 scripts/import_goodinfo_history.py
  把 goodinfo 18 個 .xls 檔案匯入本地 SQLite DB：
  * dividend_history.db: 股利 15,253 列 / 2,040 檔 / 10 年 (2017-2026)
  * eps_history.db: EPS 22,040 列 / 1,965 檔 / 12 年 (2014-2025)
  * .tmp/avg_price_history.json: 平均股價 2,375 檔 / 12 年 (2015-2026)
- 重要 mapping 規則：goodinfo「發放年度」= 除息年 = DB year（不用 -1）
- 支援 --dry 預演模式 + --only {div,eps,price,2026exdate,nodiv} 個別子任務
- 【使用量】dry run 4.5 秒、正式寫入 5.0 秒

【Phase 2 - 每日排程自動補抓】
- 新增 scripts/daily_fetch_dividend.sh（crontab shell 腳本）
  - 15:00 自動跑 FinMind 差額補抓（batch=100）
  - 週一到週五（避開週末未開盤）
  - Log 寫入 .tmp/logs/fetch_dividend_YYYY-MM-DD.log
  - 最後抓取時間寫入 .tmp/dividend_last_fetch.txt
- crontab entry: 0 15 * * 1-5 /home/aping/MyProjects/StockTools/scripts/daily_fetch_dividend.sh
  - 走系統 crontab（不包 LLM agent）以避開 FinMind 額度被 M2.7 過載
- scripts/fetch_dividend.py 新增 --all --batch N 全市場補抓 CLI
  - 全市場 2,040 檔股號自動從 TWSE 即時 API 取得
  - 補抓 100 檔/次（Free tier 300-1000/月 額度友善）

【Phase 3 - App 狀態面板】
- _ms_refresh_dividend_status() 加上「最後自動抓取時間」顯示
  - 讀取 .tmp/dividend_last_fetch.txt
  - 狀態列格式：「股利 DB: ✅ 2040/2040 檔（全部就絡）｜自動抓取 2026-06-16 22:09」
  - App 重啟時自動重讀

【Phase 4 - 2026 股利除息日補入】
- 讀 goodinfo 3 個 2026 股利股息檔（P50U/P20-50/P20L）
- 解析「除息交易日」欄位（ROC 'YY/MM/DD 格式 → 西元 YYYY-MM-DD）
- 1,666 筆 UPDATE ex_date（只補除息日、不覆寫 cash/stock）
- 0 筆 INSERT（DB 已有 2026 金額記錄、只補日期）
- 2026 股票股利除權息日尚未到：ex_date_close 留 NULL
  → App 殖利率計算會用最新收盤價 fallback（V0.9.5+ Phase 10 設計）

【Phase 5 - 修 Bug：335 檔「goodinfo 已查無股利」股號】
- William 反映手動選股「股利 DB: 2030/2374 檔（缺漏 335）」
- 根因：goodinfo 10Y 檔對 335 檔「無股利」標的沒資料
  - 新發行的主動式 ETF (00400A~00406A)
  - 槓桿/反向型 ETF (006205~00646)
  - 跨境 ETF 無股利 (0057、0061、00636 等)
- 修法：mark_no_dividend_stocks() 函式
  - 把 price_df 有、但 DB 沒的股號 INSERT 標記 (cash=0, source='goodinfo_no_div')
  - 手動選股即可正確顯示「無缺漏」（避免誤報 335 缺漏）
- 結果：DB 股號總數 2040 → 2375（+335 標記）
- 標記 source='goodinfo_no_div'，方便之後區分「實際有股利」vs「查無股利」

【TWSE / FinMind 分工重大設計決策】
- 月營收 / 營收 YoY：TWSE t187ap05_L.csv（App 已在用，不走 FinMind）
- 季 EPS：TWSE t187ap14_L.csv（App 已在用，不走 FinMind）
- 股利分派：TWSE 找不到公開 CSV（試過 t05st10ifrs_L.csv → 404）
  → 仍用 FinMind + goodinfo 互補
- 歷史股利 (10-12 年)：goodinfo 一次匯入
- 每日新股利：FinMind 差額補抓（crontab 15:00）

【pytest】146 個 test 全部通過 ✅（與 v0.9.5-alpha 相同）
- test_dividend_year_mapping.py（5 個）
- test_pe_filter.py（5 個）
- test_dividend_specific.py（10 個）
- test_dividend_fetch_all.py（6 個）
- test_dividend_scan_batch.py（8 個）
- test_fetch_dividend_cli.py（10 個）
- test_filter_b_logic.py（7 個）
- test_div_cache_expiry.py（8 個）
- test_ms_refresh_price.py（3 個）
- test_filter_last_yld_unbound.py（4 個）
- test_fetch_dividend_update.py（8 個）
- test_market_hours.py（16 個）
- test_get_or_fetch_market_hours.py（5 個）
- test_ms_display_div_columns.py（5 個）
- test_portfolio_refresh_loop.py（10 個）
- test_fetch_stock_info_fallback.py（9 個）
- test_ex_date_yield.py（15 個）
- test_current_tax.py（12 個）

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-twser2 更新內容】2026-06-18 10:31 (William 反映)
════════════════════════════════════════════════════════════════════════════════
【William 反映】
1. 殖利率欄位全部顯示「-」（一個都沒有）
2. 現金股利數字錯了（懷疑股票+現金被加總）

【Bug 1：殖利率全部 "-" — 根因 + 修法】
- 根因：`_fetch_finmind_dividend` 用 `_query_div_history` 查 DB
  → `_query_div_history` 只回 `cash/stock/ex_date`，不包含 `cash_yield_pct/share_yield_pct`
  → 所以輸出的 `{cy}現金殖利率_goodinfo` 等欄位全部是 None → Treeview 顯示「-」
- 修法：改用 `_query_div_history_with_fetched`（有完整 9 欄含殖利率）
  - 同時注意 nested 結構差異：`.get("years", {})` → `.get(year)`

【Bug 2：_upsert_div_history 只寫 7 欄 — 會洗掉 goodinfo 殖利率】
- 根因：`INSERT OR REPLACE` 只給 7 欄（stock_id~ex_date_close）
  → `cash_yield_pct/share_yield_pct` 兩個欄位變成 NULL（被洗掉）
  → 這是「次要風險」（主要 App 用 `skip_remote=True` 不會跑 upsert）
- 修法：`_upsert_div_history` 擴充支援 9-tuple
  - 5-tuple（舊）：補足到 9 欄
  - 7-tuple（現有 caller）：補 2 個 None
  - 9-tuple（新）：直接寫入、不洗掉既有值

【pytest】test_dividend_yield_fix.py（5 個守護 test）

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-twser3 更新內容】2026-06-18 11:16 (William 反映)
════════════════════════════════════════════════════════════════════════════════
【William 反映】
1. 現金股利你還是把現金＋股票加總了！所以殖利率是錯的數字！
   → 【查證結果】DB 跟螢幕值完全一致、現金股利確實是 cash only：
     - DB cash + stock 是分開存分開顯示（goodinfo 6 檔：3 現金 + 3 股票）
     - 2548 華固：DB cash=8.5, stock=0.5 → 螢幕「今現金=8.50, 今股票=0.50」✓
     - 2442 新美齊：DB cash=2.7, stock=0.7 → 螢幕「今現金=2.70, 今股票=0.70」✓
   - 殖利率也是從 goodinfo cash_yield_pct 直接拿（不是現金/現價 算出來的）
   - 【為什麼看起來「錯」】goodinfo 用「除息日前 5 日均價」（= ex-date close）
     算殖利率、跟現價不同 → 2548 cash=8.5、殖利率 6.53% → 隱含價 130.17（不是現價 107）
   - 應不會有加總問題、但加了 test_cash_strictly_cash_only 整合測試守護
2. 篩選結果中不需要看股票殖利率、盤中不顯示成交量（顯示 "-"）、收盤後顯示總成交量

【修法 1：Treeview 拿掉股票殖利率欄】
- 原本 15 欄 → 改後 13 欄
- 拿掉「今股票殖%」、「去年股票殖%」（Treeview header + display values）
- DataFrame 還是產出 stock_yield 欄位（Excel 匯出還想保留）

【修法 2：盤中成交量顯示 "-"、收盤後顯示總成交量】
- 用 _is_market_hours() 判斷盤中（週一~五 09:00~13:30）
- 盤中 → vol_str = "-"（TWSE 即時 API 每 15-20 秒更新累積量、顯示沒意義還會誤導）
- 收盤後（含週末）→ 維持原本邏輯、顯示千分位總成交量

【pytest】test_ms_no_stock_yield_vol_display.py（7 個守護 test）
- test_treeview_columns_拿掉股票殖利率（13 欄結構守護）
- test_成交量_盤中顯示橫線（盤中邏輯守護）
- test_成交量_收盤後顯示總量（收盤後邏輯守護）
- test_成交量_收盤後None顯示橫線（None 守護）
- test_成交量_週末收盤後顯示總量（週末守護）
- test_run_manual_selection_還是產出_stock_yield_欄位（Excel 匯出守護）
- test_cash_strictly_cash_only（現金 vs 股票分開守護）

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-goodinfo4+5 更新內容】2026-06-18 13:05 (William 反映)
════════════════════════════════════════════════════════════════════════════════
【William 反映】
1. 現金股利你還是把現金＋股票加總了！以 2442 為例 今年現金=2.0、去年現金=0.079 才對！
2. 順便把股票股利及現金股利改成顯示小數點下 3 位數

【Bug 1：goodinfo 10Y_div 本來就是「合計股利」（2017-2026 全部都是）】
- 【根因】William 2026-06-18 17:56 反映
  - 「dividend10Y 的股利是股票＋現金股利所以要減掉 Share10Y 的股票股利！」
  - 原本理解是「goodinfo 從 2026 才改成合計」→ 錯了、其實十年都是合計
  - 2017-2025 之所以看起來 cash 對、是因為該年股票股利=0 (10Y_div = 10Y_div - 0 = cash)
  - 2017-2025 沒股票股利的股、看起來 cash 對；有股票股利的股、cash 就錯了
- 【證據】對照 goodinfo 2442 2025 公開資料：
  - 10Y_div=0.237 (合計), 10Y_share=0.158 (股票), 公開 cash=0.079
  - 0.237 - 0.158 = 0.079 ✓（這就是 William 一直反映的 0.079）
  - 其他股驗證：
    | 代號 | 2019 | 2021 | 2022 | 2023 | 2024 |
    | 2442 cash | 0.502 | 0.102 | 0.204 | 0.051 | 0.110 |
    | 2442 stock | 1.004 | 0.202 | 0.511 | 0.120 | 0.224 |
    | 2442 10Y_div | 1.506 | 0.304 | 0.715 | 0.171 | 0.334 |
    | 1.506-1.004=0.502 ✓ | 0.304-0.202=0.102 ✓ | 0.715-0.511=0.204 ✓ | 0.171-0.120=0.051 ✓ | 0.334-0.224=0.110 ✓ |
- 【修法】改 `import_dividend()` 為 `cash = 10Y_div - 10Y_share`（處理 2017-2026 全部）
  - 拿掉原本的 `import_2026_dividend()` 函式（不需要單獨覆寫 2026）
  - 用 NaN 防呆：若 cash < 0（10Y_share 異常 > 10Y_div）、警告 + 設 0
- 【run 順序】`import_dividend()` → `import_yield_rate()`（不再需要 import_2026_dividend）
- 【DB 修補範圍】2017-2025 全部（不是只有 2026）

【Bug 2：股利顯示精度不夠】
- 原本 `_fmt_float(..., decimals=2)` → 2442 2025 現金 0.237 顯示 0.24（精度丟失）
- 改 `_fmt_float(..., decimals=3)` → 顯示 0.237（保留精度）
- 應用範圍：4 個股利欄位（今年股票/今年現金/去年股票/去年現金）
  其他欄位（現價/殖利率/PE/成交量）仍維持 2 位

【pytest】test_dividend_3decimal_2026_cash_bug.py（10 個守護 test）
- test_股票股利顯示_3位小數
- test_現金股利顯示_3位小數
- test_去年股票股利顯示_3位小數
- test_DB_2026_cash_不等於_cash_plus_stock
- test_2442_2026_cash_等於_2_0_不是_2_7
- test_2442_2025_cash_等於_0_079_不是_0_237（William 一直反映的 0.079 來源）
- test_2442_歷年_cash_符合_10Y_div_扣_10Y_share（2019-2026 全部）
- test_2548_2026_cash_等於_8_0_不是_8_5
- test_import_2026_dividend_保留_殖利率
- test_季配股_2026_cash_未公布_保留_既有值

【DB 修補結果】
- 2017-2025 全部重算 cash（10Y_div - 10Y_share）
- 受影響股數：所有有股票股利的股（2017-2026 加起來估計幾千筆）
- 修法：重跑 `python3 scripts/import_goodinfo_history.py --only div` 自動修補
- 修補後重點驗證：
  - 2442 2025 cash: 0.237 → 0.079 ✓
  - 2442 2026 cash: 2.7 → 2.0 ✓
  - 2442 2019 cash: 1.506 → 0.502 ✓
  - 2542 cash 大多下降（之前是 cash+stock 合計）
  - 9946 2026 cash 保留 1.37（季配 2026 cash=NaN、保留 10Y 加總）

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-goodinfo4+5 (vol + sort) 更新內容】2026-06-18 18:12 (William 反映)
════════════════════════════════════════════════════════════════════════════════
【William 反映】
1. 「成交量不是我要的今日成交量！」 → 拿掉盤中/收盤後切換邏輯
2. 「順便將篩選結果依照營收累計YoY由大到小排序」

【修法 1：成交量直接顯示今日量】
- 【原本 V0.9.5-twser3】盤中 → "-"，收盤後 → 總成交量
- 【V0.9.5-goodinfo4+5 修正】拿掉 _is_market_hours() 判斷、直接顯示 price_df 的「成交量(張)」
- William 說「就是要看今日即時量」→ 盤中的累積量也是有意義的

【修法 2：主排序改為營收累計YoY 降序】
- 【原本】sort = [_yld_has_data, _sort_yld, _sort_stock, _sort_rev, _sort_pe]
  → 殖利率有資料、殖利率高、股票股利高、營收YoY 高、PE 低
- 【新】sort = [_sort_rev, _yld_has_data, _sort_yld, _sort_stock, _sort_pe]
  → 營收YoY 高、殖利率有資料、殖利率高、股票股利高、PE 低
- 主排序從「殖利率」改為「營收累計YoY」
- 同營收YoY 時、還是依殖利率排序
- None 排最後（用 -9999 作 sort key）

【pytest】
- test_ms_vol_rev_sort.py（6 個新守護 test）
  - test_成交量_直接顯示今日量_不管時段
  - test_成交量_None_顯示橫線
  - test_成交量_盤中不再顯示橫線（regression 守護：盤中也不再 "-"）
  - test_排序_以營收累計YoY_降序為主
  - test_排序_同_營收YoY_時_殖利率高排前
  - test_排序_None_排最後
- test_ms_no_stock_yield_vol_display.py 重寫（拿掉舊的盤中/收盤後 test）

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-goodinfo4+5 (vol+cache) 更新內容】2026-06-18 18:34 (William 反映)
════════════════════════════════════════════════════════════════════════════════
【William 反映 3 點】
1. 現價沒資料：抓不到的股應該 delay + retry、收盤後為什麼會沒資料？兩個股都重跑都一樣
2. 抓完應該要 update cache
3. 成交量依舊不是今日總成交量

【修法 1：成交量單位修正】
- 【根因】TWSE MIS API 的 v 欄位是「股」、不是「張」！原本 int(v/1000) 會把 4016 股變成 4 張
  例：v=4016 股 → 原本 int(4.016)=4 張（只 4000 股、偏小 16 股）
  修法：vol = v / 1000 保留小數（張）、顯示用 f"{vol:,.3f}"
- 驗證：2548 v=4016 → 4.016 張（原來顯示 4 張，現顯示 4.016 張）
  1815 v=21416 → 21.416 張（原來顯示 21 張，現顯示 21.416 張）

【修法 2：otc_ fallback（修 6 開頭 = 上櫃 的誤判）】
- 【根因】原本 _prefix_v2 判斷「6 開頭 = otc_」、但 6669 緯穎是上市
  結果：6669 用 otc_ 抓不到、現價 = None
  修法：先打 tse_、c="" 的股再用 otc_ 重打（fallback 邏輯）
- 驗證：6669 現在能抓到 5130.0 現價（修正前是 None）
  5386 青雲（otc_） 521.0、5274 信驊（otc_） 18960.0 都能抓到

【修法 3：抓完後 update cache】
- 【William 反映】「手動選股有開啟 TWSE 即時股價時、抓完全部的股價應該要去 update cache 中的股價資料」
- 修法：merge 完後 save_cache(get_cache_file("price"), price_df)
- 效果：下次開啟 App 不必重抓、從 cache 讀

【pytest】test_twse_realtime_vol_otc.py（9 個守護 test）
- test_vol_換算_股轉張_保留小數
- test_vol_2548_正確值
- test_vol_大於1000張_用千分位
- test_vol_None_顯示橫線
- test_vol_NaN_顯示橫線
- test_vol_0_保留為0
- test_otc_fallback_合併6開頭上櫃股
- test_otc_fallback_6開頭上市股（如 6669）
- test_抓完後_save_cache

【驗證】
- 修正前 2548 顯示 4 張、修正後顯示 4.016 張（/1000 保留小數）
- 修正前 6669 緯穎「—」、修正後 5130.00
- 修正前 5386 青雲「—」、修正後 521.00
- 修正前 5274 信驊「—」、修正後 18960.00

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-goodinfo4+5 (retry+vol) 更新內容】2026-06-18 19:25 (William 反映)
════════════════════════════════════════════════════════════════════════════════
【William 反映 3 點】
1. 成交量還是不對：5386 顯示 0.000（vol=0）
2. 這個篩選條件為什麼沒抓到 6669
3. 還是有很多沒現價的：otc fallback 整批失敗（Connection aborted）

console：⚠️ TWSE API otc fallback 失敗：('Connection aborted.', RemoteDisconnected(...))
console：⚠️ TWSE API 失敗（批48/48、tse）：('Connection aborted.', ...)

【修法 1：retry 機制】_query_twse 加 3 次 retry
- 原本 0 retry、48 批連打可能導致後面幾批被 rate limit
- 修法：重試 3 次、間隔 1.0s / 2.0s / 3.0s 成長退避
- otc_ fallback 同一份 retry 邏輯

【修法 2：batch 間 sleep】避免連打被 rate limit
- 原本 0 sleep、48 批連打 0.15s/批 → 連續發 7.2s 請求
- 修法：batch 1 之後每批 sleep 0.5s

【修法 3：cache 現價 fillna 股價】
- 【根因】cache 的「現價」欄位可能是 NaN（之前 TWSE 抓不到）、但「股價」有值
- merge 後 fillna(現價) 拿不到舊值、結果還是 NaN
- 修法：merge 前先把 cache 現價用股價 fallback 填補

【修法 4：vol=0 顯示 "—" 不是 0.000】
- 原本 vol=0.0 顯示 "0.000"、看起來像「有資料但成交量為 0」、會誤導
- 修法：vol=0 一律顯示 "—" 表「無資料」

【6669 為什麼没被抓到】
- 6669 本益比 = 現價 5130 / EPS 49.46 = 103.7
- 本益比 ≤ 70 過濾掉是正確的
- 之前版本 cache 股價較低（可能是 5080）→ PE 102.7 仍 > 70
- 【真的要看 6669、請把「本益比 (PE) ≤」改為 110 或 150】

【pytest】test_twse_realtime_retry.py（4 個新守護 test）
- test_query_twse_retry_一次失敗後成功
- test_query_twse_三次都失敗回傳空
- test_vol_0_顯示橫線不是0_000
- test_merge前_cache_現價_fillna_股價

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-goodinfo4+5 (vol-int) 更新內容】2026-06-18 20:05 (William 反映)
════════════════════════════════════════════════════════════════════════════════
【William 反映 2 點】
1. 「你說 2548 成交量 4.016 修了、是錯的、每日總成交量不會有小數點」
2. 「今天 2548 成交量是 4020 張」

【修法：張是整數單位】
- 之前寫 vol = v / 1000.0 顯示 4.016 張、是錯的（沒這個單位）
- 「張」是整數單位、v=4,020,000 股 → vol = int(v) // 1000 = 4020 張
- 16 股 = 0 張（零股不算進張）
- 顯示：f"{int(vol):,}" → "4,020"（帶千分位整數）

【pytest】
- test_twse_realtime_vol_otc.py：4 個 vol 測試改為整數守護
- test_twse_realtime_retry.py：format_vol 改為整數
- test_twse_realtime.py：test_成交量單位是張 改為 == 5（int）

【重要教訓】
- 「張」是整數單位、不是浮點數
- 寫單位換算時要對照實際業務語意（零股另外處理）
- 我之前測試用 v=4016 剛好是 4 張 16 股、用浮點顯示 4.016 看起來合理
  → 但實際交易中「張」永遠是整數、不會有 4.016 張

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-goodinfo4+5 (vol-no-divide) 更新內容】2026-06-18 21:54 (William 反映)
════════════════════════════════════════════════════════════════════════════════
【William 反映】
- 「成交量不要除以1000應該就對了！」
- 之前版本：v=4016 → vol = int(4016/1000) = 4 張（錯）
- 正確版本：v=4016 → vol = int(4016) = 4,016 張（接近你說的 4020 張收盤量）
- → TWSE MIS API 的 v 欄位已經是「張」、不要再除以 1000

【根因】
- 我之前看 Asoul/tsrtc GitHub 文件以為 v 是「股」、所以寫 // 1000
- 但你的實際驗證（2548 收盤 4020 張、API 抓 4016）證明 v 已經是「張」
- → 不要被第三方文件誤導、要對照實際 API response

【修法】
- _fetch_twse_realtime_batch：vol = int(float(v_raw))（不再 // 1000）
- _ms_display_results：保持 f"{int(vol):,}"（顯示邏輯不變、只是輸入值變大）
- cache 內舊的「int(v/1000)」值清空、讓下次抓股價用新邏輯重抓

【pytest】
- test_twse_realtime.py：test_成交量單位是張 改為 == 5000
- test_twse_realtime.py：test_現價欄位型態 改為 == 5000
- test_twse_realtime_vol_otc.py：test_vol_換算 改為張直接顯示
- test_twse_realtime_vol_otc.py：test_vol_2548_正確值 改為 4016
- test_twse_realtime_vol_otc.py：test_otc_fallback_6開頭上市股 改為 1537

【驗證】
- 2548 v=4016 → vol=4,016 張（接近收盤量 4020 張）
- 6669 v=1537 → vol=1,537 張
- 5386 v=1162 → vol=1,162 張
- 5274 v=148 → vol=148 張

【重要教訓】
- 「不要被第三方文件誤導」：Asoul/tsrtc 說 v 是股、實際是張
- 寫單位換算時要對照實際 API response、不能只信文件
- 你是 API 真正使用者、你的觀察比文件更權威

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-goodinfo4+5 (cache-meta-fallback) 更新內容】2026-06-18 22:07 (William 反映)
════════════════════════════════════════════════════════════════════════════════
【William 反映 2 點】
1. console 顯示「Worksheet named 'meta' not found → fallback 讀舊 cache」
2. 「開始選股不用一秒就完成並沒重抓」「成交量沒值」

【根因】
- 之前舊 cache 只有 data sheet、沒有 meta sheet
- save_cache 後來才加入 meta sheet、但已經存在的 cache 檔案沒有 meta
- load_cache 嘗試讀 meta sheet → 直接 crash
- get_or_fetch 失敗 → fallback 讀舊 cache（讀 data OK）
- 但同時「TWSE 即時抓股價」觸發路徑被中斷 → 沒重抓
- → 所有成交量都是 None、顯示為 "—"

【修法】
1. load_cache：meta sheet 不存在時 fallback 回傳今天日期（不 crash）
2. _is_cache_fresh：meta sheet 不存在時 return True（視為剛抓的、不觸發重抓）
3. cache/price.xlsx：手動補上 meta sheet（下次 save_cache 會自動寫入）
4. fileheader：版本號升級為 (2026-06-18 22:07)

【pytest】test_cache_meta_sheet_fallback.py（4 個新守護 test）
- test_load_cache_沒有meta_sheet_不crash
- test_load_cache_有meta_sheet_正常讀取
- test_is_cache_fresh_沒有meta_回傳True
- test_save_cache_同時寫data和meta

【驗證】pytest 217/217 全綠（213 → 217）

【重要教訓】
- 「新版本加新功能、要保留舊檔案容錯」
- 「Tkinter Treeview 會把千分位逗號轉成小數點」：locale=zh_TW.UTF-8 時，
  Treeview values 傳 "4,016" 會顯示成 "4.016"（逗號被當成歐洲小數點）
  → 解決：vol 是整數、不需要千分位、直接 str(int(vol))
  → 如果未來需要千分位、Treeview cell 必須避免字串含逗號

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-goodinfo4+5 (rate-mode) 更新內容】2026-06-18 23:59 (William 要求)
════════════════════════════════════════════════════════════════════════════════
【William 要求】2026-06-18 23:57
- 「跑到 14xx 筆時開始有 error message 跟剛才沒什麼差別」
- TWSE 全批失敗（rate limit）、batch 10 也失敗、耗時 123 秒

【修法】新增 TWSE 速率模式 UI 切換（🚀 快速 / 🐌 緩慢）
- 🚀 快速：batch delay 0.3s，省時但逾 1,400 批可能被 TWSE 限制
- 🐌 緩慢：batch delay 5.0s，確保完成（2376 檔約需 20 分鐘）
- UI：在「TWSE 即時股價」checkbox 下方新增 Radiobutton 切換

【程式碼改動】
- _fetch_twse_realtime_batch 加 slow_mode 參數
- batch sleep: if slow_mode → sleep(5.0) else → sleep(0.3)
- UI 新增 _ms_twse_slow_mode BooleanVar + Radiobutton × 2
- _ms_twse_rate_mode_changed() 回撥更新狀態列

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-goodinfo4+5 (batch-10+treeview-comma) 更新內容】2026-06-18 23:52
════════════════════════════════════════════════════════════════════════════════
【問題】William 2026-06-18 21:54 反映：成交量顯示 4.016（小數點）
【根因】Tkinter Treeview + locale=zh_TW.UTF-8 → 逗號被當成歐洲數字小數分隔符
  → 傳入 values=("4,016") 會被渲染成 "4.016"（句點）
【修法】vol_str = str(int(vol))（不做千分位格式化）
【附帶】_TWSE_REALTIME_BATCH_SIZE 50→10（避免 rate limit）

【重要教訓】
- 「Tkinter Treeview 格式化要測試 locale 情境」
- 「系統 locale 會改變 Tkinter 數字渲染行為」：save_cache 後加 meta sheet
  → 但舊 cache 沒 meta → load_cache crash → 整條 get_or_fetch 中斷
  → 解法：load_cache 容錯讀不到 meta 時用 today 日期 fallback
- 「忘記更新 fileheader 是新手錯誤」：每次改完要更新版本號
  → pre-commit hook 會自動更新「最後更新」、但「版本號」要手動
  → 我這次 22:07 改了 4 處 code、忘了更新 fileheader、被 William 抓包
  - test_排序_None_排最後
- test_ms_no_stock_yield_vol_display.py 重寫（拿掉舊的盤中/收盤後 test）

════════════════════════════════════════════════════════════════════════════════

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-twser 更新內容】2026-06-18 10:05 (William 指示)
════════════════════════════════════════════════════════════════════════════════
【背景】William 確認 TWSE 即時資訊延遲只有 15-20 秒（不是 15 分鐘），且有免費 JSON API 可用。

【重大改版：FinMind 股價 → TWSE 即時 API】
- 新增 _fetch_twse_realtime_batch()：完全用 TWSE 即時 API 取代 FinMind 股價
  - URL: https://mis.twse.com.tw/stock/api/getStockInfo.jsp
  - 上市: tse_XXXX.tw，上櫃: otc_XXXX.tw
  - 主力欄位: z=現價，o/h/l/y=開高低昨
  - 預開盤（9:00-9:30）z="-" → fallback 到 o（開盤拍賣價）
  - 完全免費，無額度限制，可無限次呼叫
- _ms_run_selection 的「即時抓股價」checkbox 改走 TWSE API
  - 2376 檔分批（50 檔/批）約 20-30 秒完成
  - UI 動態顯示「🔄 TWSE 即時股價抓取中... X/Y (Z%)」
- FinMind 額度完全解放，專注留給股利補抓（crontab每日 15:00）
- checkbox label 改：「🔄 TWSE 即時股價（走 TWSE 免費 API，盤中 15-20 秒延遲）」

【pytest】test_twse_realtime.py 新增（6 個守護 test）

════════════════════════════════════════════════════════════════════════════════

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-goodinfo4 更新內容】2026-06-17 21:04 (William 反映)
════════════════════════════════════════════════════════════════════════════════
【William 3 點反映】
1. 選股結果殖利率都是破折號（0.0 被當 None）
2. 選股現價是昨日收盤（不是 6/17 盤中即時）
3. 持倉總攬算法確認 OK（未實現 + net_realized - current_tax）

【修法 1：殖利率 0.0 不再被當 None】
- 【原本】_ms_display_results 7 個欄位用「if val and ...」truthy 判斷
  → 0.0 是 falsy → 被當 None 顯示 '—'
  → 5386 現金殖利率 0.3 看起來像 0.0 一樣是破折號
- 【修法】新增 _fmt_float() module-level helper
  → 用 pd.isna(v) 判斷（None/NaN 才視為空）
  → 0.0 顯示 '0.00'、0.3 顯示 '0.30'、None 顯示 '—'
- 修法 1 是「顯示問題」、DB 內 cash_yield_pct 本來就有 0.0 值

【修法 2：盤中現價不再取昨日收盤】
- 【原本】_fetch_finmind_prices_batch 用 data[-1] 拿「最後一筆」
  → 盤中時 data[-1] 的 date 是「今日」但 close 是盤中即時
  → 收盤後 data[-1] 的 date 是「今日」但 close 是今日收盤
  → 週六 週日 / 國定假日 data[-1] 的 date 是「上週五」、不是「昨日」
  → 原本不會誤判、但若 TWSE 資料型態是 tick 會出問題
- 【修法】新增 _pick_latest_price_row() helper
  → 從後往前找 date == today 的那筆
  → 找不到（週末）→ 取 data[-1]（上週五收盤、合理 fallback）
- 同時順手拿掉股利 finmind 抓取（設 skip_remote=True）
  → DB 內已有 goodinfo 寫的 1,710 筆股利資料、finmind 不再需要
  → 歷史資料來自 goodinfo、現價來自 TWSE+TPEx+finmind（盤中）

【修法 3：拿掉股利 finmind 抓取】
- 【原本】_run_manual_selection 內 _fetch_finmind_dividend(all_codes)
  → DB 沒的會去抓 finmind、finmind 額度限制（每小時 300 次）出問題
- 【修法】改成 _fetch_finmind_dividend(all_codes, skip_remote=True)
  → DB 沒的永遠不抓、殖利率直接 None → 跟未配息一樣顯示
  → 全部 1,710 檔股利從 goodinfo DB 來、不依賴 finmind

【pytest】163 個 test 全部通過 ✅
- test_goodinfo_yield_rate.py：+ 2 個 test（殖利率 0.0 守護）
- test_pick_latest_price_row.py：+ 6 個 test（新 helper 守護）
- 其他既有 test 全部保留過

【使用】
- App 重啟生效
- 「即時抓股價」按鈕的 finmind 股價抓取已加 date 判斷、避開昨日收盤 bug
- 選股結果不會再顯示「殖利率破折號」、會顯示 0.00
- 持倉總攬的 599,501 數字不變（算法原本就對、已驗證）

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-goodinfo3 更新內容】2026-06-17 12:03
════════════════════════════════════════════════════════════════════════════════
【William 三點修正要求】
1. 拿掉 10Y 平均殖利率欄位（不需要了）
2. 舊邏輯：「cash=0 → continue 跳過 → 殖利率 None」 是錯的
   ex: 5386 cash=0 但 goodinfo cash_yield=0.76% → 應用 goodinfo 值
3. 「殖利率應該不用任何計算直接用才對」→ 拿掉所有 fallback

【修法】
1. 拿掉 10Y 平均殖利率欄位
   - Treeview 從 16 欄變 15 欄
   - sort_by 拿掉 _sort_avg_yld
   - final_cols 拿掉 「歷史平均現金殖利率(%)」
2. 拿掉 cash/現價、cash/ex_date_close、現價所有 fallback
   - 殖利率 100% 直接用 goodinfo cash_yield_pct / share_yield_pct
   - cash=0 但 goodinfo 有殖利率值 → 殖利率直接用 goodinfo 值
   - goodinfo 殖利率 = 0（未配息）→ 顯示 0%
   - goodinfo 殖利率 = None → 殖利率 None
3. 順手修 import_dividend 合併 bug：
   - 【原本】`{**cash_agg, **share_agg}` 用 dict unpack、後者覆蓋前者
     對 cash 跟 share 都有資料的股票（ex: 5386 2018）cash 被洗成 0
     受影響：1,710 筆 / 646 檔
   - 【修法】明確取 cash_agg.cash + share_agg.stock
4. 重跑 import_dividend + import_yield_rate、修復 5386 等 646 檔 cash 資料
5. 修正後驗證：
   - 3231 緯創：今 5.5/3.48%、去 3.799/3.3% ✅
   - 5386 捷敏：今 6.5/0.3%、去 1.968/0.76% ✅（cash=0 但殖利率照顯示）

【pytest】155 個 test 全部通過 ✅
- test_dividend_year_mapping.py：更新 3 個 test 預期（殖利率用 goodinfo）
- test_ex_date_yield.py：更新 3 個 test 預期（殖利率用 goodinfo）
- test_fetch_dividend_update.py：更新 1 個 test 預期
- test_ms_display_div_columns.py：更新 1 個 test 預期
- test_goodinfo_yield_rate.py：重寫為 9 個（V0.9.5-goodinfo3 行為）

【使用】
- 重跑 import_dividend（已自動跑過、5386 等 646 檔 cash 修對了）
- 重跑 import_yield_rate（已自動跑過）
- App 重啟即可生效

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-goodinfo2 更新內容】2026-06-17 11:10
════════════════════════════════════════════════════════════════════════════════
【手動選股殖利率改用 goodinfo 來源】（William 2026-06-17 11:10 反映）
- 問題：原本殖利率算法 = 現金股利 / 現價 → 只反映「最近一次配息 vs 現價」
  偏差大、不適合做「歷史殖利率」参考
- 修正：優先用 goodinfo 提供的「該年現金/股票殖利率」（%）
  * goodinfo 用「除息日前 5 日均價」算 → 不被單日股價波動干擾
  * 涵蓋全年多次配息、不會只算第一次除息
- 【DB schema 擴充】
  * dividend_history 新增 cash_yield_pct / share_yield_pct 兩欄
  * ALTER TABLE 自動 migration（既有 DB 不需手動處理）
- 【import script 擴充】scripts/import_goodinfo_history.py
  * 新增 import_yield_rate() 函式、讀 6 個 .xls 檔
    - P50U/P20-50/P20L_DividendRate.xls（現金殖利率，2017~2026）
    - P50U/P20-50/P20L_ShareRate.xls（股票殖利率，2017~2026）
  * 新增 --only yield 選項
  * 寫入結果：UPDATE 15,394 筆、現金殖利率涵蓋 2,209 檔
  * 同一 stock_id + year 跨三個價位帶「取平均」（不像股利加總）
  * 只 UPDATE cash_yield_pct / share_yield_pct、不動 cash/stock/ex_date
- 【演算法優先順序】_run_manual_selection
  * 今年現金殖利率：goodinfo → cash/現價 fallback
  * 去年現金殖利率：goodinfo → cash/ex_date_close → cash/現價 fallback
  * 重要：goodinfo 殖利率 = 0 代表「該年未配息」→ 不誤判為高殖利率
- 【新增 3 個欄位】
  * 今年股票殖利率(%) / 去年股票殖利率(%) — goodinfo 提供
  * 歷史平均現金殖利率(%) — 10 年平均、解決「平均價算歷史殖利率偏差大」問題
  * 排序優先用「歷史平均現金殖利率」(10Y) → 不被單一年度高殖利率股票誤導
- 【UI】
  * 手動選股 Treeview 新增「今股票殖%」、「去年股票殖%」、「10Y平均殖%」3 欄
  * Treeview 現共 16 欄（原本 13 欄）
- 【pytest】156 個 test 全部通過 ✅（v0.9.5-goodinfo 146 個 + 新增 10 個）
  * test_goodinfo_yield_rate.py（10 個新）
    - 殖利率優先用 goodinfo（今年/去年）
    - fallback 到 cash/現價、cash/ex_date_close、現價
    - 股票殖利率 goodinfo 提供
    - 歷史平均殖利率 = goodinfo 各年算術平均
    - 缺資料 / 完全無資料 = None
    - 排序優先用歷史平均

【未來修】finmind 跟 goodinfo year 語意不一致
- finmind year=2025 = 「2025 盈餘的股利」（在 2026 除息）
- goodinfo year=2025 = 「2025 除息」
- 同一 DB row 兩種語意混合（例如 2408 2025：finmind cash=1.347、goodinfo cash_yield=0.0）
- 建議：_fetch_finmind_dividend 寫入 DB 時 year +1（變 payment year）
- 本版先不動、要覍察看其他股票是否也有同樣問題

════════════════════════════════════════════════════════════════════════════════
【v0.9.4 更新內容】2026-06-11
════════════════════════════════════════════════════════════════════════════════
Phase 2.3 — 買賣記錄 5 項更新：
1. 股票股利配發（price=0）支援
2. 萬年曆日期挑選（_CalendarDialog，純 Tkinter 原生）
3. 成本加計手續費 + 證交稅（Treeview 新增「證交稅」欄）
4. 策略參數設定支援券商折扣（broker_discount，預設 1.0）
5. 交易明細可編輯（✏️編輯，action/shares/price/date 皆可改）

════════════════════════════════════════════════════════════════════════════════
【v0.9.3 緊急修正內容】2026-06-08
════════════════════════════════════════════════════════════════════════════════

【問題描述】
- EPSYoY_raw 欄位完全為空，導致 EPSYoY_顯示(%) 全部為 0
- Score 欄位計算異常，出現 -1e+18 負無限大值
- PE 欄位出現 inf 無限值未正確處理
- 簡易評分門檻過濾邏輯錯誤，導致所有個股被排除
- Top10 選股結果全部為 ETF 而非正常個股

【修正內容】
1. 修正 fetch_eps_latest() 函數
   - 改用「去年同期 EPS 差值」計算 EPS YoY
   - 新增無限值處理 (inf/-inf → pd.NA)

2. 修正 calculate_simple_score() 函數
   - 新增 PE 和 EPSYoY_raw 的無限值處理
   - 修正門檻過濾邏輯（改用 -998 判斷閾值啟用狀態）
   - 未通過門檻的 Score 改為 pd.NA 而非 -1e+18

3. 修正 calculate_multi_factor_score() 函數
   - 新增營收YoY和EPSYoY的無限值處理

4. 確認 DEFAULT_CONFIG 中門檻預設值正確
   - simple_min_rev_yoy: -999.0
   - simple_min_eps_yoy: -999.0
   - simple_min_eps: -999.0
   - simple_max_pe: 999.0

════════════════════════════════════════════════════════════════════════════════
【修正後執行步驟】
════════════════════════════════════════════════════════════════════════════════

1. 儲存本檔案
2. 刪除 cache/ 目錄（強制重新下載資料）
3. 重新執行 python StockTool.py
4. 確認 GUI 中簡易評分門檻皆為 -999 / 999
5. 按下「執行策略」驗證結果

════════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

# ==========================================================
# Version 常數（V0.9.5-goodinfo4 設定）
# ==========================================================
# 【v1.1 重構】VERSION 已搬到 stocktool.config
# ==========================================================


import io
import os
import json
import time
import queue
import threading
import warnings
from dataclasses import dataclass, asdict, field
from datetime import datetime, date, timedelta
from typing import Dict, Any, Tuple, Optional, List
from itertools import product

import pandas as pd
import numpy as np
import requests

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))

from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.formatting.rule import CellIsRule

# V0.9.4 買賣記錄模組
from portfolio import PortfolioDB, Transaction, DEFAULT_PORTFOLIO_DB

warnings.filterwarnings("ignore")

# ==========================================================
# 0) Config 檔案路徑與預設設定
# ==========================================================

# ==========================================================
# v1.1 重構：Config 從 stocktool.config 統一管理
# ==========================================================
from stocktool.config import (
    CONFIG_FILE,
    DEFAULT_CONFIG,
    HISTORY_DIR,
    _HALF_DAY_DATES,
    load_config,
    save_config,
    StrategyConfig,
    GuiLogger,
    build_session,
    find_col,
    _is_market_hours,
    VERSION,
)
from stocktool.cache import (
    get_cache_file,
    save_cache,
    load_cache,
    get_or_fetch,
    _is_price_cache_valid,
)
from stocktool.database import (
    DIV_HISTORY_SCHEMA,
    DIV_HISTORY_MIGRATIONS,
    EPS_HISTORY_SCHEMA,
    ETF_HISTORY_SCHEMA,
    _init_div_history_db,
    _init_eps_history_db,
    _init_etf_history_db,
    _save_etf_holding_snapshot,
    _query_etf_holdings_by_date,
    _query_latest_two_dates,
    _compute_etf_changes,
    _upsert_div_history,
    _query_div_history,
    _query_div_history_with_fetched,
    _div_history_stats,
    _upsert_eps_history,
    _query_eps_history,
    _eps_history_stats,
)
from stocktool.fetch_market import (
    to_num_series,
    month_starts_back,
    roc_to_ad,
    _load_goodinfo_12q_epsrate,
    _fetch_market_stock_list,
    _fetch_twse_realtime_batch,
    _pick_latest_price_row,
    _finmind_get,
    _parse_roc_year,
    _fetch_finmind_prices_batch,
    _fmt_float,
    _fetch_finmind_dividend,
    _background_fetch_all_dividend,
    _update_ex_date_close,
    _fetch_ex_date_close,
    fetch_csv_requests,
    fetch_prices,
    fetch_revenue_latest,
    fetch_eps_latest,
    safe_parse_json,
    fetch_twse_stock_day_month,
    fetch_twse_history,
    _MS_PROGRESS,
)
from stocktool.etf import (
    fetch_active_etf_list,
    fetch_etf_top10_holdings,
    build_etf_holdings_table,
    aggregate_etf_holdings,
    ETF_ACTIVELIST_URL,
    ETFINFO_ETF_URL,
    _display_width,
)
from stocktool.scoring import (
    _run_manual_selection,
    calculate_multi_factor_score,
    calculate_enhanced_score,
    calculate_simple_score,
)
from stocktool.technical import (
    calc_enhanced_tech_indicators,
    run_tech,
)
from stocktool.backtest import (
    event_exit_return,
    max_losing_streak,
    profit_factor,
    annualize_sharpe,
    annualize_sortino,
    signal_level_backtest_event,
    build_gate_map,
    portfolio_backtest_topk_event,
    performance_by_year,
    run_walk_forward,
    get_codes_for_period,
    quick_backtest_for_period,
)
from stocktool.export_excel import (
    load_stock_list_from_excel,
    get_history_file,
    init_stock_history,
    update_stock_history,
    get_stock_history,
    autosize_columns,
    style_header,
    write_explanation,
    highlight_true,
)
from stocktool.pipeline import (
    _apply_strong_filter,
    _run_selection_only,
    run_pipeline,
)
from stocktool.gui.calendar import _CalendarDialog











class StrategyGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"StockTool {VERSION} (Multi-Factor + Top10 Backtest + Portfolio + ETF + goodinfo)")

        self.log_queue = queue.Queue()
        self.logger = GuiLogger(self.log_queue)

        saved_config = load_config()
        self.cfg = StrategyConfig()
        self.cfg.update_from_dict(saved_config)

        # V0.9.4 phase2.3: 買賣記錄（broker_discount 從 StrategyConfig 讀）
        self.portfolio = PortfolioDB(DEFAULT_PORTFOLIO_DB,
                                    broker_discount=self.cfg.broker_discount)
        # 記憶體中現價（stock_id → price）
        self._current_prices: Dict[str, float] = {}
        # 記憶體中股票名稱（stock_id → name，fetch 回來時順便快取）
        self._current_names: Dict[str, str] = {}

        self._build_ui()
        self._poll_log_queue()
        self._load_config_to_ui()

        # V0.9.5: 啟動時背景重抓股價（若 cache 過期就重抓、今天就跳過）
        # 用 flag 避免和「手動重抓股價」按鈕重複觸發
        self._bg_price_fetching = False
        self._price_last_update: Optional[datetime] = None
        self.after(800, self._startup_bg_fetch_price)

        # V0.9.5+ Phase 8：買賣記錄 Tab 開盤 30 秒 refresh 持倉現價的 job id
        self._portfolio_refresh_job_id = None

        # 【V0.9.5-etf】ETF Tab 背景自動抓取 flag（防止重複）
        self._etf_fetching = False
        # ETF Tab 背景自動抓（延後 2.5 秒、讙 manual_select 跟 price fetch 先跑）
        self.after(2500, self._etf_auto_startup_fetch)

    def _build_ui(self):
        self.geometry("1280x720")

        # 【v1.1.1 HOTFIX #5】2026-06-24 22:10 William 反映：App 啟動時 crash
        # _init_tab_presets_on_startup() 會讀 self._preset_vars / self.vars /
        # _apply_tab_values(tab_key, preset) 讀 self.vars.get(k)
        # 但 _add_preset_bar() 和 self.vars = {} 都在後面才 call/初始化。
        # 原設計靠內部「if not hasattr」defensive check 負責初始化，
        # 但 _init 早於 _add 就會 crash。
        # 修法：_build_ui 一進來就預設初始化 _preset_vars / _preset_combos / vars
        #      （後面 _add_preset_bar 的 hasattr check 仍是安全網）
        self._preset_vars = {}
        self._preset_combos = {}
        self.vars = {}

        # V0.9.4 Tab 化：notebook 包兩個分頁（不改 V0.9.3 既有 widget 結構）
        # 2026-06-20 V0.9.5-tab-split-fix3：先建 top_frame 並 pack、
        # notebook 以 top_frame 為 master 直接建構（pack(in_=...) 不會 reparent）
        # V0.9.5-tab-split-fix3：用 grid 切上下兩列、top_frame expand、console 固定 180
        self.grid_rowconfigure(0, weight=1)  # 上（notebook）拿剩餘空間
        self.grid_rowconfigure(1, weight=0)  # 下（console）固定 180px
        self.grid_columnconfigure(0, weight=1)
        self._top_frame = ttk.Frame(self)
        self._top_frame.grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 4))
        self.notebook = ttk.Notebook(self._top_frame)

        # 【V0.9.5-tab-split-phase3-C】tab 順序重排（William 09:02 要求）
        # 新順序：系統選股 → 主動式 ETF → 手動選股 → 買賣記錄 → 回測模擬

        # Tab 1：系統選股
        self.select_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.select_tab, text="📊 系統選股")

        # Tab 2：主動式 ETF（從 Tab 5 拉到 Tab 2）
        self.etf_tab = ttk.Frame(self.notebook)
        self._init_etf_history()
        self.notebook.add(self.etf_tab, text="📊 主動式 ETF")
        self._build_etf_tab(self.etf_tab)

        # Tab 3：手動選股（從 Tab 4 拉到 Tab 3）
        self.manual_select_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.manual_select_tab, text="🔍 手動選股")
        self._build_manual_select_tab(self.manual_select_tab)

        # Tab 4：買賣記錄（從 Tab 3 拉到 Tab 4）
        self.portfolio_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.portfolio_tab, text="📒 買賣記錄")
        self._build_portfolio_tab(self.portfolio_tab)

        # Fix14: 啟動時自動載入每個 tab 上次的 Preset
        self._init_tab_presets_on_startup()

        # Tab 5：回測模擬（從 Tab 2 拉到 Tab 5）
        self.backtest_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.backtest_tab, text="🧪 回測模擬")
        self._build_backtest_tab(self.backtest_tab)

        # 綁定 Tab 切換 → 切到買賣記錄時自動 refresh
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # V0.9.5-tab-split Phase 3：兩個 tab 用 _build_tab_layout（左 params + 右 results）
        # 【V0.9.5-tab-split-phase3-C】改回傳 (left, right_frame, tree)、select_tab 加 export 按鈕
        left, self.select_right, self.select_tree = self._build_tab_layout(self.select_tab)
        bt_left, self.backtest_right, self.backtest_tree = self._build_tab_layout(self.backtest_tab)
        self._bt_left = bt_left

        # 【V0.9.5-tab-split-phase3-C】「💾 匯出股票清單」按鈕（select_tab）
        # 放在 right_top 內、跟 title 同一行
        self.export_select_btn = ttk.Button(
            self.select_right.winfo_children()[0],  # right_top
            text="💾 匯出股票清單",
            command=self._export_select_results_excel,
            state="disabled",
        )
        self.export_select_btn.pack(side="right")
        self._last_select_df = None  # 記住最近一次選股結果

        ttk.Label(left, text="📊 系統選股參數", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 8))

        self.vars: Dict[str, tk.Variable] = {}

        # Fix14: 系統選股 Preset bar
        self._add_preset_bar(left, "system_select")

        # 1. 基本參數
        basic_frame = ttk.LabelFrame(left, text="📊 基本參數", padding=5)
        basic_frame.pack(fill="x", pady=5)
        self._add_entry(basic_frame, "選股檔數 (TopN)", "top_n_for_tech", tk.IntVar, self.cfg.top_n_for_tech)
        self._add_entry(basic_frame, "歷史月數", "history_months", tk.IntVar, self.cfg.history_months)
        self._add_entry(basic_frame, "回測月數", "tech_months", tk.IntVar, self.cfg.tech_months)
        # 持股檔數已移至回測模擬 tab

        # 2. 評分系統
        score_frame = ttk.LabelFrame(left, text="⭐ 評分系統", padding=5)
        score_frame.pack(fill="x", pady=5)

        self.use_enhanced_score_var = tk.BooleanVar(value=self.cfg.use_enhanced_score)
        ttk.Radiobutton(score_frame, text="多因子評分 (動能+成長)", variable=self.use_enhanced_score_var, value=True).pack(anchor="w")

        # 多因子評分的設定（與 radio button 同一個視覺區塊）
        weight_frame = ttk.Frame(score_frame)
        weight_frame.pack(fill="x", padx=(20, 0), pady=(0, 5))
        ttk.Label(weight_frame, text="因子權重:", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self._add_entry(weight_frame, "動能1M", "factor_weight_mom1", tk.DoubleVar, self.cfg.factor_weight_mom1)
        self._add_entry(weight_frame, "動能3M", "factor_weight_mom3", tk.DoubleVar, self.cfg.factor_weight_mom3)
        self._add_entry(weight_frame, "動能6M", "factor_weight_mom6", tk.DoubleVar, self.cfg.factor_weight_mom6)
        self._add_entry(weight_frame, "營收YoY", "factor_weight_rev", tk.DoubleVar, self.cfg.factor_weight_rev)
        self._add_entry(weight_frame, "EPS YoY", "factor_weight_eps", tk.DoubleVar, self.cfg.factor_weight_eps)

        ttk.Radiobutton(score_frame, text="簡易評分 (可調權重+門檻)", variable=self.use_enhanced_score_var, value=False).pack(anchor="w")

        # 簡易評分的設定（與 radio button 同一個視覺區塊）
        self.adv_btn = ttk.Button(score_frame, text="⚙ 簡易評分進階設定", command=self._open_simple_score_settings)
        self.adv_btn.pack(fill="x", padx=(20, 0), pady=(0, 5))

        # Fix15 (2026-06-21): 回測模擬 Preset bar 移到最頂端
        self._add_preset_bar(bt_left, "backtest")

        # 3. 技術指標（V0.9.5-tab-split Phase 2：移到回測模擬 tab）
        tech_frame = ttk.LabelFrame(bt_left, text="📈 技術指標 (強化版)", padding=5)
        tech_frame.pack(fill="x", pady=5)

        self.mtf_var = tk.BooleanVar(value=self.cfg.use_mtf_confirmation)
        ttk.Checkbutton(tech_frame, text="多時間框架確認 (週線/月線)", variable=self.mtf_var).pack(anchor="w")

        self.divergence_var = tk.BooleanVar(value=self.cfg.use_divergence_detection)
        ttk.Checkbutton(tech_frame, text="RSI 背離檢測", variable=self.divergence_var).pack(anchor="w")

        self._add_entry(tech_frame, "成交量爆發倍數", "volume_surge_multiplier", tk.DoubleVar,
                        self.cfg.volume_surge_multiplier)
        self._add_entry(tech_frame, "RSI 超賣門檻", "rsi_oversold", tk.IntVar, self.cfg.rsi_oversold)
        self._add_entry(tech_frame, "MA20 容忍度 (%)", "ma20_tolerance", tk.DoubleVar, self.cfg.ma20_tolerance * 100)

        self.volume_filter_var = tk.BooleanVar(value=self.cfg.require_volume_filter)
        ttk.Checkbutton(tech_frame, text="需要成交量過濾", variable=self.volume_filter_var).pack(anchor="w")

        # ✅ 進階技術參數
        ttk.Separator(tech_frame, orient="horizontal").pack(fill="x", pady=5)
        ttk.Label(tech_frame, text="--- 進階技術參數 ---", font=("Segoe UI", 9, "bold")).pack(anchor="w")

        self.trend_filter_var = tk.BooleanVar(value=self.cfg.require_trend_filter)
        ttk.Checkbutton(tech_frame, text="需要趨勢過濾 (站穩MA20)", variable=self.trend_filter_var).pack(anchor="w")

        self.use_aggressive_signal_var = tk.BooleanVar(value=self.cfg.use_aggressive_signal)
        ttk.Checkbutton(tech_frame, text="使用積極轉強訊號 (RSI門檻較高)",
                        variable=self.use_aggressive_signal_var).pack(anchor="w")

        self._add_entry(tech_frame, "RSI 轉強門檻 (積極)", "rsi_aggressive", tk.IntVar, self.cfg.rsi_aggressive)
        self._add_entry(tech_frame, "RSI 轉強門檻 (保守)", "rsi_recover", tk.IntVar, self.cfg.rsi_recover)
        self._add_entry(tech_frame, "超跌檢查天數", "oversold_lookback", tk.IntVar, self.cfg.oversold_lookback)
        self._add_entry(tech_frame, "MA20 斜率計算天數", "ma_slope_days", tk.IntVar, self.cfg.ma_slope_days)

        # 4. 出場參數（V0.9.5-tab-split Phase 2：移到回測模擬 tab）
        exit_frame = ttk.LabelFrame(bt_left, text="🚪 出場參數", padding=5)
        exit_frame.pack(fill="x", pady=5)
        self._add_entry(exit_frame, "停損 (%)", "stop_loss", tk.DoubleVar, self.cfg.stop_loss * 100)
        self._add_entry(exit_frame, "停利 (%)", "take_profit", tk.DoubleVar, self.cfg.take_profit * 100)
        self._add_entry(exit_frame, "RSI 出場", "exit_rsi", tk.IntVar, self.cfg.exit_rsi)
        self._add_entry(exit_frame, "最大持有天數", "hold_days", tk.IntVar, self.cfg.hold_days)
        self._add_entry(exit_frame, "交易成本 (%)", "roundtrip_cost_pct", tk.DoubleVar, self.cfg.roundtrip_cost_pct * 100)

        # 5. Walk-forward 分析（V0.9.5-tab-split Phase 2：移到回測模擬 tab）
        wf_frame = ttk.LabelFrame(bt_left, text="🔄 Walk-forward 分析", padding=5)
        wf_frame.pack(fill="x", pady=5)

        self.wf_enabled_var = tk.BooleanVar(value=self.cfg.wf_enabled)
        ttk.Checkbutton(wf_frame, text="啟用 Walk-forward 分析", variable=self.wf_enabled_var).pack(anchor="w")

        wf_params_frame = ttk.Frame(wf_frame)
        wf_params_frame.pack(fill="x", pady=5)
        self._add_entry(wf_params_frame, "訓練期 (年)", "wf_train_years", tk.IntVar, self.cfg.wf_train_years)
        self._add_entry(wf_params_frame, "測試期 (年)", "wf_test_years", tk.IntVar, self.cfg.wf_test_years)
        self._add_entry(wf_params_frame, "步進 (年)", "wf_step_years", tk.IntVar, self.cfg.wf_step_years)

        # 6. 選股來源（V0.9.5-tab-split Phase 2：移到回測模擬 tab）
        # V0.9.5-tab-split-phase3-C Fix3：回測永遠從 Excel 讀，移除 toggle
        source_frame = ttk.LabelFrame(bt_left, text="📁 選股來源（永遠從 Excel 讀取）", padding=5)
        source_frame.pack(fill="x", pady=5)

        # Excel 檔案：entry + 瀏覽按鈕（Fix3 新增）
        file_row = ttk.Frame(source_frame)
        file_row.pack(fill="x", pady=2)
        ttk.Label(file_row, text="Excel 檔案：").pack(side="left")
        self.excel_file_var = tk.StringVar(value=self.cfg.excel_stock_file)
        file_entry = ttk.Entry(file_row, textvariable=self.excel_file_var)
        file_entry.pack(side="left", fill="x", padx=(2, 0))

        def _browse_excel():
            f = filedialog.askopenfilename(
                title="選擇 Excel 股票清單",
                filetypes=[("Excel", "*.xlsx"), ("所有檔案", "*.*")],
                initialdir=SOURCE_DIR,
            )
            if f:
                self.excel_file_var.set(f)
                self.cfg.excel_stock_file = f

        ttk.Button(file_row, text=" 瀏覽 ", command=_browse_excel).pack(side="left", padx=(4, 0))

        # ✅ v0.9.4 Excel 清單強制買點模式
        self.excel_force_buy_var = tk.BooleanVar(value=self.cfg.excel_force_buy)
        ttk.Checkbutton(
            source_frame,
            text="📊 Excel 清單強制買點模式\n   （跳過技術買點過濾）",
            variable=self.excel_force_buy_var
        ).pack(anchor="w", pady=(5, 0))
        ttk.Label(source_frame, text="  ※ 使用 Excel 股票清單 + 不經過買點過濾（強制滿倉）", foreground="gray").pack(anchor="w")

        # 7. 回測參數（Fix5：持股檔數+總投入資金移至此）
        bt_params_frame = ttk.LabelFrame(bt_left, text="📊 回測參數", padding=5)
        bt_params_frame.pack(fill="x", pady=5)
        self._add_entry(bt_params_frame, "同時持股檔數", "topk", tk.IntVar, self.cfg.topk)
        self._add_entry(bt_params_frame, "總投入資金 (元)", "capital", tk.DoubleVar, self.cfg.capital)

        # 7. 強勢股過濾（系統選股 tab）
        strong_frame = ttk.LabelFrame(left, text="💪 強勢股過濾", padding=5)
        strong_frame.pack(fill="x", pady=5)
        self._add_entry(strong_frame, "最低營收YoY (%)", "strong_revenue_yoy", tk.DoubleVar, self.cfg.strong_revenue_yoy)
        self._add_entry(strong_frame, "最高本益比", "strong_pe_max", tk.DoubleVar, self.cfg.strong_pe_max)
        self._add_entry(strong_frame, "最低股價", "strong_price_min", tk.DoubleVar, self.cfg.strong_price_min)

        # 8. 按鈕區（V0.9.5-tab-split Phase 2：拆兩份、各自放自己 tab 底部）
        # 系統選股 tab 的按鈕
        btn_frame = ttk.Frame(left)
        btn_frame.pack(fill="x", pady=10)

        self.run_btn = ttk.Button(btn_frame, text="▶ 執行系統選股", command=self._on_run)
        self.run_btn.pack(fill="x", pady=2)

        # Fix15 (2026-06-21): 移除「💾 儲存設定」「🔄 載入預設」按鈕
        # Preset bar 已取代這兩個功能（手動選股也是這樣）
        self.clear_btn = ttk.Button(btn_frame, text="🗑 清除控制台", command=self._on_clear_console)
        self.clear_btn.pack(fill="x", pady=2)

        # 回測模擬 tab 的按鈕（階段 C 實作執行回測、目前先 disabled）
        bt_btn_frame = ttk.Frame(bt_left)
        bt_btn_frame.pack(fill="x", pady=10)

        ttk.Label(bt_btn_frame, text="選擇 Excel 檔案後，直接按「執行回測模擬」", foreground="gray").pack(fill="x", pady=2)
        self.bt_run_btn = ttk.Button(bt_btn_frame, text="▶ 執行回測模擬", command=self._on_bt_run, state="normal")
        self.bt_run_btn.pack(fill="x", pady=2)

        # V0.9.5-tab-split：console 已改為全域（在 _build_ui 結尾建構）
        # 原本這裡有 title_row + tip label 在 right 內、已廢除

        # V0.9.5-tab-split-fix3：notebook 已建好、只要確保 layout 完整
        self.notebook.pack(fill="both", expand=True)

        # 全域 console 放下（grid row=1、固定 180px）
        console_container = ttk.LabelFrame(self, text="📝 執行記錄 (Program Console) — 全域", padding=2)
        console_container.grid(row=1, column=0, sticky="ew", padx=8, pady=(4, 8))
        console_container.grid_propagate(False)
        console_container.configure(height=180)
        console_frame = ttk.Frame(console_container)
        console_frame.pack(fill="both", expand=True)
        self.console = tk.Text(console_frame, height=10, wrap="word")
        console_scrollbar_y = ttk.Scrollbar(console_frame, orient="vertical", command=self.console.yview)
        console_scrollbar_x = ttk.Scrollbar(console_frame, orient="horizontal", command=self.console.xview)
        self.console.configure(yscrollcommand=console_scrollbar_y.set, xscrollcommand=console_scrollbar_x.set)
        self.console.pack(side="left", fill="both", expand=True)
        console_scrollbar_y.pack(side="right", fill="y")
        console_scrollbar_x.pack(side="bottom", fill="x")

    def _build_tab_layout(self, parent):
        """【V0.9.5-tab-split Phase 3】建一個標準的「左 params + 右 results」tab layout

        【V0.9.5-tab-split-phase3-C】改回傳值多一個 right_frame
        - 原本 (left, tree) → 改 (left, right_frame, tree)
        - right_frame 給 caller 加按鈕用（select_tab 加「💾 匯出股票清單」）
        - backtest_tab 暫不加、但簽名統一

        Args:
            parent: parent widget（select_tab 或 backtest_tab）

        Returns:
            (left_scrollable_frame, right_frame, results_tree)
        """
        container = ttk.Frame(parent)
        container.pack(fill="both", expand=True, padx=4, pady=4)

        # 左：params
        left_canvas = tk.Canvas(container, width=400)
        left_scrollbar = ttk.Scrollbar(container, orient="vertical", command=left_canvas.yview)
        left_scrollable_frame = ttk.Frame(left_canvas)

        left_scrollable_frame.bind(
            "<Configure>",
            lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all"))
        )
        left_canvas.create_window((0, 0), window=left_scrollable_frame, anchor="nw", width=380)
        left_canvas.configure(yscrollcommand=left_scrollbar.set)

        left_canvas.pack(side="left", fill="y")
        left_scrollbar.pack(side="left", fill="y")

        # Fix14 (2026-06-21): mousewheel 滾輪 scroll
        # 綁 <Enter>/<Leave> 動態切換 active，避免和其他 scrollable widget 搶
        def _on_canvas_enter(_e):
            left_canvas.bind_all("<MouseWheel>", lambda ev: left_canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units"))
            left_canvas.bind_all("<Button-4>", lambda _ev: left_canvas.yview_scroll(-1, "units"))
            left_canvas.bind_all("<Button-5>", lambda _ev: left_canvas.yview_scroll(1, "units"))

        def _on_canvas_leave(_e):
            left_canvas.unbind_all("<MouseWheel>")
            left_canvas.unbind_all("<Button-4>")
            left_canvas.unbind_all("<Button-5>")

        left_canvas.bind("<Enter>", _on_canvas_enter)
        left_canvas.bind("<Leave>", _on_canvas_leave)

        # 右：results Treeview（先空、之後 Phase 3B 填資料）
        right_frame = ttk.Frame(container)
        right_frame.pack(side="left", fill="both", expand=True, padx=(10, 0))

        # 【V0.9.5-tab-split-phase3-C】title 與 export 按鈕放同一行
        # (回傳 right_frame 給 caller、用 caller 決定要不要加按鈕)
        right_top = ttk.Frame(right_frame)
        right_top.pack(fill="x", pady=(0, 5))
        title_label = ttk.Label(right_top, text="📋 結果（執行後顯示）", font=("Segoe UI", 11, "bold"))
        title_label.pack(side="left", anchor="w")
        # export 按鈕由 caller 決定要不要加（select_tab 加、backtest_tab 暫不加）

        # Treeview
        tree_frame = ttk.Frame(right_frame)
        tree_frame.pack(fill="both", expand=True)

        results_tree = ttk.Treeview(tree_frame, show="headings", height=20)
        tree_scrollbar_y = ttk.Scrollbar(tree_frame, orient="vertical", command=results_tree.yview)
        tree_scrollbar_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=results_tree.xview)
        results_tree.configure(yscrollcommand=tree_scrollbar_y.set, xscrollcommand=tree_scrollbar_x.set)
        results_tree.pack(side="left", fill="both", expand=True)
        tree_scrollbar_y.pack(side="right", fill="y")
        tree_scrollbar_x.pack(side="bottom", fill="x")

        # 【V0.9.5-tab-split-phase3-C】勾選 + hover tag
        results_tree.tag_configure("checked", background="#d0e8ff")
        results_tree.tag_configure("unchecked", background="#ffffff")
        results_tree.tag_configure("hover", background="#fff3a0")
        results_tree.bind("<Motion>", self._on_select_tree_hover)
        results_tree.bind("<Leave>", self._on_select_tree_leave)
        results_tree.bind("<Button-1>", self._on_select_tree_click)
        # 【V0.9.5-tab-split-phase3-F】拿掉右鍵「全選/全不選」選單
        # 原本：results_tree.bind("<Button-3>", self._on_select_tree_rclick)
        # 為什麼拿：header 已是 ☐/☑/▣ 動態 checkbox、點下去就是全選/全不選
        #   右鍵選單多一重入口、重複、已不需要
        #   拿掉 <Button-3> bind 後右鍵點 tree 不會跳選單（避免出現空選單）

        # 【V0.9.5-tab-split-phase3-D】初始 header 設為 ☐（看起來像個 checkbox）
        try:
            first_col = results_tree["columns"][0]
            results_tree.heading(first_col, text="☐")
        except (IndexError, tk.TclError):
            pass

        # 【V0.9.5-tab-split-phase3-C】多回傳 right_frame
        return left_scrollable_frame, right_frame, results_tree

    def _build_backtest_tab(self, parent):
        """【V0.9.5-tab-split Phase 2】回測模擬 tab 內容

        Phase 2：已加技術指標、出場、WF、選股來源、執行回測按鈕
        Phase 3（下次）：加右側 Treeview 顯示回測結果
        """
        # 這個 method 在 _build_ui 內已被呼叫、
        # 實際的「左側 params」由 _build_ui 的 bt_left 處理
        # 此 method 留作未來擴充（ex: 全域提示訊息、tab 切換處理）
        # 暫時不做事
        pass

    # 【V0.9.5-tab-split-phase3-D Fix14】Tab Preset 機制
    # 白名單：每個 tab 包含哪些 self.vars key
    TAB_VAR_KEYS = {
        "system_select": [
            "top_n_for_tech", "history_months", "tech_months",
            "factor_weight_mom1", "factor_weight_mom3", "factor_weight_mom6",
            "factor_weight_rev", "factor_weight_eps",
            "simple_score_weight_rev", "simple_score_weight_eps",
            "simple_score_weight_div", "simple_score_weight_pe",
            "simple_min_rev_yoy", "simple_min_eps_yoy", "simple_min_eps", "simple_max_pe",
            "volume_surge_multiplier", "rsi_oversold", "ma20_tolerance",
            "rsi_aggressive", "rsi_recover", "oversold_lookback", "ma_slope_days",
            "strong_revenue_yoy", "strong_pe_max", "strong_price_min",
            "rsi_oversold", "ma20_tolerance",
        ],
        "backtest": [
            "stop_loss", "take_profit", "exit_rsi", "hold_days",
            "roundtrip_cost_pct", "topk", "capital",
            "wf_train_years", "wf_test_years", "wf_step_years",
            "min_rev_yoy", "min_eps_yoy",
        ],
    }
    TAB_DISPLAY_NAME = {
        "system_select": "系統選股",
        "backtest": "回測模擬",
    }

    def _add_preset_bar(self, parent, tab_key):
        """【Fix14】在某個 tab 頂端加 Preset 列 (ComboBox + 儲存/刪除按鈕)"""
        if not hasattr(self, "_preset_vars"):
            self._preset_vars = {}
        if not hasattr(self, "_preset_combos"):
            self._preset_combos = {}

        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(0, 6), padx=2)

        ttk.Label(bar, text=f"📋 {self.TAB_DISPLAY_NAME.get(tab_key, tab_key)} Preset:",
                  font=("Segoe UI", 9, "bold")).pack(side="left")

        var = tk.StringVar(value="")
        self._preset_vars[tab_key] = var

        combo = ttk.Combobox(bar, textvariable=var, width=18, state="normal")
        combo.pack(side="left", padx=4)
        combo.bind("<<ComboboxSelected>>", lambda e, k=tab_key: self._load_tab_preset(k))
        self._preset_combos[tab_key] = combo

        ttk.Button(bar, text="💾 儲存", width=7,
                   command=lambda k=tab_key: self._save_tab_preset(k)).pack(side="left", padx=1)
        ttk.Button(bar, text="🗑️ 刪除", width=7,
                   command=lambda k=tab_key: self._delete_tab_preset(k)).pack(side="left", padx=1)

        # 初始化：填入現有 preset 列表
        self._refresh_preset_list(tab_key)
        return bar

    def _refresh_preset_list(self, tab_key):
        """更新某 tab 的 preset 下拉選單"""
        if not hasattr(self, "_preset_combos") or tab_key not in self._preset_combos:
            return
        presets = self._get_tab_presets(tab_key)
        names = list(presets.keys())
        self._preset_combos[tab_key]["values"] = names

    def _get_tab_presets(self, tab_key) -> dict:
        """讀 cfg.tab_presets[tab_key]"""
        if not hasattr(self, "cfg") or not hasattr(self.cfg, "tab_presets"):
            return {}
        return self.cfg.tab_presets.get(tab_key, {}) or {}

    def _set_tab_presets(self, tab_key, presets: dict):
        """寫 cfg.tab_presets[tab_key] = presets"""
        if not hasattr(self.cfg, "tab_presets") or self.cfg.tab_presets is None:
            self.cfg.tab_presets = {}
        self.cfg.tab_presets[tab_key] = presets

    def _collect_tab_values(self, tab_key) -> dict:
        """從 UI (self.vars) 抓某 tab 的所有參數"""
        keys = self.TAB_VAR_KEYS.get(tab_key, [])
        out = {}
        for k in keys:
            var = self.vars.get(k)
            if var is None:
                continue
            try:
                v = var.get()
                # 百分比類型 key 從 % 還原成小數（與 _save_ui_to_config 一致）
                if k in ["stop_loss", "take_profit", "roundtrip_cost_pct", "ma20_tolerance"]:
                    v = float(v) / 100.0
                out[k] = v
            except Exception:
                pass
        # 加 boolean / checkbox vars（不在 self.vars 但也屬於這個 tab）
        if tab_key == "system_select":
            for attr in ["use_enhanced_score_var", "volume_filter_var",
                         "mtf_var", "divergence_var", "trend_filter_var",
                         "use_aggressive_signal_var"]:
                vobj = getattr(self, attr, None)
                if vobj is not None:
                    out[attr] = bool(vobj.get())
        return out

    def _apply_tab_values(self, tab_key, data: dict):
        """把 preset 套回 UI (self.vars)"""
        for k, v in (data or {}).items():
            # boolean / checkbox 變數（_xxx_var 結尾）
            if k.endswith("_var"):
                vobj = getattr(self, k, None)
                if vobj is not None:
                    try:
                        vobj.set(bool(v))
                    except Exception:
                        pass
                continue
            var = self.vars.get(k)
            if var is None:
                continue
            # 還原百分比 → 顯示 %
            if k in ["stop_loss", "take_profit", "roundtrip_cost_pct", "ma20_tolerance"]:
                try:
                    var.set(float(v) * 100.0)
                except Exception:
                    pass
            else:
                try:
                    var.set(v)
                except Exception:
                    pass

    def _save_tab_preset(self, tab_key):
        """儲存目前 tab 參數為命名 preset"""
        from tkinter import simpledialog, messagebox
        name = simpledialog.askstring(
            "儲存 Preset",
            f"請輸入 [{self.TAB_DISPLAY_NAME.get(tab_key, tab_key)}] Preset 名稱：",
            initialvalue=f"{self.TAB_DISPLAY_NAME.get(tab_key, 'preset')}_1",
        )
        if not name:
            return
        name = name.strip()
        if not name:
            return

        values = self._collect_tab_values(tab_key)
        presets = self._get_tab_presets(tab_key)
        presets[name] = values
        self._set_tab_presets(tab_key, presets)

        # 記住 last_preset
        last = self.cfg.tab_last_preset or {}
        last[tab_key] = name
        self.cfg.tab_last_preset = last

        save_config(self.cfg.to_dict())
        self._refresh_preset_list(tab_key)
        if tab_key in self._preset_vars:
            self._preset_vars[tab_key].set(name)
        messagebox.showinfo("已儲存", f"Preset「{name}」已儲存")

    def _load_tab_preset(self, tab_key):
        """從 UI 選的 preset 載入到 self.vars"""
        name = self._preset_vars.get(tab_key, tk.StringVar()).get().strip()
        if not name:
            return
        presets = self._get_tab_presets(tab_key)
        data = presets.get(name)
        if not data:
            return
        self._apply_tab_values(tab_key, data)
        # 同步到 StrategyConfig
        for k, v in (data or {}).items():
            if hasattr(self.cfg, k) and not k.endswith("_var"):
                try:
                    setattr(self.cfg, k, v)
                except Exception:
                    pass
        # 記住 last_preset
        last = self.cfg.tab_last_preset or {}
        last[tab_key] = name
        self.cfg.tab_last_preset = last
        save_config(self.cfg.to_dict())
        self.logger.log(f"✅ Preset「{name}」已套用至 [{self.TAB_DISPLAY_NAME.get(tab_key, tab_key)}]")

    def _delete_tab_preset(self, tab_key):
        from tkinter import messagebox
        name = self._preset_vars.get(tab_key, tk.StringVar()).get().strip()
        if not name:
            messagebox.showwarning("未選", "請先從下拉選單選一個 preset")
            return
        if not messagebox.askyesno("確認刪除", f"刪除 Preset「{name}」？"):
            return
        presets = self._get_tab_presets(tab_key)
        if name in presets:
            del presets[name]
            self._set_tab_presets(tab_key, presets)
            save_config(self.cfg.to_dict())
            self._refresh_preset_list(tab_key)
            self._preset_vars[tab_key].set("")
            self.logger.log(f"🗑️ Preset「{name}」已刪除")

    def _init_tab_presets_on_startup(self):
        """App 啟動時自動載入每個 tab 上次的 preset"""
        last = (self.cfg.tab_last_preset or {}) if hasattr(self.cfg, "tab_last_preset") else {}
        for tab_key in self.TAB_VAR_KEYS.keys():
            name = last.get(tab_key)
            if not name:
                continue
            presets = self._get_tab_presets(tab_key)
            if name not in presets:
                continue
            self._refresh_preset_list(tab_key)
            if tab_key in self._preset_vars:
                self._preset_vars[tab_key].set(name)
            self._apply_tab_values(tab_key, presets[name])
            self.logger.log(f"📋 [{self.TAB_DISPLAY_NAME.get(tab_key, tab_key)}] 自動載入 Preset「{name}」")

    def _add_entry(self, parent, label, key, var_cls, default):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=18).pack(side="left")
        if var_cls == tk.BooleanVar:
            v = var_cls(value=default)
            ttk.Checkbutton(row, variable=v).pack(side="left")
        else:
            v = var_cls(value=default)
            ttk.Entry(row, textvariable=v, width=12).pack(side="left")
        self.vars[key] = v

    def _load_config_to_ui(self):
        for key, var in self.vars.items():
            if hasattr(self.cfg, key):
                value = getattr(self.cfg, key)
                if key in ["stop_loss", "take_profit", "roundtrip_cost_pct", "ma20_tolerance"]:
                    value = value * 100.0
                var.set(value)
        self.use_enhanced_score_var.set(self.cfg.use_enhanced_score)
        self.volume_filter_var.set(self.cfg.require_volume_filter)
        self.mtf_var.set(self.cfg.use_mtf_confirmation)
        self.divergence_var.set(self.cfg.use_divergence_detection)
        self.wf_enabled_var.set(self.cfg.wf_enabled)
        self.excel_force_buy_var.set(self.cfg.excel_force_buy)
        self.excel_file_var.set(self.cfg.excel_stock_file)

        # ✅ 新增以下程式碼
        self.trend_filter_var.set(self.cfg.require_trend_filter)
        self.use_aggressive_signal_var.set(self.cfg.use_aggressive_signal)

    def _save_ui_to_config(self):
        for key, var in self.vars.items():
            if hasattr(self.cfg, key):
                value = var.get()
                if key in ["stop_loss", "take_profit", "roundtrip_cost_pct", "ma20_tolerance"]:
                    value = value / 100.0
                setattr(self.cfg, key, value)
        self.cfg.use_enhanced_score = self.use_enhanced_score_var.get()
        # Fix3：回測永遠從 Excel 讀（移除 use_excel_var toggle）
        self.cfg.use_excel_stock_list = True
        self.cfg.require_volume_filter = self.volume_filter_var.get()
        self.cfg.use_mtf_confirmation = self.mtf_var.get()
        self.cfg.use_divergence_detection = self.divergence_var.get()
        self.cfg.wf_enabled = self.wf_enabled_var.get()
        self.cfg.excel_force_buy = self.excel_force_buy_var.get()
        self.cfg.excel_stock_file = self.excel_file_var.get()

        # ✅ 新增以下程式碼
        self.cfg.require_trend_filter = self.trend_filter_var.get()
        self.cfg.use_aggressive_signal = self.use_aggressive_signal_var.get()

    def _on_save_config(self):
        self._save_ui_to_config()
        if save_config(self.cfg.to_dict()):
            self.logger.log("✅ 設定已儲存到 config.json")
        else:
            self.logger.log("❌ 設定儲存失敗")

    def _on_reset_config(self):
        if messagebox.askyesno("確認", "確定要恢復所有預設設定嗎？"):
            self.cfg.update_from_dict(DEFAULT_CONFIG)
            self._load_config_to_ui()
            save_config(self.cfg.to_dict())
            self.logger.log("🔄 已恢復預設設定")

    def _open_simple_score_settings(self):
        win = tk.Toplevel(self)
        win.title("簡易評分參數設定")
        win.geometry("550x650")
        win.transient(self)
        win.grab_set()

        canvas = tk.Canvas(win)
        scrollbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        row = 0

        ttk.Label(scrollable_frame, text="═ 權重設定（總和建議100%） ═", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, columnspan=2, pady=(10, 5), sticky="w")
        row += 1

        self.simple_vars = {}

        ttk.Label(scrollable_frame, text="營收YoY 權重 (%)：").grid(row=row, column=0, sticky="w", padx=10, pady=2)
        self.simple_vars["weight_rev"] = tk.DoubleVar(value=self.cfg.simple_score_weight_rev)
        ttk.Entry(scrollable_frame, textvariable=self.simple_vars["weight_rev"], width=10).grid(row=row, column=1, sticky="w")
        row += 1

        ttk.Label(scrollable_frame, text="EPSYoY 權重 (%)：").grid(row=row, column=0, sticky="w", padx=10, pady=2)
        self.simple_vars["weight_eps"] = tk.DoubleVar(value=self.cfg.simple_score_weight_eps)
        ttk.Entry(scrollable_frame, textvariable=self.simple_vars["weight_eps"], width=10).grid(row=row, column=1, sticky="w")
        row += 1

        ttk.Label(scrollable_frame, text="殖利率 權重 (%)：").grid(row=row, column=0, sticky="w", padx=10, pady=2)
        self.simple_vars["weight_div"] = tk.DoubleVar(value=self.cfg.simple_score_weight_div)
        ttk.Entry(scrollable_frame, textvariable=self.simple_vars["weight_div"], width=10).grid(row=row, column=1, sticky="w")
        row += 1

        ttk.Label(scrollable_frame, text="本益比 權重 (%)：").grid(row=row, column=0, sticky="w", padx=10, pady=2)
        self.simple_vars["weight_pe"] = tk.DoubleVar(value=self.cfg.simple_score_weight_pe)
        ttk.Entry(scrollable_frame, textvariable=self.simple_vars["weight_pe"], width=10).grid(row=row, column=1, sticky="w")
        ttk.Label(scrollable_frame, text="（負值表示扣分）", foreground="gray").grid(row=row, column=2, sticky="w", padx=5)
        row += 1

        ttk.Separator(scrollable_frame, orient="horizontal").grid(row=row, column=0, columnspan=3, sticky="ew", pady=10)
        row += 1

        ttk.Label(scrollable_frame, text="═ 門檻過濾（低於門檻直接排除） ═", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, columnspan=2, pady=(5, 5), sticky="w")
        row += 1

        ttk.Label(scrollable_frame, text="最低營收YoY (%)：").grid(row=row, column=0, sticky="w", padx=10, pady=2)
        self.simple_vars["min_rev_yoy"] = tk.DoubleVar(value=self.cfg.simple_min_rev_yoy)
        ttk.Entry(scrollable_frame, textvariable=self.simple_vars["min_rev_yoy"], width=10).grid(row=row, column=1, sticky="w")
        ttk.Label(scrollable_frame, text="（-999 = 不限制）", foreground="gray").grid(row=row, column=2, sticky="w", padx=5)
        row += 1

        ttk.Label(scrollable_frame, text="最低EPSYoY (%)：").grid(row=row, column=0, sticky="w", padx=10, pady=2)
        self.simple_vars["min_eps_yoy"] = tk.DoubleVar(value=self.cfg.simple_min_eps_yoy)
        ttk.Entry(scrollable_frame, textvariable=self.simple_vars["min_eps_yoy"], width=10).grid(row=row, column=1, sticky="w")
        ttk.Label(scrollable_frame, text="（-999 = 不限制）", foreground="gray").grid(row=row, column=2, sticky="w", padx=5)
        row += 1

        ttk.Label(scrollable_frame, text="最低EPS (元)：").grid(row=row, column=0, sticky="w", padx=10, pady=2)
        self.simple_vars["min_eps"] = tk.DoubleVar(value=self.cfg.simple_min_eps)
        ttk.Entry(scrollable_frame, textvariable=self.simple_vars["min_eps"], width=10).grid(row=row, column=1, sticky="w")
        ttk.Label(scrollable_frame, text="（-999 = 不限制）", foreground="gray").grid(row=row, column=2, sticky="w", padx=5)
        row += 1

        ttk.Label(scrollable_frame, text="最高本益比：").grid(row=row, column=0, sticky="w", padx=10, pady=2)
        self.simple_vars["max_pe"] = tk.DoubleVar(value=self.cfg.simple_max_pe)
        ttk.Entry(scrollable_frame, textvariable=self.simple_vars["max_pe"], width=10).grid(row=row, column=1, sticky="w")
        ttk.Label(scrollable_frame, text="（999 = 不限制）", foreground="gray").grid(row=row, column=2, sticky="w", padx=5)
        row += 1

        ttk.Separator(scrollable_frame, orient="horizontal").grid(row=row, column=0, columnspan=3, sticky="ew", pady=10)
        row += 1

        def set_defaults():
            self.simple_vars["weight_rev"].set(35)
            self.simple_vars["weight_eps"].set(35)
            self.simple_vars["weight_div"].set(20)
            self.simple_vars["weight_pe"].set(-5)
            self.simple_vars["min_rev_yoy"].set(-999)
            self.simple_vars["min_eps_yoy"].set(-999)
            self.simple_vars["min_eps"].set(-999)
            self.simple_vars["max_pe"].set(999)
            self.simple_vars["broker_discount"].set(1.0)

        # ── V0.9.4 phase2.3: 交易成本設定 ──
        ttk.Separator(scrollable_frame, orient="horizontal").grid(row=row, column=0, columnspan=3, sticky="ew", pady=(8, 4))
        row += 1
        ttk.Label(scrollable_frame, text="═ 交易成本設定 ═", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, columnspan=2, pady=(4, 5), sticky="w")
        row += 1

        ttk.Label(scrollable_frame, text="券商折扣：").grid(row=row, column=0, sticky="w", padx=10, pady=2)
        self.simple_vars["broker_discount"] = tk.DoubleVar(value=self.cfg.broker_discount)
        ttk.Entry(scrollable_frame, textvariable=self.simple_vars["broker_discount"], width=10).grid(row=row, column=1, sticky="w")
        ttk.Label(scrollable_frame, text="（1.0 = 無折扣，0.6 = 6折，0.5 = 5折）", foreground="gray").grid(row=row, column=2, sticky="w", padx=5)
        row += 1

        def set_defaults():
            self.simple_vars["weight_rev"].set(35)
            self.simple_vars["weight_eps"].set(35)
            self.simple_vars["weight_div"].set(20)
            self.simple_vars["weight_pe"].set(-5)
            self.simple_vars["min_rev_yoy"].set(-999)
            self.simple_vars["min_eps_yoy"].set(-999)
            self.simple_vars["min_eps"].set(-999)
            self.simple_vars["max_pe"].set(999)
            self.simple_vars["broker_discount"].set(1.0)

        ttk.Button(scrollable_frame, text="恢復預設值", command=set_defaults).grid(row=row, column=0, columnspan=2, pady=5)
        row += 1

        def save_settings():
            self.cfg.simple_score_weight_rev = self.simple_vars["weight_rev"].get()
            self.cfg.simple_score_weight_eps = self.simple_vars["weight_eps"].get()
            self.cfg.simple_score_weight_div = self.simple_vars["weight_div"].get()
            self.cfg.simple_score_weight_pe = self.simple_vars["weight_pe"].get()
            self.cfg.simple_min_rev_yoy = self.simple_vars["min_rev_yoy"].get()
            self.cfg.simple_min_eps_yoy = self.simple_vars["min_eps_yoy"].get()
            self.cfg.simple_min_eps = self.simple_vars["min_eps"].get()
            self.cfg.simple_max_pe = self.simple_vars["max_pe"].get()
            self.cfg.broker_discount = self.simple_vars["broker_discount"].get()
            # V0.9.4 phase2.3: 即時更新 PortfolioDB 的券商折扣
            self.portfolio.broker_discount = self.cfg.broker_discount
            win.destroy()
            self.logger.log("✅ 簡易評分參數已更新")
            save_config(self.cfg.to_dict())

        ttk.Button(scrollable_frame, text="儲存設定", command=save_settings).grid(row=row, column=0, columnspan=2, pady=10)

    def _poll_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                # v1.1 重構：GuiLogger 把 log 包成 (type, msg) tuple
                # 解構拿 msg_text
                if isinstance(msg, tuple) and len(msg) == 2 and msg[0] == "log":
                    msg_text = msg[1]
                else:
                    # backward compat: 舊版直接傳 str
                    msg_text = str(msg)
                self.console.insert("end", msg_text + "\n")
                self.console.see("end")
        except queue.Empty:
            pass
        self.after(120, self._poll_log_queue)

    def _on_clear_console(self):
        self.console.delete("1.0", "end")

    # ==========================================================
    # V0.9.4 買賣記錄 Tab（不動 V0.9.3 上面所有 method）
    # ==========================================================
    def _on_tab_changed(self, event):
        """Tab 切換時自動 refresh 買賣記錄 + 抓持倉現價"""
        try:
            current = self.notebook.index(self.notebook.select())
            if current == 3:  # Tab 4 = 買賣記錄
                self._refresh_portfolio_view()
                # 背景執行抓現價（不 blocking GUI）
                self.after(100, self._auto_fetch_positions_prices)
                # V0.9.5+ Phase 8（William 2026-06-15 11:02）：
                # 開盤時段（09:00~13:30）每 30 秒 refresh 一次持倉現價
                self._schedule_portfolio_refresh()
            else:
                # 切離買賣記錄 Tab → 取消 refresh loop
                self._cancel_portfolio_refresh()
        except Exception as e:
            self.logger.log(f"⚠️ Tab 切換 refresh 失敗：{e}")

    def _schedule_portfolio_refresh(self):
        """V0.9.5+ Phase 8：盤中（09:00~13:30）每 30 秒 refresh 一次持倉現價
        收盤後、週末、切離 Tab 時自動停止
        """
        # 取消上次的排程（避免重複）
        self._cancel_portfolio_refresh()

        # 檢查是否在盤中
        if not _is_market_hours():
            self.logger.log("⏸️ 收盤時段、停止持倉現價自動 refresh（要 30 秒 refresh 請在 09:00~13:30 間瀠覽本 Tab）")
            return

        # 排程下一次 refresh（30 秒後）
        self._portfolio_refresh_job_id = self.after(30000, self._portfolio_refresh_loop)
        self.logger.log("🔄 盤中持倉現價自動 refresh 啟動（每 30 秒）")

    def _cancel_portfolio_refresh(self):
        """取消持倉現價 refresh 排程（無論是切離 Tab 或收盤）"""
        if getattr(self, '_portfolio_refresh_job_id', None):
            try:
                self.after_cancel(self._portfolio_refresh_job_id)
            except Exception:
                pass
            self._portfolio_refresh_job_id = None

    def _portfolio_refresh_loop(self):
        """refresh loop 本體：刷新一次持倉現價、判斷是否要排下一次
        終止條件：
        1. 使用者切離買賣記錄 Tab
        2. 收盤（_is_market_hours() = False）
        """
        try:
            current = self.notebook.index(self.notebook.select())
            if current != 3:
                # 已切離買賣記錄 Tab、停止 loop
                self.logger.log("⏸️ 已切離買賣記錄 Tab、停止持倉現價自動 refresh")
                return
        except Exception:
            return

        # 抓一次現價
        self._auto_fetch_positions_prices()

        # 排程下一次（內部會檢查 _is_market_hours、收盤就停）
        self._schedule_portfolio_refresh()

    def _auto_fetch_positions_prices(self):
        """切到買賣記錄 Tab 時自動抓持倉所有股票現價（背景 thread）
        V0.9.5+ Phase 10（William 11:39 反映）：加上動態進度顯示
        - 起動：log 顯示「⏰ 下次 refresh HH:MM:SS」
        - 抓取中：每一檔 log 「🔄 [3/8] 正在抓 2330...」
        - 完成：log 顯示「✅ 11:30:15 refresh 完成、5 檔成功」
        """
        positions = self.portfolio.get_positions()
        if not positions:
            return
        stock_ids = [p.stock_id for p in positions if p.stock_id]

        # 顯示「下次 refresh 預定時間」（給使用者信心 polling 有在跑）
        next_refresh_time = (datetime.now() + timedelta(seconds=30)).strftime("%H:%M:%S")
        self.logger.log(
            f"⏰ 下次持倉現價 refresh：{next_refresh_time}（30 秒後）"
        )

        def worker():
            from portfolio import fetch_prices_batch
            started_at = datetime.now()
            self.after(0, lambda: self.logger.log(f"🔄 [{len(stock_ids)} 檔] 抓取中..."))
            try:
                def _progress(idx, total, sid):
                    # 每一檔動態 log（讓使用者看到 progress 不會以為卡住）
                    self.after(0, lambda: self.logger.log(
                        f"🔄 [{idx}/{total}] 抓 {sid} 中... ({int((idx/total)*100)}%)"
                    ))

                results = fetch_prices_batch(stock_ids, progress_callback=_progress)
                elapsed = (datetime.now() - started_at).total_seconds()
                # 用 after 回主執行緒更新 GUI
                self.after(0, lambda: self._apply_fetched_prices(results))
                self.after(0, lambda: self.logger.log(
                    f"✅ refresh 完成：{elapsed:.1f} 秒抓完 {len(stock_ids)} 檔"
                ))
            except Exception as e:
                self.after(0, lambda: self.logger.log(f"⚠️ 自動抓現價失敗：{e}"))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_fetched_prices(self, results: Dict[str, Dict[str, Any]]):
        """把背景抓回來的現價套到 GUI（主執行緒）"""
        fallback_count = 0
        for sid, info in results.items():
            if info.get("ok") and info.get("price", 0) > 0:
                self._current_prices[sid] = info["price"]
                # 同步快取股票名稱（fetch 回來時順便存）
                if info.get("name"):
                    self._current_names[sid] = info["name"]
                    self._backfill_stock_name(sid, info["name"])
                # 【V0.9.5+ Phase 9】fallback 提示：若 price 是用 mid 估算的、log 提示使用者
                if info.get("price_fallback") == "mid":
                    fallback_count += 1
                    self.logger.log(
                        f"⚠️ {sid} 無即時成交價、用今日高低价中點估算：{info['price']:.2f}（TWSE 記錄 z='-'）"
                    )
                elif info.get("price_fallback") == "prev_close":
                    fallback_count += 1
                    self.logger.log(
                        f"⚠️ {sid} 無即時成交價、用昨收估算：{info['price']:.2f}（TWSE 連 h/l 也缺資料）"
                    )
        self._refresh_portfolio_view()
        ok_count = sum(1 for v in results.values() if v.get("ok"))
        msg = f"✅ 現價抓取完成：{ok_count}/{len(results)} 檔成功"
        if fallback_count:
            msg += f"（{fallback_count} 檔用估算價、缺即時成交）"
        self.logger.log(msg)

    def _backfill_stock_name(self, stock_id: str, name: str):
        """把抓到的名稱補回 DB 中所有該代號的紀錄"""
        try:
            with self.portfolio._connect() as conn:
                conn.execute(
                    "UPDATE transactions SET stock_name=? WHERE stock_id=? AND (stock_name IS NULL OR stock_name='')",
                    (name, stock_id)
                )
                conn.commit()
        except Exception:
            pass

    def _build_portfolio_tab(self, parent):
        """建立「買賣記錄」Tab 的 UI"""
        # 上方：8 個總覽 Label（2行×4欄）V0.9.4 phase2.3: 加手續費/證交稅/淨利潤
        summary_frame = ttk.LabelFrame(parent, text="📊 持倉總覽", padding=8)
        summary_frame.pack(fill="x", padx=8, pady=(8, 4))
        self._summary_labels = {}

        # Row 0: 成本/市值/未實現/手續費/總報酬率（V0.9.5+ Phase 11 修正：加回 total_return_pct）
        #   原因：之前 row1 加了「歷史累計已付稅」後變 4 個、total_return_pct 沒地方放 → KeyError
        #   解法：row0 加 total_return_pct 變 5 個、row1 維持 4 個
        row0 = [
            ("total_cost", "總成本（含費用）"),
            ("total_market_value", "總市值"),
            ("total_unrealized_pl", "未實現損益"),
            ("total_fee", "累計手續費"),
            ("total_return_pct", "總報酬率 %"),  # V0.9.5+ Phase 11：從 row1 移回 row0
        ]
        # Row 1: 現價累計證交稅/歷史累計已付稅/已實現淨/總損益
        #   V0.9.5+ Phase 11（William 2026-06-15 19:15）：
        #   「累計證交稅」改成「以持股現價計算」= Σ(現價 × 股數 × 0.003)
        #   歷史已付稅另以小字顯示
        row1 = [
            ("total_tax", "現價累計證交稅"),       # ← 顯示 current_tax（V0.9.5+ Phase 11）
            ("historical_tax", "歷史累計已付稅"),   # ← 顯示 total_tax（保留歷史）
            ("net_realized_pl", "已實現淨損益"),
            ("total_pl", "總損益（含現價稅）"),
        ]

        for col, (key, label) in enumerate(row0):
            cell = ttk.Frame(summary_frame)
            cell.grid(row=0, column=col, padx=10, pady=2, sticky="w")
            ttk.Label(cell, text=label, font=("Segoe UI", 9), foreground="#666").pack(anchor="w")
            val_lbl = ttk.Label(cell, text="—", font=("Segoe UI", 12, "bold"))
            val_lbl.pack(anchor="w")
            self._summary_labels[key] = val_lbl

        for col, (key, label) in enumerate(row1):
            cell = ttk.Frame(summary_frame)
            cell.grid(row=1, column=col, padx=10, pady=2, sticky="w")
            ttk.Label(cell, text=label, font=("Segoe UI", 9), foreground="#666").pack(anchor="w")
            val_lbl = ttk.Label(cell, text="—", font=("Segoe UI", 12, "bold"))
            val_lbl.pack(anchor="w")
            self._summary_labels[key] = val_lbl

        # 按鈕區：移至「持倉總攬」與「持倉明細」之間（William 2026-06-24 11:19 反映）
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill="x", padx=8, pady=(4, 4))
        ttk.Button(btn_frame, text="➕ 新增買入", command=self._open_buy_dialog).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="➖ 新增賣出", command=self._open_sell_dialog).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="💲 更新現價", command=self._update_prices_dialog).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="🗑 刪除選中", command=self._delete_selected_tx).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="🔄 重新整理", command=self._refresh_portfolio_view).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="✏️ 編輯", command=self._open_edit_tx_dialog).pack(side="left", padx=2)  # V0.9.4 phase2.3
        ttk.Button(btn_frame, text="📤 匯出 Excel", command=self._export_portfolio_excel).pack(side="right", padx=2)

        # 中間：持倉明細 Treeview
        pos_frame = ttk.LabelFrame(parent, text="🌳 持倉明細", padding=4)
        pos_frame.pack(fill="both", expand=False, padx=8, pady=(0, 4))
        pos_cols = ("代號", "名稱", "股數", "均價", "現價", "市值", "未實現損益", "報酬率%", "已實現損益")
        self._positions_tree = ttk.Treeview(pos_frame, columns=pos_cols, show="headings", height=8)
        for col, w in zip(pos_cols, [60, 80, 80, 70, 70, 90, 90, 70, 90]):
            self._positions_tree.heading(col, text=col)
            self._positions_tree.column(col, width=w, anchor="e" if col not in ("代號", "名稱") else "w")
        pos_scroll = ttk.Scrollbar(pos_frame, orient="vertical", command=self._positions_tree.yview)
        self._positions_tree.configure(yscrollcommand=pos_scroll.set)
        self._positions_tree.pack(side="left", fill="both", expand=True)
        pos_scroll.pack(side="right", fill="y")
        self._positions_tree.bind("<<TreeviewSelect>>", self._on_position_selected)

        # 下方：交易明細 Treeview
        tx_frame = ttk.LabelFrame(parent, text="📋 交易明細", padding=4)
        tx_frame.pack(fill="both", expand=True, padx=8, pady=4)
        tx_cols = ("id", "日期", "代號", "名稱", "買/賣", "股數", "價格", "手續費", "證交稅", "備註")  # V0.9.4 phase2.3: 加證交稅欄
        self._tx_tree = ttk.Treeview(tx_frame, columns=tx_cols, show="headings", height=8)
        for col, w in zip(tx_cols, [40, 80, 60, 80, 50, 65, 65, 55, 55, 100]):
            self._tx_tree.heading(col, text=col)
            self._tx_tree.column(col, width=w, anchor="w" if col in ("代號", "名稱", "買/賣", "備註", "日期") else "e")
        tx_scroll = ttk.Scrollbar(tx_frame, orient="vertical", command=self._tx_tree.yview)
        self._tx_tree.configure(yscrollcommand=tx_scroll.set)
        self._tx_tree.pack(side="left", fill="both", expand=True)
        tx_scroll.pack(side="right", fill="y")

    # ==========================================================
    # 【V0.9.5-etf】主動式 ETF 持股 Tab
    # ==========================================================

    def _build_etf_tab(self, parent):
        """【V0.9.5-etf】建立「主動式 ETF」Tab 的 UI
        - 左面板：篩選條件（最小 ETF 數、是否限定有收盤價） + 按鈕
        - 右面板：Treeview（5 欄）+ 移到「ETF數」欄顯示 popup
        """
        # ---- 上方：狀態列 ----
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill="x", padx=8, pady=(6, 0))
        self._etf_status = tk.StringVar(value="主動式 ETF 持股：首次進入會自動抓取（19 檔 × 前 10 大）")
        ttk.Label(status_frame, textvariable=self._etf_status,
                  foreground="#555555", font=("Helvetica", 9)).pack(anchor="w")

        # 進度條
        self._etf_progress = ttk.Progressbar(status_frame, mode='determinate', length=200)
        self._etf_progress.pack(anchor="w", pady=(2, 0))
        self._etf_progress.pack_forget()

        # ---- 主區：左面板 + 右結果 ----
        paned = ttk.PanedWindow(parent, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=6, pady=6)

        # ── 左面板：篩選條件 + 按鈕 ──
        left_container = ttk.Frame(paned)
        paned.add(left_container, weight=0)

        left_canvas = tk.Canvas(left_container, width=300, highlightthickness=0)
        left_scrollbar = ttk.Scrollbar(left_container, orient="vertical", command=left_canvas.yview)
        left_canvas.configure(yscrollcommand=left_scrollbar.set)
        left_scrollbar.pack(side="right", fill="y")
        left_canvas.pack(side="left", fill="both", expand=True)

        def _on_mousewheel(event):
            left_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        # Fix16 (2026-06-21): 用 Enter/Leave 動態 bind_all，避免跟其他 tab 衝突
        def _on_canvas_enter(_e):
            left_canvas.bind_all("<MouseWheel>", lambda ev: left_canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units"))
            left_canvas.bind_all("<Button-4>", lambda _ev: left_canvas.yview_scroll(-1, "units"))
            left_canvas.bind_all("<Button-5>", lambda _ev: left_canvas.yview_scroll(1, "units"))

        def _on_canvas_leave(_e):
            left_canvas.unbind_all("<MouseWheel>")
            left_canvas.unbind_all("<Button-4>")
            left_canvas.unbind_all("<Button-5>")

        left_canvas.bind("<Enter>", _on_canvas_enter)
        left_canvas.bind("<Leave>", _on_canvas_leave)

        left_frame = ttk.LabelFrame(left_canvas, text="🔎 ETF 持股篩選", padding=8)
        left_canvas.create_window((0, 0), window=left_frame, anchor="nw")
        left_frame.bind(
            "<Configure>",
            lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all")),
        )
        # left_frame 建好之後才 bind Enter/Leave
        left_frame.bind("<Enter>", _on_canvas_enter)
        left_frame.bind("<Leave>", _on_canvas_leave)

        # 最小 ETF 數
        row1 = ttk.Frame(left_frame)
        row1.pack(fill="x", pady=2)
        ttk.Label(row1, text="最少被幾檔 ETF 持有 ≥", width=22).pack(side="left")
        self._etf_min_count_var = tk.IntVar(value=1)
        ttk.Entry(row1, textvariable=self._etf_min_count_var, width=8).pack(side="left")
        ttk.Label(row1, text="檔", width=4).pack(side="left")

        # 只顯示有收盤價
        self._etf_only_with_price_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            left_frame, text="只顯示有收盤價的股票",
            variable=self._etf_only_with_price_var,
        ).pack(anchor="w", pady=2)

        # 結果上限
        row2 = ttk.Frame(left_frame)
        row2.pack(fill="x", pady=(6, 0))
        ttk.Label(row2, text="結果上限：", width=22).pack(side="left")
        self._etf_limit_var = tk.IntVar(value=500)
        ttk.Entry(row2, textvariable=self._etf_limit_var, width=8).pack(side="left")
        ttk.Label(row2, text="檔", width=4).pack(side="left")

        # 按鈕區
        btn_row = ttk.Frame(left_frame)
        btn_row.pack(fill="x", pady=(12, 0))
        ttk.Button(btn_row, text="🔍 套用篩選",
                   command=self._etf_apply_filter).pack(fill="x", pady=1)
        ttk.Button(btn_row, text="🔄 重新抓 ETF 持股",
                   command=self._etf_refresh_holdings).pack(fill="x", pady=1)
        self._etf_data_status = tk.StringVar(value="ETF 持股：未抓取")
        ttk.Label(btn_row, textvariable=self._etf_data_status,
                  font=("Helvetica", 8), foreground="#666666").pack(anchor="w", pady=(0, 4))
        # 【V0.9.5-tab-split-phase3-E】2026-06-22 William 反映：
        #   結果畫面勾選欄 header 已是 ☐/☑/▣ 動態 checkbox、可點全選/全不選
        #   參數區的全選/全不選按鈕重複、拿掉
        #   （_etf_select_all / _etf_select_none methods 保留、header click 仍會叫）
        # 【V0.9.5-tab-split-phase3-G】2026-06-22 William 反映：
        #   匯出按鈕從左邊參數區移到右上面板右邊、跟系統選股一致
        #   文字統一「💾 匯出股票清單」

        # ── 右面板：title + export 按鈕 + Treeview（跟系統選股同結構）──
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)

        # 右上面板：title 左邊、export 按鈕右邊
        right_top = ttk.Frame(right_frame)
        right_top.pack(fill="x", pady=(0, 5))
        ttk.Label(right_top, text="📊 ETF 成份股持股統計（依 ETF 數排序）",
                  font=("Segoe UI", 11, "bold")).pack(side="left", anchor="w")
        # 【V0.9.5-tab-split-phase3-G】跟 select_tab 同名、同位置
        self.export_etf_btn = ttk.Button(
            right_top,
            text="💾 匯出股票清單",
            command=self._etf_export_excel,
            state="disabled",
        )
        self.export_etf_btn.pack(side="right")

        # Treeview 子 frame
        tree_frame = ttk.Frame(right_frame)
        tree_frame.pack(fill="both", expand=True)

        cols = ("勾選", "代號", "名稱", "收盤價", "ETF數", "今日異動")
        self._etf_tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                      selectmode="none", height=25)
        col_widths = (40, 70, 130, 80, 70, 100)
        for col, w in zip(cols, col_widths):
            self._etf_tree.heading(col, text=col)
            self._etf_tree.column(col, width=w, anchor="center")

        # 【V0.9.5-tab-split-phase3-D】初始 header 設為 ☐（看起來像個 checkbox）
        try:
            self._etf_tree.heading(cols[0], text="☐")
        except (IndexError, tk.TclError):
            pass

        etf_scroll_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self._etf_tree.yview)
        etf_scroll_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=self._etf_tree.xview)
        self._etf_tree.configure(yscrollcommand=etf_scroll_y.set, xscrollcommand=etf_scroll_x.set)
        self._etf_tree.pack(side="left", fill="both", expand=True)
        etf_scroll_y.pack(side="right", fill="y")
        etf_scroll_x.pack(side="bottom", fill="x")

        # 複用手動選股的 hover / 勾選 highlight 配色
        self._etf_tree.tag_configure("checked", background="#d0e8ff")
        self._etf_tree.tag_configure("unchecked", background="#ffffff")
        self._etf_tree.tag_configure("hover", background="#fff3a0")
        self._etf_hover_iid = None  # 跟手動選股一樣機制
        # popup 變數
        self._etf_popup = None  # Toplevel 視窗（若有）

        # Bind events
        # Fix12 (2026-06-21): 原本重複綁 <Motion>、<Leave>，
        # 後綁定的 _etf_tree_hover_new / _leave_new 覆蓋了 _on_etf_tree_hover / _leave
        # → popup 邏輯 (顯示 ETF 持股) 永遠不會被觸發
        # 修法：合併成一個 handler、保留新版的 highlight + 舊版的 popup 邏輯
        self._etf_tree.bind("<Motion>", self._etf_tree_hover_combined)
        self._etf_tree.bind("<Leave>", self._etf_tree_leave_combined)
        self._etf_tree.bind("<Button-1>", self._etf_toggle_check)
        # 【V0.9.5-tab-split-phase3-F】拿掉右鍵「全選/全不選」選單
        # 原本：self._etf_tree.bind("<Button-3>", self._etf_tree_rclick_new)
        # 為什麼拿：header 已是 ☐/☑/▣ 動態 checkbox、右鍵選單重複

        # 資料儲存（長期持有的 DataFrame）
        self._etf_long_df = None  # long-format raw（來自 build_etf_holdings_table）
        self._etf_agg_df = None   # wide-format（來自 aggregate_etf_holdings）
        self._etf_checked = {}    # iid -> bool（複用手動選股 _ms_checked 機制）
    def _build_manual_select_tab(self, parent):
        """建立「手動選股」Tab 的 UI"""
        # ---- 上方：狀態列 ----
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill="x", padx=8, pady=(6, 0))
        self._ms_status = tk.StringVar(value="請先執行一次「策略回測」以載入市場資料，或直接點「選股」從 FinMind 抓取最新資料")
        ttk.Label(status_frame, textvariable=self._ms_status,
                  foreground="#555555", font=("Helvetica", 9)).pack(anchor="w")

        # 進度條（默認隱藏，選股中才顯示）
        self._ms_progress = ttk.Progressbar(status_frame, mode='determinate', length=200)
        self._ms_progress.pack(anchor="w", pady=(2, 0))
        self._ms_progress.pack_forget()

        # ---- 主區：左側條件 + 右側結果 ----
        paned = ttk.PanedWindow(parent, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=6, pady=6)

        # ── 左面板：篩選條件 + Preset + 按鈕 ──
        # 【v1.0-scrollfix 改】2026-06-19 22:12 William 反映：
        # 「window size 不夠大、手動選股左邊欄位沒有全部顯示時請提供 scroll bar 可以 scroll」
        # 原實作 left_frame = ttk.LabelFrame(paned) → widget 比視窗高就被裁掉
        # 改為：外層 left_container（含 Canvas + scrollbar）→ 內層 left_frame（LabelFrame）
        left_container = ttk.Frame(paned)
        paned.add(left_container, weight=0)

        # Canvas + scrollbar（參考策略參數 Tab 的 scroll pattern）
        left_canvas = tk.Canvas(left_container, width=380, highlightthickness=0)
        left_scrollbar = ttk.Scrollbar(left_container, orient="vertical", command=left_canvas.yview)
        left_canvas.configure(yscrollcommand=left_scrollbar.set)
        left_scrollbar.pack(side="right", fill="y")
        left_canvas.pack(side="left", fill="both", expand=True)

        # 滑鼠滾輪支援（Fix16 2026-06-21: 用 Enter/Leave 動態 bind_all，避免跟其他 tab 的滾輪事件衝突）
        def _on_canvas_enter(_e):
            left_canvas.bind_all("<MouseWheel>", lambda ev: left_canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units"))
            left_canvas.bind_all("<Button-4>", lambda _ev: left_canvas.yview_scroll(-1, "units"))
            left_canvas.bind_all("<Button-5>", lambda _ev: left_canvas.yview_scroll(1, "units"))

        def _on_canvas_leave(_e):
            left_canvas.unbind_all("<MouseWheel>")
            left_canvas.unbind_all("<Button-4>")
            left_canvas.unbind_all("<Button-5>")

        left_canvas.bind("<Enter>", _on_canvas_enter)
        left_canvas.bind("<Leave>", _on_canvas_leave)

        # 真正的內容在 left_frame 裡、embed 到 canvas
        left_frame = ttk.LabelFrame(left_canvas, text="🔎 篩選條件", padding=8)
        left_canvas.create_window((0, 0), window=left_frame, anchor="nw")
        left_frame.bind(
            "<Configure>",
            lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all")),
        )
        # left_frame 建好之後才 bind Enter/Leave（避免 UnboundLocalError）
        left_frame.bind("<Enter>", _on_canvas_enter)
        left_frame.bind("<Leave>", _on_canvas_leave)

        # Preset 管理
        preset_top = ttk.Frame(left_frame)
        preset_top.pack(fill="x", pady=(0, 8))
        ttk.Label(preset_top, text="Preset：", font=("Helvetica", 9, "bold")).pack(side="left")
        self._ms_preset_var = tk.StringVar(value="")
        self._ms_preset_combo = ttk.Combobox(preset_top, textvariable=self._ms_preset_var,
                                             state="readonly", width=14)
        self._ms_preset_combo.pack(side="left", padx=4)
        self._ms_preset_combo.bind("<<ComboboxSelected>>", lambda e: self._ms_load_preset())
        ttk.Button(preset_top, text="💾 儲存", width=5,
                   command=self._ms_save_preset).pack(side="left", padx=1)
        ttk.Button(preset_top, text="🗑 刪", width=4,
                   command=self._ms_delete_preset).pack(side="left", padx=1)

        # 篩選條件 Entry（每列：[checkbox] [label] [Entry]）
        # 格式：(label_text, config_key, default_value, skip_value, unit)
        self._ms_filter_vars = {}
        self._ms_filter_defaults = {
            "min_rev_yoy":      (10.0,  None,  "% YoY"),
            "min_stock_div":    (0.0,   None,  "元/股"),
            "min_cash_div_yld": (1.0,   None,  "%殖利率"),
            "min_pe":           (30.0,  None,  "倍"),
            "min_price":        (10.0,  None,  "元"),
            "min_volume":       (100.0, None,  "張/月均"),
            "min_last_stock_div":(0.0,  None,  "元/股"),
            "min_last_cash_yld":(1.0,   None,  "%殖利率"),
        }
        filter_labels = {
            "min_rev_yoy":      "累計營收 YoY ≥",
            "min_stock_div":    "今年股票股利 ≥",
            "min_cash_div_yld": "今年現金殖利率 ≥",
            "min_pe":           "本益比 (PE) ≤",
            "min_price":        "現價 ≥",
            "min_volume":       "月均成交量 ≥",
            "min_last_stock_div":"去年股票股利 ≥",
            "min_last_cash_yld":"去年現金殖利率 ≥",
        }

        def _add_filter_row(parent, label, key, default_val, skip_val, unit):
            row = ttk.Frame(parent)
            row.pack(fill="x", pady=2)
            var = tk.BooleanVar(value=False)
            cb = ttk.Checkbutton(row, variable=var)
            cb.pack(side="left")
            ttk.Label(row, text=label, width=20).pack(side="left")
            entry_var = tk.DoubleVar(value=default_val)
            ttk.Entry(row, textvariable=entry_var, width=8).pack(side="left")
            ttk.Label(row, text=unit, width=7).pack(side="left")
            self._ms_filter_vars[key] = (var, entry_var, skip_val)

        for key, (default, skip, unit) in self._ms_filter_defaults.items():
            _add_filter_row(left_frame, filter_labels[key], key, default, skip, unit)

        # 結果上限
        limit_row = ttk.Frame(left_frame)
        limit_row.pack(fill="x", pady=(6, 0))
        ttk.Label(limit_row, text="結果上限：", width=20).pack(side="left")
        self._ms_limit_var = tk.IntVar(value=500)
        ttk.Entry(limit_row, textvariable=self._ms_limit_var, width=8).pack(side="left")
        ttk.Label(limit_row, text="檔", width=7).pack(side="left")

        # 按鈕
        btn_row = ttk.Frame(left_frame)
        btn_row.pack(fill="x", pady=(12, 0))
        ttk.Button(btn_row, text="🔍 開始選股",
                   command=self._ms_run_selection).pack(fill="x", pady=1)
        # 【v1.0-cleanup1】2026-06-19 William 決定：
        #   手動選股一律用 cache 的收盤價、不需要「即時抓股價」checkbox
        #   → 看即時 tick 改去「買賣紀錄」Tab（有 30 秒 polling）
        #   → 想強制重抓 cache 用「🔄 重新抓股價」按鈕即可
        #   連帶拿掉：TWSE 速率模式 radio（配 checkbox 用的、失去意義）
        # V0.9.5: 手動重抓股價（背景跑中就跳過）
        ttk.Button(btn_row, text="🔄 重新抓股價",
                   command=self._ms_force_refresh_price).pack(fill="x", pady=1)
        self._ms_price_status = tk.StringVar(value="股價未抓取")
        ttk.Label(btn_row, textvariable=self._ms_price_status,
                  font=("Helvetica", 8), foreground="#666666").pack(anchor="w", pady=(0, 4))
        # V0.9.5+: 指定股補抓（Free tier 適用：手動輸入股號、只要用少數 API 額度）
        # 順序放在 💰 上面（推薦用法：只抓關心的）
        ttk.Button(btn_row, text="🎯 指定股補抓 (推薦 Free tier)",
                   command=self._ms_fetch_specific_dividend).pack(fill="x", pady=1)
        # V0.9.5+: 掃描全部股票 (100檔/次) — 一個月一個月慢慢補、按次分批避免 Free tier 爆 402
        ttk.Button(btn_row, text="💰 掃描全部股票 (100檔/次)",
                   command=self._ms_fetch_all_dividend).pack(fill="x", pady=1)
        self._ms_dividend_status = tk.StringVar(value="股利 DB: 計算中...")
        ttk.Label(btn_row, textvariable=self._ms_dividend_status,
                  font=("Helvetica", 8), foreground="#666666").pack(anchor="w", pady=(0, 4))
        # 【V0.9.5-tab-split-phase3-E】2026-06-22 William 反映：
        #   結果畫面勾選欄 header 已是 ☐/☑/▣ 動態 checkbox、可點全選/全不選
        #   參數區的全選/全不選按鈕重複、拿掉
        #   （_ms_select_all / _ms_select_none methods 保留、header click 仍會叫）
        # 【V0.9.5-tab-split-phase3-G】2026-06-22 William 反映：
        #   匯出按鈕從左邊參數區移到右上面板右邊、跟系統選股一致
        #   文字統一「💾 匯出股票清單」

        # ── 右面板：title + export 按鈕 + Treeview（跟系統選股同結構）──
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)

        # 右上面板：title 左邊、export 按鈕右邊
        right_top = ttk.Frame(right_frame)
        right_top.pack(fill="x", pady=(0, 5))
        ttk.Label(right_top, text="📊 篩選結果",
                  font=("Segoe UI", 11, "bold")).pack(side="left", anchor="w")
        # 【V0.9.5-tab-split-phase3-G】跟 select_tab 同名、同位置
        self.export_ms_btn = ttk.Button(
            right_top,
            text="💾 匯出股票清單",
            command=self._ms_export_excel,
            state="disabled",
        )
        self.export_ms_btn.pack(side="right")

        # Treeview 子 frame
        tree_frame = ttk.Frame(right_frame)
        tree_frame.pack(fill="both", expand=True)

        # Treeview with checkbox
        # 【V0.9.5+ Phase 8 修 Bug】2026-06-15 William 反映：
        #   殖利率沒對照到原始股利金額、無法驗算是否正確
        #   修法：加「今現金」/「去年現金」欄位（股利金額，原始股數）
        #   並修正之前 key 錯位（找「今年股票股利(元)」但欄位是「今年股票股利」）
        # 【V0.9.5-twser3 修 Bug】2026-06-18 William 反映：
        #   1. 「今股票殖%」/「去年股票殖%」拿掉（不需要看股票殖利率）
        # 【V0.9.5-goodinfo4+5 修 Bug】2026-06-18 18:12 William 反映：
        #   1. 「成交量不是我要的今日成交量」→ 拿掉盤中/收盤後切換、直接顯示 price_df 的「成交量(張)」
        #   2. 「順便將篩選結果依照營收累計YoY由大到小排序」→ 主排序改為營收累計YoY 降序
        cols = ("勾選","代號","名稱","現價","累計YoY%",
                "今股票","今現金","今現金殖%",
                "PE","成交量(張)",
                "去年股票","去年現金","去年現金殖%",
                "資料日期")
        self._ms_tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                     selectmode="none", height=25)
        # 14 欄（拿掉 2 個股票殖利率 + 加 1 個資料日期）：原本 15 欄 - 2 + 1 = 14
        col_widths = (40, 60, 100, 70, 70, 60, 60, 80,
                      50, 80, 60, 60, 80,
                      90)
        for col, w in zip(cols, col_widths):
            self._ms_tree.heading(col, text=col)
            self._ms_tree.column(col, width=w, anchor="center")

        # 【V0.9.5-tab-split-phase3-D】初始 header 設為 ☐（看起來像個 checkbox）
        try:
            self._ms_tree.heading(cols[0], text="☐")
        except (IndexError, tk.TclError):
            pass

        ms_scroll_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self._ms_tree.yview)
        ms_scroll_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=self._ms_tree.xview)
        self._ms_tree.configure(yscrollcommand=ms_scroll_y.set, xscrollcommand=ms_scroll_x.set)
        self._ms_tree.pack(side="left", fill="both", expand=True)
        ms_scroll_y.pack(side="right", fill="y")
        ms_scroll_x.pack(side="bottom", fill="x")

        # 【v1.0-hover 新增】2026-06-19 William 要求：
        # 滑鼠移到某 row 時、整列黃色 highlight、移走取消
        # 實現方式：建立 _hover iid 變數。
        #   - Motion 進新 row 時：把 _hover 設為該 iid、用 item.configure(tag) 動態改 tag
        #   - Leave 或 Motion 到別的 row：清掉 _hover、該 row 設回原本 tag
        # 注意：ttk.Treeview 多 tag 只取第一個生效、所以只動態切換 tag 字串。
        self._ms_tree.tag_configure("checked", background="#d0e8ff")
        self._ms_tree.tag_configure("unchecked", background="#ffffff")
        self._ms_tree.tag_configure("hover", background="#fff3a0")
        self._ms_hover_iid = None  # 記住目前 hover 的 row iid（若有）
        self._ms_tree.bind("<Motion>", self._on_tree_hover)
        self._ms_tree.bind("<Leave>", self._on_tree_leave)

        # Click to toggle checkbox
        self._ms_tree.bind("<Button-1>", self._ms_toggle_check)
        self._ms_tree.bind("<Motion>", self._ms_tree_hover)
        self._ms_tree.bind("<Leave>", self._ms_tree_leave)
        # 【V0.9.5-tab-split-phase3-F】拿掉右鍵「全選/全不選」選單
        # 原本：
        #   self._ms_tree.bind("<Button-3>", self._ms_tree_rclick)  # 原本是 dead code、被下面那行覆蓋
        #   self._ms_tree.bind("<Button-3>", self._ms_show_context_menu)
        # 為什麼拿：header 已是 ☐/☑/▣ 動態 checkbox、右鍵選單重複

        # 初始化：先 refresh preset 下拉（自動選中上次的）、再載入
        # 【V0.9.5+ Phase 7 修 Bug】2026-06-15 William 反映：
        #   儲存 preset 後重開 App 找不到儲存資料
        #   根因：_ms_preset_var 預設空字串、_ms_load_preset 拿空字串會早退
        #   修法：先呼叫 _ms_refresh_preset_list 把 manual_select_last_preset 設進 var
        self._ms_refresh_preset_list()
        self._ms_load_preset()
        self._ms_refresh_pipeline_status()
        self._ms_refresh_dividend_status()

    def _ms_refresh_pipeline_status(self):
        """更新狀態列：顯示 pipeline 資料是否已載入"""
        has_price = hasattr(self, '_price_df') and self._price_df is not None and not self._price_df.empty
        has_revenue = hasattr(self, '_revenue_df') and self._revenue_df is not None and not self._revenue_df.empty
        has_eps = hasattr(self, '_eps_df') and self._eps_df is not None and not self._eps_df.empty

        status = []
        if has_price: status.append(f"股價({len(self._price_df)}筆)")
        if has_revenue: status.append(f"營收({len(self._revenue_df)}筆)")
        if has_eps: status.append(f"EPS({len(self._eps_df)}筆)")

        if status:
            self._ms_status.set("✅ Pipeline 資料已就緒：" + " / ".join(status) +
                               "｜可直接選股，或點「選股」從 FinMind 實時抓取")
        else:
            self._ms_status.set("⚠️ Pipeline 尚未執行｜點「選股」將從 FinMind 即時抓取市場資料")

    def _ms_get_filters(self) -> dict:
        """從 UI 讀取目前的篩選條件，回傳 dict。"""
        f = {}
        for key, (cb_var, entry_var, skip_val) in self._ms_filter_vars.items():
            if cb_var.get():  # 有勾選
                f[key] = entry_var.get()
            else:
                f[key] = skip_val  # None = skip
        f["top_n"] = self._ms_limit_var.get()
        return f

    # ==========================================================
    # V0.9.5: 背景重抓股價（啟動時 + 手動按鈕）
    # ==========================================================
    def _startup_bg_fetch_price(self):
        """App 啟動 0.8s 後背景重抓股價（跳過選項：pipeline 剛抓過且是今天）
        - 用 get_or_fetch：meta last_update == today → 用 cache、不抓
        - 反之走 fetch_prices 重抓、寫回 cache
        - 重抓中使用者點「重新抓股價」按鈕 → 旗標判斷跳過
        """
        if self._bg_price_fetching:
            return
        self._bg_price_fetching = True
        self._ms_price_status.set("🔄 背景抓取股價中（啟動時自動）...")
        self._ms_status.set("🔄 背景重抓股價中（啟動時自動、跳過今天已抓的 cache）...")

        def _bg_worker():
            try:
                _s = build_session()
                # get_or_fetch 內部會判斷 meta last_update == today
                df = get_or_fetch("price", lambda: fetch_prices(_s, self.cfg), self.logger)
                self.after(0, lambda: self._on_bg_price_done(df, source="啟動時自動"))
            except Exception as e:
                self.after(0, lambda err=str(e): self._on_bg_price_err(err, source="啟動時自動"))

        threading.Thread(target=_bg_worker, daemon=True).start()

    def _ms_force_refresh_price(self):
        """手動選股 Tab「🔄 重新抓股價」按鈕
        - 若背景正在抓 → 跳過、提示使用者（避免重複打 FinMind）
        - 反之強制重抓（不走 cache）
        """
        if self._bg_price_fetching:
            self._ms_status.set("⏳ 背景抓取股價中｜按鈕已跳過、請稍候...")
            self.logger.log("⏳ 背景抓股價中，手動按鈕跳過（避免重複打 FinMind）")
            return

        self._bg_price_fetching = True
        self._ms_status.set("🔄 手動重抓股價中（強制重抓、不走 cache）...")
        self._ms_price_status.set("🔄 抓取中...")

        def _force_worker():
            try:
                _s = build_session()
                # 強制重抓：直接呼叫 fetch_prices（不查 cache）
                df = fetch_prices(_s, self.cfg)
                # 寫回 cache（更新 meta last_update = today）
                save_cache(get_cache_file("price"), df)
                self.after(0, lambda: self._on_bg_price_done(df, source="手動重抓"))
            except Exception as e:
                self.after(0, lambda err=str(e): self._on_bg_price_err(err, source="手動重抓"))

        threading.Thread(target=_force_worker, daemon=True).start()

    def _on_bg_price_done(self, df, source: str = ""):
        """背景重抓股價完成（不論啟動或手動）→ 更新 GUI"""
        self._bg_price_fetching = False
        if df is not None and not df.empty:
            self._price_df = df
            self._price_last_update = datetime.now()
            self._update_price_status_label()
            # 【v1.0-info】順手加股價更新時間到 status bar
            # 讓使用者不管在哪個 Tab 都看得到「最後更新時間」
            update_str = self._price_last_update.strftime("%Y-%m-%d %H:%M:%S")
            # 【v1.0-info】順手顯示 cache 的 data_date（個股最後交易日）
            # 若 df 有 data_date 欄位且有資料，顯示該日期
            data_date_hint = ""
            try:
                if "data_date" in df.columns:
                    _dates = df["data_date"].dropna().astype(str)
                    _dates = _dates[_dates != ""]
                    if not _dates.empty:
                        _latest = _dates.iloc[0]
                        # 如果有多个不同日期、顯示範圍
                        _unique_dates = sorted(set(_dates.tolist()))
                        if len(_unique_dates) == 1:
                            data_date_hint = f"｜資料日期：{_latest}"
                        else:
                            data_date_hint = f"｜資料日期：{_unique_dates[0]} ~ {_unique_dates[-1]}"
            except Exception:
                pass
            # 【v1.0-vol-fix】2026-06-19 18:50 William 反映：
            # 手動重抓股價完成後、Treeview 不會自動更新（要按「選股」才會 refresh）
            # 看起來「什麼都沒變」、使用者誤以為重抓失敗。
            # 修法：手動重抓完成時、如果 Treeview 已有結果 → 自動重跑選股 refresh Treeview。
            auto_rerun = (
                source == "手動重抓"
                and self._ms_tree is not None
                and self._ms_tree.get_children()  # Treeview 有結果才重跑
            )
            if auto_rerun:
                self._ms_status.set(
                    f"✅ {source}完成：{len(df)} 筆、股價更新：{update_str}{data_date_hint}"
                    f"｜正在自動重跑選股以 refresh 結果..."
                )
                self.logger.log(
                    f"✅ {source}完成：{len(df)} 筆、股價更新：{update_str}{data_date_hint}"
                    f"｜自動重跑選股中..."
                )
                self.after(100, self._ms_run_selection)
            else:
                self._ms_status.set(
                    f"✅ 股價資料就緒（{source}、{len(df)} 筆）｜股價更新：{update_str}{data_date_hint}｜可點「選股」"
                )
                self.logger.log(f"✅ {source}股價完成：{len(df)} 筆、股價更新：{update_str}{data_date_hint}")
        else:
            self._ms_status.set(f"⚠️ {source}股價完成但無資料")
            self.logger.log(f"⚠️ {source}股價完成但無資料")

    def _on_bg_price_err(self, err: str, source: str = ""):
        """背景重抓股價失敗 → log + 更新狀態列（不阻擋使用者）"""
        self._bg_price_fetching = False
        self._ms_price_status.set(f"⚠️ {source}失敗：{err[:40]}")
        self._ms_status.set(f"⚠️ {source}股價失敗：{err}（可手動重試）")
        self.logger.log(f"⚠️ {source}股價失敗：{err}")

    def _update_price_status_label(self):
        """更新手動選股 Tab 的「股價更新時間」label"""
        if self._price_last_update:
            self._ms_price_status.set(
                f"股價更新：{self._price_last_update.strftime('%Y-%m-%d %H:%M:%S')}"
            )

    # ==========================================================
    # V0.9.5: 一次性補抓全部股利（避免每次選股都打 FinMind）
    # ==========================================================
    def _ms_refresh_dividend_status(self):
        """更新股利 DB 狀態 label：顯示「股利 DB: 351/2374 檔（缺漏 2023）」"""
        try:
            _init_div_history_db("dividend_history.db")
            price_df = getattr(self, "_price_df", None)
            if price_df is None or price_df.empty:
                # fallback: 從 price cache 讀
                for p in ["cache/price.xlsx", "source/cache/price.xlsx"]:
                    if os.path.exists(p):
                        try:
                            price_df = pd.read_excel(p, sheet_name="data", engine="openpyxl")
                            break
                        except Exception:
                            pass
            if price_df is None or price_df.empty:
                self._ms_dividend_status.set("股利 DB: 無法計算（未抓到股價名單）")
                return
            all_codes = price_df["股票代號"].astype(str).str.strip().tolist()
            cached = _query_div_history("dividend_history.db", all_codes)
            in_db = len(cached)
            total = len(all_codes)
            missing = total - in_db

            # 讀取每日排程最後抓取時間
            last_fetch = ""
            for p in [".tmp/dividend_last_fetch.txt",
                      "../.tmp/dividend_last_fetch.txt",
                      os.path.join(os.path.dirname(os.path.dirname(__file__)), ".tmp", "dividend_last_fetch.txt")]:
                if os.path.exists(p):
                    try:
                        with open(p) as f:
                            ts = f.read().strip()
                        if ts:
                            # 格式化：只取 日期 和 時:分
                            parts = ts.split()
                            if len(parts) >= 2:
                                last_fetch = f"｜自動抓取 {parts[0]} {parts[1]}"
                            break
                    except Exception:
                        pass

            if missing == 0:
                self._ms_dividend_status.set(f"股利 DB: ✅ {in_db}/{total} 檔（全部就絡）{last_fetch}")
            else:
                self._ms_dividend_status.set(f"股利 DB: {in_db}/{total} 檔（缺漏 {missing}）{last_fetch}")
        except Exception as e:
            self._ms_dividend_status.set(f"股利 DB: 查詢失敗 {str(e)[:30]}")

    # V0.9.5+: 「💰 掃描全部股票」分批參數
    _MS_SCAN_BATCH = 100  # 每批 100 檔（Free tier 300-1000 筆/月額度友善）

    def _ms_fetch_all_dividend(self):
        """手動選股 Tab「💰 掃描全部股票 (100檔/次)」按鈕
        - 從 price_df 取所有股票代號
        - 比對 DB，只補抓缺漏中的「前 100 檔」
        - 一個月一個月慢慢補：跑完停、下次再按繼續抓下一批
        - 全部抓完後股利 DB 完整、可發現關注清單外的標的
        """
        # 避免重複
        if getattr(self, "_ms_dividend_fetching", False):
            self._ms_status.set("⏳ 掃描股利中，請稍候...")
            return

        # 計算缺漏數
        self._ms_refresh_dividend_status()
        cur = self._ms_dividend_status.get()
        if "缺漏 0" in cur or "全部就絡" in cur:
            self._ms_status.set("✅ 股利 DB 完整、無需補抓")
            return

        # 解析缺漏數（從 status label 抓數字）
        import re as _re_scan
        m = _re_scan.search(r"缺漏\s*(\d+)", cur)
        missing = int(m.group(1)) if m else 0
        if missing <= 0:
            self._ms_status.set("✅ 股利 DB 完整、無需補抓")
            return

        # 分批計算
        batch = self._MS_SCAN_BATCH
        this_batch = min(batch, missing)
        runs_left_total = (missing + batch - 1) // batch  # 含這次

        # 確認
        if not messagebox.askyesno(
            "確認掃描股利",
            f"這次會從 FinMind 掃描補抓 {this_batch} 檔股利寫入本地 DB。\n\n"
            f"目前狀態：{cur}\n\n"
            f"📦 分批設定：{batch} 檔/次\n"
            f"⏱️ 預計 {int(this_batch * 0.4) + 1} 秒、{this_batch} 筆 API 額度\n"
            f"🔁 全部補完約需再按 {runs_left_total} 次（可分散在不同天）\n\n"
            f"💡 Free tier 額度 300-1000 筆/月，建議一天最多跑 1-2 次\n"
            f"💡 想只抓關注個股可用「🎯 指定股補抓」更省額度\n\n"
            f"按「Yes」開始，期間可按「取消」中斷。",
        ):
            return

        self._ms_dividend_fetching = True
        self._ms_status.set(f"🔄 掃描股利中（{this_batch}/{missing} 檔、請勿關 App）...")

        # 取得所有股票代號
        price_df = getattr(self, "_price_df", None)
        if price_df is None or price_df.empty:
            for p in ["cache/price.xlsx", "source/cache/price.xlsx"]:
                if os.path.exists(p):
                    try:
                        price_df = pd.read_excel(p, sheet_name="data", engine="openpyxl")
                        break
                    except Exception:
                        pass
        if price_df is None or price_df.empty:
            self._ms_dividend_fetching = False
            self._ms_status.set("❌ 掃描失敗：未取得股價名單（請先點「重抓股價」）")
            return
        all_codes = price_df["股票代號"].astype(str).str.strip().tolist()

        def _fetch_worker():
            try:
                # 背景補抓：給 progress_callback 讓 UI 更新
                def _progress(done, total):
                    self.after(0, lambda d=done, t=total: self._ms_status.set(
                        f"🔄 掃描股利中... {d}/{t}（{int(d/t*100)}%）"
                    ))

                # 【v1.1 重構】用模組存取取代直接名稱、避免 monkeypatch st_fetch_market 後找不到
                from stocktool import fetch_market as _fm_bg_scan
                added = _fm_bg_scan._background_fetch_all_dividend(
                    all_codes, db_path="dividend_history.db",
                    progress_callback=_progress, batch_size=batch,
                )
                self.after(0, lambda: self._on_dividend_fetch_done(added))
            except Exception as e:
                self.after(0, lambda err=str(e): self._on_dividend_fetch_err(err))

        threading.Thread(target=_fetch_worker, daemon=True).start()

    def _on_dividend_fetch_done(self, added: int):
        """補抓股利完成（💰 掃描全部股票 / 🎯 指定股補抓 共用）
        - 重新 refresh DB 狀態 → 算出剩餘缺漏
        - 顯示「這次 +X 檔｜剩 Y 檔（再 N 次可補完）」
        """
        self._ms_dividend_fetching = False
        self._ms_refresh_dividend_status()
        cur = self._ms_dividend_status.get()
        if added == -1:
            # FinMind 額度用完（_background_fetch_all_dividend 回傳 -1）
            self._ms_status.set(
                "❌ 補抓中斷：FinMind 額度用完（status 402）｜"
                "已補抓的資料已寫入 DB"
            )
            self.logger.log("❌ 補抓股利中斷：FinMind 額度用完（status 402）")
            return
        # 從 cur 抓剩餘缺漏（regex）
        import re as _re_done
        m = _re_done.search(r"缺漏\s*(\d+)", cur)
        remaining = int(m.group(1)) if m else 0
        if remaining == 0:
            # 全部完成
            self._ms_status.set(f"✅ 補抓股利完成：新增 {added} 檔｜{cur}")
            self.logger.log(f"✅ 補抓股利完成：新增 {added} 檔（全部就絡）")
        else:
            # 還有缺漏、告訴使用者還要按幾次
            batch = self._MS_SCAN_BATCH
            runs_left = (remaining + batch - 1) // batch
            self._ms_status.set(
                f"✅ 這次補 {added} 檔｜剩 {remaining} 檔（再按 {runs_left} 次可補完）｜{cur}"
            )
            self.logger.log(f"✅ 補抓股利：這次 +{added}｜剩 {remaining} 檔（{runs_left} 次可補完）")
        # 自動重跑選股（讓使用者直接看到補抓後的結果）
        self._ms_run_selection()

    def _on_dividend_fetch_err(self, err: str):
        """補抓股利失敗"""
        self._ms_dividend_fetching = False
        self._ms_status.set(f"❌ 補抓股利失敗：{err}（可重試）")
        self.logger.log(f"❌ 補抓股利失敗：{err}")

    def _ms_fetch_specific_dividend(self):
        """手動選股 Tab「🎯 指定股補抓」按鈕

        適用情境：FinMind Free tier 額度不夠一次抓全部
        流程：
          1. 跳出輸入框（多行、可貼上「2330, 2454, 2317」這類格式）
          2. 解析股號、只抓那些
          3. 寫入 DB、狀態列顯示進度
        """
        if getattr(self, "_ms_dividend_fetching", False):
            self._ms_status.set("⏳ 補抓股利中，請稍候...")
            return

        # 對話框：可輸入多行股號（逗號、空格、換行分隔）
        from tkinter import simpledialog
        default = "2330, 2454, 2317"  # 台積電、聯發科、鴻海
        codes_raw = simpledialog.askstring(
            "指定股補抓股利",
            "請輸入要補抓的股號（可貼上）：\n"
            "格式：「2330, 2454, 2317」或一行一個\n"
            "限 1-100 檔（超過 100 不收）",
            initialvalue=default,
            parent=self.manual_select_tab,
        )
        if not codes_raw:
            return

        # 解析
        import re as _re_codes
        codes = [c.strip() for c in _re_codes.split(r"[\s,，]+", codes_raw) if c.strip()]
        # 限 100 檔
        if len(codes) > 100:
            messagebox.showwarning("超過限制", f"只取前 100 檔（你輸入 {len(codes)} 檔）")
            codes = codes[:100]
        if not codes:
            messagebox.showwarning("無股號", "請至少輸入 1 個股號")
            return

        # 看哪些不在 DB
        _init_div_history_db("dividend_history.db")
        cached = _query_div_history("dividend_history.db", codes)
        to_fetch = [c for c in codes if c not in cached]
        if not to_fetch:
            messagebox.showinfo("無需補抓", f"這 {len(codes)} 檔都已在 DB 中，無需補抓")
            return

        if not messagebox.askyesno(
            "確認補抓",
            f"將補抓 {len(to_fetch)} 檔股利到本地 DB。\n"
            f"（{len(codes) - len(to_fetch)} 檔已在 DB 跳過）\n\n"
            f"預計需要 {int(len(to_fetch) * 0.4) + 1} 秒、{len(to_fetch)} 筆 API 額度。",
        ):
            return

        self._ms_dividend_fetching = True
        self._ms_status.set(f"🔄 指定股補抓中（{len(to_fetch)} 檔）...")

        def _fetch_worker():
            try:
                def _progress(done, total):
                    self.after(0, lambda d=done, t=total: self._ms_status.set(
                        f"🔄 指定股補抓中... {d}/{t}（{int(d/t*100)}%）"
                    ))

                # 【v1.1 重構】用模組存取取代直接名稱、避免 monkeypatch st_fetch_market 後找不到
                from stocktool import fetch_market as _fm_bg_specific
                added = _fm_bg_specific._background_fetch_all_dividend(
                    to_fetch, db_path="dividend_history.db", progress_callback=_progress,
                )
                self.after(0, lambda: self._on_dividend_fetch_done(added))
            except Exception as e:
                self.after(0, lambda err=str(e): self._on_dividend_fetch_err(err))

        threading.Thread(target=_fetch_worker, daemon=True).start()

    def _ms_run_selection(self):
        """點「選股」：抓取資料 → 篩選 → 顯示結果"""
        # V0.9.5: 背景抓股價中→跳過避免重複打 FinMind
        if self._bg_price_fetching:
            self._ms_status.set("⏳ 背景抓股價中，請稍候再點「選股」...")
            self.logger.log("⏳ 背景抓股價中，「選股」跳過（避免重複打 FinMind）")
            return
        # V0.9.5: 背景補抓股利中→跳過
        if getattr(self, "_ms_dividend_fetching", False):
            self._ms_status.set("⏳ 補抓股利中，請稍候再點「選股」...")
            self.logger.log("⏳ 補抓股利中，「選股」跳過")
            return

        filters = self._ms_get_filters()
        top_n = filters.pop("top_n", 500)

        # 顯示進度條
        self._ms_progress.pack(anchor="w", pady=(2, 0))
        self._ms_progress["value"] = 0
        self._ms_status.set("🔄 抓取資料中，請稍候...")
        self._ms_tree.delete(*self._ms_tree.get_children())
        self.update_idletasks()

        # 啟動進度輪詢 timer
        self._ms_poll_running = True
        self._ms_poll_progress()

        def _do():
            try:
                # 優先用 pipeline 快取
                price_df = getattr(self, '_price_df', None)
                revenue_df = getattr(self, '_revenue_df', None)
                eps_df = getattr(self, '_eps_df', None)

                # 【v1.0-cleanup1】2026-06-19 William 決定：
                #   手動選股一律用 cache 的收盤價、不再提供「即時抓股價」選項
                #   → 拿掉舊的「即時抓股價」if 分支（原本用 TWSE 即時 API 抓）
                #   → 仍保留「🔄 重新抓股價」按鈕（強制重抓 cache 用、走正常 fetch_prices）
                # 詳見上方按鈕區註解


                # fallback 1：若 GUI 沒記、但 cache/ 有 → 讀 cache
                # 注：讀 cache 前先檢查 last_update；若 != today 就走 get_or_fetch 重抓
                #     （避免六日不開盤下「last_update 是昨天 = today」就誤判過期）
                from datetime import datetime as _dt
                _today = _dt.now().strftime("%Y-%m-%d")
                def _is_cache_fresh(path):
                    """【V0.9.5-goodinfo4+5 容錯】2026-06-18 22:07 William 反映
                    meta sheet 不存在時、視為「剛抓的」(return True)
                    → 不會走重抓路徑、不會卡 meta not found
                    """
                    try:
                        _meta = pd.read_excel(path, sheet_name="meta", engine="openpyxl")
                        _last = str(_meta.loc[0, "last_update"])
                        return _last >= _today   # 含今天（避免跨交易日誤判）
                    except Exception:
                        # 舊 cache 沒 meta sheet → 視為剛抓的
                        return True
                if price_df is None or price_df.empty:
                    for p in ["cache/price.xlsx", "source/cache/price.xlsx"]:
                        if os.path.exists(p):
                            if _is_cache_fresh(p):
                                try:
                                    price_df = pd.read_excel(p, sheet_name="data", engine="openpyxl")
                                    print(f"✅ 讀 price cache (last_update={pd.read_excel(p, sheet_name='meta', engine='openpyxl').loc[0, 'last_update']}): {len(price_df)} 筆")
                                    break
                                except Exception:
                                    pass
                            else:
                                # cache 過期 → 走 get_or_fetch 重抓（會自動寫回 cache）
                                try:
                                    _s = build_session()
                                    price_df = get_or_fetch("price", lambda: fetch_prices(_s, self.cfg), self.logger)
                                    print(f"♻️ price cache 過期 → 重抓 {len(price_df)} 筆")
                                    break
                                except Exception as _e:
                                    print(f"⚠️ price 重抓失敗：{_e} → fallback 讀舊 cache")
                                    try:
                                        price_df = pd.read_excel(p, sheet_name="data", engine="openpyxl")
                                        print(f"✅ 讀 price cache (舊): {len(price_df)} 筆")
                                        break
                                    except Exception:
                                        pass
                if revenue_df is None or revenue_df.empty:
                    for p in ["cache/revenue.xlsx", "source/cache/revenue.xlsx"]:
                        if os.path.exists(p):
                            try:
                                revenue_df = pd.read_excel(p, sheet_name="data", engine="openpyxl")
                                print(f"✅ 讀 revenue cache: {len(revenue_df)} 筆")
                                break
                            except Exception:
                                pass
                if eps_df is None or eps_df.empty:
                    for p in ["cache/eps.xlsx", "source/cache/eps.xlsx"]:
                        if os.path.exists(p):
                            try:
                                eps_df = pd.read_excel(p, sheet_name="data", engine="openpyxl")
                                print(f"✅ 讀 eps cache: {len(eps_df)} 筆")
                                break
                            except Exception:
                                pass

                result = _run_manual_selection(
                    price_df=price_df if (price_df is not None and not price_df.empty) else pd.DataFrame(),
                    revenue_df=revenue_df if (revenue_df is not None and not revenue_df.empty) else pd.DataFrame(),
                    eps_df=eps_df if (eps_df is not None and not eps_df.empty) else pd.DataFrame(),
                    filters=filters,
                    top_n=top_n,
                )
                self._ms_result_df = result
                self._ms_poll_running = False
                self.after(0, lambda: self._ms_display_results(result))
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                # 完整訊息寫到主 console（背景 thread 也能輸出）
                print(f"[手動選股失敗] {e}\n{tb}")
                err_msg = f"❌ 選股失敗：{e}\n{tb.splitlines()[-1] if tb else ''}"
                self._ms_poll_running = False
                self.after(0, lambda msg=err_msg: self._ms_status.set(msg))

        threading.Thread(target=_do, daemon=True).start()

    def _ms_poll_progress(self):
        """每 0.5 秒更新狀態列 + 進度條"""
        if not getattr(self, '_ms_poll_running', False):
            self._ms_progress.pack_forget()
            return
        stage = _MS_PROGRESS.get("stage", "")
        done = _MS_PROGRESS.get("done", 0)
        total = _MS_PROGRESS.get("total", 0)
        err = _MS_PROGRESS.get("error", "")
        if err:
            # V0.9.5+ 強化 402 額度提示
            if "402" in err or "額度" in err:
                self._ms_status.set(
                    f"❌ FinMind 額度用完（status 402）｜已完成 {done}/{total} 檔｜"
                    f"已寫入的資料已保存｜💡 請下月重置後再跑或升級 plan"
                )
            else:
                self._ms_status.set(f"❌ {err[:80]}")
        elif total > 0:
            pct = min(100, int(done / total * 100))
            self._ms_progress["value"] = pct
            self._ms_status.set(f"🔄 抓取{stage}中... {done}/{total} ({pct}%)")
        else:
            self._ms_status.set(f"🔄 準備抓取{stage}...")
        self.after(500, self._ms_poll_progress)

    def _ms_display_results(self, result):
        """把 DataFrame 顯示在 Treeview 上"""
        self._ms_tree.delete(*self._ms_tree.get_children())
        if result.empty:
            # V0.9.5+ 强化提示：可能原因
            self._ms_status.set(
                "❌ 這次篩選沒有合格股票｜可能原因："
                "(1) 條件太嚴格、(2) DB 缺漏（殖利率/股利為 None 的股票已被排除）、"
                "(3) 可按「💰 掃描全部股票 (100檔/次)」補抓股利"
            )
            self.logger.log("❌ 篩選無結果（可能條件太嚴格或 DB 缺漏）")
            return

        # 快取勾選狀態（股票代號 → 是否勾選）
        self._ms_checked = {}

        for _, row in result.iterrows():
            code = str(row.get("股票代號", "")).strip()
            name = str(row.get("股票名稱", "")).strip()
            price_str = _fmt_float(row.get("現價"))
            rev_str = _fmt_float(row.get("累計營收YoY(%)"))
            # 【V0.9.5+ Phase 8】key 保留「(元)」：_run_manual_selection final rename
            # 把「今年股票股利」→「今年股票股利(元)」、這裡要跟著帶「(元)」
            # 【V0.9.5-goodinfo4+5】改 3 位小數：cash/stock 可能小於 0.5、2 位會看不出
            # (ex: 2442 2025 現金 0.237、股票 0.158；4114 2026 現金 0.85)
            stock_str = _fmt_float(row.get("今年股票股利(元)"), decimals=3)
            # 【V0.9.5+ Phase 8 新增】今年現金股利金額（原本 _ms_display_results 完全沒讀這個欄位）
            cash_div_str = _fmt_float(row.get("今年現金股利(元)"), decimals=3)
            cash_str = _fmt_float(row.get("今年現金殖利率(%)"))
            pe_str = _fmt_float(row.get("PE"))
            # 【V0.9.5-twser3 原始】盤中 → 收盤後總量
            # 【V0.9.5-goodinfo4+5 修正】2026-06-18 18:12 William 反映：
            #   「成交量不是我要的今日成交量！」
            #   → 拿掉盤中/收盤後切換邏輯、直接顯示 price_df 的「成交量(張)」（今日成交量）
            #   → 盤中雖然是累積量、但 William 就是要看今日即時量
            # 【V0.9.5-goodinfo4+5 (vol+cache) 修正】2026-06-18 18:34 William 反映：
            #   「成交量依舊不是今日總成交量」→ 根因是 v 欄位是「股」、原本 int() 丟失小數
            #   例：4016 股 → 原本 int(4.016) = 4 張、數字偏小 1000 倍
            #   修法：vol 已經是「張」（v/1000）、用 f"{vol:,.3f}" 顯示 4.016 張
            vol = row.get("成交量(張)")
            try:
                # 【V0.9.5-goodinfo4+5 (vol-int) 修正】2026-06-18 20:05 William 反映
                # 「每日總成交量不會有小數點」→ 顯示為整數張
                # vol=0 表示「沒抓到」、顯示 "—"（不是 0）
                if pd.isna(vol) or (isinstance(vol, (int, float)) and vol == 0):
                    vol_str = "—"
                else:
                    # 【V0.9.5-goodinfo4+5】Tkinter Treeview 會把千分位逗號轉成小數點
                    # → 直接用 str()、不做千分位格式化
                    vol_str = str(int(vol))
            except (TypeError, ValueError):
                vol_str = "—"
            last_stock_str = _fmt_float(row.get("去年股票股利(元)"), decimals=3)
            # 【V0.9.5+ Phase 8 新增】去年現金股利金額
            # 【V0.9.5-goodinfo4+5】改 3 位小數
            last_cash_div_str = _fmt_float(row.get("去年現金股利(元)"), decimals=3)
            last_cash_str = _fmt_float(row.get("去年現金殖利率(%)"))
            # 【V0.9.5-twser3 拿掉】股票殖利率欄位（William 不需要看）
            # stock_yld_this_str = _fmt_float(row.get("今年股票殖利率(%)"))
            # stock_yld_last_str = _fmt_float(row.get("去年股票殖利率(%)"))

            tag = "checked" if self._ms_checked.get(code, False) else "unchecked"
            # 【v1.0-info】加「資料日期」欄位（從 price_df.data_date）
            # 顯示個股本身的「最後交易日」、不是 cache 抓取日
            # 例：週五 13:35 抓的 cache、某些股週五暫停交易 → 顯示「2026-06-18」而不是「2026-06-19」
            data_date = str(row.get("data_date", "")).strip()
            data_date_str = data_date if data_date else "—"
            # 【V0.9.5-twser3】Treeview 從 15 欄變 13 欄（拿掉 2 個股票殖利率）
            # 【v1.0-info】再加 1 欄「資料日期」變 14 欄
            self._ms_tree.insert("", "end", iid=code, values=(
                "☑" if self._ms_checked.get(code, False) else "☐",
                code, name, price_str, rev_str,
                stock_str, cash_div_str, cash_str,
                pe_str, vol_str,
                last_stock_str, last_cash_div_str, last_cash_str,
                data_date_str
            ), tags=(tag,))

        self._ms_status.set(f"✅ 符合條件：{len(result)} 檔（上限 {self._ms_limit_var.get()} 檔）｜排序：營收YoY > 今年股票 > 今年現金殖% > PE")
        # 【V0.9.5-tab-split-phase3-D】動態更新 checkbox header（新資料剛填、預設全未勾 → ☐）
        self._update_checkbox_header(self._ms_tree, self._ms_checked)
        # 【V0.9.5-tab-split-phase3-G】enable 匯出按鈕（跟 select_tab 一致）
        if hasattr(self, "export_ms_btn"):
            self.export_ms_btn.config(state="normal")

        # 【V0.9.5-alpha Phase 6】2026-06-15：偵測 FinMind 402 額度錯誤
        # 情境：_fetch_finmind_dividend 中途被 402 中斷（已抓 X 筆寫入 DB），
        # _run_manual_selection 仍會完成並回傳部分結果（殖利率欄位一堆 None），
        # 使用者會困惑「為什麼殖利率都沒有？」→ 主動提示額度問題。
        quota_err = _MS_PROGRESS.get("error", "")
        if quota_err and ("402" in quota_err or "額度" in quota_err):
            done = _MS_PROGRESS.get("done", 0)
            total = _MS_PROGRESS.get("total", 0)
            self._ms_status.set(
                f"✅ 符合條件：{len(result)} 檔｜"
                f"⚠️ FinMind 額度用完（已抓 {done}/{total} 檔、已寫入 DB）｜"
                f"部分股票殖利率/股利欄位為 None｜"
                f"💡 可改用「🎯 指定股補抓」補關注股，或等下月重置"
            )
            self.logger.log(
                f"⚠️ FinMind 額度用完（已抓 {done}/{total} 檔），"
                f"已用 DB 資料顯示部分結果（殖利率欄位可能為 None）"
            )

    def _on_tree_hover(self, event):
        """【v1.0-hover】滑鼠移到 Treeview 任一列時
        - 若不是 cell (在捲軸/header) → 清除 hover
        - 若進入同一列 → 不動
        - 若進入新列 → 離開舊列 hover、進入新列 hover（黃色）
        - 注意：勾選狀態 (checked/unchecked) 不能被覆蓋。
          解法：現在用「只設一個 tag」、hover 時設為「hover」、離開時讀 _ms_checked 恢復。
        """
        region = self._ms_tree.identify("region", event.x, event.y)
        if region != "cell":
            # 滑鼠移到捲軸或 header → 清除 hover
            self._clear_hover()
            return
        iid = self._ms_tree.identify_row(event.y)
        if not iid:
            self._clear_hover()
            return
        if iid == self._ms_hover_iid:
            return
        # 離開舊列（如果還在 hover）
        self._clear_hover()
        # 進新列
        self._ms_hover_iid = iid
        self._ms_tree.item(iid, tags=("hover",))

    def _on_tree_leave(self, event):
        """【v1.0-hover】滑鼠離開 Treeview → 清除 hover"""
        self._clear_hover()

    def _clear_hover(self):
        """【v1.0-hover】取消目前 hover、恢復該列原本的 checked/unchecked tag"""
        if not self._ms_hover_iid:
            return
        old_iid = self._ms_hover_iid
        self._ms_hover_iid = None
        # 若該列已被刪除（重跑選股）→ tree.item() 會例外、跳過
        try:
            if old_iid in self._ms_tree.get_children():
                checked = self._ms_checked.get(old_iid, False)
                self._ms_tree.item(
                    old_iid,
                    tags=("checked" if checked else "unchecked",),
                )
        except tk.TclError:
            pass

    def _ms_toggle_check(self, event):
        """點勾選欄 header → 全選/全不選；點任一列 → toggle"""
        region = self._ms_tree.identify("region", event.x, event.y)
        column = self._ms_tree.identify_column(event.x)

        if region == "heading" and column == "#1":
            all_checked = all(self._ms_checked.get(i, False) for i in self._ms_tree.get_children())
            if all_checked:
                self._ms_select_none()
            else:
                self._ms_select_all()
            return

        if region != "cell" or column != "#1":
            return
        item_id = self._ms_tree.identify_row(event.y)
        if not item_id:
            return
        current = self._ms_checked.get(item_id, False)
        self._ms_checked[item_id] = not current
        vals = list(self._ms_tree.item(item_id, "values"))
        vals[0] = "☑" if not current else "☐"
        self._ms_tree.item(item_id, values=vals,
                           tags=("checked" if not current else "unchecked",))
        # 【V0.9.5-tab-split-phase3-D】動態更新 header
        self._update_checkbox_header(self._ms_tree, self._ms_checked)


    def _ms_tree_hover(self, event):
        """手動選股 Treeview hover：黃色 highlight"""
        region = self._ms_tree.identify("region", event.x, event.y)
        if region != "cell":
            self._ms_clear_hover()
            return
        iid = self._ms_tree.identify_row(event.y)
        if not iid:
            self._ms_clear_hover()
            return
        if iid == self._ms_hover_iid:
            return
        self._ms_clear_hover()
        self._ms_hover_iid = iid
        self._ms_tree.item(iid, tags=("hover",))

    def _ms_tree_leave(self, event):
        self._ms_clear_hover()

    def _ms_clear_hover(self):
        if not self._ms_hover_iid:
            return
        old_iid = self._ms_hover_iid
        self._ms_hover_iid = None
        try:
            if old_iid in self._ms_tree.get_children():
                checked = self._ms_checked.get(old_iid, False)
                self._ms_tree.item(old_iid, tags=("checked" if checked else "unchecked",))
        except Exception:
            pass

    def _ms_select_all(self):
        for item in self._ms_tree.get_children():
            self._ms_checked[item] = True
            vals = list(self._ms_tree.item(item, "values"))
            vals[0] = "☑"
            self._ms_tree.item(item, values=vals, tags=("checked",))
        # 【V0.9.5-tab-split-phase3-D】動態更新 header
        self._update_checkbox_header(self._ms_tree, self._ms_checked)

    def _ms_select_none(self):
        for item in self._ms_tree.get_children():
            self._ms_checked[item] = False
            vals = list(self._ms_tree.item(item, "values"))
            vals[0] = "☐"
            self._ms_tree.item(item, values=vals, tags=("unchecked",))
        # 【V0.9.5-tab-split-phase3-D】動態更新 header
        self._update_checkbox_header(self._ms_tree, self._ms_checked)

    # ==========================================================
    # 【V0.9.5-etf】主動式 ETF Tab — Hover / Toggle / Filter / Refresh / Export
    # ==========================================================


    def _etf_tree_hover_new(self, event):
        """【Fix12 廢棄】改成 _etf_tree_hover_combined"""

    def _etf_tree_hover_combined(self, event):
        """【V0.9.5-tab-split-phase3-C Fix12】ETF Treeview hover：
        - 移到 cell（任意欄） → 該列 highlight 黃色
        - 移到「ETF數」欄（column #5） → popup 顯示包含此股的 ETF 列表
        - 移到「今日異動」欄（column #6） → popup 顯示異動明細
        - 移到非 cell 區（捲軸/header） → 清除 hover + 關 popup
        """
        region = self._etf_tree.identify("region", event.x, event.y)
        if region != "cell":
            self._clear_etf_hover()
            self._close_etf_popup()
            return
        iid = self._etf_tree.identify_row(event.y)
        if not iid:
            self._clear_etf_hover()
            self._close_etf_popup()
            return

        column = self._etf_tree.identify_column(event.x)

        # Highlight（新版的 _etf_hover_iid_new 邏輯）
        if iid != getattr(self, "_etf_hover_iid_new", None):
            self._etf_clear_hover_new()
            self._etf_hover_iid_new = iid
            self._etf_tree.item(iid, tags=("hover",))
        # 同步舊版的 _etf_hover_iid（讓 _clear_etf_hover 也能運作）
        self._etf_hover_iid = iid

        # Popup（舊版的 _show_etf_popup 邏輯）
        if column == "#5":
            self._show_etf_popup(iid, event.x_root, event.y_root, mode="etf_list")
        elif column == "#6":
            self._show_etf_popup(iid, event.x_root, event.y_root, mode="changes")
        else:
            self._close_etf_popup()

    def _etf_tree_leave_new(self, event):
        """【Fix12 廢棄】"""

    def _etf_tree_leave_combined(self, event):
        """【V0.9.5-tab-split-phase3-C Fix12】離開 Treeview → 清除 hover + 關 popup"""
        self._etf_clear_hover_new()
        self._clear_etf_hover()
        self._close_etf_popup()

    def _etf_clear_hover_new(self):
        iid = getattr(self, "_etf_hover_iid_new", None)
        if not iid:
            return
        self._etf_hover_iid_new = None
        try:
            if iid in self._etf_tree.get_children():
                checked = self._etf_checked.get(iid, False)
                self._etf_tree.item(iid, tags=("checked" if checked else "unchecked",))
        except Exception:
            pass

    # 【V0.9.5-tab-split-phase3-F】拿掉右鍵「全選/全不選」選單（_etf_tree_rclick_new）

    def _on_etf_tree_hover(self, event):
        """【V0.9.5-etf】ETF Treeview hover：
        - 移到 cell（任意欄） → 該列 highlight 黃色
        - 移到「ETF數」欄（column #5） → 顯示 popup 顯示包含此股的 ETF 列表
        - 移到非 cell 區（捲軸/header） → 清除 hover + 關 popup
        """
        region = self._etf_tree.identify("region", event.x, event.y)
        if region != "cell":
            self._clear_etf_hover()
            self._close_etf_popup()
            return
        iid = self._etf_tree.identify_row(event.y)
        if not iid:
            self._clear_etf_hover()
            self._close_etf_popup()
            return

        column = self._etf_tree.identify_column(event.x)

        # 先處理 hover highlight
        if iid != self._etf_hover_iid:
            self._clear_etf_hover()
            self._etf_hover_iid = iid
            self._etf_tree.item(iid, tags=("hover",))

        # 在「ETF數」欄（第 5 欄 = #5）上才顯示 popup
        if column == "#5":
            self._show_etf_popup(iid, event.x_root, event.y_root, mode="etf_list")
        elif column == "#6":
            self._show_etf_popup(iid, event.x_root, event.y_root, mode="changes")
        else:
            self._close_etf_popup()

    def _on_etf_tree_leave(self, event):
        """【V0.9.5-etf】離開 Treeview → 清除 hover + 關 popup"""
        self._clear_etf_hover()
        self._close_etf_popup()

    def _clear_etf_hover(self):
        if not self._etf_hover_iid:
            return
        old_iid = self._etf_hover_iid
        self._etf_hover_iid = None
        try:
            if old_iid in self._etf_tree.get_children():
                checked = self._etf_checked.get(old_iid, False)
                self._etf_tree.item(
                    old_iid,
                    tags=("checked" if checked else "unchecked",),
                )
        except tk.TclError:
            pass

    def _show_etf_popup(self, iid, x_root, y_root, mode="etf_list"):
        """【V0.9.5-etf】在滑鼠位置顯示 Toplevel 視窗
        mode="etf_list"：顯示持有此股的 ETF 列表
        mode="changes"：【V0.9.5-etf-history】顯示各 ETF 對該股的異動明細
        - 重複呼叫不重建視窗，只更新內容
        """
        if self._etf_agg_df is None or self._etf_agg_df.empty:
            return
        # iid 是 row 的識別碼、在 _etf_display_results 中設為股票代號
        stock_code = str(iid)
        # 取該股的 ETF 列表
        match = self._etf_agg_df[self._etf_agg_df["股票代號"].astype(str).str.strip() == stock_code]
        if match.empty:
            self._close_etf_popup()
            return
        # 【V0.9.5-etf-history】mode="changes"：顯示各 ETF 異動明細
        if mode == "changes":
            change_df = getattr(self, "_etf_change_df", None)
            if change_df is None or change_df.empty:
                self._close_etf_popup()
                return
            stock_changes = change_df[change_df["stock_code"].astype(str).str.strip() == stock_code]
            if stock_changes.empty:
                self._close_etf_popup()
                return
            change_lines = []
            total = 0.0
            for _, cr in stock_changes.iterrows():
                etf_code = str(cr.get("etf_code", "")).strip()
                etf_name = str(cr.get("etf_name", etf_code))
                # 【V0.9.5-tab-split-phase3-H FixA2】2026-06-23 12:12 William 反映
                # _compute_etf_changes 回傳欄位是 today_change_lots、不是 change_lots
                # 之前用 change_lots 永遠抓到 0（.get 預設值）、沒人發現
                cl = cr.get("today_change_lots", 0) or 0
                if abs(cl) < 0.001:
                    continue
                total += cl
                sign = "+" if cl > 0 else ""
                change_lines.append(f"{sign}{cl:,.1f}  {etf_code} {etf_name}")
            if not change_lines:
                self._close_etf_popup()
                return
            sign = "+" if total > 0 else ""
            change_lines.append("-" * 20)
            change_lines.append(f"總和 {sign}{total:,.1f} 張")
            popup_text = "\n".join(change_lines)
        else:
            # etf_list mode：顯示持有此股的 ETF 列表
            etf_list_str = match.iloc[0].get("etf_list", "")
            if not etf_list_str:
                self._close_etf_popup()
                return
            popup_title = f"{stock_code} {match.iloc[0].get("股票名稱", "")} 被 {match.iloc[0].get("etf_count", 0)} 檔 ETF 持有："
            popup_text = popup_title + "\n" + etf_list_str
        # 建立 popup（一次一個）
        if self._etf_popup is None or not self._etf_popup.winfo_exists():
            self._etf_popup = tk.Toplevel(self)
            self._etf_popup.wm_overrideredirect(True)
            self._etf_popup.wm_attributes("-topmost", True)
            self._etf_popup.configure(bg="#fff8dc", relief="solid", borderwidth=1)
            # 【V0.9.5-etf-popup-fix】改用 Text widget 顯示多行
            # Label 在多行時會被擠成「最長那行 + 其他 wrap」、視覺擠在一起
            # Text widget 會以「max line width」算寬度、每行清楚顯示
            self._etf_popup_text = tk.Text(
                self._etf_popup,
                bg="#fff8dc", font=("Helvetica", 9),
                padx=10, pady=6,
                relief="flat", borderwidth=0,
                highlightthickness=0,
                wrap=tk.NONE,
                height=10, width=30,  # 預設值、稍後依內容調整
                # 【V0.9.5-etf-popup-spacing】加行距、行間呼吸感
                spacing1=4,  # 每行之上 4px
                spacing3=4,  # 每行之下 4px
            )
            self._etf_popup_text.pack()

        # 內容
        # 【V0.9.5-etf-history】all_text 在 mode block 中已設定
        all_text = popup_text

        # 計算最長行（用於設定 Text widget 寬度）
        # 【V0.9.5-etf-popup-width】中文字算 2、其他算 1（Text widget width 是平均字元寬度）
        lines = all_text.split("\n")
        max_line_len = max(_display_width(line) for line in lines) if lines else 30
        total_lines = len(lines)

        self._etf_popup_text.config(state="normal")
        self._etf_popup_text.delete("1.0", "end")
        self._etf_popup_text.insert("1.0", all_text)
        # 寬度 = 最長行字元數、高度 = 行數（最多 25 行避免超出螢幕）
        self._etf_popup_text.config(
            width=max_line_len,
            height=min(total_lines, 25),
            state="disabled",
        )

        # 位置（滑鼠右邊一點點）
        # 計算 popup 大小、避免超出螢幕
        self._etf_popup.update_idletasks()
        w = self._etf_popup.winfo_reqwidth()
        h = self._etf_popup.winfo_reqheight()
        sx = self._etf_popup.winfo_screenwidth()
        sy = self._etf_popup.winfo_screenheight()
        px = min(x_root + 10, sx - w - 10)
        py = min(y_root + 10, sy - h - 10)
        self._etf_popup.wm_geometry(f"+{px}+{py}")

    def _close_etf_popup(self):
        if self._etf_popup is not None:
            try:
                if self._etf_popup.winfo_exists():
                    self._etf_popup.destroy()
            except tk.TclError:
                pass
            self._etf_popup = None

    def _etf_toggle_check(self, event):
        """【V0.9.5-etf】點 ETF Treeview → toggle 勾選
        【V0.9.5-tab-split-phase3-D】header 點下去 → 全選/全不選（與 select_tree / ms_tree 一致）
        """
        region = self._etf_tree.identify("region", event.x, event.y)
        column = self._etf_tree.identify_column(event.x)
        if column != "#1":
            return

        # header click → 全選/全不選
        if region == "heading":
            items = list(self._etf_tree.get_children())
            if not items:
                return
            all_checked = all(self._etf_checked.get(iid, False) for iid in items)
            if all_checked:
                self._etf_select_none()
            else:
                self._etf_select_all()
            return

        if region != "cell":
            return
        item_id = self._etf_tree.identify_row(event.y)
        if not item_id:
            return
        current = self._etf_checked.get(item_id, False)
        self._etf_checked[item_id] = not current
        vals = list(self._etf_tree.item(item_id, "values"))
        vals[0] = "☑" if not current else "☐"
        self._etf_tree.item(
            item_id, values=vals,
            tags=("checked" if not current else "unchecked",),
        )
        # 【V0.9.5-tab-split-phase3-D】動態更新 header
        self._update_checkbox_header(self._etf_tree, self._etf_checked)

    def _etf_select_all(self):
        for item in self._etf_tree.get_children():
            self._etf_checked[item] = True
            vals = list(self._etf_tree.item(item, "values"))
            vals[0] = "☑"
            self._etf_tree.item(item, values=vals, tags=("checked",))
        # 【V0.9.5-tab-split-phase3-D】動態更新 header
        self._update_checkbox_header(self._etf_tree, self._etf_checked)

    def _etf_select_none(self):
        for item in self._etf_tree.get_children():
            self._etf_checked[item] = False
            vals = list(self._etf_tree.item(item, "values"))
            vals[0] = "☐"
            self._etf_tree.item(item, values=vals, tags=("unchecked",))
        # 【V0.9.5-tab-split-phase3-D】動態更新 header
        self._update_checkbox_header(self._etf_tree, self._etf_checked)


    # ── ETF 持股歷史庫（V0.9.5-etf-history）────────────────────────────────
    def _init_etf_history(self):
        """【V0.9.5-etf-history】ETF 持股歷史庫初始化（App 起動時呼叫一次）"""
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "etf_history.db")
        _init_etf_history_db(db_path)
        self._etf_history_db = db_path

    def _save_etf_holdings_to_db(self, long_df):
        """【V0.9.5-etf-history】把 long_df 寫入 DB"""
        if long_df is None or long_df.empty:
            return
        import sqlite3
        from datetime import datetime as _dt
        db_path = getattr(self, "_etf_history_db", None)
        if db_path is None:
            return
        date_str = _dt.now().strftime("%Y-%m-%d")
        try:
            with sqlite3.connect(db_path) as conn:
                for _, r in long_df.iterrows():
                    shares = int(r.get("shares", 0) or 0)
                    _save_etf_holding_snapshot(
                        db_path,
                        str(r["etf_code"]).strip(),
                        [{
                            "stock_code": str(r["stock_code"]).strip(),
                            "stock_name": str(r.get("stock_name", "")),
                            "weight": float(r.get("weight", 0) or 0),
                            "shares": shares,
                            "industry": str(r.get("industry", "")),
                        }],
                        date_str=date_str,
                    )
        except Exception as e:
            self.logger.log(f"⚠️ [ETF] 寫入 etf_history.db 失敗：{e}")

    def _compute_etf_changes_from_db(self):
        """【V0.9.5-etf-history】從 DB 拿今日 vs 昨日異動"""
        db_path = getattr(self, "_etf_history_db", None)
        if db_path is None:
            return pd.DataFrame()
        try:
            return _compute_etf_changes(db_path)
        except Exception as e:
            self.logger.log(f"⚠️ [ETF] 計算 ETF 異動失敗：{e}")
            return pd.DataFrame()

    def _etf_apply_filter(self):
        """【V0.9.5-etf】套用左面板篩選、刷新 Treeview
        - 需要先 _etf_refresh_holdings 有資料
        """
        if self._etf_agg_df is None or self._etf_agg_df.empty:
            messagebox.showwarning("無資料", "請先按「🔄 重新抓 ETF 持股」")
            return
        self._etf_display_results(self._etf_agg_df)

    def _etf_refresh_holdings(self):
        """【V0.9.5-etf】重新抓取 19 檔 ETF 的前 10 大持股 → merge price cache → 重新顯示
        用 threading 避免凍結 UI
        """
        if hasattr(self, '_bg_price_fetching') and self._bg_price_fetching:
            messagebox.showwarning("請稍後", "股價背景抓取中、請等候完成")
            return

        self._etf_status.set("⏳ 抓取中...")
        self._etf_progress.pack(anchor="w", pady=(2, 0))
        self._etf_progress["mode"] = "indeterminate"
        self._etf_progress.start(10)

        def _worker():
            try:
                # 1) 抓 ETF 列表 + 持股（【V0.9.5-etf-session-fix】修正 self.session 不存在的 bug）
                _s = build_session()
                long_df = build_etf_holdings_table(_s, self.cfg, self.logger)
                if long_df.empty:
                    self.after(0, lambda: self._etf_refresh_done(None, "ETF 持股抓取失敗"))
                    return

                # 2) merge 股價（從 cache）
                price_df = self._load_price_df()
                agg_df = aggregate_etf_holdings(long_df, price_df)

                # 【V0.9.5-etf-gui fix 2026-06-19】避免 closure trap：agg_df/long_df 用 default arg 鎖住
                self.after(0, lambda a=agg_df, l=long_df: self._etf_refresh_done(a, None, long_df=l))
            except Exception as e:
                self.logger.log(f"❌ ETF 持股抓取例外：{e}")
                # 【V0.9.5-etf-gui fix 2026-06-19】用 default arg 鎖住 e
                self.after(0, lambda err=str(e): self._etf_refresh_done(None, err))

        threading.Thread(target=_worker, daemon=True).start()

    def _etf_refresh_done(self, agg_df, err, long_df=None):
        self._etf_progress.stop()
        self._etf_progress.pack_forget()
        if err or agg_df is None or agg_df.empty:
            self._etf_status.set(f"❌ ETF 持股抓取失敗：{err or '空資料'}")
            return

        self._etf_agg_df = agg_df
        if long_df is not None:
            self._etf_long_df = long_df

        # 【V0.9.5-etf-history】寫入 etf_history.db
        self._save_etf_holdings_to_db(long_df)
        # 計算今日異動
        self._etf_change_df = self._compute_etf_changes_from_db()
        self._etf_data_status.set(
            f"ETF 持股：最後更新 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ({len(agg_df)} 檔個股)"
        )
        self._etf_status.set(f"✅ ETF 持股抓取完成：{len(agg_df)} 檔個股被多檔 ETF 持有")
        # 自動套用一次篩選
        self._etf_display_results(agg_df, self._etf_change_df)

    def _etf_display_results(self, agg_df, change_df=None):
        """【V0.9.5-etf】依左面板條件、刷新 Treeview 內容"""
        df = agg_df.copy()

        # 【V0.9.5-etf-history】合併今日異動
        if change_df is None:
            change_df = getattr(self, "_etf_change_df", None)
        if change_df is not None and not change_df.empty:
            # 【V0.9.5-tab-split-phase3-H FixA2】2026-06-23 12:12 William 反映
            # KeyError: 'Column not found: change_lots'
            # _compute_etf_changes 回傳的欄位是 today_change_lots、不是 change_lots
            # 這個 bug 之前測試沒抓到、是因為：
            # - 過去 DB shares 全 0 → _compute_etf_changes 回傳空 DataFrame
            # - 走 else 分支 df["total_change_lots"] = 0.0、不觸發 groupby
            # - 今早 migration 補 shares → _compute_etf_changes 回傳有資料 → 才爆
            stock_change = (
                change_df.groupby("stock_code", as_index=False)["today_change_lots"]
                .sum()
                .rename(columns={"today_change_lots": "total_change_lots"})
            )
            df = df.merge(
                stock_change,
                left_on=df["股票代號"].astype(str).str.strip(),
                right_on="stock_code",
                how="left"
            )
            df["total_change_lots"] = df["total_change_lots"].fillna(0)
        else:
            df["total_change_lots"] = 0.0

        # 篩選：最小 ETF 數
        min_count = self._etf_min_count_var.get()
        df = df[df["etf_count"] >= min_count]

        # 篩選：是否限定有收盤價
        if self._etf_only_with_price_var.get():
            df = df[df["收盤價"].notna()]

        # 【v1.1.1 ETF sort】William 2026-06-24 10:39 反映：
        # 排序邏輯：
        # 1. 今日有異動的股票優先（total_change_lots != 0）
        # 2. 有異動者：依 total_change_lots 降序（由大到小）
        # 3. 無異動者：依 total_change_lots 升序（由小到大，all 0，保持原有 etf_count 順序）
        # 實作：today_mover 作為第一 key（True > False → movers first）
        df["today_mover"] = df["total_change_lots"] != 0
        df = df.sort_values(
            ["today_mover", "total_change_lots"],
            ascending=[False, False],  # movers first, 各自內部降序
        )
        df = df.drop(columns=["today_mover"])

        # 結果上限
        limit = self._etf_limit_var.get()
        if limit and len(df) > limit:
            df = df.head(limit)

        # 清空 Treeview + 勾選狀態
        self._close_etf_popup()
        self._clear_etf_hover()
        for item in self._etf_tree.get_children():
            self._etf_tree.delete(item)
        self._etf_checked = {}

        # 插入資料（iid = 股票代號、讓 popup 用 iid 直接查 etf_list）
        for _, row in df.iterrows():
            iid = str(row["股票代號"]).strip()
            price = row.get("收盤價", None)
            if pd.isna(price):
                price_str = "--"
            else:
                # 【V0.9.5-locale-comma-fix】不用千分位、Tkinter Treeview 會把 , 轉成 .
                price_str = f"{float(price):.2f}"
            change_lots = row.get("total_change_lots", 0) or 0
            if abs(change_lots) < 0.001:
                change_str = "--"
            else:
                change_str = f"{change_lots:+.1f}"
            self._etf_tree.insert(
                "", "end", iid=iid,
                values=("☐", iid, str(row.get("股票名稱", "")), price_str, int(row["etf_count"]), change_str),
                tags=("unchecked",),
            )

        self._etf_status.set(
            f"✅ 顯示 {len(df)} 檔個股（總資料 {len(agg_df)} 檔）"
        )
        # 【V0.9.5-tab-split-phase3-D】動態更新 checkbox header（新資料剛填、預設全未勾 → ☐）
        self._update_checkbox_header(self._etf_tree, self._etf_checked)
        # 【V0.9.5-tab-split-phase3-G】enable 匯出按鈕（跟 select_tab 一致）
        if hasattr(self, "export_etf_btn"):
            self.export_etf_btn.config(state="normal")

    def _etf_export_excel(self):
        """【V0.9.5-etf】匯出 ETF 成份股持股到 Excel
        - 同手動選股的格式、可被策略參數 Tab 讀回
        - 包含完整欄位（代號、名稱、收盤價、ETF 數、ETF 列表、權重）
        """
        if self._etf_agg_df is None or self._etf_agg_df.empty:
            messagebox.showwarning("無資料", "請先按「🔄 重新抓 ETF 持股」")
            return
        checked = [code for code, v in self._etf_checked.items() if v]
        if not checked:
            messagebox.showwarning("未勾選", "請先勾選要匯出的股票")
            return

        result = self._etf_agg_df[
            self._etf_agg_df["股票代號"].astype(str).str.strip().isin(checked)
        ].copy()

        filename = simpledialog.askstring(
            "儲存名稱設定",
            "請輸入檔案名稱（不含副檔名）:",
            initialvalue=f"ETF成份股_{datetime.now().strftime('%Y%m%d_%H%M')}"
        )
        if not filename:
            return
        filename = filename.strip()
        if not filename:
            return
        if not filename.endswith(".xlsx"):
            filename += ".xlsx"
        filepath = os.path.join(SOURCE_DIR, filename)

        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment

            wb = Workbook()
            ws = wb.active
            ws.title = "ETF成份股"

            headers = list(result.columns)
            ws.append(headers)
            for cell in ws[1]:
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="DDEEFF", end_color="DDEEFF", fill_type="solid")
                cell.alignment = Alignment(horizontal="center")

            for _, row in result.iterrows():
                ws.append([
                    "" if pd.isna(v) else v
                    for v in [row.get(c) for c in headers]
                ])

            # 欄寬
            for col_idx, col_name in enumerate(headers, start=1):
                col_letter = ws.cell(row=1, column=col_idx).column_letter
                ws.column_dimensions[col_letter].width = max(12, min(50, len(str(col_name)) * 2 + 4))

            wb.save(filepath)
            messagebox.showinfo(
                "匯出成功",
                f"已匯出 {len(result)} 檔 ETF 成份股到：\n{filepath}\n\n"
                f"📌 此檔可餵給「⚙️ 策略參數」的股票清單載入功能。"
            )
            self.logger.log(f"📤 [ETF] 匯出 {len(result)} 檔到 {filepath}")
        except Exception as e:
            messagebox.showerror("匯出失敗", str(e))
            self.logger.log(f"❌ [ETF] 匯出失敗：{e}")

    def _etf_auto_startup_fetch(self):
        """【V0.9.5-etf】App 開機 2.5 秒後自動抓 ETF 持股（背景跑、不跳 popup）
        - 重複 fetch 會跳過（用 _etf_fetching flag）
        - 抓完就會 populate ETF Tab（就算使用者還沒切到該 Tab）
        """
        if self._etf_fetching:
            return
        self._etf_fetching = True
        self.logger.log("📊 [ETF] 開機自動抓取 ETF 持股...")

        def _worker():
            try:
                # 【V0.9.5-etf-session-fix】StockTool 主類別沒有 self.session 屬性
                # → 跟其他 fetcher 一樣在 worker 內 build_session() 拿 session
                _s = build_session()
                long_df = build_etf_holdings_table(_s, self.cfg, self.logger)
                if long_df.empty:
                    self.after(0, lambda: self._etf_auto_startup_done(None, "ETF 持股抓取失敗"))
                    return
                price_df = self._load_price_df()
                agg_df = aggregate_etf_holdings(long_df, price_df)
                # 【V0.9.5-etf-gui fix 2026-06-19】避免 closure trap：agg_df/long_df 用 default arg 鎖住
                self.after(0, lambda a=agg_df, l=long_df: self._etf_auto_startup_done(a, None, long_df=l))
            except Exception as e:
                self.logger.log(f"❌ [ETF] 開機抓取例外：{e}")
                # 【V0.9.5-etf-gui fix 2026-06-19】用 default arg 鎖住 e（except 離開後 e 會被釋放）
                self.after(0, lambda err=str(e): self._etf_auto_startup_done(None, err))

        threading.Thread(target=_worker, daemon=True).start()

    def _etf_auto_startup_done(self, agg_df, err, long_df=None):
        self._etf_fetching = False
        if err or agg_df is None or agg_df.empty:
            self._etf_status.set(f"❌ ETF 開機抓取失敗：{err or '空資料'}")
            return
        self._etf_agg_df = agg_df
        if long_df is not None:
            self._etf_long_df = long_df

        # 【V0.9.5-etf-history】寫入 etf_history.db
        self._save_etf_holdings_to_db(long_df)
        # 計算今日異動
        self._etf_change_df = self._compute_etf_changes_from_db()
        if self._etf_change_df is not None and not self._etf_change_df.empty:
            self._etf_data_status.set(
            f"ETF 持股：最後更新 {datetime.now().strftime('%%Y-%%m-%%d %%H:%%M:%%S')} ({len(agg_df)} 檔個股) ✅ 有昨日資料可比較"
            )
        else:
            self._etf_data_status.set(
            f"ETF 持股：最後更新 {datetime.now().strftime('%%Y-%%m-%%d %%H:%%M:%%S')} ({len(agg_df)} 檔個股) ⚠️ 無昨日資料"
            )
    def _load_price_df(self):
        """【V0.9.5-etf】讀取 price 快取 DataFrame、若不存在就 try fetch_prices 一次
        回傳的 df 至少含欄位：股票代號、股價
        """
        try:
            df, _, _ = load_cache(get_cache_file("price"))
            if df is not None and not df.empty and "股票代號" in df.columns:
                return df
        except Exception as e:
            self.logger.log(f"⚠️ [ETF] 讀取 price cache 失敗：{e}")
        # cache 沒資料 → try fetch_prices 抓一次（【V0.9.5-etf-session-fix】改用 build_session()）
        try:
            _s = build_session()
            df = fetch_prices(_s, self.cfg)
            if df is not None and not df.empty:
                save_cache(get_cache_file("price"), df)
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            self.logger.log(f"⚠️ [ETF] fetch_prices 也失敗：{e}")
            return pd.DataFrame()

    def _ms_export_excel(self):
        """匯出選中的股票到 Excel"""
        if not hasattr(self, '_ms_result_df') or self._ms_result_df is None or self._ms_result_df.empty:
            messagebox.showwarning("無資料", "請先執行「選股」")
            return

        checked = [code for code, v in self._ms_checked.items() if v]
        if not checked:
            messagebox.showwarning("未勾選", "請先勾選要匯出的股票")
            return

        result = self._ms_result_df[
            self._ms_result_df["股票代號"].astype(str).str.strip().isin(checked)
        ].copy()

        # 加入「使用者設定的篩選門檻值」當備註欄
        filters = self._ms_get_filters()
        for key, (cb_var, entry_var, skip_val) in self._ms_filter_vars.items():
            label_map = {
                "min_rev_yoy": "篩_累計營收YoY%",
                "min_stock_div": "篩_今年股票股利元",
                "min_cash_div_yld": "篩_今年現金殖利率%",
                "min_pe": "篩_PE上限",
                "min_price": "篩_現價下限",
                "min_volume": "篩_成交量下限張",
                "min_last_stock_div": "篩_去年股票股利元",
                "min_last_cash_yld": "篩_去年現金殖利率%",
            }
            col_name = label_map.get(key, key)
            val = entry_var.get() if cb_var.get() else "不限"
            result[col_name] = val

        filename = simpledialog.askstring(
            "儲存名稱設定",
            "請輸入檔案名稱（不含副檔名）:",
            initialvalue=f"手動選股_{datetime.now().strftime('%Y%m%d_%H%M')}"
        )
        if not filename:
            return
        filename = filename.strip()
        if not filename:
            return
        if not filename.endswith(".xlsx"):
            filename += ".xlsx"
        filepath = os.path.join(SOURCE_DIR, filename)

        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment

            wb = Workbook()
            ws = wb.active
            ws.title = "手動選股"

            headers = list(result.columns)
            ws.append(headers)

            header_fill = PatternFill("solid", fgColor="4472C4")
            header_font = Font(color="FFFFFF", bold=True)
            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center")

            for row_data in result.values.tolist():
                ws.append(row_data)

            for col in ws.columns:
                max_len = max(len(str(cell.value or "")) for cell in col)
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 30)

            wb.save(filepath)
            # 【v1.0-savelist-fix2】2026-06-19 22:15 William 反映：
            # 「匯出 excel 可以餵回策略參數中的選股來源嗎？可以就只要這個功能」
            # 是的：load_stock_list_from_excel 只要「股票代號」欄（find_col 找「股票/code」）
            # 這個檔案包含「股票代號」+「股票名稱」+ 其他欄位 → load 只讀代號、其它忽略
            # 所以不需要額外加「存成 Excel 股票清單」按鈕、這個檔案直接就能用。
            messagebox.showinfo(
                "匯出成功",
                f"已匯出 {len(result)} 檔\n→ {filepath}\n\n"
                f"💡 這個檔案可以直接給「策略參數 → 使用 Excel 股票清單」讀取使用\n"
                f"   （只取「股票代號」欄、其他欄位會被忽略）\n\n"
                f"📊 已勾選 {len(result)} 檔，自動套用「▶ 執行回測模擬」",
            )
        except Exception as e:
            messagebox.showerror("匯出失敗", str(e))

    # ── Preset 管理 ──
    def _ms_get_presets(self) -> dict:
        raw = self.cfg.to_dict().get("manual_select_presets", {})
        return raw if isinstance(raw, dict) else {}

    def _ms_save_preset(self):
        """彈出對話框，輸入 preset 名稱，儲存當前條件"""
        name = simpledialog.askstring("儲存 Preset", "請輸入Preset名稱：",
                                      initialvalue="我的篩選")
        if not name:
            return
        name = name.strip()
        filters = self._ms_get_filters()
        presets = self._ms_get_presets()
        presets[name] = filters
        self.cfg.update_from_dict({"manual_select_presets": presets,
                                   "manual_select_last_preset": name})
        save_config(self.cfg.to_dict())
        self._ms_refresh_preset_list()
        self._ms_preset_var.set(name)
        messagebox.showinfo("已儲存", f"Preset「{name}」已儲存")

    def _ms_load_preset(self):
        """根據目前選中的 preset 名稱，載入條件到 UI"""
        name = self._ms_preset_var.get().strip()
        presets = self._ms_get_presets()
        data = presets.get(name, {})
        if not data:
            return

        # 還原 top_n
        if "top_n" in data:
            self._ms_limit_var.set(int(data["top_n"]))

        # 還原各 filter（跳過 top_n key）
        for key, val in data.items():
            if key == "top_n":
                continue
            if key in self._ms_filter_vars:
                cb_var, entry_var, skip_val = self._ms_filter_vars[key]
                cb_var.set(val is not None and val != skip_val)
                if val is not None:
                    entry_var.set(float(val))

    def _ms_delete_preset(self):
        name = self._ms_preset_var.get().strip()
        if not name:
            return
        if not messagebox.askyesno("確認刪除", f"刪除 Preset「{name}」？"):
            return
        presets = self._ms_get_presets()
        presets.pop(name, None)
        last = self.cfg.to_dict().get("manual_select_last_preset")
        self.cfg.update_from_dict({"manual_select_presets": presets})
        if last == name:
            self.cfg.update_from_dict({"manual_select_last_preset": None})
        save_config(self.cfg.to_dict())
        self._ms_refresh_preset_list()
        self._ms_preset_var.set("")
        messagebox.showinfo("已刪除", f"Preset「{name}」已刪除")

    def _ms_refresh_preset_list(self):
        """重新整理 preset 下拉選項，並自動選中上次"""
        presets = list(self._ms_get_presets().keys())
        self._ms_preset_combo["values"] = presets
        last = self.cfg.to_dict().get("manual_select_last_preset")
        if last and last in presets:
            self._ms_preset_var.set(last)
        elif presets:
            self._ms_preset_var.set(presets[0])

    def _on_position_selected(self, event):
        """持倉明細任一列被點擊 → 顯示該股票完整統計"""
        sel = self._positions_tree.selection()
        if not sel:
            return
        item = sel[0]
        vals = self._positions_tree.item(item, "values")
        # vals: (代號, 名稱, 股數, 均價, 現價, 市值, 未實現損益, 報酬率%, 已實現損益)
        stock_id = str(vals[0]).strip()
        self._show_position_detail(stock_id)

    def _show_position_detail(self, stock_id: str):
        """顯示指定股票的完整統計視窗（V0.9.4 phase2.3：可滾動 + 預估賣出成本）"""
        txs = self.portfolio.list_transactions()
        stock_txs = [t for t in txs if t.stock_id == stock_id]
        if not stock_txs:
            return

        # 顯示名稱：優先用 fetch 到的最新名稱，其次用 DB 儲存的名稱
        stored_name = stock_txs[0].stock_name or ""
        stock_name = self._current_names.get(stock_id, stored_name) or stored_name or stock_id
        buys = [t for t in stock_txs if t.action == "BUY"]
        sells = [t for t in stock_txs if t.action == "SELL"]

        # 計算
        total_fee = sum(t.fee for t in stock_txs)
        total_tax = sum(t.tax for t in stock_txs)
        total_shares = sum(t.shares for t in buys) - sum(t.shares for t in sells)
        buy_cost_excl_fee = sum(t.shares * t.price for t in buys)
        sell_net = sum(t.shares * t.price - t.fee - t.tax for t in sells)
        realized_pl = sell_net - buy_cost_excl_fee if sells else 0.0
        avg_cost = buy_cost_excl_fee / sum(t.shares for t in buys) if buys else 0.0
        cur_price = self._current_prices.get(stock_id, 0.0)
        cur_mv = total_shares * cur_price

        # 預估賣出（以現價）
        est_fee = max(20, cur_mv * 0.001425 * self.portfolio.broker_discount)
        est_tax = cur_mv * 0.003
        est_net = cur_mv - est_fee - est_tax
        unrealized_pl = (cur_price - avg_cost) * total_shares if total_shares > 0 else 0.0

        # 建立可滾動視窗
        win = tk.Toplevel(self)
        win.title(f"📊 {stock_id} {stock_name} — 統計明細")
        win.geometry("540x500")
        win.transient(self)

        # Canvas + Scrollbar
        canvas = tk.Canvas(win, highlightthickness=0, bg="#f5f5f5")
        vscroll = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        # 所有內容放在 content_frame 裡
        cf = tk.Frame(canvas, bg="#f5f5f5")
        canvas.create_window((0, 0), window=cf, anchor="nw")

        def on_frame_config(e):
            canvas.configure(scrollregion=canvas.bbox("all"))

        cf.bind("<Configure>", on_frame_config)

        # 工具函式
        def lbl(parent, text, font=("Segoe UI", 10), fg="#222", **kw):
            return tk.Label(parent, text=text, font=font, fg=fg, bg="#f5f5f5", **kw)

        def section_hdr(parent, text):
            hdr = tk.Frame(parent, bg="#0070c0", pady=3)
            hdr.pack(fill="x", padx=10, pady=(12, 4))
            tk.Label(hdr, text=text, font=("Segoe UI", 10, "bold"),
                    fg="white", bg="#0070c0").pack(anchor="w", padx=8)

        def stat(parent, label, value, color="black"):
            row = tk.Frame(parent, bg="#f5f5f5")
            row.pack(fill="x", padx=14)
            tk.Label(row, text=label, font=("Segoe UI", 10),
                    anchor="e", width=20, bg="#f5f5f5").pack(side="left")
            tk.Label(row, text=value, font=("Segoe UI", 10, "bold"),
                    anchor="w", foreground=color, bg="#f5f5f5").pack(side="left", padx=(6, 0))

        # ── 抬頭 ──
        hdr_f = tk.Frame(cf, bg="#0055a5", pady=8)
        hdr_f.pack(fill="x")
        tk.Label(hdr_f, text=f"{stock_id}  {stock_name}",
                font=("Segoe UI", 13, "bold"), fg="white", bg="#0055a5").pack(pady=(0, 2))
        tk.Label(hdr_f, text=f"共 {len(stock_txs)} 筆交易（買入 {len(buys)} 筆 / 賣出 {len(sells)} 筆）",
                font=("Segoe UI", 9), fg="#cce0ff", bg="#0055a5").pack()

        # ── 持有概況 ──
        section_hdr(cf, "【持有概況】")
        stat(cf, "目前持有股數", f"{total_shares:,.0f} 股")
        stat(cf, "平均成本（不含費用）", f"{avg_cost:,.4f} 元")
        stat(cf, "目前現價", f"{cur_price:,.2f} 元")
        stat(cf, "市值", f"{cur_mv:,.2f} 元")
        stat(cf, "未實現損益", f"{unrealized_pl:+,.2f} 元",
             "#0a7d2c" if unrealized_pl >= 0 else "#c00000")

        # ── 預估賣出（以現價）──
        section_hdr(cf, "【預估賣出（以現價）】")
        stat(cf, "預估手續費", f"{est_fee:,.2f} 元（費率 {self.portfolio.broker_discount*0.1425:.4f}%）")
        stat(cf, "預估證交稅", f"{est_tax:,.2f} 元（0.3%）")
        stat(cf, "預估淨收入", f"{est_net:,.2f} 元",
             "#0a7d2c" if est_net >= cur_mv - cur_mv * 0.004425 else "#c00000")
        stat(cf, "含費總成本", f"{(total_fee + sum(t.shares*t.price+t.fee for t in buys)):,.2f} 元")

        # ── 費用累計 ──
        section_hdr(cf, "【費用累計】")
        stat(cf, "總手續費", f"{total_fee:,.2f} 元")
        stat(cf, "總證交稅", f"{total_tax:,.2f} 元")
        stat(cf, "總買入成本（含費）", f"{sum(t.shares*t.price+t.fee for t in buys):,.2f} 元")

        # ── 已實現損益 ──
        if sells:
            section_hdr(cf, "【已實現損益】")
            stat(cf, "總賣出淨收入", f"{sell_net:,.2f} 元")
            stat(cf, "含費總成本", f"{buy_cost_excl_fee + total_fee:,.2f} 元")
            stat(cf, "已實現損益（扣費稅）", f"{realized_pl:+,.2f} 元",
                 "#0a7d2c" if realized_pl >= 0 else "#c00000")

        # ── 交易明細 mini table ──
        section_hdr(cf, "【交易明細】")
        t_frame = tk.Frame(cf, bg="white")
        t_frame.pack(fill="both", expand=False, padx=10, pady=(4, 12))
        cols = ("日期", "買/賣", "股數", "價格", "手續費", "證交稅", "備註")
        mini = ttk.Treeview(t_frame, columns=cols, show="headings", height=8)
        for col, w in zip(cols, [90, 40, 65, 65, 60, 60, 90]):
            mini.heading(col, text=col)
            mini.column(col, width=w, anchor="e" if col not in ("日期","備註") else "w")
        mini.pack(side="left", fill="both", expand=True)
        ts = ttk.Scrollbar(t_frame, orient="vertical", command=mini.yview)
        mini.configure(yscrollcommand=ts.set)
        ts.pack(side="right", fill="y")
        for t in sorted(stock_txs, key=lambda x: x.trade_date):
            mini.insert("", "end", values=(
                t.trade_date,
                "買" if t.action == "BUY" else "賣",
                # 【V0.9.5-locale-comma-fix】Treeview cell 不用千分位、Tkinter 會把 , 轉成 .
                # 【V0.9.5-shares-int】股數顯示整數、避免 float 的 .0
                str(int(t.shares)),
                f"{t.price:.2f}",
                f"{t.fee:.2f}",
                f"{t.tax:.2f}",
                t.note or "",
            ))

        # ── 關閉按鈕 ──
        tk.Frame(cf, bg="#f5f5f5", height=20).pack()  # bottom padding
        tk.Button(cf, text="關閉", font=("Segoe UI", 10),
                 command=win.destroy).pack(pady=(0, 16))

        # 啟動滾輪（Linux 用 MouseWheel）
        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1*(e.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        win.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

    def _refresh_portfolio_view(self):
        """重新查詢 DB，更新總覽 + 兩個 Treeview"""
        try:
            positions = self.portfolio.get_positions(self._current_prices)
            summary = self.portfolio.get_summary(self._current_prices)
            txs = self.portfolio.list_transactions()

            # 總覽（8 個 label）V0.9.4 phase2.3
            self._summary_labels["total_cost"].config(text=f"{summary.total_cost:,.0f}")
            self._summary_labels["total_market_value"].config(text=f"{summary.total_market_value:,.0f}")
            pl_color = "#0a7d2c" if summary.total_unrealized_pl >= 0 else "#c00000"
            self._summary_labels["total_unrealized_pl"].config(text=f"{summary.total_unrealized_pl:+,.0f}", foreground=pl_color)
            self._summary_labels["total_fee"].config(text=f"{summary.total_fee:,.0f}")
            # V0.9.5+ Phase 11：累計證交稅 = 持倉現價累計（current_tax）
            #   「歷史累計已付稅」另外顯示（historical_tax = summary.total_tax）
            self._summary_labels["total_tax"].config(text=f"{summary.current_tax:,.0f}")
            self._summary_labels["historical_tax"].config(text=f"{summary.total_tax:,.0f}")
            net_color = "#0a7d2c" if summary.net_realized_pl >= 0 else "#c00000"
            self._summary_labels["net_realized_pl"].config(text=f"{summary.net_realized_pl:+,.0f}", foreground=net_color)
            ret_color = "#0a7d2c" if summary.total_return_pct >= 0 else "#c00000"
            self._summary_labels["total_return_pct"].config(text=f"{summary.total_return_pct:+.2f}%", foreground=ret_color)
            pl_color2 = "#0a7d2c" if summary.total_pl >= 0 else "#c00000"
            self._summary_labels["total_pl"].config(text=f"{summary.total_pl:+,.0f}", foreground=pl_color2)

            # 持倉明細
            for item in self._positions_tree.get_children():
                self._positions_tree.delete(item)
            for p in positions:
                # 顯示名稱：優先用 fetch 到的最新名稱，其次用 DB 儲存的名稱
                display_name = self._current_names.get(p.stock_id, p.stock_name) or p.stock_name
                self._positions_tree.insert("", "end", values=(
                    p.stock_id, display_name,
                    # 【V0.9.5-locale-comma-fix】Treeview cell 不用千分位
                    # 【V0.9.5-shares-int】股數顯示整數、避免 float 的 .0
                    str(int(p.shares)),
                    f"{p.avg_cost:.2f}",
                    f"{p.current_price:.2f}" if p.current_price > 0 else "—",
                    f"{p.market_value:.0f}" if p.current_price > 0 else "—",
                    f"{p.unrealized_pl:+.0f}" if p.current_price > 0 else "—",
                    f"{p.unrealized_pl_pct:+.2f}%" if p.current_price > 0 else "—",
                    f"{p.realized_pl:+.0f}",
                ))

            # 交易明細
            for item in self._tx_tree.get_children():
                self._tx_tree.delete(item)
            for t in txs:
                self._tx_tree.insert("", "end", values=(
                    t.id, t.trade_date, t.stock_id, t.stock_name,
                    "買" if t.action == "BUY" else "賣",
                    # 【V0.9.5-locale-comma-fix】Treeview cell 不用千分位
                    # 【V0.9.5-shares-int】股數顯示整數、避免 float 的 .0
                    str(int(t.shares)),
                    f"{t.price:.2f}",
                    f"{t.fee:.0f}",
                    f"{t.tax:.0f}",   # V0.9.4 phase2.3: 顯示證交稅（買入為 0）
                    t.note,
                ))

        except Exception as e:
            messagebox.showerror("Refresh 失敗", str(e))

    # ── V0.9.4 phase2.3: 萬年曆挑選日期 ──
    def _pick_date(self, win: tk.Toplevel, var: tk.StringVar, entry: ttk.Entry):
        """打開萬年曆，選中後把 YYYY-MM-DD 寫入 StringVar + Entry"""
        initial = var.get().strip()
        chosen = _CalendarDialog.pick(win, initial)
        if chosen:
            var.set(chosen)
            pass  # date written to var by var.set(chosen) above

    def _open_buy_dialog(self):
        """新增買入對話框（V0.9.4 phase2.3：支援股利配發 price=0、萬年曆選日期）"""
        win = tk.Toplevel(self)
        win.title("新增買入")
        win.geometry("460x420")
        win.transient(self)
        win.grab_set()

        fields = {}

        # Row 0: 股票代號
        ttk.Label(win, text="股票代號", width=10, anchor="e").grid(row=0, column=0, padx=8, pady=4, sticky="e")
        v = tk.StringVar(value="")
        e = ttk.Entry(win, textvariable=v, width=22)
        e.grid(row=0, column=1, padx=8, pady=4, sticky="w")
        fields["stock_id"] = v

        # Row 1: 股票名稱（自動帶出，設為 readonly）
        ttk.Label(win, text="股票名稱", width=10, anchor="e").grid(row=1, column=0, padx=8, pady=4, sticky="e")
        v = tk.StringVar(value="（輸入代號後自動帶出）")
        ttk.Label(win, textvariable=v, foreground="#555", font=("Segoe UI", 9)
                   ).grid(row=1, column=1, padx=8, pady=4, sticky="w")
        fields["stock_name"] = v

        # Row 2: 買入日期（entry + 萬年曆按鈕）V0.9.4 phase2.3
        ttk.Label(win, text="買入日期", width=10, anchor="e").grid(row=2, column=0, padx=8, pady=4, sticky="e")
        date_frame = ttk.Frame(win)
        date_frame.grid(row=2, column=1, padx=8, pady=4, sticky="w")
        v = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        date_entry = ttk.Entry(date_frame, textvariable=v, width=14)
        date_entry.pack(side="left")
        ttk.Button(date_frame, text="📅", width=3, padding="2px",
                   command=lambda v=v, de=date_entry: self._pick_date(win, v, de)
                   ).pack(side="left", padx=(4, 0))
        fields["trade_date"] = v

        # Row 3: 買入股數
        ttk.Label(win, text="買入股數", width=10, anchor="e").grid(row=3, column=0, padx=8, pady=4, sticky="e")
        v = tk.StringVar(value="0")
        ttk.Entry(win, textvariable=v, width=22).grid(row=3, column=1, padx=8, pady=4, sticky="w")
        fields["shares"] = v

        # Row 4: 買入價格（支援 price=0 股利配發）V0.9.4 phase2.3
        ttk.Label(win, text="買入價格", width=10, anchor="e").grid(row=4, column=0, padx=8, pady=4, sticky="e")
        v = tk.StringVar(value="0")
        price_entry = ttk.Entry(win, textvariable=v, width=22)
        price_entry.grid(row=4, column=1, padx=8, pady=4, sticky="w")
        fields["price"] = v

        # Row 5: 備註
        ttk.Label(win, text="備註", width=10, anchor="e").grid(row=5, column=0, padx=8, pady=4, sticky="e")
        v = tk.StringVar(value="")
        ttk.Entry(win, textvariable=v, width=22).grid(row=5, column=1, padx=8, pady=4, sticky="w")
        fields["note"] = v

        # Row 6: 預估手續費 label（V0.9.4 phase2.3: 支援 price=0 股利）
        est_label = ttk.Label(win, text="預估手續費：—（股利配發請設 price=0，手續費為 0）",
                              foreground="#444", font=("Segoe UI", 9, "bold"))
        est_label.grid(row=6, column=0, columnspan=2, padx=8, pady=(10, 4), sticky="w")

        # ── 股票代號失焦 → 自動抓現價 + 名稱 ──
        def on_stock_id_focusout(event=None):
            sid = fields["stock_id"].get().strip()
            if not sid or not sid.isdigit():
                return
            def worker():
                from portfolio import fetch_stock_info
                try:
                    info = fetch_stock_info(sid)
                except Exception as e:
                    info = {"ok": False, "error": str(e)}
                def update_ui():
                    if info.get("ok"):
                        fields["stock_name"].set(info.get("name", ""))
                        if info.get("price", 0) > 0 and fields["price"].get() in ("0", ""):
                            fields["price"].set(f"{info['price']:.2f}")
                        self._update_fee_estimate(fields, "BUY", est_label, win)
                        self.logger.log(f"📡 {sid} {info.get('name', '')} 現價 {info.get('price', 0):.2f}")
                    else:
                        self.logger.log(f"⚠️ {sid} 抓不到現價：{info.get('error', '')}")
                win.after(0, update_ui)
            threading.Thread(target=worker, daemon=True).start()

        # 綁定 FocusOut
        for child in win.grid_slaves():
            if isinstance(child, ttk.Entry) and child.grid_info().get("row") == 0:
                child.bind("<FocusOut>", on_stock_id_focusout)
                child.bind("<Return>", on_stock_id_focusout)
                break

        # 股數 / 價格改變 → 重算預估
        def on_change(*_):
            self._update_fee_estimate(fields, "BUY", est_label, win)
        for k in ("shares", "price"):
            fields[k].trace_add("write", on_change)

        def on_submit():
            try:
                self.portfolio.add_buy(
                    stock_id=fields["stock_id"].get().strip(),
                    trade_date=fields["trade_date"].get().strip(),
                    shares=float(fields["shares"].get()),
                    price=float(fields["price"].get()),
                    stock_name=fields["stock_name"].get().strip(),
                    note=fields["note"].get().strip(),
                )
                self.logger.log(f"✅ 買入新增成功：{fields['stock_id'].get()} {fields['stock_name'].get()}")
                win.destroy()
                self._refresh_portfolio_view()
            except Exception as e:
                messagebox.showerror("新增失敗", str(e), parent=win)

        ttk.Button(win, text="確定", command=on_submit).grid(row=7, column=0, padx=8, pady=12, sticky="e")
        ttk.Button(win, text="取消", command=win.destroy).grid(row=7, column=1, padx=8, pady=12, sticky="w")

    def _open_sell_dialog(self):
        """新增賣出對話框（V0.9.4 phase2.3：萬年曆選日期、手續費+證交稅自動算）"""
        win = tk.Toplevel(self)
        win.title("新增賣出")
        win.geometry("460x400")
        win.transient(self)
        win.grab_set()

        fields = {}

        # Row 0: 股票代號
        ttk.Label(win, text="股票代號", width=10, anchor="e").grid(row=0, column=0, padx=8, pady=4, sticky="e")
        v = tk.StringVar(value="")
        e = ttk.Entry(win, textvariable=v, width=22)
        e.grid(row=0, column=1, padx=8, pady=4, sticky="w")
        fields["stock_id"] = v

        # Row 1: 股票名稱
        ttk.Label(win, text="股票名稱", width=10, anchor="e").grid(row=1, column=0, padx=8, pady=4, sticky="e")
        v = tk.StringVar(value="（輸入代號後自動帶出）")
        ttk.Label(win, textvariable=v, foreground="#555", font=("Segoe UI", 9)
                   ).grid(row=1, column=1, padx=8, pady=4, sticky="w")
        fields["stock_name"] = v

        # Row 2: 賣出日期（entry + 萬年曆按鈕）V0.9.4 phase2.3
        ttk.Label(win, text="賣出日期", width=10, anchor="e").grid(row=2, column=0, padx=8, pady=4, sticky="e")
        date_frame = ttk.Frame(win)
        date_frame.grid(row=2, column=1, padx=8, pady=4, sticky="w")
        v = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        date_entry = ttk.Entry(date_frame, textvariable=v, width=14)
        date_entry.pack(side="left")
        ttk.Button(date_frame, text="📅", width=3, padding="2px",
                   command=lambda v=v, de=date_entry: self._pick_date(win, v, de)
                   ).pack(side="left", padx=(4, 0))
        fields["trade_date"] = v

        # Row 3: 賣出股數
        ttk.Label(win, text="賣出股數", width=10, anchor="e").grid(row=3, column=0, padx=8, pady=4, sticky="e")
        v = tk.StringVar(value="0")
        ttk.Entry(win, textvariable=v, width=22).grid(row=3, column=1, padx=8, pady=4, sticky="w")
        fields["shares"] = v

        # Row 4: 賣出價格
        ttk.Label(win, text="賣出價格", width=10, anchor="e").grid(row=4, column=0, padx=8, pady=4, sticky="e")
        v = tk.StringVar(value="0")
        ttk.Entry(win, textvariable=v, width=22).grid(row=4, column=1, padx=8, pady=4, sticky="w")
        fields["price"] = v

        # Row 5: 備註
        ttk.Label(win, text="備註", width=10, anchor="e").grid(row=5, column=0, padx=8, pady=4, sticky="e")
        v = tk.StringVar(value="")
        ttk.Entry(win, textvariable=v, width=22).grid(row=5, column=1, padx=8, pady=4, sticky="w")
        fields["note"] = v

        # Row 6: 預估成本（手續費 + 證交稅）V0.9.4 phase2.3
        est_label = ttk.Label(win, text="預估成本：—（賣出需繳手續費 + 0.3% 證交稅）",
                              foreground="#444", font=("Segoe UI", 9, "bold"))
        est_label.grid(row=6, column=0, columnspan=2, padx=8, pady=(10, 4), sticky="w")

        # ── 股票代號失焦 → 自動抓現價 + 名稱 ──
        def on_stock_id_focusout(event=None):
            sid = fields["stock_id"].get().strip()
            if not sid or not sid.isdigit():
                return
            def worker():
                from portfolio import fetch_stock_info
                try:
                    info = fetch_stock_info(sid)
                except Exception as e:
                    info = {"ok": False, "error": str(e)}
                def update_ui():
                    if info.get("ok"):
                        fields["stock_name"].set(info.get("name", ""))
                        if info.get("price", 0) > 0 and fields["price"].get() in ("0", ""):
                            fields["price"].set(f"{info['price']:.2f}")
                        self._update_fee_estimate(fields, "SELL", est_label, win)
                        self.logger.log(f"📡 {sid} {info.get('name', '')} 現價 {info.get('price', 0):.2f}")
                    else:
                        self.logger.log(f"⚠️ {sid} 抓不到現價：{info.get('error', '')}")
                win.after(0, update_ui)
            threading.Thread(target=worker, daemon=True).start()

        # 綁定 FocusOut
        for child in win.grid_slaves():
            if isinstance(child, ttk.Entry) and child.grid_info().get("row") == 0:
                child.bind("<FocusOut>", on_stock_id_focusout)
                child.bind("<Return>", on_stock_id_focusout)
                break

        # 股數 / 價格改變 → 重算預估
        def on_change(*_):
            self._update_fee_estimate(fields, "SELL", est_label, win)
        for k in ("shares", "price"):
            fields[k].trace_add("write", on_change)

        def on_submit():
            try:
                self.portfolio.add_sell(
                    stock_id=fields["stock_id"].get().strip(),
                    trade_date=fields["trade_date"].get().strip(),
                    shares=float(fields["shares"].get()),
                    price=float(fields["price"].get()),
                    note=fields["note"].get().strip(),
                )
                self.logger.log(f"✅ 賣出新增成功：{fields['stock_id'].get()}")
                win.destroy()
                self._refresh_portfolio_view()
            except Exception as e:
                messagebox.showerror("新增失敗", str(e), parent=win)

        ttk.Button(win, text="確定", command=on_submit).grid(row=7, column=0, padx=8, pady=12, sticky="e")
        ttk.Button(win, text="取消", command=win.destroy).grid(row=7, column=1, padx=8, pady=12, sticky="w")

    def _update_fee_estimate(self, fields: Dict[str, tk.StringVar], action: str, label: ttk.Label, win: tk.Toplevel):
        """即時更新對話框的『預估手續費 / 成本』label（V0.9.4 phase2.3: 支援 price=0 股利配發）"""
        try:
            shares = float(fields["shares"].get() or 0)
            price = float(fields["price"].get() or 0)
            if shares <= 0:
                label.config(text="預估手續費：—（請輸入股數）")
                return
            if price == 0:
                # V0.9.4 phase2.3: 股利配發（price=0）時不收手續費
                if action == "BUY":
                    label.config(text="股利配發：手續費 0 元（無需填價格）")
                else:
                    label.config(text="預估成本：—（請輸入賣出價格）")
                return
            from portfolio import estimate_total_cost
            est = estimate_total_cost(action, shares, price, self.portfolio.broker_discount)
            if action == "BUY":
                label.config(text=f"預估手續費：{est['fee']:,.2f} 元（買入不收證交稅）")
            else:
                label.config(text=f"預估成本：手續費 {est['fee']:,.2f} + 證交稅 {est['tax']:,.2f} = 共 {est['total']:,.2f} 元")
        except (ValueError, tk.TclError):
            label.config(text="預估手續費：—")

    def _update_prices_dialog(self):
        """V0.9.4：批次從 TWSE 抓現價（可手動覆寫）"""
        positions = self.portfolio.get_positions()
        if not positions:
            messagebox.showinfo("無持倉", "目前沒有持倉股票可更新現價")
            return

        win = tk.Toplevel(self)
        win.title("更新現價（TWSE 自動抓）")
        win.geometry("420x460")
        win.transient(self)
        win.grab_set()

        ttk.Label(win, text="從 TWSE / TPEx 抓取每檔現價（可手動修改）",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 4))
        ttk.Label(win, text="按「自動抓 TWSE」按鈕一次抓全部，個別欄位可手動覆寫",
                  foreground="#666", font=("Segoe UI", 9)).pack(anchor="w", padx=10, pady=(0, 8))

        price_vars = {}
        frame = ttk.Frame(win)
        frame.pack(fill="both", expand=True, padx=10, pady=4)
        for p in positions:
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=f"{p.stock_id} {p.stock_name}", width=20, anchor="w").pack(side="left")
            cur = self._current_prices.get(p.stock_id, 0.0)
            v = tk.StringVar(value=f"{cur:.2f}" if cur > 0 else "")
            ttk.Entry(row, textvariable=v, width=14).pack(side="right")
            price_vars[p.stock_id] = v

        def fetch_all():
            stock_ids = list(price_vars.keys())
            def worker():
                from portfolio import fetch_prices_batch
                try:
                    results = fetch_prices_batch(stock_ids)
                except Exception as e:
                    win.after(0, lambda: messagebox.showerror("抓取失敗", str(e), parent=win))
                    return
                def apply():
                    for sid, info in results.items():
                        if info.get("ok") and info.get("price", 0) > 0:
                            price_vars[sid].set(f"{info['price']:.2f}")
                            if info.get("name"):
                                self._backfill_stock_name(sid, info["name"])
                    self.logger.log(f"📡 自動抓取完成：{sum(1 for v in results.values() if v.get('ok'))}/{len(results)} 檔")
                win.after(0, apply)
            threading.Thread(target=worker, daemon=True).start()

        btn_frame = ttk.Frame(win)
        btn_frame.pack(fill="x", padx=10, pady=8)
        ttk.Button(btn_frame, text="📡 自動抓 TWSE", command=fetch_all).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="確定", command=lambda: apply_and_close()).pack(side="right", padx=2)
        ttk.Button(btn_frame, text="取消", command=win.destroy).pack(side="right", padx=2)

        def apply_and_close():
            for sid, var in price_vars.items():
                txt = var.get().strip()
                if txt:
                    try:
                        self._current_prices[sid] = float(txt)
                    except ValueError:
                        messagebox.showerror("格式錯誤", f"{sid} 現價格式錯誤：{txt!r}", parent=win)
                        return
            self.logger.log(f"✅ 已更新 {len(price_vars)} 檔現價")
            win.destroy()
            self._refresh_portfolio_view()

    def _delete_selected_tx(self):
        """刪除選中的交易（從交易明細 Treeview）"""
        sel = self._tx_tree.selection()
        if not sel:
            messagebox.showinfo("未選取", "請先在「交易明細」表格中選取要刪除的紀錄")
            return
        if not messagebox.askyesno("確認刪除", f"確定要刪除 {len(sel)} 筆交易紀錄？此操作無法復原。"):
            return
        try:
            for item in sel:
                vals = self._tx_tree.item(item, "values")
                tx_id = int(vals[0])
                self.portfolio.delete_transaction(tx_id)
            self.logger.log(f"🗑 已刪除 {len(sel)} 筆交易")
            self._refresh_portfolio_view()
        except Exception as e:
            messagebox.showerror("刪除失敗", str(e))

    # V0.9.4 phase2.3: 編輯交易明細
    def _open_edit_tx_dialog(self):
        """編輯選中的交易（支援 BUY/SELL 修改，fee/tax 自動重算）V0.9.4 phase2.3 修復：action 可編輯"""
        sel = self._tx_tree.selection()
        if not sel:
            messagebox.showinfo("未選取", "請先在「交易明細」表格中選取要編輯的紀錄")
            return
        item = sel[0]
        vals = self._tx_tree.item(item, "values")
        tx_id = int(vals[0])
        tx = self.portfolio.get_transaction(tx_id)
        if not tx:
            messagebox.showerror("錯誤", "找不到這筆交易，請重新整理後再試")
            return

        win = tk.Toplevel(self)
        win.title(f"編輯交易 #{tx_id}")
        win.geometry("460x440")
        win.transient(self)
        win.grab_set()

        fields = {}

        # Row 0: 股票代號（readonly）
        ttk.Label(win, text="股票代號", width=10, anchor="e").grid(row=0, column=0, padx=8, pady=4, sticky="e")
        ttk.Label(win, text=f"{tx.stock_id} {tx.stock_name}", foreground="#555", font=("Segoe UI", 9, "bold")
                  ).grid(row=0, column=1, padx=8, pady=4, sticky="w")

        # Row 1: 買/賣（可切換 BUY↔SELL）V0.9.4 phase2.3 fix: 改為 Combobox
        ttk.Label(win, text="買/賣", width=10, anchor="e").grid(row=1, column=0, padx=8, pady=4, sticky="e")
        v = tk.StringVar(value=tx.action)  # "BUY" or "SELL"
        action_cbox = ttk.Combobox(win, textvariable=v, values=["BUY", "SELL"],
                                   state="readonly", width=8)
        action_cbox.grid(row=1, column=1, padx=8, pady=4, sticky="w")
        fields["action"] = v

        # Row 2: 交易日期（entry + 萬年曆按鈕）
        ttk.Label(win, text="交易日期", width=10, anchor="e").grid(row=2, column=0, padx=8, pady=4, sticky="e")
        date_frame = ttk.Frame(win)
        date_frame.grid(row=2, column=1, padx=8, pady=4, sticky="w")
        v = tk.StringVar(value=tx.trade_date)
        date_entry = ttk.Entry(date_frame, textvariable=v, width=14)
        date_entry.pack(side="left")
        ttk.Button(date_frame, text="📅", width=3, padding="2px",
                   command=lambda v=v, de=date_entry: self._pick_date(win, v, de)
                   ).pack(side="left", padx=(4, 0))
        fields["trade_date"] = v

        # Row 3: 股數
        ttk.Label(win, text="股數", width=10, anchor="e").grid(row=3, column=0, padx=8, pady=4, sticky="e")
        v = tk.StringVar(value=str(tx.shares))
        ttk.Entry(win, textvariable=v, width=22).grid(row=3, column=1, padx=8, pady=4, sticky="w")
        fields["shares"] = v

        # Row 4: 價格（支援 price=0 股利配發 BUY）
        ttk.Label(win, text="價格", width=10, anchor="e").grid(row=4, column=0, padx=8, pady=4, sticky="e")
        v = tk.StringVar(value=str(tx.price))
        ttk.Entry(win, textvariable=v, width=22).grid(row=4, column=1, padx=8, pady=4, sticky="w")
        fields["price"] = v

        # Row 5: 備註
        ttk.Label(win, text="備註", width=10, anchor="e").grid(row=5, column=0, padx=8, pady=4, sticky="e")
        v = tk.StringVar(value=tx.note or "")
        ttk.Entry(win, textvariable=v, width=22).grid(row=5, column=1, padx=8, pady=4, sticky="w")
        fields["note"] = v

        # Row 6: 預估訊息 label
        est_label = ttk.Label(win, text="（ fee / 證交稅將自動重算）",
                              foreground="#444", font=("Segoe UI", 9))
        est_label.grid(row=6, column=0, columnspan=2, padx=8, pady=(10, 4), sticky="w")

        # fee/tax 自動重算（當 action / shares / price 改變時）V0.9.4 phase2.3
        def _recalc(action, shares, price, label):
            try:
                if shares <= 0:
                    label.config(text="（ fee / 證交稅將自動重算）")
                    return
                if price == 0 and action == "BUY":
                    label.config(text="股利配發：手續費 0 元（fee/tax 將自動更新）")
                    return
                if price <= 0:
                    label.config(text="（ fee / 證交稅將自動重算）")
                    return
                from portfolio import estimate_total_cost
                est = estimate_total_cost(action, shares, price, self.portfolio.broker_discount)
                if action == "BUY":
                    label.config(text=f"預估手續費：{est['fee']:,.2f} 元（fee/tax 將自動更新）")
                else:
                    label.config(text=f"預估成本：手續費 {est['fee']:,.2f} + 證交稅 {est['tax']:,.2f} = 共 {est['total']:,.2f} 元")
            except ValueError:
                label.config(text="（ fee / 證交稅將自動重算）")

        def on_change(*_):
            action = fields["action"].get()
            try:
                shares = float(fields["shares"].get() or 0)
                price = float(fields["price"].get() or 0)
            except ValueError:
                shares, price = 0.0, 0.0
            _recalc(action, shares, price, est_label)

        for k in ("action", "shares", "price"):
            fields[k].trace_add("write", on_change)
        on_change()  # 初始顯示一次

        def on_submit():
            try:
                tx.action = fields["action"].get()  # 可能 BUY↔SELL
                tx.trade_date = fields["trade_date"].get().strip()
                tx.shares = float(fields["shares"].get())
                tx.price = float(fields["price"].get())
                tx.note = fields["note"].get().strip()
                # fee / tax 自動重算（以新的 action 為準）
                if tx.action == "BUY":
                    from portfolio import calc_fee
                    tx.fee = calc_fee(tx.shares, tx.price, self.portfolio.broker_discount)
                    tx.tax = 0.0
                else:
                    from portfolio import calc_fee, calc_tax
                    tx.fee = calc_fee(tx.shares, tx.price, self.portfolio.broker_discount)
                    tx.tax = calc_tax(tx.shares, tx.price)
                self.portfolio.update_transaction(tx)
                self.logger.log(f"✏️ 交易 #{tx_id} 已更新（{tx.action}）")
                win.destroy()
                self._refresh_portfolio_view()
            except Exception as e:
                messagebox.showerror("更新失敗", str(e), parent=win)

        ttk.Button(win, text="儲存", command=on_submit).grid(row=7, column=0, padx=8, pady=12, sticky="e")
        ttk.Button(win, text="取消", command=win.destroy).grid(row=7, column=1, padx=8, pady=12, sticky="w")

    def _export_portfolio_excel(self):
        """匯出 4 sheet Excel（讓使用者選存檔位置）"""
        default_name = f"portfolio_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        out = filedialog.asksaveasfilename(
            title="匯出買賣記錄",
            defaultextension=".xlsx",
            initialfile=default_name,
            filetypes=[("Excel 檔案", "*.xlsx"), ("所有檔案", "*.*")],
        )
        if not out:
            return
        try:
            self.portfolio.export_excel(out, current_prices=self._current_prices)
            self.logger.log(f"📤 已匯出：{out}")
            messagebox.showinfo("匯出成功", f"已寫入：\n{out}")
        except Exception as e:
            messagebox.showerror("匯出失敗", str(e))

    def _on_run(self):
        self.run_btn.config(state="disabled")
        self.console.insert("end", "=" * 60 + "\n")
        self.console.insert("end", f"🚀 StockTool {VERSION} 開始執行\n")
        self.console.insert("end", "=" * 60 + "\n")
        self.console.see("end")

        self._save_ui_to_config()
        cfg = self.cfg
        save_config(cfg.to_dict())

        def worker():
            try:
                # V0.9.5-tab-split-phase3 B-1：接收 result
                # 【V0.9.5-tab-split-phase3-C Fix2】只跑篩選（不回測）
                df_sel = _run_selection_only(cfg, self.logger)
                self._last_select_df = df_sel
                self._select_checked = {}
                self.after(0, lambda df=df_sel: self._display_select_results(df))
                self.after(0, lambda: self.logger.log(
                    f"✅ 篩選完成，共 {len(df_sel)} 檔｜"
                    f"勾選後按「💾 匯出股票清單」可匯出至 Excel\n"
                    f"→ 餵入「策略參數 → 使用 Excel 股票清單」執行回測"
                ))
            except Exception as e:
                self.logger.log(f"❌ 執行失敗：{e}")
                import traceback
                self.logger.log(traceback.format_exc())
            finally:
                self.run_btn.config(state="normal")

        threading.Thread(target=worker, daemon=True).start()

    def _on_bt_run(self):
        """【V0.9.5-tab-split-phase3-C】回測 Tab 的「▶ 執行回測模擬」按鈕"""
        # Fix4：回測是獨立功能，直接從 excel_file_var 讀取，不依賴系統選股勾選
        excel_file = self.excel_file_var.get().strip()
        if not excel_file:
            messagebox.showwarning("無檔案", "請先選擇 Excel 股票清單檔案，再執行回測")
            return

        # 複製一份 cfg，強制使用 Excel 清單模式
        import copy
        cfg = copy.copy(self.cfg)
        cfg.use_excel_stock_list = True
        cfg.excel_stock_file = excel_file
        cfg.excel_force_buy = self.excel_force_buy_var.get()
        cfg.use_top10_backtest = False  # Fix3：永遠不用 Top10 模式

        self.bt_run_btn.config(state="disabled")
        self.console.insert("end", "\n" + "=" * 60 + "\n")
        self.console.insert("end", "📊 執行回測模擬（" + excel_file + ")\n")
        self.console.insert("end", "=" * 60 + "\n")
        self.console.see("end")

        def worker():
            try:
                result = run_pipeline(cfg, self.logger)
                if result and "df_sel" in result:
                    self.after(0, lambda: self._display_bt_results(result))
            except Exception as e:
                self.logger.log(f"❌ 回測失敗：{e}")
                import traceback
                self.logger.log(traceback.format_exc())
            finally:
                self.after(0, lambda: self.bt_run_btn.config(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def _display_bt_results(self, result):
        """【V0.9.5-tab-split-phase3-C Fix7】把回測 KPI 結果顯示在 bt_tree"""
        bt_tree = getattr(self, 'backtest_tree', None)
        if bt_tree is None:
            self.logger.log("⚠️ 回測結果 Treeview 未找到")
            return

        for item in bt_tree.get_children():
            bt_tree.delete(item)

        def _fmt(v, na="--"):
            try:
                if pd.isna(v) or v is None:
                    return na
                return format(float(v), ".2f")
            except Exception:
                return na

        def _icol(v, na="--"):
            try:
                if pd.isna(v) or v is None:
                    return na
                return format(int(float(v)), ".0f")
            except Exception:
                return na

        if not bt_tree["columns"]:
            cols = ("指標", "數值1", "數值2", "數值3", "數值4", "數值5", "數值6", "數值7")
            col_widths = (140, 100, 90, 80, 70, 70, 70, 70)
            bt_tree.configure(columns=cols)
            for col, w in zip(cols, col_widths):
                bt_tree.heading(col, text=col)
                bt_tree.column(col, width=w, anchor="center")
            bt_tree.column("#0", width=0)

        BLANK = ("", "", "", "", "", "", "", "")

        # ── Portfolio-level KPI ──────────────────────────────────────────
        bt_tree.insert("", "end", iid="hdr_pf", values=("📊 投組層級 KPI", "", "", "", "", "", "", ""))
        pf_kpi = result.get("pf_kpi")
        if pf_kpi is not None and not pf_kpi.empty:
            row = pf_kpi.iloc[0]
            items = [
                ("CAGR (%)", _fmt(row.get("CAGR(%)"))),
                ("MDD (%)", _fmt(row.get("MDD(%)"))),
                ("Sharpe", _fmt(row.get("Sharpe"))),
                ("Sortino", _fmt(row.get("Sortino"))),
                ("總交易次數", _icol(row.get("Trades"))),
                ("最大連虧次數", _icol(row.get("MaxLosingStreak"))),
                ("Profit Factor", _fmt(row.get("ProfitFactor"))),
            ]
            for i, (label, val) in enumerate(items):
                row_data = [label, val] + [""] * 6
                bt_tree.insert("", "end", iid=f"pf_{i}", values=tuple(row_data))

        # ── 實收金額 ──────────────────────────────────────────────────
        capital = result.get("capital", 0)
        final_equity = result.get("final_equity", 0)
        if capital and final_equity:
            total_ret = (final_equity / capital - 1) * 100
            bt_tree.insert("", "end", iid="hdr_money", values=("💰 資金摘要", "", "", "", "", "", "", ""))
            money_items = [
                ("初始本金 (元)", f"{capital:,.0f}"),
                ("最終權益 (元)", f"{final_equity:,.0f}"),
                ("總報酬 (%)", f"{total_ret:+.1f}%"),
                ("標準化起始→最終", f"1.0000  →  {final_equity/capital:.4f}"),
            ]
            for i, (label, val) in enumerate(money_items):
                row_data = [label, val] + [""] * 6
                bt_tree.insert("", "end", iid=f"money_{i}", values=tuple(row_data))

        # ── Signal-level KPI ────────────────────────────────────────────
        bt_tree.insert("", "end", iid="hdr_sig", values=("📈 訊號層級 KPI", "", "", "", "", "", "", ""))
        sig = result.get("sig_summary")
        if sig is not None and not sig.empty:
            row = sig.iloc[0]
            items = [
                ("訊號數", _icol(row.get("訊號數"))),
                ("平均報酬 (%)", _fmt(row.get("事件型平均報酬_扣成本(%)"))),
                ("勝率 (%)", _fmt(row.get("事件型勝率_扣成本(%)"))),
                ("中位數報酬 (%)", _fmt(row.get("事件型中位數_扣成本(%)"))),
                ("Profit Factor", _fmt(row.get("ProfitFactor"))),
            ]
            for i, (label, val) in enumerate(items):
                row_data = [label, val] + [""] * 6
                bt_tree.insert("", "end", iid=f"sig_{i}", values=tuple(row_data))

        # ── 年度績效 ──────────────────────────────────────────────────
        yearly = result.get("yearly_perf")
        if yearly is not None and not yearly.empty:
            bt_tree.insert("", "end", iid="hdr_yr", values=("📅 年度績效", "年份", "交易次數", "勝率(%)", "平均報酬(%)", "Profit Factor", "", ""))
            for i, (_, yr) in enumerate(yearly.iterrows()):
                row_data = [
                    "",
                    _icol(yr.get("year")),
                    _icol(yr.get("trades")),
                    _fmt(yr.get("win_rate(%)")),
                    _fmt(yr.get("avg_return(%)")),
                    _fmt(yr.get("profit_factor")),
                    "", ""
                ]
                bt_tree.insert("", "end", iid=f"yr_{i}", values=tuple(row_data))

        # ── 出場原因統計 ──────────────────────────────────────────────
        reason = result.get("reason_stats")
        if reason is not None and not reason.empty:
            bt_tree.insert("", "end", iid="hdr_exit", values=("🚪 出場原因統計", "", "", "", "", "", "", ""))
            for i, (_, rw) in enumerate(reason.iterrows()):
                row_data = [
                    "",
                    str(rw.get("index", "")),
                    _icol(rw.get("次數")),
                    _fmt(rw.get("比例(%)")),
                    "", "", "", ""
                ]
                bt_tree.insert("", "end", iid=f"exit_{i}", values=tuple(row_data))

        self.logger.log("✅ 回測結果已顯示於上方表格")

    def _display_select_results(self, df_sel):
        """【V0.9.5-tab-split-phase3 B-1】把選股結果顯示在 select_tree

        顯示欄位：代號、名稱、股價、Score、營收YoY、EPSYoY、PE、殖利率
        """
        if df_sel is None or df_sel.empty:
            self.logger.log("⚠️ 選股結果為空、無法顯示")
            return

        # 清空舊資料
        for item in self.select_tree.get_children():
            self.select_tree.delete(item)

        # 設定欄位（如果還沒設定）
        if not self.select_tree["columns"]:
            cols = ("☑", "代號", "名稱", "股價", "Score", "營收YoY(%)", "EPSYoY(%)", "PE", "殖利率(%)")
            col_widths = (35, 60, 100, 60, 60, 80, 80, 50, 70)
            self.select_tree.configure(columns=cols)
            for col, w in zip(cols, col_widths):
                self.select_tree.heading(col, text=col)
                self.select_tree.column(col, width=w, anchor="center")
            # 【V0.9.5-tab-split-phase3-D】初始 header 設為 ☐（看起來像個 checkbox）
            try:
                self.select_tree.heading(cols[0], text="☐")
            except (IndexError, tk.TclError):
                pass

        # 【V0.9.5-goodinfo6+】William 2026-06-26 13:56 反映：
        #  系統選股結果 9946 殖利率顯示 0.07 (應為 0)、
        #                4973 殖利率顯示 0.015 (應為 1.28%)
        # 根因：Treeview 用 _fmt(yld) = 0.069 → 顯示 0.07
        #       但 yld 是小數 (0.069 = 6.9%)、應該 * 100 變成 %
        # 修法：殖利率用 _fmt_pct(yld)、×100 變成 %
        def _fmt_pct(v, fmt=".2f", na="--"):
            try:
                if pd.isna(v) or v is None:
                    return na
                return format(v * 100, fmt)
            except Exception:
                return na

        # 填資料（取前 60 筆、避免太慢）
        display_count = 0
        for idx, row in df_sel.head(60).iterrows():
            code = str(row.get("股票代號", "")).strip()
            if not code:
                continue
            name = str(row.get("公司名稱_來源", row.get("股票名稱", "")))
            price = row.get("股價", row.get("收盤價", 0))
            score = row.get("Score", 0)
            rev_yoy = row.get("營收YoY(%)", 0)
            _raw_ey = row.get("EPSYoY_顯示(%)", row.get("EPSYoY(%)", 0))
            eps_yoy = 0 if (isinstance(_raw_ey, float) and __import__("pandas").isna(_raw_ey)) else _raw_ey
            pe = row.get("PE", 0)
            yld = row.get("殖利率(估)", row.get("殖利率(%)", 0))

            # 顯示：股價用 .2f、PE 用 .2f（無千分位避免 locale bug）
            def _fmt(v, fmt=".2f", na="--"):
                try:
                    if pd.isna(v) or v is None:
                        return na
                    return format(v, fmt)
                except Exception:
                    return na

            tag = "checked" if self._select_checked.get(code, False) else "unchecked"
            self.select_tree.insert("", "end", iid=code, values=(
                "☑" if self._select_checked.get(code, False) else "☐",
                code,
                name[:8] if name else "--",
                _fmt(price),
                _fmt(score, fmt=".3f"),
                _fmt(rev_yoy),
                _fmt(eps_yoy),
                _fmt(pe),
                _fmt_pct(yld),
            ), tags=(tag,))
            display_count += 1

        self.logger.log(f"📋 已顯示 {display_count} 筆選股結果（總共 {len(df_sel)} 筆）")
        # 【V0.9.5-tab-split-phase3-D】動態更新 checkbox header（新資料剛填、預設全未勾 → ☐）
        self._update_checkbox_header(self.select_tree, self._select_checked)
        # 【V0.9.5-tab-split-phase3-C】enable 匯出按鈕
        if hasattr(self, "export_select_btn"):
            self.export_select_btn.config(state="normal")
            self.logger.log("💾 [B-3] 匯出股票清單按鈕已啟用")

    def _export_select_results_excel(self):
        """【V0.9.5-tab-split-phase3-C】匯出系統選股結果到 Excel

        跟手動選股 / ETF 的匯出邏輯類似：
        - 沒資料 → 跳 warning
        - 詢問存檔位置、預設檔名 系統選股_YYYYMMDD_HHMM.xlsx
        - 寫 xlsx（openpyxl）+ 標題列高亮 + 自動欄寬 + NaN 處理
        - 提示：可直接餵回「使用 Excel 股票清單」
        """
        if not hasattr(self, "_last_select_df") or self._last_select_df is None or self._last_select_df.empty:
            messagebox.showwarning("無資料", "請先按「▶ 執行系統選股」產生結果")
            return

        result = self._last_select_df.copy()

        # 【V0.9.5-tab-split-phase3-C】只匯出勾選檔
        checked_codes = [k for k, v in self._select_checked.items() if v]
        if not checked_codes:
            messagebox.showwarning("無勾選", "請先在系統選股結果中勾選要匯出的股票\n（點擊左側☑/☐欄位切換勾選狀態）")
            return
        result = result[result["股票代號"].astype(str).str.strip().isin(checked_codes)]
        if result.empty:
            messagebox.showwarning("無勾選", "選股結果中找不到已勾選的股票代號，請重新勾選")
            return

        filename = simpledialog.askstring(
            "儲存名稱設定",
            "請輸入檔案名稱（不含副檔名）:",
            initialvalue=f"系統選股_{datetime.now().strftime('%Y%m%d_%H%M')}"
        )
        if not filename:
            return
        filename = filename.strip()
        if not filename:
            return
        if not filename.endswith(".xlsx"):
            filename += ".xlsx"
        filepath = os.path.join(SOURCE_DIR, filename)

        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment

            wb = Workbook()
            ws = wb.active
            ws.title = "系統選股"

            headers = list(result.columns)
            ws.append(headers)

            header_fill = PatternFill("solid", fgColor="4472C4")
            header_font = Font(color="FFFFFF", bold=True)
            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center")

            for row_data in result.values.tolist():
                ws.append([
                    "" if (v is None or (isinstance(v, float) and pd.isna(v))) else v
                    for v in row_data
                ])

            for col in ws.columns:
                max_len = max(len(str(cell.value or "")) for cell in col)
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 30)

            wb.save(filepath)
            self.logger.log(f"📤 已匯出 {len(result)} 檔到 {filepath}")
            messagebox.showinfo(
                "匯出成功",
                f"已匯出 {len(result)} 檔\n\n📂 已儲存至 source/ 資料夾\n💡 這個檔案可以直接給「策略參數 → 使用 Excel 股票清單」讀取使用",
            )
        except Exception as e:
            messagebox.showerror("匯出失敗", str(e))
            self.logger.log(f"❌ 匯出失敗：{e}")


    # ══════════════════════════════════════════════════════════════
    # 【V0.9.5-tab-split-phase3-C】勾選機制 handler
    # ══════════════════════════════════════════════════════════════

    def _on_select_tree_hover(self, event):
        """系統選股 / 回測結果 Treeview hover：黃色 highlight

        邏輯：
        - 進新列 → 離開舊列（restore 原本 tag）、進新列（hover）
        - 離開 cell/列 → restore 舊列原本 tag
        - 移到同一列 → 不動作
        """
        tree = event.widget
        if not hasattr(self, "_select_hover_iids"):
            self._select_hover_iids = {}

        region = tree.identify("region", event.x, event.y)
        iid = tree.identify_row(event.y) if region == "cell" else None

        old_iid = self._select_hover_iids.get(id(tree))

        # 移到同一列 → 不動作
        if iid and iid == old_iid:
            return

        # 離開舊列：restore 原本 tag（hover → checked/unchecked）
        if old_iid and old_iid in tree.get_children():
            checked = self._select_checked.get(old_iid, False) if tree == self.select_tree else getattr(self, "_bt_checked", {}).get(old_iid, False)
            tree.item(old_iid, tags=("checked" if checked else "unchecked",))

        # 進新列 or 無效區域
        if iid and iid in tree.get_children():
            self._select_hover_iids[id(tree)] = iid
            tree.item(iid, tags=("hover",))
        else:
            # 離開範圍：刪除 hover 記錄
            self._select_hover_iids.pop(id(tree), None)

    def _on_select_tree_leave(self, event):
        self._clear_select_hover(event.widget)

    def _clear_select_hover(self, tree):
        """清除 hover highlight、restore 該列原本 tag（供外部呼叫）"""
        if not hasattr(self, "_select_hover_iids"):
            return
        iid = self._select_hover_iids.get(id(tree))
        if not iid or iid not in tree.get_children():
            return
        checked = self._select_checked.get(iid, False) if tree == self.select_tree else getattr(self, "_bt_checked", {}).get(iid, False)
        tree.item(iid, tags=("checked" if checked else "unchecked",))
        self._select_hover_iids.pop(id(tree), None)

    def _on_select_tree_click(self, event):
        """點勾選欄 header → 全選/全不選；點任一列 → toggle"""
        tree = event.widget
        region = tree.identify("region", event.x, event.y)
        column = tree.identify_column(event.x)

        # header click → 全選/全不選
        if region == "heading" and column == "#1":
            if tree == self.select_tree:
                checked_dict = self._select_checked
            else:
                if not hasattr(self, "_bt_checked"):
                    self._bt_checked = {}
                checked_dict = self._bt_checked
            all_checked = all(checked_dict.get(item, False) for item in tree.get_children())
            if all_checked:
                self._select_none(tree)
            else:
                self._select_all(tree)
            return

        # cell click → toggle
        if region != "cell" or column != "#1":
            return
        iid = tree.identify_row(event.y)
        if not iid:
            return
        if tree == self.select_tree:
            checked_dict = self._select_checked
        else:
            if not hasattr(self, "_bt_checked"):
                self._bt_checked = {}
            checked_dict = self._bt_checked
        current = checked_dict.get(iid, False)
        checked_dict[iid] = not current
        vals = list(tree.item(iid, "values"))
        vals[0] = "☑" if not current else "☐"
        tree.item(iid, values=vals, tags=("checked" if not current else "unchecked",))
        # 【V0.9.5-tab-split-phase3-D】動態更新 header（個別 toggle 也會影響整體狀態）
        self._update_checkbox_header(tree, checked_dict)

    # 【V0.9.5-tab-split-phase3-F】拿掉右鍵「全選/全不選」選單（_on_select_tree_rclick）

    def _select_all(self, tree=None):
        tree = tree or self.select_tree
        checked_dict = self._select_checked if tree == self.select_tree else getattr(self, "_bt_checked", {})
        for item in tree.get_children():
            checked_dict[item] = True
            vals = list(tree.item(item, "values"))
            vals[0] = "☑"
            tree.item(item, values=vals, tags=("checked",))
        # 【V0.9.5-tab-split-phase3-D】動態更新 header
        self._update_checkbox_header(tree, checked_dict)

    def _select_none(self, tree=None):
        tree = tree or self.select_tree
        checked_dict = self._select_checked if tree == self.select_tree else getattr(self, "_bt_checked", {})
        for item in tree.get_children():
            checked_dict[item] = False
            vals = list(tree.item(item, "values"))
            vals[0] = "☐"
            tree.item(item, values=vals, tags=("unchecked",))
        # 【V0.9.5-tab-split-phase3-D】動態更新 header
        self._update_checkbox_header(tree, checked_dict)

    def _update_checkbox_header(self, tree, checked_dict):
        """【V0.9.5-tab-split-phase3-D】依全選狀態動態更新 checkbox header ☑/☐/▣

        - 0 個 rows 或 0 個 checked → ☐
        - 全部 checked → ☑
        - 部分 checked → ▣（混和狀態）

        為什麼要動態更新？
        - 原本 header 永遠是「勾選」字樣、不管全選/全不選都長一樣
        - 使用者點 header 後 rows 都勾起來了、但 header 沒反饋、看不出點成功
        - 動態切 ☑/☐/▣ 可以明確表達「目前整體狀態」

        Args:
            tree: ttk.Treeview（select_tree / backtest_tree / ms_tree / etf_tree 都可用）
            checked_dict: dict[iid -> bool]
        """
        try:
            items = list(tree.get_children())
            if not items:
                header_text = "☐"
            else:
                checked_count = sum(
                    1 for iid in items if checked_dict.get(iid, False)
                )
                if checked_count == 0:
                    header_text = "☐"
                elif checked_count == len(items):
                    header_text = "☑"
                else:
                    header_text = "▣"  # 混和狀態
            # 取第一欄 ID 來更新 header
            cols = tree["columns"]
            if cols:
                first_col = cols[0]
                tree.heading(first_col, text=header_text)
        except (tk.TclError, IndexError, KeyError):
            # Treeview 已被銷毀 / 還沒建好 / 欄位未設定 → 靜默跳過
            pass


if __name__ == "__main__":
    app = StrategyGUI()
    app.mainloop()
