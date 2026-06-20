"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                               StockTool.py                                   ║
║               台灣股市量化選股系統 v0.9.5-tab-split-phase3 (2026-06-20 22:30)      ║
╚══════════════════════════════════════════════════════════════════════════════╝
V0.9.5-cache
【版本資訊】
Version: v0.9.5-tab-split-phase3
最後更新: 2026-06-20 22:39 (Asia/Taipei)
Python 版本: 3.8+
依賴套件: tkinter, pandas, requests, openpyxl, numpy, itertools

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
# 中央管理版本號、避免各處手動改不到
VERSION = "v0.9.5-tab-split-phase3"


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

from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.formatting.rule import CellIsRule

# V0.9.4 買賣記錄模組
from portfolio import PortfolioDB, Transaction, DEFAULT_PORTFOLIO_DB

warnings.filterwarnings("ignore")

# ==========================================================
# 0) Config 檔案路徑與預設設定
# ==========================================================

CONFIG_FILE = "stocktool_config.json"

DEFAULT_CONFIG = {
    "top_n_for_tech": 60,
    "tech_months": 24,
    "history_months": 60,
    "timeout": 30,
    "verify_ssl": False,
    "use_excel_stock_list": False,
    "excel_stock_file": "stock_list.xlsx",
    "use_enhanced_score": True,
    "use_top10_backtest": False,
    "excel_force_buy": False,
    "factor_weight_mom1": 0.15,
    "factor_weight_mom3": 0.15,
    "factor_weight_mom6": 0.20,
    "factor_weight_rev": 0.25,
    "factor_weight_eps": 0.25,
    "simple_score_weight_rev": 35.0,
    "simple_score_weight_eps": 35.0,
    "simple_score_weight_div": 20.0,
    "simple_score_weight_pe": -5.0,
    "simple_min_rev_yoy": -999.0,
    "simple_min_eps_yoy": -999.0,
    "simple_min_eps": -999.0,
    "simple_max_pe": 999.0,
    "eps_history_db": "eps_history.db",
    "use_mtf_confirmation": True,
    "use_divergence_detection": True,
    "volume_surge_multiplier": 2.0,
    "wf_enabled": False,
    "wf_train_years": 2,
    "wf_test_years": 1,
    "wf_step_years": 1,
    "twse_retries": 3,
    "twse_backoff": 0.8,
    "twse_sleep": 0.12,
    "topk": 7,
    "hold_days": 10,
    "roundtrip_cost_pct": 0.004,
    "stop_loss": -0.03,
    "take_profit": 0.08,
    "exit_rsi": 70,
    "use_gate": False,
    "min_rev_yoy": 0.0,
    "min_eps_yoy": 0.0,
    "allow_eps_yoy_nan": True,
    "risk_free_annual": 0.0,
    "mar_annual": 0.0,
    "trading_days": 252,
    "rsi_oversold": 40,
    "oversold_lookback": 10,
    "rsi_recover": 40,
    "rsi_aggressive": 45,
    "use_aggressive_signal": True,
    "require_trend_filter": True,
    "ma_slope_days": 3,
    "ma20_tolerance": 0.01,
    "require_volume_filter": True,
    "strong_revenue_yoy": 10.0,
    "strong_pe_max": 30.0,
    "strong_price_min": 10.0,
    "out_file_prefix": "選股報表",
    # V0.9.4 phase2.3: 交易成本設定（台股預設值）
    "broker_discount": 1.0,          # 券商折扣（1.0 = 無折扣，0.6 = 6折）
    # V0.9.5: 手動選股 Preset
    "manual_select_presets": {},
    "manual_select_last_preset": None,
}


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved_config = json.load(f)
            config = DEFAULT_CONFIG.copy()
            config.update(saved_config)
            return config
        except Exception as e:
            print(f"載入設定檔失敗: {e}")
            return DEFAULT_CONFIG.copy()
    else:
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"儲存設定檔失敗: {e}")
        return False


# ==========================================================
# StrategyConfig
# ==========================================================

HISTORY_DIR = "cache/history"


@dataclass
class StrategyConfig:
    top_n_for_tech: int = 60
    tech_months: int = 24
    history_months: int = 60
    timeout: int = 30
    verify_ssl: bool = False
    use_excel_stock_list: bool = False
    excel_stock_file: str = "stock_list.xlsx"
    use_enhanced_score: bool = True
    use_top10_backtest: bool = False
    excel_force_buy: bool = False      # Excel 清單強制買點模式
    factor_weight_mom1: float = 0.15
    factor_weight_mom3: float = 0.15
    factor_weight_mom6: float = 0.20
    factor_weight_rev: float = 0.25
    factor_weight_eps: float = 0.25
    simple_score_weight_rev: float = 35.0
    simple_score_weight_eps: float = 35.0
    simple_score_weight_div: float = 20.0
    simple_score_weight_pe: float = -5.0
    simple_min_rev_yoy: float = -999.0
    simple_min_eps_yoy: float = -999.0
    simple_min_eps: float = -999.0
    simple_max_pe: float = 999.0
    eps_history_db: str = "eps_history.db"
    # V0.9.4 phase2.3: 券商折扣（1.0 = 無折扣，0.6 = 6折）
    broker_discount: float = 1.0
    use_mtf_confirmation: bool = True
    use_divergence_detection: bool = True
    volume_surge_multiplier: float = 2.0
    wf_enabled: bool = False
    wf_train_years: int = 2
    wf_test_years: int = 1
    wf_step_years: int = 1
    twse_retries: int = 3
    twse_backoff: float = 0.8
    twse_sleep: float = 0.12
    topk: int = 7
    hold_days: int = 10
    roundtrip_cost_pct: float = 0.004
    stop_loss: float = -0.03
    take_profit: float = 0.08
    exit_rsi: int = 70
    use_gate: bool = False
    min_rev_yoy: float = 0.0
    min_eps_yoy: float = 0.0
    allow_eps_yoy_nan: bool = True
    risk_free_annual: float = 0.0
    mar_annual: float = 0.0
    trading_days: int = 252
    rsi_oversold: int = 45
    oversold_lookback: int = 10
    rsi_recover: int = 40
    rsi_aggressive: int = 45
    use_aggressive_signal: bool = True
    require_trend_filter: bool = True
    ma_slope_days: int = 3
    ma20_tolerance: float = 0.01
    require_volume_filter: bool = True
    strong_revenue_yoy: float = 10.0
    strong_pe_max: float = 30.0
    strong_price_min: float = 10.0
    out_file_prefix: str = "選股報表"
    # V0.9.5: 手動選股 Preset
    manual_select_presets: dict = field(default_factory=dict)
    manual_select_last_preset: str = None

    def to_dict(self) -> dict:
        return asdict(self)

    def update_from_dict(self, data: dict):
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)


# ==========================================================
# Logger
# ==========================================================

class GuiLogger:
    def __init__(self, q: queue.Queue):
        self.q = q

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.q.put(f"[{ts}] {msg}")
# ==========================================================
# Session
# ==========================================================

def build_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) StockTool/AdvisorStyle-{VERSION}",
        "Accept": "application/json,text/plain,*/*"
    })
    return s


# ==========================================================
# Utility functions
# ==========================================================

def find_col(cols, keywords):
    for c in cols:
        s = str(c)
        for k in keywords:
            if k in s:
                return c
    return None


def get_cache_file(name):
    return f"cache/{name}.xlsx"


def save_cache(file_path, df):
    os.makedirs("cache", exist_ok=True)
    today = datetime.today().strftime("%Y-%m-%d")
    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="data", index=False)
        meta = pd.DataFrame({"last_update": [today]})
        meta.to_excel(writer, sheet_name="meta", index=False)


def load_cache(file_path):
    """讀取快取檔案（data + meta sheet）

    【V0.9.5-goodinfo4+5 (vol-no-divide) 修容錯】2026-06-18 22:07 William 反映
    - 之前舊 cache 只有 data sheet、沒有 meta → load_cache 直接 crash
    - 「Worksheet named 'meta' not found → fallback 讀舊 cache」錯訊
    - 修法：meta 不存在時 fallback 回傳今天日期（視為剛抓的、不觸發 refresh）
    """
    df = pd.read_excel(file_path, sheet_name="data", engine="openpyxl")
    try:
        meta = pd.read_excel(file_path, sheet_name="meta", engine="openpyxl")
        last_update = meta.loc[0, "last_update"]
    except Exception:
        # 舊 cache 沒 meta sheet → 視為剛抓的、不觸發 refresh
        # 下次 save_cache 時會補上 meta sheet
        last_update = datetime.today().strftime("%Y-%m-%d")
    return df, last_update


# 【V0.9.5-cache-info 新增】2026-06-19 William 要求：
#   「_is_market_hours() 要處理台股半日盤（過年前封關日 13:00 收盤）」
#   每年封關日不同、需手動維護此表
#   來源：台灣證券交易所公告的「市場開休市日程」
_HALF_DAY_DATES = {
    "2026-02-13",  # 2026 過年封關日（除夕 2/16 前最後交易日、週五），13:00 收盤
    # "2027-02-05",  # 2027 過年封關日（待驗證）
    # 每年加新日期之前先查證：https://www.twse.com.tw/zh/holidaySchedule/holiday
}


def _is_market_hours(now: Optional[datetime] = None) -> bool:
    """判斷是否在台股盤中時段

    V0.9.5+ Phase 7 新規則（William 2026-06-15 09:56）：
    - 平日 09:00 開盤後到收盤前：股價會一直變 → 任何需要現價的功能都要 refresh
    - 收盤後到隔天 09:00 開盤前：股價已固定 → 一天只要 refresh 一次
    - 週末（週六、週日）：不開盤 → 用上週五收盤價、一天只要 refresh 一次

    V0.9.5-cache-info 新規則（William 2026-06-19 14:17）：
    - 半日盤（過年封關日等）：13:00 收盤、不是 13:30
    - 依據 _HALF_DAY_DATES 清單判斷

    Returns
    -------
    bool
        True = 盤中（強制 refresh 股價）
        False = 盤前/盤後/週末（一天只 refresh 一次、靠 cache 判斷）

    用途：get_or_fetch 內判斷「price 類 cache」是否要走強制 refresh 路徑
    """
    now = now or datetime.now()
    # 週末（週六=5、週日=6）不開盤
    if now.weekday() >= 5:
        return False
    # 半日盤 → 13:00 收盤；一般交易日 → 13:30 收盤
    is_half_day = now.strftime("%Y-%m-%d") in _HALF_DAY_DATES
    if is_half_day:
        market_close = now.replace(hour=13, minute=0, second=0, microsecond=0)
    else:
        market_close = now.replace(hour=13, minute=30, second=0, microsecond=0)
    market_open = now.replace(hour=9, minute=0, second=0, microsecond=0)
    return market_open <= now <= market_close


def get_or_fetch(name: str, fetch_func, logger: GuiLogger):
    file_path = get_cache_file(name)
    today = datetime.today().strftime("%Y-%m-%d")
    if not os.path.exists(file_path):
        logger.log(f"📥 [{name}] 無快取 → 下載資料")
        df = fetch_func()
        save_cache(file_path, df)
        return df
    df, last_update = load_cache(file_path)

    # V0.9.5+ Phase 7（William 2026-06-15 09:56）：
    # 股價 (price) 在盤中會一直變 → 強制 refresh、不限次數
    # 盤後/盤前/週末 → 一天只 refresh 一次（last_update == today → 用 cache）
    # 注：revenue/eps 不適用本規則、仍用原本「last_update == today」判斷
    if name == "price" and _is_market_hours():
        logger.log(f"🔄 [{name}] 盤中時段 → 強制 refresh 股價")
        df = fetch_func()
        save_cache(file_path, df)
        return df

    if last_update == today:
        # 【V0.9.5-cache-vol 結構遷移】2026-06-19 William 反映
        # 即使 cache 是今天的、也可能是 v0.9.5-goodinfo4+5 以前的舊版（缺 成交量_張 / data_date）
        # 加一次結構檢查：有缺欄位就強制重抓一次、寫入新結構
        if name == "price":
            required_cols = {"成交量_張", "data_date"}
            missing = required_cols - set(df.columns)
            if missing:
                logger.log(
                    f"♻️ [{name}] cache 缺欄位 {sorted(missing)}、強制重抓一次 → 寫入新結構"
                )
                df = fetch_func()
                save_cache(file_path, df)
                return df
        logger.log(f"✅ [{name}] 使用快取資料")
        return df
    logger.log(f"♻️ [{name}] 資料過期 → 重新下載")
    df = fetch_func()
    save_cache(file_path, df)
    return df


def to_num_series(s: pd.Series) -> pd.Series:
    return pd.to_numeric(
        s.astype(str)
         .str.replace(",", "", regex=False)
         .str.replace("%", "", regex=False)
         .str.replace("+", "", regex=False)
         .str.strip(),
        errors="coerce"
    )


def month_starts_back(n_months: int) -> List[str]:
    today = date.today()
    y, m = today.year, today.month
    out = []
    for i in range(n_months):
        mm = m - i
        yy = y
        while mm <= 0:
            yy -= 1
            mm += 12
        out.append(f"{yy}{mm:02d}01")
    return out


def roc_to_ad(roc_str: str):
    parts = str(roc_str).strip().split("/")
    if len(parts) != 3:
        return None
    yy = int(parts[0]) + 1911
    mm = int(parts[1])
    dd = int(parts[2])
    return date(yy, mm, dd)


# ==========================================================


# 股利歷史庫（跟 eps_history 同一風格）
DIV_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS dividend_history (
    stock_id        TEXT    NOT NULL,
    year            INTEGER NOT NULL,
    cash            REAL,
    stock           REAL,
    source          TEXT,
    fetched_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    ex_date         TEXT,        -- V0.9.5+ Phase 10：除息日 (YYYY-MM-DD)
    ex_date_close   REAL,        -- V0.9.5+ Phase 10：除息日收盤價（用來算 殖利率）
    cash_yield_pct  REAL,        -- V0.9.5-goodinfo：該年現金殖利率（%, goodinfo 來源）
    share_yield_pct REAL,        -- V0.9.5-goodinfo：該年股票殖利率（%, goodinfo 來源）
    PRIMARY KEY (stock_id, year)
);
CREATE INDEX IF NOT EXISTS idx_div_period ON dividend_history(year);
"""

# V0.9.5+ Phase 10：DB migration for new columns
#   既有 DB 沒有 ex_date / ex_date_close 欄位 → ALTER TABLE 動態加
DIV_HISTORY_MIGRATIONS = [
    "ALTER TABLE dividend_history ADD COLUMN ex_date TEXT",
    "ALTER TABLE dividend_history ADD COLUMN ex_date_close REAL",
    # V0.9.5-goodinfo：殖利率欄位（goodinfo 10Y 殖利率檔一次匯入）
    "ALTER TABLE dividend_history ADD COLUMN cash_yield_pct REAL",
    "ALTER TABLE dividend_history ADD COLUMN share_yield_pct REAL",
]

def _init_div_history_db(db_path: str):
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        conn.executescript(DIV_HISTORY_SCHEMA)
        # V0.9.5+ Phase 10：自動 migration 加新欄位（漏了加也不會爆）
        for col_sql in DIV_HISTORY_MIGRATIONS:
            try:
                conn.execute(col_sql)
            except Exception:
                pass  # 欄位已存在（重複 migration 安全）
        conn.commit()


# ==========================================================
# 【V0.9.5-etf-history】ETF 持股歷史庫（etf_history.db）
# ==========================================================
# William 17:54 需求：
# - ETF 成份股統計加「今日異動」欄（張）
# - Hover 顯示各 ETF 異動明細
# - App 啟動只抓一次、歷史存 local DB
# 為避免污染既有 dividend_history.db、獨立一個 db
ETF_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS etf_holding_history (
    date          TEXT    NOT NULL,       -- 'YYYY-MM-DD'
    etf_code      TEXT    NOT NULL,       -- '0050'
    stock_code    TEXT    NOT NULL,       -- '2330'
    stock_name    TEXT,                   -- '台積電'
    weight_pct    REAL    NOT NULL,       -- 佔 ETF 淨值 %（如 57.01）
    shares        INTEGER NOT NULL,       -- 持股股數（從 etfinfo.tw SSR）
    shares_lots   REAL    NOT NULL,       -- 持股張數（= shares / 1000）
    industry      TEXT,                   -- 產業別（從 etfinfo.tw）
    fetched_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    PRIMARY KEY (date, etf_code, stock_code)
);
CREATE INDEX IF NOT EXISTS idx_etf_hist_date ON etf_holding_history(date);
CREATE INDEX IF NOT EXISTS idx_etf_hist_etf ON etf_holding_history(etf_code);
CREATE INDEX IF NOT EXISTS idx_etf_hist_stock ON etf_holding_history(stock_code);
CREATE TABLE IF NOT EXISTS fetch_meta (
    key            TEXT PRIMARY KEY,
    value          TEXT,
    updated_at     TEXT
);
"""

def _init_etf_history_db(db_path: str = "etf_history.db"):
    """【V0.9.5-etf-history】建立 ETF 持股歷史庫（etf_history.db）

    Schema：
    - etf_holding_history(date, etf_code, stock_code, stock_name, weight_pct, shares, shares_lots, industry, fetched_at)
    - fetch_meta(key, value, updated_at)
    """
    import sqlite3
    os.makedirs(os.path.dirname(os.path.abspath(db_path)) if os.path.dirname(db_path) else ".", exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(ETF_HISTORY_SCHEMA)
        conn.commit()


def _save_etf_holding_snapshot(db_path: str, etf_code: str, holdings: list, date_str: str = None):
    """【V0.9.5-etf-history】寫入單檔 ETF 持股快照

    holdings: list of dict，每個含 {stock_code, stock_name, weight, shares, industry}
    date_str: 'YYYY-MM-DD'、None = 今日
    """
    import sqlite3
    from datetime import datetime
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    rows = []
    for h in holdings:
        shares = int(h.get("shares", 0))
        shares_lots = shares / 1000.0  # 股 → 張
        rows.append((
            date_str,
            etf_code,
            h["stock_code"],
            h["stock_name"],
            float(h.get("weight", 0)),
            shares,
            shares_lots,
            h.get("industry", ""),
        ))
    if not rows:
        return 0
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """INSERT OR REPLACE INTO etf_holding_history
               (date, etf_code, stock_code, stock_name, weight_pct, shares, shares_lots, industry)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        conn.execute(
            """INSERT OR REPLACE INTO fetch_meta (key, value, updated_at)
               VALUES (?, ?, datetime('now','localtime'))""",
            ("last_etf_snapshot_date", date_str),
        )
        conn.commit()
    return len(rows)


def _query_etf_holdings_by_date(db_path: str, date_str: str) -> pd.DataFrame:
    """【V0.9.5-etf-history】查詢指定日期的 ETF 持股快照

    回傳 DataFrame: date, etf_code, stock_code, stock_name, weight_pct, shares, shares_lots, industry
    """
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(
            """SELECT date, etf_code, stock_code, stock_name,
                      weight_pct, shares, shares_lots, industry
               FROM etf_holding_history
               WHERE date = ?""",
            conn,
            params=(date_str,),
        )


def _query_latest_two_dates(db_path: str):
    """【V0.9.5-etf-history】查詢最近兩個有資料的日期（今日、昨日）

    回傳 (today_str, yesterday_str) 或 (today_str, None) 若沒有昨日資料
    """
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT date FROM etf_holding_history ORDER BY date DESC LIMIT 2"
        ).fetchall()
    if not rows:
        return (None, None)
    today = rows[0][0]
    yesterday = rows[1][0] if len(rows) > 1 else None
    return (today, yesterday)


def _compute_etf_changes(db_path: str, today_str: str = None, yesterday_str: str = None) -> pd.DataFrame:
    """【V0.9.5-etf-history】計算個股的「今日 ETF 異動張數總和」

    算法：
    - 對每檔個股、聚合所有持有它的 ETF（today 跟 yesterday 都要有資料）
    - 異動張數 = Σ (today_shares_lots - yesterday_shares_lots)
    - 若某個 ETF 今天新增（昨日無資料）→ 算 +today_shares_lots（全部增持）
    - 若某個 ETF 今天刪除（今日無資料）→ 算 -yesterday_shares_lots（全部減持）
    - 沒有 yesterday 資料的個股 → 該個股無變化（不列入結果）

    回傳 DataFrame:
    - stock_code, stock_name, etf_count, today_change_lots, etf_changes_json
    - etf_changes_json: 各 ETF 異動明細（JSON 格式、給 popup 用）
    """
    import json
    import sqlite3
    from datetime import datetime
    if today_str is None:
        today_str = datetime.now().strftime("%Y-%m-%d")

    with sqlite3.connect(db_path) as conn:
        # 找最近兩個有效日期
        cur = conn.execute(
            "SELECT DISTINCT date FROM etf_holding_history ORDER BY date DESC LIMIT 2"
        )
        dates = [r[0] for r in cur.fetchall()]
        if not dates:
            return pd.DataFrame()
        if today_str not in dates:
            return pd.DataFrame()
        today_str = dates[0]
        yesterday_str = dates[1] if len(dates) > 1 else None

        if yesterday_str is None:
            # 沒有昨日資料 → 無法計算異動
            return pd.DataFrame()

        # 抓 today / yesterday 全部持股
        today_df = pd.read_sql_query(
            "SELECT * FROM etf_holding_history WHERE date = ?", conn, params=(today_str,)
        )
        yesterday_df = pd.read_sql_query(
            "SELECT * FROM etf_holding_history WHERE date = ?", conn, params=(yesterday_str,)
        )

    if today_df.empty and yesterday_df.empty:
        return pd.DataFrame()

    # 用 (etf_code, stock_code) 作為 join key
    today_df["key"] = today_df["etf_code"].astype(str) + "_" + today_df["stock_code"].astype(str)
    yesterday_df["key"] = yesterday_df["etf_code"].astype(str) + "_" + yesterday_df["stock_code"].astype(str)

    # Outer merge：保留兩邊資料（今天新增、今天刪除都要算）
    merged = today_df.merge(
        yesterday_df[["key", "shares_lots", "stock_name"]].rename(
            columns={"shares_lots": "y_lots", "stock_name": "y_name"},
        ),
        on="key",
        how="outer",
    )
    # stock_code：today 有就用 today、否則從 yesterday 補
    if "stock_code" not in merged.columns:
        merged["stock_code"] = None
    # 用 yesterday 的 stock_code fillna
    # 從 key 拆 stock_code 出來
    merged["key_stock"] = merged["key"].str.split("_").str[1]
    merged["stock_code"] = merged["stock_code"].fillna(merged["key_stock"])

    merged["t_lots"] = merged["shares_lots"].fillna(0)
    merged["y_lots"] = merged["y_lots"].fillna(0)
    merged["change_lots"] = merged["t_lots"] - merged["y_lots"]

    # 聚合到個股層級
    rows = []
    for stock_code, g in merged.groupby("stock_code"):
        change_entries = []
        total_change = 0.0
        for _, r in g.iterrows():
            if r["change_lots"] != 0:
                # etf_code：today 有就用 today、否則從 key 拆
                ec = r["etf_code"]
                if pd.isna(ec):
                    ec = r["key"].split("_")[0]
                change_entries.append({
                    "etf_code": str(ec),
                    "etf_name": "",
                    "change_lots": float(r["change_lots"]),
                })
                total_change += float(r["change_lots"])
        # 取 stock_name：今日優先、若今日刪除則用昨日
        today_name = g["stock_name"].dropna()
        y_name = g["y_name"].dropna()
        stock_name = today_name.iloc[0] if not today_name.empty else (y_name.iloc[0] if not y_name.empty else "")

        # 計算「現有 etf 數量」（today 為主、若全刪則從 yesterday 取）
        etf_count = int(g["etf_code"].notna().sum())
        if etf_count == 0:
            etf_count = int((g["y_lots"] > 0).sum())

        if not change_entries:
            continue
        rows.append({
            "stock_code": stock_code,
            "stock_name": stock_name,
            "etf_count": etf_count,
            "today_change_lots": round(total_change, 3),
            "etf_changes_json": json.dumps(change_entries, ensure_ascii=False),
        })

    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(
            by="today_change_lots",
            key=lambda s: s.abs(),
            ascending=False,
        ).reset_index(drop=True)
    return result


def _upsert_div_history(db_path: str, rows: list):
    """
    寫入股利資料到 dividend_history.db。

    V0.9.5-twser2 Fix（重要）：
    - 現有 schema 有 10 個實體欄位（不含 PRIMARY KEY）：
      stock_id, year, cash, stock, source, fetched_at, ex_date, ex_date_close,
      cash_yield_pct, share_yield_pct
    - `INSERT OR REPLACE` 會刪除舊列、插入新列。未指定的欄位 → DEFAULT（fetched_at）或 NULL（其他）。
    - 因此所有 tuple 都必須膨脹到 10 個實體欄位 + 2 個 PRIMARY KEY = 11 值，
      否則會對位錯誤，把 cash_yield_pct/share_yield_pct 寫成 NULL。

    向後相容：
    - 5-tuple：(stock_id, year, cash, stock, source) → 墊到 11 值
    - 7-tuple：(stock_id, year, cash, stock, source, ex_date, ex_date_close) → 墊到 11 值
    - 9-tuple：(stock_id, year, cash, stock, source, ex_date, ex_date_close, cash_yield_pct, share_yield_pct) → 墊到 11 值
    - 11-tuple：(stock_id, year, cash, stock, source, fetched_at, ex_date, ex_date_close, cash_yield_pct, share_yield_pct) → 直接寫
    """
    import sqlite3
    if not rows:
        return 0

    # INSERT column list: 10 cols
    #   stock_id, year, cash, stock, source, fetched_at, ex_date, ex_date_close, cash_yield_pct, share_yield_pct
    # VALUES: 9 ? placeholders
    #   ?1=stock_id, ?2=year, ?3=cash, ?4=stock, ?5=source, datetime('now','localtime') [hardcoded, NOT a placeholder],
    #   ?6=ex_date, ?7=ex_date_close, ?8=cash_yield_pct, ?9=share_yield_pct
    # 結論：所有 normalized row 必須剛好 9 值（對應 9 個 ?）
    import sqlite3 as _sq
    normalized = []
    for r in rows:
        n = len(r)
        if n == 5:
            # (stock_id, year, cash, stock, source) → 9 值：[r0-4, r5=none(fetched), r6=none(ex_date), r7=none(ex_close), r8=none(cash), r9=none(share)]
            normalized.append((r[0], r[1], r[2], r[3], r[4], None, None, None, None))
        elif n == 6:
            # (stock_id, year, cash, stock, source, ex_date) → 9 值：[r0-4, fetched_at硬編, r5=ex_date, r6=none, r7=none(cash), r8=none(share)]
            normalized.append((r[0], r[1], r[2], r[3], r[4], r[5], None, None, None))
        elif n == 7:
            # 【V0.9.5-twser2 Fix】
            # FinMind 舊 caller：(stock_id, year, cash, stock, source, ex_date, ex_date_close)
            # INSERT OR REPLACE 會清除未指定的 cash_yield/share_yield → 先查詢舊值再合併
            with _sq.connect(db_path) as conn:
                old = conn.execute(
                    "SELECT cash_yield_pct, share_yield_pct FROM dividend_history "
                    "WHERE stock_id=? AND year=?", (r[0], r[1])
                ).fetchone()
            old_cash_yld = old[0] if old else None
            old_share_yld = old[1] if old else None
            # 9 值：[r0-4, fetched_at硬編, r5=ex_date, r6=ex_date_close, old_cash, old_share]
            normalized.append((r[0], r[1], r[2], r[3], r[4], r[5], r[6], old_cash_yld, old_share_yld))
        elif n == 8:
            # (stock_id, year, cash, stock, source, ex_date, ex_date_close, cash_yield_pct) → 9 值
            normalized.append((r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], None))
        elif n == 9:
            # (stock_id, year, cash, stock, source, ex_date, ex_date_close, cash_yield_pct, share_yield_pct) → 9 值
            normalized.append((r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]))
        elif n == 10:
            # (stock_id, year, cash, stock, source, fetched_at, ex_date, ex_date_close, cash_yield_pct, share_yield_pct) → 9 值
            # r[5] is fetched_at but it's hardcoded, we still pass r[5] (it goes into VALUES ?6=ex_date)
            # 10-tuple: (stock_id, year, cash, stock, source, fetched_at, ex_date, ex_date_close, cash_yield_pct, share_yield_pct)
            # VALUES: ?1-?5=r0-4, datetime=hardcode, ?6=ex_date=r[6], ?7=ex_date_close=r[7], ?8=cash_yield=r[8], ?9=share_yield=r[9]
            # → 9 values: r0,r1,r2,r3,r4,r5,r6,r7,r8
            normalized.append((r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]))
        else:
            # 取前 9 個值
            normalized.append(tuple(r[:9]))
    with _sq.connect(db_path) as conn:
        conn.executemany(
            """INSERT OR REPLACE INTO dividend_history
               (stock_id, year, cash, stock, source, fetched_at, ex_date, ex_date_close,
                cash_yield_pct, share_yield_pct)
               VALUES (?, ?, ?, ?, ?, datetime('now','localtime'), ?, ?, ?, ?)""",
            normalized,
        )
        conn.commit()
    return len(normalized)

def _query_div_history(db_path: str, codes: list) -> dict:
    """查詢多檔股票的所有年度股利 → {code: {year: {cash, stock, ex_date}}}
    V0.9.5+ Phase 10：多回傳 ex_date（除息日）、供去年現金殖利率算法使用
    """
    import sqlite3
    if not codes:
        return {}
    with sqlite3.connect(db_path) as conn:
        placeholders = ",".join("?" * len(codes))
        rows = conn.execute(
            f"SELECT stock_id, year, cash, stock, ex_date FROM dividend_history WHERE stock_id IN ({placeholders})",
            codes,
        ).fetchall()
    result: Dict[str, Dict[int, Dict[str, Any]]] = {}
    for code, year, cash, stock, ex_date in rows:
        code = str(code).strip()
        result.setdefault(code, {})
        result[code][year] = {
            "cash": cash or 0.0,
            "stock": stock or 0.0,
            "ex_date": ex_date or "",  # V0.9.5+ Phase 10：除息日（可能為空）
        }
    return result


def _query_div_history_with_fetched(db_path: str, codes: list) -> dict:
    """查詢多檔股票的股利 + fetched_at → {code: {"_fetched_at": iso_str, "years": {year: {cash, stock, ex_date, ex_date_close, cash_yield_pct, share_yield_pct}}}}

    V0.9.5+ 用來判斷 DB 資料是否過期（> cache_max_age_days 天）
    V0.9.5+ Phase 10：多回傳 ex_date、ex_date_close（除息日 + 除息日收盤價）
    V0.9.5-goodinfo：多回傳 cash_yield_pct、share_yield_pct（goodinfo 年殖利率）
    """
    import sqlite3
    if not codes:
        return {}
    with sqlite3.connect(db_path) as conn:
        placeholders = ",".join("?" * len(codes))
        rows = conn.execute(
            f"""SELECT stock_id, year, cash, stock, fetched_at, ex_date, ex_date_close,
                       cash_yield_pct, share_yield_pct
                FROM dividend_history WHERE stock_id IN ({placeholders})""",
            codes,
        ).fetchall()
    result: Dict[str, Dict] = {}
    for code, year, cash, stock, fetched_at, ex_date, ex_date_close, cash_yld, share_yld in rows:
        code = str(code).strip()
        if code not in result:
            result[code] = {"_fetched_at": fetched_at, "years": {}}
        result[code]["years"][year] = {
            "cash": cash or 0.0,
            "stock": stock or 0.0,
            "ex_date": ex_date or "",
            "ex_date_close": ex_date_close,  # None 也保留為 None
            # V0.9.5-goodinfo：殖利率（百分比，ex: 3.17 = 3.17%）
            "cash_yield_pct": cash_yld,
            "share_yield_pct": share_yld,
        }
    return result

def _div_history_stats(db_path: str) -> dict:
    import sqlite3
    if not os.path.exists(db_path):
        return {"total": 0, "stocks": 0, "years": 0}
    with sqlite3.connect(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM dividend_history").fetchone()[0]
        stocks = conn.execute("SELECT COUNT(DISTINCT stock_id) FROM dividend_history").fetchone()[0]
        years = conn.execute("SELECT COUNT(DISTINCT year) FROM dividend_history").fetchone()[0]
    return {"total": total, "stocks": stocks, "years": years}


# V0.9.4 phase4: EPS 歷史庫（補抓不到去年同期的解法）
# 每日把最新一季 EPS 存進 SQLite，累積一年後 fetch_eps_latest 就能算 YoY
# ==========================================================
EPS_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS eps_history (
    stock_id    TEXT    NOT NULL,
    year        INTEGER NOT NULL,
    quarter     INTEGER NOT NULL,
    eps         REAL,
    source      TEXT,
    fetched_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    PRIMARY KEY (stock_id, year, quarter)
);
CREATE INDEX IF NOT EXISTS idx_eps_period ON eps_history(year, quarter);
"""


def _init_eps_history_db(db_path: str):
    """初始化/建立 EPS 歷史庫（不重複執行也不會壞）"""
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        conn.executescript(EPS_HISTORY_SCHEMA)
        conn.commit()


def _upsert_eps_history(db_path: str, rows: list):
    """
    rows: [(stock_id, year, quarter, eps, source), ...]
    用 REPLACE 策略：新資料覆蓋舊的（讓 CSV 更新時自動修正）
    """
    import sqlite3
    if not rows:
        return 0
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """INSERT OR REPLACE INTO eps_history
               (stock_id, year, quarter, eps, source)
               VALUES (?, ?, ?, ?, ?)""",
            rows,
        )
        conn.commit()
    return len(rows)


def _query_eps_history(db_path: str, year: int, quarter: int) -> pd.DataFrame:
    """查詢指定 (year, quarter) 的歷史 EPS"""
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(
            "SELECT stock_id, year, quarter, eps FROM eps_history WHERE year = ? AND quarter = ?",
            conn, params=(year, quarter),
        )
    if not df.empty:
        df["stock_id"] = df["stock_id"].astype(str).str.strip()
    return df


def _eps_history_stats(db_path: str) -> dict:
    """回傳歷史庫摘要（給 GUI 狀態列用）"""
    import sqlite3
    if not os.path.exists(db_path):
        return {"total": 0, "periods": 0, "latest": None}
    with sqlite3.connect(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM eps_history").fetchone()[0]
        periods = conn.execute("SELECT COUNT(DISTINCT year*10+quarter) FROM eps_history").fetchone()[0]
        latest = conn.execute(
            "SELECT year, quarter, COUNT(*) FROM eps_history "
            "ORDER BY year DESC, quarter DESC LIMIT 1"
        ).fetchone()
    return {
        "total": total,
        "periods": periods,
        "latest": f"{latest[0]}Q{latest[1]} ({latest[2]}筆)" if latest else None,
    }


# ==========================================================
# V0.9.5: 手動選股功能 - FinMind 資料拉取輔助
# ==========================================================

FINMIND_BASE = "https://api.finmindtrade.com/api/v4/data"

# 手動選股進度（背景 thread 寫、UI thread 讀）
_MS_PROGRESS = {"stage": "", "done": 0, "total": 0, "msg": "", "error": ""}


def _fetch_market_stock_list() -> pd.DataFrame:
    """
    從 TWSE / TPEx 抓全市場股票代號與名稱（當 pipeline 未執行時的 fallback）。
    回傳 DataFrame：[股票代號, 股票名稱]
    """
    import sqlite3
    # 優先用 eps_history.db 湊出名單（已有股票代號，快速）
    db_path = "eps_history.db"
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            codes = pd.read_sql_query(
                "SELECT DISTINCT stock_id FROM eps_history ORDER BY stock_id", conn)
            conn.close()
            if not codes.empty:
                df = codes.copy()
                df["股票名稱"] = ""
                return df.rename(columns={"stock_id": "股票代號"})
        except Exception:
            pass

    # TWSE / TPEx 上市股票清單（從 ISIN 頁面）
    rows = []
    for url in ["https://isin.twse.com.tw/isin/C_public.jsp?strMode=2",
                 "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"]:
        try:
            r = requests.get(url, timeout=20, verify=False)
            from io import StringIO
            tables = pd.read_html(StringIO(r.text), header=0)
            for t in tables:
                if "有價證券代號及名稱" in t.columns:
                    # 第一欄是「代號　名稱」混合，需用空白拆開
                    combined = t["有價證券代號及名稱"].dropna().tolist()
                    for item in combined:
                        s = str(item).strip()
                        # 格式：「1101　台泥」或「1101 台泥」
                        parts = s.split(maxsplit=1)
                        if len(parts) == 2 and parts[0].strip().isdigit() and len(parts[0].strip()) == 4:
                            rows.append({"股票代號": parts[0].strip(), "股票名稱": parts[1].strip()})
                    break  # 只處理第一張表
        except Exception:
            continue

    if rows:
        result = pd.DataFrame(rows).drop_duplicates("股票代號")
        result["股票代號"] = result["股票代號"].astype(str).str.strip()
        return result
    return pd.DataFrame(columns=["股票代號", "股票名稱"])

# ────────────────────────────────────────────────────────────────
# V0.9.5-twser：TWSE 即時股價（取代 FinMind）
# URL: https://mis.twse.com.tw/stock/api/getStockInfo.jsp
# 格式：上市 tse_XXXX.tw，上櫃 otc_XXXX.tw
# 主力欄位：z=現價，tv=當筆量，v=累積量，o/h/l/y=開高低昨
# 延遲：實測 15-20 秒（TWSE 官方）
# 限制：一次建議 50 檔，興櫃不支援
# ────────────────────────────────────────────────────────────────
_TWSE_REALTIME_BATCH_SIZE = 10   # 【V0.9.5-goodinfo4+5】降批：50→10（避免TWSE rate limit）


def _fetch_twse_realtime_batch(stock_ids: List[str],
                                progress_callback=None) -> pd.DataFrame:
    """
    批次抓取台灣證券交易所即時股價（TWSE / TPEx 即時資訊）。
    完全取代 FinMind TaiwanStockPrice，實現【免費、無額度限制】的即時股價。

    URL 格式
    ----------
    https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_2330.tw|otc_3188.tw|...

    主力欄位
    ---------
    - z : 現價（盤中即時成交價）；若為 "-" 表示該股票目前無成交（可能處於預約拍賣階段）
    - o : 開盤價（揭示）
    - tv : 當筆成交量
    - v : 累積成交量
    - h / l / y : 今日最高 / 最低 / 昨日收盤

    預開盤行為（9:00–9:30）
    ------------------------
    - z = "-"（尚未成交）→ fallback 到 o（開盤拍賣價，視為現時合理報價）
    - 若 o 也是 "-" → fallback 到 y（昨日收盤價）

    【V0.9.5-goodinfo4+5 (vol+cache) 重要修正】2026-06-18 18:34 William 反映
    - 「現價沒資料、成交不是今日總量」
    - 根因 1：v 欄位是「股」不是「張」、原本 int(v/1000) 會丟失 99% 資料
      例：v=4016（股）= 4.016 張、原本顯示 "4"（=4 張）
      修法：vol = v / 1000 保留小數、顯示用 f"{vol:.3f}" 張
    - 根因 2：上市/上櫃前綴誤判（6 開頭並非都是上櫃）
      例：6669 緯穎是上市、不是上櫃
      修法：先打 tse_ 拿、抓不到的股再用 otc_ 重打
    - 根因 3：抓完後沒回寫 cache、下次還要重抓
      修法：在 caller merge 完後 save_cache()

    Parameters
    ----------
    stock_ids : list[str]
        股票代號清單（如 ["2330", "0050", "3188"]）
        系統會自動判斷上市（tse_）或上櫃（otc_）、抓不到的股會 fallback
    progress_callback : callable, optional
        (n_done, n_total) → 每批完成後呼叫，用於 UI 動態進度顯示

    Returns
    -------
    pd.DataFrame，欄位：[股票代號, 現價, 成交量_張]
    - 現價：float 或 None（完全抓不到時）
    - 成交量_張：float（v / 1000，**股轉張**、保留小數）
      例：v=4016 股 → 4.016 張（不是 4 張）
    """
    rows = []
    codes = [str(c).strip() for c in stock_ids if str(c).strip()]
    total = len(codes)
    n_batches = (total + _TWSE_REALTIME_BATCH_SIZE - 1) // _TWSE_REALTIME_BATCH_SIZE
    _MS_PROGRESS["stage"] = "TWSE即時股價"
    _MS_PROGRESS["total"] = total

    for batch_idx in range(n_batches):
        batch_codes = codes[
            batch_idx * _TWSE_REALTIME_BATCH_SIZE:
            (batch_idx + 1) * _TWSE_REALTIME_BATCH_SIZE
        ]
        # 【V0.9.5-goodinfo4+5 (vol-int) 修 batch sleep】2026-06-18 21:37 William 反映
        # 原本 0.5s × 48 批 = 24s、加上 retry 6 次 × 6s = 36s
        # 改 0.3s × 48 = 14.4s、總耗時可控制在 30s 內
        if batch_idx > 0:
            time.sleep(0.3)
        # 【V0.9.5-goodinfo4+5 (vol+cache) 修正】2026-06-18 18:34 William 反映
        # 原本 6 開頭 = otc_ 是粗略判斷、有些 6 開頭是上市（例：6669 緯穎）
        # 修法：先全部打 tse_、回傳中沒有 c 欄位的股再用 otc_ 重打
        def _query_twse(prefix: str, max_retries: int = 3) -> list:
            """打一次 TWSE MIS API、回傳 msgArray（prefix 是 tse 或 otc）

            V0.9.5-goodinfo4+5 (vol+cache) 加 retry：2026-06-18 19:25 William 反映
            - 原本 0 retry、48 批連打可能導致最後幾批被 rate limit
            - 加 3 次 retry、間隔 1.0s / 2.0s / 4.0s 成長退避
            """
            ex_ch = "|".join(f"{prefix}_{c}.tw" for c in batch_codes)
            url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={ex_ch}"
            for attempt in range(max_retries):
                try:
                    resp = requests.get(
                        url,
                        headers={
                            # 【V0.9.5-goodinfo4+5 (vol-int) 修 UA】2026-06-18 21:37 William 反映
                            # User-Agent 寫死 Windows NT、但 William 在 Ubuntu 上跑
                            # → TWSE 可能辨識為偽 UA、加上 retry 6 次 (tse+otc) 連打
                            # → 被當 bot 擋
                            # 修法：用 StockTool/VERSION 標識 + Linux UA
                            "User-Agent": f"StockTool/{VERSION} (+https://github.com/apingchang/StockTools)",
                            "Referer": "https://mis.twse.com.tw/",
                            "Accept": "application/json,text/plain,*/*",
                            "Accept-Language": "zh-TW,zh;q=0.9",
                            "Accept-Encoding": "gzip, deflate",
                        },
                        timeout=20,
                    )
                    resp.raise_for_status()
                    return resp.json().get("msgArray", [])
                except Exception as e:
                    # 【V0.9.5-goodinfo4+5 (vol-int) 修 retry】2026-06-18 21:37 William 反映
                    # 原本 1.0s / 2.0s / 3.0s 太短、tse 還沒放人就重試
                    # → 改 3.0s / 8.0s / 15.0s 拉長退避
                    wait_sec = [3.0, 8.0, 15.0][attempt] if attempt < 3 else 15.0
                    if attempt < max_retries - 1:
                        print(f"⚠️ TWSE API 失敗（批{batch_idx+1}/{n_batches}、{prefix}，重試 {attempt+1}/{max_retries}）：{type(e).__name__} - 等 {wait_sec}s")
                        time.sleep(wait_sec)
                    else:
                        print(f"⚠️ TWSE API 失敗（批{batch_idx+1}/{n_batches}、{prefix}，放棄）：{type(e).__name__}: {e}")
            return []

        # Step 1: 先打 tse_
        msg_tse = _query_twse("tse")
        # 找出 tse_ 沒回應的股
        tse_codes = {str(rec.get("c", "")).strip() for rec in msg_tse if rec.get("c")}
        missing_codes = [c for c in batch_codes if c not in tse_codes]

        # Step 2: missing 的股用 otc_ 重打（V0.9.5-goodinfo4+5 vol+cache 用同一個 retry helper）
        msg_otc = []
        # 【V0.9.5-goodinfo4+5 (vol-int) 修 otc fallback】2026-06-18 21:37 William 反映
        # 原本 missing_codes 全部 codes（tse 完全失敗時）→ otc 也打 50 個 → 也失敗
        # 改：missing 超過 batch 90%（表示 tse 整批失敗、不是「抓不到個別股」）→ 跳過 otc
        if missing_codes and len(missing_codes) < len(batch_codes) * 0.9:
            time.sleep(0.5)  # 避免連打兩個請求被擋
            ex_ch = "|".join(f"otc_{c}.tw" for c in missing_codes)
            url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={ex_ch}"
            for attempt in range(2):  # otc fallback 只 retry 2 次（比 tse 少）
                try:
                    resp = requests.get(
                        url,
                        headers={
                            "User-Agent": f"StockTool/{VERSION} (+https://github.com/apingchang/StockTools)",
                            "Referer": "https://mis.twse.com.tw/",
                            "Accept": "application/json,text/plain,*/*",
                            "Accept-Language": "zh-TW,zh;q=0.9",
                        },
                        timeout=15,
                    )
                    resp.raise_for_status()
                    msg_otc = resp.json().get("msgArray", [])
                    break
                except Exception as e:
                    wait_sec = [2.0, 5.0][attempt] if attempt < 2 else 5.0
                    if attempt < 1:
                        print(f"⚠️ TWSE API otc fallback 失敗（重試 {attempt+1}/2）：{type(e).__name__} - 等 {wait_sec}s")
                        time.sleep(wait_sec)
                    else:
                        print(f"⚠️ TWSE API otc fallback 失敗（放棄）：{type(e).__name__}: {e}")
                        msg_otc = []
        elif missing_codes:
            # tse 整批失敗（missing > 90%）→ 不打 otc（otc 也會被擋）
            print(f"⚠️ TWSE tse 整批失敗（{len(missing_codes)}/{len(batch_codes)}）→ 跳過 otc fallback")

        all_msg = msg_tse + msg_otc

        for rec in all_msg:
            raw_code = rec.get("c", "").strip()
            if not raw_code:
                continue
            z = rec.get("z", "-")   # 現價（盤中）
            o = rec.get("o", "-")   # 開盤價
            y = rec.get("y", "-")   # 昨收

            # 現價計算：z 為 "-" → fallback 到 o → fallback 到 y
            if z != "-":
                price = float(z)
            elif o != "-":
                price = float(o)
            elif y != "-":
                price = float(y)
            else:
                price = None

            # 【V0.9.5-goodinfo4+5 (vol-int) 修正】2026-06-18 20:05 William 反映
            # 「每日總成交量不會有小數點」、「今天 2548 是 4020 張」
            # 【V0.9.5-goodinfo4+5 (vol-no-divide) 修正】2026-06-18 21:54 William 反映
            # 「成交量不要除以1000應該就對了」
            # → TWSE MIS API 的 v 欄位已經是「張」（不是股）
            # → 2548 v=4016 → 顯示 4,016 張（不是 4 張）
            # → 我之前看 Asoul/tsrtc 文件以為是股、所以寫 // 1000 → 顯示 4 張
            # → 那是錯的：v 已經是張、不需要除
            v_raw = rec.get("v", "0")
            try:
                vol = int(float(v_raw))  # v 已經是「張」（整數）
            except (ValueError, TypeError):
                vol = 0

            rows.append({"股票代號": raw_code, "現價": price, "成交量_張": vol})

        # tse_ + otc_ 都沒回的股 → 另設 None（後面 caller 會 fallback 到 cache / FinMind）
        for code in batch_codes:
            if not any(str(r.get("c", "")).strip() == code for r in all_msg):
                rows.append({"股票代號": code, "現價": None, "成交量_張": 0.0})

        # 進度回呼
        n_done = min((batch_idx + 1) * _TWSE_REALTIME_BATCH_SIZE, total)
        _MS_PROGRESS["done"] = n_done
        if progress_callback:
            progress_callback(n_done, total)

        # 輕微延遲，避免對 TWSE 伺服器造成壓力
        if batch_idx < n_batches - 1:
            time.sleep(0.1)

    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["股票代號", "現價", "成交量_張"])
    df["股票代號"] = df["股票代號"].astype(str).str.strip()
    return df


_FINMIND_PRICE_CACHE = {}   # {stock_id: {date: row}}（多日 cache）


def _pick_latest_price_row(data: list) -> tuple:
    """從 FinMind TaiwanStockPrice 資料中選「今日」或退到「前一個交易日」的一筆

    V0.9.5-goodinfo4 修 Bug：2026-06-17 William 反映
    原本：直接 data[-1] → 盤中時 data[-1] 可能是今日（對）或昨日（誤）
    修法：從後往前找第一個 date == today 的、找不到就回傳 data[-1]（最後一個交易日）

    Returns
    -------
    (row, date_str) → 選到的 row 跟它的 date（ROC 格式 '1150617'）
    """
    from datetime import datetime as _dt
    today_roc = (_dt.now().year - 1911) * 10000 + _dt.now().month * 100 + _dt.now().day
    # 從後往前找
    for rec in reversed(data):
        rec_date = rec.get("date", "")
        if str(rec_date) == str(today_roc):
            return rec, rec_date
    # 找不到今日 → 取最後一筆（上一個交易日的收盤）
    if data:
        return data[-1], data[-1].get("date", "")
    return None, None


_FINMIND_DIVIDEND_CACHE = {}  # {stock_id: {year: {cash, stock}}}


def _finmind_get(dataset: str, stock_id: str, start: str, end: str, retry: int = 2) -> list:
    """統一的 FinMind API 呼叫（含 429 回退、402 額度檢查）。

    重要：402 Payment Required 表示 FinMind plan 額度用完
          此時應規舉到上层、不要 silently 回傳空 list
    （空 list 會讓 caller 誤以為「該股沒股利」而不是「API 額度不夠」）
    """
    for attempt in range(retry + 1):
        try:
            r = requests.get(FINMIND_BASE, params={
                "dataset": dataset,
                "data_id": stock_id,
                "start_date": start,
                "end_date": end,
            }, timeout=20)
            if r.status_code == 429:
                time.sleep(61)
                continue
            if r.status_code == 402:
                # FinMind plan 額度用完 → 拋例外（不再 silently 回傳空）
                raise RuntimeError(
                    "FinMind 額度已用完（status 402）｜請升級 plan 或等下月重置"
                    f"｜URL: {r.url}"
                )
            r.raise_for_status()
            d = r.json()
            return d.get("data", []) or []
        except RuntimeError:
            # 402 額度錯誤直接往上拋
            raise
        except Exception:
            if attempt < retry:
                time.sleep(2)
            return []
    return []


def _parse_roc_year(year_str: str) -> int:
    """把 "113年第3季" → 2024（西元年）。民國年 = 西元年 - 1911。"""
    import re
    m = re.match(r"(\d+)年", str(year_str))
    if m:
        return int(m.group(1)) + 1911  # 錯誤：-1911；修正：+1911
    return 0


def _fetch_finmind_prices_batch(stock_ids: List[str],
                                progress_callback=None,
                                force_refresh: bool = False) -> pd.DataFrame:
    """
    批次抓取股票現價（FinMind TaiwanStockPrice，支援 rate limit 回退）。
    每批 10 個，間隔 0.35s，超過 300/h 會被擋 → 等 61s 再試。
    progress_callback(n_done, n_total) 可傳進來做 UI 更新。

    V0.9.5-goodinfo4 修 Bug：2026-06-17 William 反映
    原本：data[-1] 直接用 → 盤中時 data[-1] 可能是「上一個交易日的收盤」誤判為今日
    修法：用 _pick_latest_price_row 判斷 date == today
          - 盤後：data[-1].date == today → 拿今日收盤
          - 盤中：data[-1].date == today → 拿今日盤中最後一筆（盤中即時）
          - 週末：data[-1].date 是上週五 → 拿上週五收盤（合理）

    V0.9.5-goodinfo4.3 修 Bug：2026-06-18 William 反映
    原本：每次呼叫都用 _FINMIND_PRICE_CACHE 命中 → 「即時抓股價」checkbox 失效
          因為 App 啟動時背景抓過一次、cache 已被填滿、按 checkbox 也直接拿 cache
    修法：加 force_refresh 參數
          - True → 先清空 _FINMIND_PRICE_CACHE 再抓（用於「即時抓股價」checkbox）
          - False → 用 cache（默認，背景抓取場景）

    Parameters
    ----------
    stock_ids : list[str]
        要抓取的股票代號清單
    progress_callback : callable
        (n_done, n_total) → 進度更新回呼（用於 UI 動態顯示）
    force_refresh : bool
        True：清 cache 重抓（耗時）；False：直接用 cache（快速）
    """
    if force_refresh:
        # 【V0.9.5-goodinfo4.3】「即時抓股價」checkbox 場景
        # App 啟動時背景抓的 cache 不能擋、必須清掉重抓
        n_cleared = len(_FINMIND_PRICE_CACHE)
        _FINMIND_PRICE_CACHE.clear()
        # log 印在 console、不走 logger（背景 thread 也行）
        print(f"🔄 [force_refresh] 已清空 {n_cleared} 檔 price cache，重新打 FinMind")

    rows = []
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
    total = len(stock_ids)
    _MS_PROGRESS["stage"] = "股價"
    _MS_PROGRESS["total"] = total

    for i, code in enumerate(stock_ids):
        code = str(code).strip()
        if code in _FINMIND_PRICE_CACHE:
            cached = _FINMIND_PRICE_CACHE[code]
            if cached:
                rows.append({"股票代號": code,
                            "現價": cached.get("close"),
                            "成交量_張": (cached.get("Trading_Volume", 0) or 0) / 1000})
        else:
            data = _finmind_get("TaiwanStockPrice", code, start_date, end_date)
            if data:
                latest, _date = _pick_latest_price_row(data)
                _FINMIND_PRICE_CACHE[code] = latest
                rows.append({"股票代號": code,
                            "現價": latest.get("close") if latest else None,
                            "成交量_張": ((latest.get("Trading_Volume", 0) or 0) / 1000) if latest else 0})
            else:
                _FINMIND_PRICE_CACHE[code] = None

            # Rate limit：每小時最多 300 次 → 每次間隔 12s
            # 實測 0.35s 可用（用 threading 並行），但避免一次打太多
            _MS_PROGRESS["done"] = i + 1
            if (i + 1) % 10 == 0 and progress_callback:
                progress_callback(i + 1, total)
            time.sleep(0.35)

    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["股票代號", "現價", "成交量_張"])


def _fmt_float(v, decimals: int = 2) -> str:
    """統一格式化數值為字串：None/NaN → '—'、否則顯示數值

    V0.9.5-goodinfo4 修 Bug：2026-06-17 William 反映
    原本用「if val and ...」是 truthy 判斷
    → 殖利率 0.0 被誤判為 None、顯示 '—'（0.0 是 falsy）
    → 5386 現金殖利率 0.3 會被當 0.0 顯示 '—' 看起來像無資料

    修法：用 pd.isna() 判斷（None/NaN 才視為空）、數值照實顯示
    """
    try:
        if pd.isna(v):
            return "—"
    except (TypeError, ValueError):
        return "—"
    try:
        return f"{float(v):.{decimals}f}"
    except (TypeError, ValueError):
        return "—"


def _fetch_finmind_dividend(stock_ids: List[str],
                             db_path: str = "dividend_history.db",
                             progress_callback=None,
                             skip_remote: bool = False,
                             cache_max_age_days: int = 30) -> pd.DataFrame:
    """
    取得近 3 年股利（先查 DB，沒有的、或過期的才即時抓 FinMind 並寫回 DB）。
    - skip_remote=True: DB 沒有的回 None，不抓 FinMind（避免 rate limit）
    - cache_max_age_days：DB 資料超過 N 天視為過期（預設 30 天）→ 重抓 FinMind
      （避免 DB 過期→使用者誤以為沒額度問題是 DB 缺漏）
    - 第一次跑：會 FinMind 抓一批 + 寫 DB
    - 之後跑：只查 DB，不打網路
    """
    rows = []
    current_year = datetime.now().year
    start_date = f"{current_year - 2}-01-01"
    end_date = f"{current_year}-12-31"

    # 1. 先查 DB（含 fetched_at 用來判斷過期）
    # 【V0.9.5-twser2 Fix】統一是用 _query_div_history_with_fetched（含 cash_yield_pct/share_yield_pct）
    #   cached[code] = {"_fetched_at": ..., "years": {year: {...}}}
    #   舊版 _query_div_history 無殖利率欄位 → 殖利率全部 None → "-"
    _init_div_history_db(db_path)
    cached_with_fetched = _query_div_history_with_fetched(
        db_path, [str(c).strip() for c in stock_ids]
    )
    cached = _query_div_history_with_fetched(
        db_path, [str(c).strip() for c in stock_ids]
    )

    # 2. 區分「DB 有的」跟「要即時抓的」
    #    - DB 沒有的 → 抓
    #    - DB 有但過期的（> cache_max_age_days）→ 抓
    #    - DB 有且新鮮的 → 跳過
    #    - cache_max_age_days < 0 視為「永不過期」→ 保持原本行為（向後相容）
    from datetime import datetime as _dt, timedelta as _td
    if cache_max_age_days < 0:
        threshold_iso = None  # 永不過期
    else:
        threshold_iso = (_dt.now() - _td(days=cache_max_age_days)).isoformat()
    to_fetch = []
    for c in [str(c).strip() for c in stock_ids]:
        if c not in cached_with_fetched:
            to_fetch.append(c)
        elif threshold_iso is not None:
            fetched_at = cached_with_fetched[c].get("_fetched_at", "")
            if fetched_at and fetched_at < threshold_iso:
                to_fetch.append(c)  # 過期
    if skip_remote:
        # 跳過 FinMind 抓取：DB 沒有的回 None（避免 rate limit）
        to_fetch = []
    fetch_rows: list = []
    _MS_PROGRESS["stage"] = "股利"
    _MS_PROGRESS["total"] = len(to_fetch)
    _MS_PROGRESS["error"] = ""  # 重設錯誤狀態
    import re as _re_div
    try:
        for i, code in enumerate(to_fetch):
            _MS_PROGRESS["done"] = i
            data = _finmind_get("TaiwanStockDividend", code, start_date, end_date)
            by_year: Dict[int, Dict[str, Any]] = {}
            for rec in data:
                year_str = rec.get("year", "")
                cash_raw = float(rec.get("CashEarningsDistribution") or 0)
                stock_raw = float(rec.get("StockEarningsDistribution") or 0)
                # 【V0.9.5+ Phase 10】保留 ex_date（除息日）給後面算殖利率用
                ex_date = rec.get("date", "") or ""
                m_q = _re_div.match(r"(\d+)年第(\d+)季", year_str)
                m_h1 = _re_div.match(r"(\d+)年前半年度", year_str)
                m_h2 = _re_div.match(r"(\d+)年後半年度", year_str)
                m_y = _re_div.match(r"^(\d+)年$", year_str)  # 純年（無季/半年度）
                is_max_logic = False  # 記 year 該年 是用 max 還是 sum 邏輯
                if m_q:
                    yr = int(m_q.group(1)) + 1911
                    is_max_logic = True
                elif m_h1:
                    yr = int(m_h1.group(1)) + 1911
                elif m_h2:
                    yr = int(m_h2.group(1)) + 1911
                elif m_y:
                    yr = int(m_y.group(1)) + 1911
                    is_max_logic = True
                else:
                    continue
                yd = by_year.setdefault(yr, {"cash": 0.0, "stock": 0.0, "ex_date": ""})
                if is_max_logic:
                    # max 邏輯：保留 cash 大的、ex_date 跟著更新到該筆
                    if cash_raw >= yd["cash"]:
                        yd["cash"] = cash_raw
                        yd["stock"] = stock_raw
                        yd["ex_date"] = ex_date
                else:
                    # sum 邏輯（半年配/季度配）：累加、ex_date 取最後一筆
                    yd["cash"] += cash_raw
                    yd["stock"] += stock_raw
                    if ex_date > yd["ex_date"]:
                        yd["ex_date"] = ex_date
            # 寫入 DB（V0.9.5+ Phase 10 加 ex_date欄位）
            for yr, d in by_year.items():
                fetch_rows.append((code, yr, d["cash"], d["stock"], "finmind", d["ex_date"], None))
            if (i + 1) % 10 == 0 and progress_callback:
                progress_callback(i + 1, len(to_fetch))
            time.sleep(0.35)
    except RuntimeError as e:
        # FinMind 402 額度已用完 → 記下錯誤、跳出 loop
        # 保留已抓到的 fetch_rows（不丢）
        _MS_PROGRESS["error"] = str(e)
        print(f"❌ FinMind 額度錯誤：{e}（已抓 {len(fetch_rows)} 筆、部分寫入 DB）")
    if fetch_rows:
        _upsert_div_history(db_path, fetch_rows)
        # 重新讀一次 DB 拿新資料（確保拿最新寫入的）
        cached = _query_div_history_with_fetched(db_path, [str(c).strip() for c in stock_ids])

    # 3. 組裝結果
    for code in [str(c).strip() for c in stock_ids]:
        # 【V0.9.5-twser2 Fix】用 _query_div_history_with_fetched 的 nested 結構：
        #   cached[code] = {"_fetched_at": ..., "years": {year: {...}}}
        #   所以要 .get("years", {}) 而不是直接 .get(year)
        code_data = cached.get(code, {})
        years_data = code_data.get("years", {}) if isinstance(code_data, dict) else {}
        this_yr = years_data.get(current_year, {})
        last_yr = years_data.get(current_year - 1, {})
        prev_yr = years_data.get(current_year - 2, {})
        rows.append({
            "股票代號": code,
            f"{current_year}現金股利": this_yr.get("cash", 0.0),
            f"{current_year}股票股利": this_yr.get("stock", 0.0),
            f"{current_year - 1}現金股利": last_yr.get("cash", 0.0),
            f"{current_year - 1}股票股利": last_yr.get("stock", 0.0),
            f"{current_year - 2}現金股利": prev_yr.get("cash", 0.0),
            f"{current_year - 2}股票股利": prev_yr.get("stock", 0.0),
            # V0.9.5+ Phase 10：回傳 ex_date / ex_date_close、供「去年現金殖利率」算法用
            f"{current_year - 1}除息日": this_yr.get("ex_date", "") or "",
            f"{current_year - 1}除息日收盤價": this_yr.get("ex_date_close"),
            # V0.9.5-goodinfo：殖利率（百分比, goodinfo 來源）— 優先用於殖利率算法
            f"{current_year}現金殖利率_goodinfo": this_yr.get("cash_yield_pct"),
            f"{current_year}股票殖利率_goodinfo": this_yr.get("share_yield_pct"),
            f"{current_year - 1}現金殖利率_goodinfo": last_yr.get("cash_yield_pct"),
            f"{current_year - 1}股票殖利率_goodinfo": last_yr.get("share_yield_pct"),
            f"{current_year - 2}現金殖利率_goodinfo": prev_yr.get("cash_yield_pct"),
            f"{current_year - 2}股票殖利率_goodinfo": prev_yr.get("share_yield_pct"),
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["股票代號", f"{current_year}現金股利", f"{current_year}股票股利",
                 f"{current_year - 1}現金股利", f"{current_year - 1}股票股利",
                 f"{current_year - 2}現金股利", f"{current_year - 2}股票股利",
                 f"{current_year - 1}除息日", f"{current_year - 1}除息日收盤價",
                 f"{current_year}現金殖利率_goodinfo", f"{current_year}股票殖利率_goodinfo",
                 f"{current_year - 1}現金殖利率_goodinfo", f"{current_year - 1}股票殖利率_goodinfo",
                 f"{current_year - 2}現金殖利率_goodinfo", f"{current_year - 2}股票殖利率_goodinfo"])

def _background_fetch_all_dividend(stock_ids: List[str], db_path: str = "dividend_history.db",
                                  progress_callback=None, batch_size: Optional[int] = None) -> int:
    """
    背景抓取全市場股利寫入 DB（手動啟動用）。

    Parameters
    ----------
    stock_ids : List[str]
        股票代號清單
    db_path : str
        DB 路徑
    progress_callback : callable
        進度回呼 (done, total)
    batch_size : int | None
        - None = 一次抓全部缺漏（舊行為）
        - 100  = 只抓缺漏中的前 N 檔（V0.9.5+ 推薦用，Free tier 額度友善）

    Returns
    -------
    int
        這次實際抓的股數（原本沒資料的）
        -1 = FinMind 402 額度錯誤
         0 = 沒缺漏、沒抓
    """
    _init_div_history_db(db_path)
    cached = _query_div_history(db_path, [str(c).strip() for c in stock_ids])
    to_fetch = [c for c in stock_ids if str(c).strip() not in cached]
    if not to_fetch:
        return 0
    # V0.9.5+: 批次切片（Free tier 額度友善、可分散跑）
    if batch_size is not None and batch_size > 0 and len(to_fetch) > batch_size:
        to_fetch = to_fetch[:batch_size]
    current_year = datetime.now().year
    start_date = f"{current_year - 2}-01-01"
    end_date = f"{current_year}-12-31"
    fetch_rows: list = []
    total = len(to_fetch)
    quota_exceeded = False
    for i, code in enumerate(to_fetch):
        try:
            data = _finmind_get("TaiwanStockDividend", code, start_date, end_date)
        except RuntimeError as e:
            # FinMind 402 額度用完 → 停止 loop、保留已抓的
            print(f"❌ {e}")
            quota_exceeded = True
            break
        for rec in data:
            yr = _parse_roc_year(rec.get("year", ""))
            if yr == 0:
                continue
            cash_raw = float(rec.get("CashEarningsDistribution") or 0)
            stock_raw = float(rec.get("StockEarningsDistribution") or 0)
            fetch_rows.append((code, yr, cash_raw, stock_raw, "finmind"))
        time.sleep(0.35)
        if progress_callback:
            try:
                progress_callback(i + 1, total)
            except Exception:
                pass
    if fetch_rows:
        _upsert_div_history(db_path, fetch_rows)
    # 用「負值」表示 FinMind 額度錯誤（讓 caller 知道不是完成）
    if quota_exceeded:
        return -1
    return len(to_fetch)


def _update_ex_date_close(db_path: str, stock_id: str, year: int,
                          ex_date: str, ex_date_close: float) -> None:
    """V0.9.5+ Phase 10：把「除息日 + 除息日收盤價」寫入 dividend_history 緩存
    下次重跑手動選股時免打 FinMind
    """
    import sqlite3
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """UPDATE dividend_history
                   SET ex_date = ?, ex_date_close = ?
                   WHERE stock_id = ? AND year = ?""",
                (ex_date, ex_date_close, stock_id, year),
            )
            conn.commit()
    except Exception:
        pass


def _fetch_ex_date_close(stock_id: str, ex_date: str) -> Optional[float]:
    """V0.9.5+ Phase 10：抓除息日當天（或附近）的收盤價

    William 11:39 反映：去年現金殖利率應除以「去年除息日收盤價」、不是現價
    本函式供「手動選股」算去年現金殖利率時使用

    Parameters
    ----------
    stock_id : str
        股票代號
    ex_date : str
        除息日 (YYYY-MM-DD)、可能是空字串

    Returns
    -------
    Optional[float]
        除息日附近的收盤價（None = 抓不到）
    """
    if not ex_date or not stock_id:
        return None
    try:
        from datetime import datetime as _dt, timedelta as _td
        ed = _dt.strptime(ex_date, "%Y-%m-%d")
        # 抓除息日 ±3 天的股價（避免假日沒資料）
        start = (ed - _td(days=3)).strftime("%Y-%m-%d")
        end = (ed + _td(days=3)).strftime("%Y-%m-%d")
        data = _finmind_get("TaiwanStockPrice", stock_id, start, end)
        if not data:
            return None
        # 找最接近 ex_date 的那一天
        best = None
        best_diff = None
        for rec in data:
            rec_date = rec.get("date", "")
            try:
                rd = _dt.strptime(rec_date, "%Y-%m-%d")
            except (ValueError, TypeError):
                continue
            diff = abs((rd - ed).days)
            if best_diff is None or diff < best_diff:
                best = rec
                best_diff = diff
        if best:
            close = float(best.get("close") or 0)
            return close if close > 0 else None
    except RuntimeError:
        # FinMind 額度用完 → silently 回 None
        return None
    except Exception:
        return None
    return None


def _run_manual_selection(
    price_df: pd.DataFrame,      # 來自 pipeline 的股價資料 [股票代號, 股價, ...]
    revenue_df: pd.DataFrame,     # 來自 pipeline 的營收資料 [股票代號, 累計營收YoY(%), ...]
    eps_df: pd.DataFrame,         # 來自 pipeline 的 EPS 資料 [股票代號, EPS本期, ...]
    filters: dict,
    top_n: int = 500,
) -> pd.DataFrame:
    """
    根據 filters 條件，從已知的市場股票中篩選並回傳結果。

    filters 格式：
        {
            "min_rev_yoy": 10.0,          # 累計營收 YoY >= 此值（None = skip）
            "min_pe": None,                # PE <= 此值（None = skip）
            "min_price": None,             # 現價 >= 此值（None = skip）
            "min_volume": None,            # 成交量(張) >= 此值（None = skip）
            "min_bvps": None,             # 淨值 >= 此值（None = skip，暫不支援）
            "min_cash_div": None,          # 今年現金股利 >= 此值（None = skip）
            "min_stock_div": None,         # 今年股票股利 >= 此值（None = skip）
            "min_last_cash_div": None,     # 去年現金股利 >= 此值（None = skip）
            "min_last_stock_div": None,    # 去年股票股利 >= 此值（None = skip）
            "sort_by": ["rev_yoy", "stock_div", "cash_div", "pe"],
        }
    """
    # 1. 取得全市場股票代號與名稱
    # 優先用 pipeline 的 price_df；若為空才 fallback 抓全市場名單
    price_df = price_df.copy() if price_df is not None else pd.DataFrame()
    if price_df.empty:
        base = _fetch_market_stock_list()
    else:
        if "公司名稱_來源" in price_df.columns:
            name_col = "公司名稱_來源"
        else:
            name_col = [c for c in price_df.columns if "名稱" in c or "name" in c.lower()]
            name_col = name_col[0] if name_col else None

        price_cols = ["股票代號"]
        if name_col:
            price_cols.append(name_col)
        # 如果 cache 也有「股價」或「現價」也一起拉進來
        # 【V0.9.5-cache-info】data_date 也要帶進來（Treeview 「資料日期」欄位用）
        for cc in ["股價", "現價", "成交量", "成交量_張", "漲跌", "data_date"]:
            if cc in price_df.columns and cc not in price_cols:
                price_cols.append(cc)
        base = price_df[price_cols].drop_duplicates("股票代號").copy()
        base["股票代號"] = base["股票代號"].astype(str).str.strip()
        if name_col:
            base = base.rename(columns={name_col: "股票名稱"})
        else:
            base["股票名稱"] = ""
        # 統一欄位名：「股價」→「現價」、「成交量_張」不變
        if "股價" in base.columns and "現價" not in base.columns:
            base = base.rename(columns={"股價": "現價"})

    # 2. 取得現價：若 base 已有「現價」就用 cache，不抓 FinMind
    if "現價" in base.columns:
        # 已有現價（來自 cache），不重抓 FinMind
        # cache 不一定有成交量，若沒有則先移除「成交量」條件
        if "成交量_張" not in base.columns:
            base["成交量_張"] = None  # None 表示 cache 沒資料
        # 「漲跌」欄位只在 cache 才有，移到後面
    else:
        all_codes = base["股票代號"].tolist()
        price_finmind = _fetch_finmind_prices_batch(all_codes)
        if not price_finmind.empty:
            base = base.merge(price_finmind, on="股票代號", how="left")
        else:
            base["現價"] = None
            base["成交量_張"] = 0

    # 3. 合併營收 YoY（容錯：空 df 跳過）
    if not revenue_df.empty and "股票代號" in revenue_df.columns:
        revenue_df = revenue_df.copy()
        revenue_df["股票代號"] = revenue_df["股票代號"].astype(str).str.strip()
        rev_cols = ["股票代號", "營收YoY(%)"]
        rev_cols = [c for c in rev_cols if c in revenue_df.columns]
        if len(rev_cols) == 2:
            base = base.merge(revenue_df[rev_cols].drop_duplicates("股票代號"),
                              on="股票代號", how="left")
    if "營收YoY(%)" not in base.columns:
        base["營收YoY(%)"] = None

    # 4. 合併 EPS（容錯：空 df 跳過）
    if not eps_df.empty and "股票代號" in eps_df.columns:
        eps_df = eps_df.copy()
        eps_df["股票代號"] = eps_df["股票代號"].astype(str).str.strip()
        eps_cols = ["股票代號", "EPS本期"]
        eps_cols = [c for c in eps_cols if c in eps_df.columns]
        if len(eps_cols) == 2:
            base = base.merge(eps_df[eps_cols].drop_duplicates("股票代號"),
                              on="股票代號", how="left")
    if "EPS本期" not in base.columns:
        base["EPS本期"] = None

    # 5. 計算 PE
    # 注：EPS 接近 0 會讓 PE 爆炸（ex: EPS=0.01、股價=24 → PE=2400）
    #     設 PE = None 讓使用者看到 --，比看到「3000 倍 PE」合理
    # 門檻：EPS >= 0.05 元視為有意義的獲利能力（低於 0.05 視為雞蛋水餃股）
    PE_MIN_EPS = 0.05
    base["PE"] = None
    pe_mask = (
        (base["現價"].notna()) & (base["現價"] > 0)
        & (base["EPS本期"].notna()) & (base["EPS本期"] >= PE_MIN_EPS)
    )
    base.loc[pe_mask, "PE"] = (base.loc[pe_mask, "現價"] / base.loc[pe_mask, "EPS本期"]).round(2)

    # 6. 抓 FinMind 股利（會用 DB 快取，只在 DB 沒有的才抓 FinMind）
    all_codes = base["股票代號"].tolist()
    div_df = _fetch_finmind_dividend(all_codes, skip_remote=True)
    if not div_df.empty:
        base = base.merge(div_df, on="股票代號", how="left")
    else:
        cy = datetime.now().year
        for suf in [f"{cy}現金股利", f"{cy}股票股利",
                    f"{cy - 1}現金股利", f"{cy - 1}股票股利",
                    f"{cy - 2}現金股利", f"{cy - 2}股票股利",
                    f"{cy - 1}除息日", f"{cy - 1}除息日收盤價",
                    # V0.9.5-goodinfo：殖利率欄位
                    f"{cy}現金殖利率_goodinfo", f"{cy}股票殖利率_goodinfo",
                    f"{cy - 1}現金殖利率_goodinfo", f"{cy - 1}股票殖利率_goodinfo",
                    f"{cy - 2}現金殖利率_goodinfo", f"{cy - 2}股票殖利率_goodinfo"]:
            if suf not in base.columns:
                base[suf] = None

    # 7. 今年/去年現金股利欄位（干擾名稱，用固定名）
    # 【V0.9.5-goodinfo 修 Bug】2026-06-16 William 反映：
    #   - 群聯 (8299) 半年配：App 原本「今年」= DB year=cy-1=2025=31.31
    #     但 goodinfo 2026 支付年 = 16.96 (2026 H1 只配了一半、H2 還沒)
    #   - 原設計「cy-1 = 該年除息」是 fiscal year 語意 → 半年配/季配會跟 goodinfo 不一致
    #   - 修法：改用「cy = 該年除息」= payment year 語意，跟 goodinfo「發放年度」一致
    #     讓使用者看到的「今年現金股利」= 今年實際收到的股利金額
    #   - 範例：cy=2026
    #     * 今年 (cy) = DB year=2026 = goodinfo 2026 = 「2026 收到的股利」
    #     * 去年 (cy-1) = DB year=2025 = goodinfo 2025 = 「2025 收到的股利」
    #     * 前年 (cy-2) = DB year=2024 = goodinfo 2024 = 「2024 收到的股利」
    cy = datetime.now().year
    base["今年現金股利"] = base.get(f"{cy}現金股利", None)
    base["今年股票股利"] = base.get(f"{cy}股票股利", None)
    base["去年現金股利"] = base.get(f"{cy - 1}現金股利", None)
    base["去年股票股利"] = base.get(f"{cy - 1}股票股利", None)
    # 前年度（保留給 UI 顯示）
    base["前年現金股利"] = base.get(f"{cy - 2}現金股利", None)
    base["前年股票股利"] = base.get(f"{cy - 2}股票股利", None)
    # V0.9.5+ Phase 10：去年除息日 + 除息日收盤價（供除息價 fallback 用）
    # 【V0.9.5-goodinfo 配合修改】去年 = cy-1 = DB year=cy-1
    base["去年除息日"] = base.get(f"{cy - 1}除息日", None)
    base["去年除息日收盤價"] = base.get(f"{cy - 1}除息日收盤價", None)
    # V0.9.5-goodinfo：殖利率原始值（goodinfo 來源）— 殖利率直接用、不計算
    base["今年現金殖利率_goodinfo"] = base.get(f"{cy}現金殖利率_goodinfo", None)
    base["今年股票殖利率_goodinfo"] = base.get(f"{cy}股票殖利率_goodinfo", None)
    base["去年現金殖利率_goodinfo"] = base.get(f"{cy - 1}現金殖利率_goodinfo", None)
    base["去年股票殖利率_goodinfo"] = base.get(f"{cy - 1}股票殖利率_goodinfo", None)

    # 8. 今年現金殖利率（V0.9.5-goodinfo3 改：100% 用 goodinfo，不 fallback）
    # 【William 2026-06-17 12:03 反映】「殖利率應該不用任何計算直接用才對」
    #   - goodinfo 已用除息基準日還原價算好殖利率、比任何 fallback 都準
    #   - 拿掉 cash/現價 fallback（會被現價偏離誤導）
    #   - cash=0 也要用 goodinfo 值（ex: 5386 2026 cash=0 但 goodinfo cash_yield=0.30%）
    #   - goodinfo 殖利率 = 0 (該年未配息) → 殖利率 0%（合理、不是 None）
    base["今年現金殖利率(%)"] = None
    goodinfo_yld_mask = base["今年現金殖利率_goodinfo"].notna()
    base.loc[goodinfo_yld_mask, "今年現金殖利率(%)"] = (
        base.loc[goodinfo_yld_mask, "今年現金殖利率_goodinfo"].round(2)
    )

    # 9. 去年現金殖利率（V0.9.5-goodinfo3：100% 用 goodinfo、不走 cash/現價 fallback）
    # 【原本】cash=0 → continue 跳過 → 殖利率 None（5386 去年現金殖利率 bug）
    # 【修正】cash=0 也要看 goodinfo 有沒有殖利率值、有就直接用
    for col in ["去年除息日", "去年除息日收盤價"]:
        if col not in base.columns:
            base[col] = None
    base["去年現金殖利率(%)"] = None
    goodinfo_last_mask = base["去年現金殖利率_goodinfo"].notna()
    base.loc[goodinfo_last_mask, "去年現金殖利率(%)"] = (
        base.loc[goodinfo_last_mask, "去年現金殖利率_goodinfo"].round(2)
    )

    # 9.5 V0.9.5-goodinfo：今年/去年股票殖利率（直接用 goodinfo 提供）
    base["今年股票殖利率(%)"] = None
    base["去年股票殖利率(%)"] = None
    sy_mask_this = base["今年股票殖利率_goodinfo"].notna()
    base.loc[sy_mask_this, "今年股票殖利率(%)"] = (
        base.loc[sy_mask_this, "今年股票殖利率_goodinfo"].round(2)
    )
    sy_mask_last = base["去年股票殖利率_goodinfo"].notna()
    base.loc[sy_mask_last, "去年股票殖利率(%)"] = (
        base.loc[sy_mask_last, "去年股票殖利率_goodinfo"].round(2)
    )

    # 10. 應用篩選條件（V0.9.5+ B 邏輯修正版）
    #     【關鍵修正】2026-06-14 William 反映「YoY < 30 還跑出來」
    #
    #     【原本的 BUG（V0.9.5-alpha 5th commit）】
    #     - 拿掉 AND mask、只用 data_score > 0 過濾
    #     - 結果：YoY 沒過、但殖利率/PE/現價/成交量過的股票也被納入
    #     - 截圖實例：1810 和成（YoY -7.42）被納入
    #
    #     【本版的設計】
    #     - 硬條件（YoY、PE、現價、成交量、股利金額）：AND mask
    #       - None 一律算 fail（資料缺漏不能說達標）
    #       - 不過門檻也算 fail
    #     - 軟條件（今年/去年現金殖利率）：不擋 mask
    #       - 殖利率 None：不擋 mask（其他條件過了還是納入）
    #       - 殖利率有值未達標：不擋 mask（其他條件過了還是納入）
    #       - 殖利率達標：拿來算排序分數
    #     - 排序：殖利率有值 > 殖利率高 > 股票股利高 > 營收 YoY 高 > PE 低
    #     - 「至少要有一個篩選 item 過關」= 任何被勾選的硬條件至少要過一個
    #       （全 None、全未達 → 全排除 → 結果為空）
    #     - 沒結果會在 caller 判斷並提示「這次篩選沒有合格股票」
    mask = pd.Series([True] * len(base), index=base.index)
    any_checked = False  # 記錄是否有任何被勾選的條件

    # 累計營收 YoY ≥ X（硬）
    if filters.get("min_rev_yoy") is not None:
        any_checked = True
        rev = base["營收YoY(%)"]
        mask &= rev.notna() & (rev >= filters["min_rev_yoy"])

    # PE ≤ X（硬，filters key 是 min_pe 但語意是「PE 不超過」）
    if filters.get("min_pe") is not None:
        any_checked = True
        pe = base["PE"]
        mask &= pe.notna() & (pe <= filters["min_pe"])

    # 現價 ≥ X（硬）
    if filters.get("min_price") is not None:
        any_checked = True
        price = base["現價"]
        mask &= price.notna() & (price > 0) & (price >= filters["min_price"])

    # 月均成交量 ≥ X（硬）
    if filters.get("min_volume") is not None:
        any_checked = True
        vol = base["成交量_張"]
        mask &= vol.notna() & (vol >= filters["min_volume"])

    # 今年現金股利 ≥ X（元）（硬）
    if filters.get("min_cash_div") is not None:
        any_checked = True
        cd = base["今年現金股利"]
        mask &= cd.notna() & (cd >= filters["min_cash_div"])

    # 今年股票股利 ≥ X（元）（硬）
    if filters.get("min_stock_div") is not None:
        any_checked = True
        sd = base["今年股票股利"]
        mask &= sd.notna() & (sd >= filters["min_stock_div"])

    # 去年現金股利 ≥ X（元）（硬）
    if filters.get("min_last_cash_div") is not None:
        any_checked = True
        cd = base["去年現金股利"]
        mask &= cd.notna() & (cd >= filters["min_last_cash_div"])

    # 去年股票股利 ≥ X（元）（硬）
    if filters.get("min_last_stock_div") is not None:
        any_checked = True
        sd = base["去年股票股利"]
        mask &= sd.notna() & (sd >= filters["min_last_stock_div"])

    # 今年現金殖利率 ≥ X%（軟：不擋 mask、只算排序）
    if filters.get("min_cash_div_yld") is not None:
        any_checked = True
        # 不動 mask、留給排序處理

    # 去年現金殖利率 ≥ X%（軟：不擋 mask、只算排序）
    # 【V0.9.5-alpha Phase 6 修 Bug】2026-06-15
    # 原本以「data_score / pass_score 雙計分」實作（舊 B 邏輯），
    # 但 Phase 4 已改成「硬 AND + 軟不擋 mask」邏輯，data_score/pass_score
    # 從未被初始化，導致勾選「去年現金殖利率 ≥ X%」時 UnboundLocalError，
    # 整個手動選股流程崩潰。
    # 修法：跟「今年現金殖利率」一樣的 no-op（只設 any_checked=True），
    # 排序階段用 _yld_has_data 自然處理殖利率有/無資料的排序。
    if filters.get("min_last_cash_yld") is not None:
        any_checked = True
        # 不動 mask、留給排序處理

    # 過濾：硬條件 AND mask（楊重複保險，殖利率軟條件不擋 mask）
    # 注：如果是「什麼都沒勾」的情況、保留全部（向後相容）
    if any_checked:
        result = base[mask].copy()
    else:
        result = base.copy()

    # 11. 排序：殖利率有值 > 殖利率高 > 股票股利高 > 營收 YoY 高 > PE 低
    # 【重點】殖利率有資料（vs None）排前面、殖利率高的排前面、None 排後面
    # V0.9.5-goodinfo3：拿掉 10Y 平均殖利率 sort key（William 不需要）
    # 【V0.9.5-goodinfo4+5 修 Bug】2026-06-18 18:12 William 反映：
    #   「順便將篩選結果依照營收累計YoY由大到小排序」
    #   → 主要 sort 改為營收累計YoY 降序（高增長排前面）
    #   → 原本是「殖利率 > 股票股利 > 營收YoY > PE」、現在改成「營收YoY > 殖利率 > 股票股利 > PE」
    result["_yld_has_data"] = result["今年現金殖利率(%)"].notna().astype(int)
    # 殖利率直接作 sort key、不加負號→降序時殖利率高排前
    result["_sort_yld"] = result["今年現金殖利率(%)"].fillna(-9999)
    result["_sort_rev"] = result["營收YoY(%)"].fillna(-9999)
    result["_sort_stock"] = result["今年股票股利"].fillna(0)
    result["_sort_pe"] = result["PE"].fillna(9999)

    result = result.sort_values(
        # 主排序：營收累計YoY 降序、其次殖利率、再來股票股利、最後 PE
        ["_sort_rev", "_yld_has_data", "_sort_yld", "_sort_stock", "_sort_pe"],
        ascending=[False, False, False, False, True]
    ).reset_index(drop=True)

    result = result.head(top_n).reset_index(drop=True)

    # 12. 整理輸出欄位
    out_cols = ["股票代號", "股票名稱", "現價", "營收YoY(%)",
                "今年股票股利", "今年現金殖利率(%)", "PE",
                "成交量_張", "今年現金股利",
                "去年現金股利", "去年股票股利", "去年現金殖利率(%)", "EPS本期",
                f"{cy}現金股利", f"{cy - 1}現金股利", f"{cy - 2}現金股利",
                # V0.9.5-goodinfo3：殖利率加強欄位（10Y 平均殖利率已拿掉，William 不需要）
                "今年股票殖利率(%)", "去年股票殖利率(%)",
                "data_date"]  # 【V0.9.5-cache-info】Treeview 「資料日期」欄位用
    out_cols = [c for c in out_cols if c in result.columns]
    # 整理重複的現金股利（保留乾淨的今年/去年/前年）
    result = result[out_cols].rename(columns={
        "成交量_張": "成交量(張)",
        f"{cy}現金股利": "今年現金股利_原始",
        f"{cy - 1}現金股利": "去年現金股利_原始",
        f"{cy - 2}現金股利": "前年現金股利_原始",
    })
    # 還原乾淨名稱
    result = result.rename(columns={
        "今年現金股利_原始": "今年現金股利_原始",
    })
    # 重新整理輸出（最終顯示欄位）
    # 先把「營收YoY(%)」改名為「累計營收YoY(%)」供 Treeview 顯示
    result = result.rename(columns={"營收YoY(%)": "累計營收YoY(%)"})
    final_cols = ["股票代號", "股票名稱", "現價", "累計營收YoY(%)",
                  "今年股票股利", "今年現金股利", "今年現金殖利率(%)",
                  "去年股票股利", "去年現金股利", "去年現金殖利率(%)",
                  "今年股票殖利率(%)", "去年股票殖利率(%)",
                  "PE", "成交量(張)", "EPS本期",
                  "data_date"]  # 【V0.9.5-cache-info】Treeview 「資料日期」欄位用
    final_cols = [c for c in final_cols if c in result.columns]
    return result[final_cols].rename(columns={
        "今年現金股利": "今年現金股利_原始",
        "去年現金股利": "去年現金股利_原始",
    }).rename(columns={
        "今年現金股利_原始": "今年現金股利(元)",
        "去年現金股利_原始": "去年現金股利(元)",
        "今年股票股利": "今年股票股利(元)",
        "去年股票股利": "去年股票股利(元)",
    })


# ==========================================================
# 通用工具
# ==========================================================

def format_for_output(df: pd.DataFrame, sort_by_code: bool = True) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    if "股票代號" in df.columns:
        df["股票代號"] = df["股票代號"].astype(str).str.strip()
    if "股票代號" in df.columns and "公司名稱_來源" in df.columns:
        cols = ["股票代號", "公司名稱_來源"] + [c for c in df.columns if c not in ["股票代號", "公司名稱_來源"]]
        df = df[cols]
    if sort_by_code and "股票代號" in df.columns:
        df["股票代號_sort"] = df["股票代號"].astype(str).str.extract(r'(\d+)').astype(int)
        df = df.sort_values("股票代號_sort", ascending=True).drop(columns=["股票代號_sort"])
    return df.reset_index(drop=True)


def ensure_str_column(df: pd.DataFrame, col_name: str) -> pd.DataFrame:
    if col_name in df.columns:
        df[col_name] = df[col_name].astype(str).str.strip()
    return df
# ==========================================================
# 多因子評分函數
# ==========================================================

def calculate_multi_factor_score(df: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    df = df.copy()

    # ✅ 新增：處理異常值
    df["營收YoY(%)"] = df["營收YoY(%)"].replace([float("inf"), -float("inf")], pd.NA)
    df["EPSYoY_顯示(%)"] = df["EPSYoY_顯示(%)"].replace([float("inf"), -float("inf")], pd.NA)

    if "Close" in df.columns:
        df["mom_1m"] = df.groupby("股票代號")["Close"].pct_change(21) * 100
        df["mom_3m"] = df.groupby("股票代號")["Close"].pct_change(63) * 100
        df["mom_6m"] = df.groupby("股票代號")["Close"].pct_change(126) * 100
    else:
        df["mom_1m"] = 0
        df["mom_3m"] = 0
        df["mom_6m"] = 0

    factors = ['mom_1m', 'mom_3m', 'mom_6m', '營收YoY(%)', 'EPSYoY_顯示(%)']
    for f in factors:
        if f in df.columns:
            mean_val = df[f].mean()
            std_val = df[f].std()
            if std_val > 0:
                df[f"{f}_zscore"] = (df[f] - mean_val) / std_val
            else:
                df[f"{f}_zscore"] = 0

    df["Score"] = (df["mom_1m_zscore"].fillna(0) * cfg.factor_weight_mom1 +
                   df["mom_3m_zscore"].fillna(0) * cfg.factor_weight_mom3 +
                   df["mom_6m_zscore"].fillna(0) * cfg.factor_weight_mom6 +
                   df["營收YoY(%)_zscore"].fillna(0) * cfg.factor_weight_rev +
                   df["EPSYoY_顯示(%)_zscore"].fillna(0) * cfg.factor_weight_eps)
    df["Score"] = df["Score"].round(2)
    df["評分_動能1M"] = df["mom_1m_zscore"].fillna(0).round(2)
    df["評分_動能3M"] = df["mom_3m_zscore"].fillna(0).round(2)
    df["評分_動能6M"] = df["mom_6m_zscore"].fillna(0).round(2)
    df["評分_成長"] = (df["營收YoY(%)_zscore"].fillna(0) * cfg.factor_weight_rev * 4).round(2)
    return df


def calculate_enhanced_score(df: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    return calculate_multi_factor_score(df, cfg)


def calculate_simple_score(df: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    df = df.copy()

    df["PE"] = df["PE"].replace([float("inf"), -float("inf")], pd.NA)
    df["EPSYoY_raw"] = df["EPSYoY_raw"].replace([float("inf"), -float("inf")], pd.NA)

    # ========== DEBUG: 簡易評分診斷 ==========
    print("\n" + "=" * 60)
    print("🔍 [DEBUG] calculate_simple_score 診斷")
    print("=" * 60)

    print(f"\n📊 原始資料筆數: {len(df)}")
    print(f"📊 有營收YoY資料的筆數: {df['營收YoY(%)'].notna().sum()}")
    print(f"📊 有EPS本期資料的筆數: {df['EPS本期'].notna().sum()}")
    print(f"📊 有EPSYoY_raw資料的筆數: {df['EPSYoY_raw'].notna().sum()}")
    print(f"📊 有PE資料的筆數: {df['PE'].notna().sum()}")

    print(f"\n⚙️ 目前門檻設定:")
    print(f"   simple_min_rev_yoy = {cfg.simple_min_rev_yoy}")
    print(f"   simple_min_eps_yoy = {cfg.simple_min_eps_yoy}")
    print(f"   simple_min_eps = {cfg.simple_min_eps}")
    print(f"   simple_max_pe = {cfg.simple_max_pe}")
    # ========== DEBUG 結束 ==========

    mask = pd.Series([True] * len(df))

    if cfg.simple_min_rev_yoy > -998:
        rev_ok = df["營收YoY(%)"].fillna(cfg.simple_min_rev_yoy - 1) >= cfg.simple_min_rev_yoy
        mask = mask & rev_ok

    if cfg.simple_min_eps_yoy > -998:
        eps_yoy_ok = (df["EPSYoY_raw"].fillna(cfg.simple_min_eps_yoy / 100 - 1) * 100) >= cfg.simple_min_eps_yoy
        mask = mask & eps_yoy_ok

    if cfg.simple_min_eps > -998:
        eps_ok = df["EPS本期"].fillna(cfg.simple_min_eps - 1) >= cfg.simple_min_eps
        mask = mask & eps_ok

    if cfg.simple_max_pe < 998:
        pe_ok = df["PE"].fillna(cfg.simple_max_pe + 1) <= cfg.simple_max_pe
        mask = mask & pe_ok

    # ========== DEBUG: 門檻通過數量 ==========
    print(f"\n✅ 各門檻通過數量:")
    if cfg.simple_min_rev_yoy > -998:
        rev_pass = (df["營收YoY(%)"].fillna(cfg.simple_min_rev_yoy - 1) >= cfg.simple_min_rev_yoy).sum()
        print(f"   營收門檻 (>= {cfg.simple_min_rev_yoy}%): {rev_pass} 檔")
    else:
        print(f"   營收門檻: 未啟用")

    if cfg.simple_min_eps_yoy > -998:
        eps_yoy_pass = (
                    (df["EPSYoY_raw"].fillna(cfg.simple_min_eps_yoy / 100 - 1) * 100) >= cfg.simple_min_eps_yoy).sum()
        print(f"   EPS YoY 門檻 (>= {cfg.simple_min_eps_yoy}%): {eps_yoy_pass} 檔")
    else:
        print(f"   EPS YoY 門檻: 未啟用")

    if cfg.simple_min_eps > -998:
        eps_pass = (df["EPS本期"].fillna(cfg.simple_min_eps - 1) >= cfg.simple_min_eps).sum()
        print(f"   EPS 門檻 (>= {cfg.simple_min_eps}元): {eps_pass} 檔")
    else:
        print(f"   EPS 門檻: 未啟用")

    if cfg.simple_max_pe < 998:
        pe_pass = (df["PE"].fillna(cfg.simple_max_pe + 1) <= cfg.simple_max_pe).sum()
        print(f"   PE 門檻 (<= {cfg.simple_max_pe}倍): {pe_pass} 檔")
    else:
        print(f"   PE 門檻: 未啟用")

    print(f"\n🎯 最終通過所有門檻的股票數量: {mask.sum()} 檔")

    if mask.sum() == 0 and len(df) > 0:
        print(f"\n⚠️ 前5筆未通過股票的診斷:")
        failed_df = df[~mask].head(5)
        for idx, row in failed_df.iterrows():
            code = row.get("股票代號", "N/A")
            name = str(row.get("公司名稱_來源", "N/A"))[:20]
            rev = row.get("營收YoY(%)", "N/A")
            eps_yoy_raw = row.get("EPSYoY_raw", "N/A")
            eps = row.get("EPS本期", "N/A")
            pe = row.get("PE", "N/A")
            print(f"   {code} {name} | 營收:{rev}% | EPS YoY:{eps_yoy_raw} | EPS:{eps} | PE:{pe}")
    # ========== DEBUG 結束 ==========

    rev_score = df["營收YoY(%)"].fillna(0)
    eps_score = (df["EPSYoY_raw"].fillna(0) * 100)
    div_score = df["殖利率(估)"].fillna(0) * 100
    pe_score = df["PE"].fillna(0)

    w_rev = cfg.simple_score_weight_rev
    w_eps = cfg.simple_score_weight_eps
    w_div = cfg.simple_score_weight_div
    w_pe = cfg.simple_score_weight_pe

    df["Score_raw"] = (rev_score * (w_rev / 100) +
                       eps_score * (w_eps / 100) +
                       div_score * (w_div / 100) +
                       pe_score * (w_pe / 100))

    df["Score"] = df["Score_raw"].where(mask, pd.NA)
    df["通過門檻"] = mask

    print("\n" + "=" * 60 + " DEBUG 結束 " + "=" * 60 + "\n")

    return df


# ==========================================================
# 強化版技術指標
# ==========================================================

def calc_enhanced_tech_indicators(cfg: StrategyConfig, df_hist: pd.DataFrame) -> pd.DataFrame:
    df_hist = df_hist.sort_values("Date").copy()
    if cfg.tech_months is not None:
        cutoff_date = datetime.today() - pd.DateOffset(months=cfg.tech_months)
        df_hist = df_hist[df_hist["Date"] >= cutoff_date]

    df_hist["MA5"] = df_hist["Close"].rolling(5).mean()
    df_hist["MA20"] = df_hist["Close"].rolling(20).mean()
    df_hist["VolMA20"] = df_hist["Volume"].rolling(20).mean()

    delta = df_hist["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    rs = gain.rolling(14).mean() / loss.rolling(14).mean()
    df_hist["RSI"] = 100 - (100 / (1 + rs))

    ema12 = df_hist["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df_hist["Close"].ewm(span=26, adjust=False).mean()
    df_hist["MACD"] = ema12 - ema26
    df_hist["MACD_signal"] = df_hist["MACD"].ewm(span=9, adjust=False).mean()
    df_hist["MACD_hist"] = df_hist["MACD"] - df_hist["MACD_signal"]

    oversold = df_hist["RSI"] < cfg.rsi_oversold
    oversold_recent = oversold.rolling(cfg.oversold_lookback).max().shift(1).fillna(0).astype(bool)

    recover_level = cfg.rsi_aggressive if cfg.use_aggressive_signal else cfg.rsi_recover
    rsi_cross_up = (df_hist["RSI"] >= recover_level) & (df_hist["RSI"].shift(1) < recover_level)
    macd_hist_turn = (df_hist["MACD_hist"] > 0) & (df_hist["MACD_hist"].shift(1) <= 0)
    turn_strong = rsi_cross_up | macd_hist_turn

    ma20_slope = df_hist["MA20"] - df_hist["MA20"].shift(cfg.ma_slope_days)
    trend_ok = (df_hist["Close"] >= df_hist["MA20"] * (1 - cfg.ma20_tolerance)) & (ma20_slope > 0)
    volume_ok = (df_hist["Volume"] >= df_hist["VolMA20"] * 1.5)

    daily_buy = oversold_recent & turn_strong
    if cfg.require_trend_filter:
        daily_buy = daily_buy & trend_ok
    if cfg.require_volume_filter:
        daily_buy = daily_buy & volume_ok

    if cfg.use_mtf_confirmation:
        df_hist["Weekly_MA20"] = df_hist["MA20"].rolling(5).mean()
        weekly_trend = df_hist["MA20"] > df_hist["Weekly_MA20"]
        df_hist["Monthly_MA20"] = df_hist["MA20"].rolling(20).mean()
        monthly_trend = df_hist["MA20"] > df_hist["Monthly_MA20"]
        df_hist["確認層級"] = daily_buy.astype(int) + weekly_trend.astype(int) + monthly_trend.astype(int)
        mtf_buy = daily_buy & (weekly_trend | monthly_trend)
    else:
        mtf_buy = daily_buy
        df_hist["確認層級"] = daily_buy.astype(int)

    if cfg.use_divergence_detection:
        price_high = df_hist["Close"].rolling(20).max()
        rsi_high = df_hist["RSI"].rolling(20).max()
        bearish_divergence = (df_hist["Close"] == price_high) & (df_hist["RSI"] < rsi_high.shift(1))
        price_low = df_hist["Close"].rolling(20).min()
        rsi_low = df_hist["RSI"].rolling(20).min()
        bullish_divergence = (df_hist["Close"] == price_low) & (df_hist["RSI"] > rsi_low.shift(1))
        df_hist["熊市背離"] = bearish_divergence
        df_hist["牛市背離"] = bullish_divergence
        mtf_buy = mtf_buy & (~bearish_divergence)
    else:
        df_hist["熊市背離"] = False
        df_hist["牛市背離"] = False

    volume_surge = df_hist["Volume"] >= df_hist["VolMA20"] * cfg.volume_surge_multiplier
    df_hist["成交量爆發"] = volume_surge

    df_hist["買點"] = mtf_buy
    df_hist["買點_基礎"] = daily_buy
    df_hist["訊號型態"] = "三段式_B_強化版"
    df_hist["Ret_1D_past(%)"] = df_hist["Close"].pct_change(1) * 100
    df_hist["Ret_5D_past(%)"] = df_hist["Close"].pct_change(5) * 100

    return df_hist
# ==========================================================
# Excel Stock List Loader
# ==========================================================

def load_stock_list_from_excel(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"找不到 Excel: {file_path}")
    df = pd.read_excel(file_path)
    col = find_col(df.columns, ["股票", "code"])
    if col is None:
        raise ValueError("Excel 必須包含 '股票代號' 或 'code' 欄位")
    return df[col].astype(str).str.strip().tolist()


# ==========================================================
# History Cache System
# ==========================================================

def get_history_file(stock_id, history_months):
    return f"{HISTORY_DIR}/{stock_id}_{history_months}m.xlsx"


def init_stock_history(session, cfg, stock_id, history_months):
    months = month_starts_back(history_months)
    frames = []
    for m in months:
        df = fetch_twse_stock_day_month(session, cfg, stock_id, m)
        if df is not None and not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    df_all = pd.concat(frames)
    df_all = df_all.drop_duplicates(subset=["Date"]).sort_values("Date")
    return df_all


def update_stock_history(session, cfg, stock_id, df_old):
    today_month = datetime.today().strftime("%Y%m01")
    df_new = fetch_twse_stock_day_month(session, cfg, stock_id, today_month)
    if df_new is None or df_new.empty:
        return df_old
    df_all = pd.concat([df_old, df_new])
    df_all = df_all.drop_duplicates(subset=["Date"]).sort_values("Date")
    return df_all


def get_stock_history(session, cfg, stock_id, logger, history_months):
    os.makedirs(HISTORY_DIR, exist_ok=True)
    file_path = get_history_file(stock_id, history_months)
    if not os.path.exists(file_path):
        logger.log(f"📥 [{stock_id}] 初始化 {history_months} 個月歷史資料")
        df = init_stock_history(session, cfg, stock_id, history_months)
        save_cache(file_path, df)
        return df
    df_old, _ = load_cache(file_path)
    logger.log(f"🔄 [{stock_id}] 更新當月資料")
    df_new = update_stock_history(session, cfg, stock_id, df_old)
    save_cache(file_path, df_new)
    return df_new


# ==========================================================
# 【V0.9.5-etf 新增】2026-06-19 William 要求：
#   主動式 ETF 成份股 Tab
#   - 來源 1：TWSE 官方 API `/rwd/zh/ETF/activeList` 拿 18 檔 domestic 主動式 ETF
#   - 來源 2：etfinfo.tw `/etf/{code}` 總覽頁、parse「前 10 大成分股」HTML 表格
# ==========================================================

ETF_ACTIVELIST_URL = "https://www.twse.com.tw/rwd/zh/ETF/activeList"
ETFINFO_ETF_URL = "https://www.etfinfo.tw/etf/{code}"

def _display_width(s: str) -> int:
    """【V0.9.5-etf-popup-width】估算字串在 Text widget 中的顯示寬度
    - 中文字（CJK）算 2 字元寬
    - ASCII 算 1 字元寬
    - 因為 Tkinter Text widget 的 width 參數以「平均字元寬度」為單位
      → 純算字元數會讓中文超出 width 計算、後面字被截斷
    """
    w = 0
    for c in s:
        cp = ord(c)
        # CJK 統一表意文字：0x4E00-0x9FFF
        # CJK 符號和標點：0x3000-0x303F
        # 全形 ASCII：0xFF00-0xFFEF
        # 平假名/片假名：0x3040-0x30FF
        if 0x3000 <= cp <= 0x9FFF or 0xFF00 <= cp <= 0xFFEF:
            w += 2
        else:
            w += 1
    return w


def fetch_active_etf_list(session: requests.Session, cfg: StrategyConfig) -> pd.DataFrame:
    """【V0.9.5-etf】抓 TWSE 主動式 ETF 列表、只保留 domestic（台股）
    回傳 DataFrame: code, name, category
    """
    r = session.get(
        ETF_ACTIVELIST_URL,
        timeout=cfg.timeout,
        verify=cfg.verify_ssl,
        headers={
            "User-Agent": "StockTool/AdvisorStyle-v0.9.5-tab-split-phase3",
            "Referer": "https://www.twse.com.tw/zh/products/securities/etf/products/active-list.html",
        },
    )
    r.raise_for_status()
    data = r.json()
    if data.get("status") != "ok":
        raise RuntimeError(f"TWSE ETF activeList 回傳非 ok：{data}")
    df = pd.DataFrame(data["data"], columns=data["fields"])
    # 只留 domestic（台股）、拿掉 foreign (海外) 和 bfIncome (債券)
    df = df[df["ETF分類"] == "domestic"].copy()
    df = df.rename(columns={
        "證券代號": "etf_code",
        "證券簡稱": "etf_name",
    })
    df["etf_code"] = df["etf_code"].astype(str).str.strip()
    df = df[["etf_code", "etf_name"]].reset_index(drop=True)
    return df


def fetch_etf_top10_holdings(session: requests.Session, cfg: StrategyConfig,
                              etf_code: str) -> list:
    """【V0.9.5-etf】抓 etfinfo.tw 總覽頁的「前 10 大成分股」

    從 SSR 解析（__NUXT_DATA__ 內含 shares + industry）：
    範例：`{"code":149,"name":150,"weight":151,"shares":152,"unit":153,"industry":17},"2330","台積電",57.01,519237994,"股","半導體"`

    回傳 list of dict，每個含 {stock_code, stock_name, weight, shares, industry}
    例：
    [
        {"stock_code": "2330", "stock_name": "台積電", "weight": 57.01, "shares": 519237994, "industry": "半導體"},
        {"stock_code": "2454", "stock_name": "聯發科", "weight": 6.28, "shares": 31410621, "industry": "半導體"},
    ]

    【V0.9.5-etf-history】shares 是持股股數（如 519237994 股 = 519,237.994 張）
    """
    import re as _re
    url = ETFINFO_ETF_URL.format(code=etf_code)
    r = session.get(
        url,
        timeout=cfg.timeout,
        verify=cfg.verify_ssl,
        headers={
            "User-Agent": "StockTool/AdvisorStyle-v0.9.5-tab-split-phase3",
            "Referer": "https://www.etfinfo.tw/",
        },
    )
    r.raise_for_status()
    html = r.text

    # 抓「前 10 大成分股」section
    section_start = html.find("前 10 大成分股")
    if section_start < 0:
        raise RuntimeError(f"{etf_code} 找不到「前 10 大成分股」section")

    # 只看 section 後 5000 字元
    section = html[section_start:section_start + 5000]

    # Parse HTML 表格（SSR 渲染、可靠）
    rows = _re.findall(
        r'<a href="/stock/(\d+)"[^>]*>(\d+)</a></td>\s*'
        r'<td[^>]*><span[^>]*>([^<]+)</span></td>\s*'
        r'<td[^>]*><strong[^>]*>([0-9.]+)%',
        section,
        _re.DOTALL,
    )
    if not rows:
        raise RuntimeError(f"{etf_code} 解析前 10 大失敗")

    # 【V0.9.5-etf-history】從 SSR __NUXT_DATA__ parse shares
    # 結構（Nuxt 3 flat array）：
    #   schema: {"code":X,"name":X,"weight":X,"shares":X,"unit":X,"industry":17}
    #   values: "2330","台積電",57.01,519237994,"股"
    # 注意：industry=17 指向 None（schema ref、沒有填值）→ 暫時拿不到 industry
    # → 重點在 shares（計算張數異動）、industry 可後續再補
    import json as _json
    nuxt_match = _re.search(r"__NUXT_DATA__[^>]*>([^<]+)</script>", html)
    nuxt_list = []
    if nuxt_match:
        try:
            nuxt_list = _json.loads(nuxt_match.group(1))
        except Exception:
            nuxt_list = []

    # 建立 stock_code → shares 對照
    # Nuxt 3 flat array 結構：每個 holding 是
    #   [schema_dict, code_val, name_val, weight_val, shares_val, unit_val]
    # schema_dict.shares 是指向 shares_val 的 index reference
    # 注意：unit 通常 reuse 已存在的 "股" ref → 不佔位置
    # 計算 holding 長度：從 schema dict 後到下一個 schema 之間 = 5 個值（reuse unit）或 6 個值（首次 unit）

    def _resolve_val(arr, idx):
        """解 Nuxt ref：追蹤整數 ref 直到拿到實際值"""
        depth = 0
        while depth < 5:
            try:
                v = arr[idx]
            except IndexError:
                return None
            if isinstance(v, int) and 0 <= v < len(arr):
                idx = v
                depth += 1
                continue
            return v
        return None

    code_to_shares = {}
    n = len(nuxt_list)
    i = 0
    while i < n:
        item = nuxt_list[i]
        # schema dict：{"code":X, "name":X, "weight":X, "shares":X, "unit":X, "industry":X}
        if not (isinstance(item, dict)
                and "code" in item and "shares" in item
                and isinstance(item.get("code"), int)
                and isinstance(item.get("shares"), int)):
            i += 1
            continue
        # schema dict 後面跟著 5 個值（code, name, weight, shares, unit）
        # unit 可能 reuse（指向已存在的 "股" ref）→ 計算 layout 長度
        schema = item
        # 從 schema 算 holding 結尾：找出 max ref index + 1
        max_ref = i  # schema 自己
        for field in ("code", "name", "weight", "shares", "unit"):
            ref = schema.get(field)
            if isinstance(ref, int) and ref > max_ref:
                max_ref = ref
        # 但 unit 可能指向已存在 ref（< i + 5）、就不會佔新位置
        # 簡化：假設 holding layout 是 schema + 5 個新值 = 6 位置
        #       除非 unit ref < i + 5（reuse）、那就只有 5 位置
        unit_ref = schema.get("unit")
        expected_end = i + 6  # schema + 5 values
        if isinstance(unit_ref, int) and unit_ref < i + 5:
            # unit reuse、不佔新位置
            expected_end = i + 5

        try:
            # 用 schema ref 拿真實值（避免 layout 偏移）
            code_val = _resolve_val(nuxt_list, schema["code"])
            name_val = _resolve_val(nuxt_list, schema["name"])
            weight_val = _resolve_val(nuxt_list, schema["weight"])
            shares_val = _resolve_val(nuxt_list, schema["shares"])
            if (isinstance(code_val, str) and code_val.isdigit()
                    and isinstance(shares_val, (int, float))
                    and shares_val > 0):
                code_to_shares[code_val] = int(shares_val)
        except (IndexError, ValueError, TypeError):
            pass

        # 推進：跳到下一個 schema（使用 expected_end）
        # 但要驗證下個位置真的是 schema、否則前進 1 格
        next_i = expected_end
        if next_i < n:
            next_item = nuxt_list[next_i]
            if isinstance(next_item, dict) and "code" in next_item and "shares" in next_item:
                i = next_i
            else:
                i += 1
        else:
            i = expected_end

    holdings = []
    for stock_code, _, stock_name, weight in rows:
        stock_code = stock_code.strip()
        stock_name = stock_name.strip()
        weight_val = float(weight)
        shares = code_to_shares.get(stock_code, 0)
        holdings.append({
            "stock_code": stock_code,
            "stock_name": stock_name,
            "weight": weight_val,
            "shares": shares,
            "industry": "",  # etfinfo.tw holdings 結構內 industry 是 ref→None、暫拿不到
        })

    # 若 shares 全為 0、可能 SSR parse 失敗、警告
    if holdings and not any(h["shares"] > 0 for h in holdings):
        print(f"[V0.9.5-etf-history] ⚠️ {etf_code} SSR parse 失敗、shares 全為 0")

    return holdings


def build_etf_holdings_table(session: requests.Session, cfg: StrategyConfig,
                              logger) -> pd.DataFrame:
    """【V0.9.5-etf】完整 ETF 持股 table
    1. 抓 18 檔 domestic ETF 列表
    2. 對每檔 ETF 抓前 10 大
    3. 合併為長表 (stock_code, stock_name, etf_code, etf_name, weight)
    """
    etfs = fetch_active_etf_list(session, cfg)
    logger.log(f"📋 [ETF] 抓到 {len(etfs)} 檔台股主動式 ETF（domestic）")

    all_rows = []
    for _, row in etfs.iterrows():
        etf_code = row["etf_code"]
        etf_name = row["etf_name"]
        try:
            holdings = fetch_etf_top10_holdings(session, cfg, etf_code)
            for h in holdings:
                all_rows.append({
                    "stock_code": h["stock_code"],
                    "stock_name": h["stock_name"],
                    "etf_code": etf_code,
                    "etf_name": etf_name,
                    "weight": h["weight"],
                })
            logger.log(f"  ✅ [{etf_code}] {etf_name} 抓到 {len(holdings)} 檔前 10 大")
        except Exception as e:
            logger.log(f"  ⚠️ [{etf_code}] {etf_name} 抓取失敗：{e}")

    df = pd.DataFrame(all_rows)
    if df.empty:
        return df

    # 整理型別
    df["stock_code"] = df["stock_code"].astype(str).str.strip()
    df["stock_name"] = df["stock_name"].astype(str).str.strip()
    df["weight"] = pd.to_numeric(df["weight"], errors="coerce")
    return df


def aggregate_etf_holdings(holdings_long: pd.DataFrame, price_df: pd.DataFrame) -> pd.DataFrame:
    """【V0.9.5-etf】合併去重、計算「被幾檔 ETF 持有」、merge 收盤價

    holdings_long: long-format (stock_code, stock_name, etf_code, etf_name, weight)
    price_df: stockTool price cache (股票代號, 公司名稱_來源, 股價, data_date, 成交量_張)

    回傳 wide-format:
    - 股票代號、股票名稱、收盤價
    - etf_count：被幾檔 ETF 持有
    - etf_list：字串 "00981A 主動統一台股增長(9.68%)\n00403A 主動統一升級50(18.29%)..."
    - 排序：依 etf_count 由大到小
    """
    if holdings_long.empty:
        return pd.DataFrame()

    # 1. 計算每檔個股的 etf_count + 整合 etf_list 字串
    grouped = holdings_long.groupby("stock_code")
    rows = []
    for stock_code, g in grouped:
        # 該檔個股被多檔 ETF 持有、每檔一個 (etf_code, etf_name, weight)
        etf_entries = []
        for _, r in g.iterrows():
            etf_entries.append(
                f"{r['etf_code']} {r['etf_name']}({r['weight']:.2f}%)"
            )
        rows.append({
            "股票代號": stock_code,
            "股票名稱": g["stock_name"].iloc[0],  # 取第一個當主名
            "etf_count": len(g),
            "etf_list": "\n".join(etf_entries),  # 【V0.9.5-etf-popup-fix】每個 ETF 一行、改用 Text widget 顯示
        })

    result = pd.DataFrame(rows)

    # 2. merge 收盤價
    if price_df is not None and not price_df.empty:
        price_map = price_df[["股票代號", "股價"]].copy()
        price_map["股票代號"] = price_map["股票代號"].astype(str).str.strip()
        price_map["股價"] = pd.to_numeric(price_map["股價"], errors="coerce")
        result = result.merge(
            price_map,
            on="股票代號",
            how="left",
        )
        result = result.rename(columns={"股價": "收盤價"})
    else:
        result["收盤價"] = None

    # 3. 排序：依 etf_count 由大到小
    result = result.sort_values(
        by=["etf_count", "股票代號"],
        ascending=[False, True],
    ).reset_index(drop=True)

    return result


def fetch_csv_requests(session: requests.Session, url: str, cfg: StrategyConfig,
                       encodings=("utf-8-sig", "utf-8")) -> pd.DataFrame:
    r = session.get(url, timeout=cfg.timeout, verify=cfg.verify_ssl)
    r.raise_for_status()
    for enc in encodings:
        try:
            return pd.read_csv(io.BytesIO(r.content), encoding=enc, engine="python", on_bad_lines="skip")
        except Exception:
            continue
    raise RuntimeError(f"讀取失敗：{url}")


# ==========================================================
# Data fetchers
# ==========================================================

def fetch_prices(session: requests.Session, cfg: StrategyConfig) -> pd.DataFrame:
    twse_url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    tpex_url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"

    try:
        twse_response = session.get(twse_url, timeout=cfg.timeout)
        twse_response.raise_for_status()
        twse = pd.DataFrame(twse_response.json())
    except Exception as e:
        print(f"⚠️ 讀取上市股價失敗：{e}")
        twse = pd.DataFrame()

    try:
        tpex_response = session.get(tpex_url, timeout=cfg.timeout)
        tpex_response.raise_for_status()
        tpex = pd.DataFrame(tpex_response.json())
    except Exception as e:
        print(f"⚠️ 讀取上櫃股價失敗：{e}")
        tpex = pd.DataFrame()

    if twse.empty and tpex.empty:
        print("❌ 無法讀取任何股價資料")
        return pd.DataFrame()

    _twse_date_col = find_col(twse.columns, ["Date", "資料日期"])
    _tpex_date_col = find_col(tpex.columns, ["Date", "資料日期"])
    # 【V0.9.5-cache-vol 新增】2026-06-19 William 反映：成交量不會顯示「—」
    # TWSE STOCK_DAY_ALL 有 TradeVolume (股數)
    # TPEx tpex_mainboard_quotes 有 TradingShares (股數)
    # 兩者都是「股」單位、要 /1000 才變「張」
    _twse_vol_col = find_col(twse.columns, ["TradeVolume"])
    _tpex_vol_col = find_col(tpex.columns, ["TradingShares", "TradeVolume"])

    # 【V0.9.5-cache-info 防呆】若某 API 完全失敗（empty df）→ 補上必要欄位
    # 否則後面 twse[["股票代號", ...]] 會 KeyError
    if twse.empty:
        twse = pd.DataFrame(columns=["股票代號", "公司名稱_來源", "股價", "漲跌"])
    if tpex.empty:
        tpex = pd.DataFrame(columns=["股票代號", "公司名稱_來源", "股價", "漲跌"])

    twse = twse.rename(columns={
        find_col(twse.columns, ["證券代號", "Code"]): "股票代號",
        find_col(twse.columns, ["證券名稱", "Name"]): "公司名稱_來源",
        find_col(twse.columns, ["收盤價", "ClosingPrice"]): "股價",
        find_col(twse.columns, ["漲跌價差", "Change"]): "漲跌",
        **({_twse_date_col: "_raw_date"} if _twse_date_col else {}),
        **({_twse_vol_col: "_raw_volume"} if _twse_vol_col else {}),
    })

    tpex = tpex.rename(columns={
        find_col(tpex.columns, ["SecuritiesCompanyCode", "股票代號", "Code"]): "股票代號",
        find_col(tpex.columns, ["CompanyName", "公司名稱", "Name"]): "公司名稱_來源",
        find_col(tpex.columns, ["Close", "收盤", "ClosingPrice"]): "股價",
        find_col(tpex.columns, ["Change", "漲跌"]): "漲跌",
        **({_tpex_date_col: "_raw_date"} if _tpex_date_col else {}),
        **({_tpex_vol_col: "_raw_volume"} if _tpex_vol_col else {}),
    })

    # 【V0.9.5-cache-info 新增】2026-06-19 William 要求：
    #   「篩選結果中增加一個欄位顯示個股資料所參考的最新日期」
    #   從 TWSE/TPEx 的 Date 欄位（民國年格式 "1150618"）轉西元 "2026-06-18"
    #   用來區分「cache 抓取日」vs「個股本身最後交易日」（個股暫停交易時這兩個會不同）
    def _roc_to_ad(s: str) -> str:
        """民國年 YYYMMDD (e.g. "1150618") → 西元 YYYY-MM-DD (e.g. "2026-06-18")
        民國年 = 西元年 - 1911
        """
        try:
            s = str(s).strip()
            if len(s) != 7 or not s.isdigit():
                return ""
            roc_y = int(s[:3])
            m = int(s[3:5])
            d = int(s[5:7])
            return f"{roc_y + 1911:04d}-{m:02d}-{d:02d}"
        except Exception:
            return ""

    # 【V0.9.5-cache-info 防呆】若某 API 沒 date 欄位 → 以空字串代替
    if "_raw_date" not in twse.columns:
        twse["_raw_date"] = ""
    if "_raw_date" not in tpex.columns:
        tpex["_raw_date"] = ""
    # 【V0.9.5-cache-vol 防呆】若某 API 沒 volume 欄位 → 以空代替
    if "_raw_volume" not in twse.columns:
        twse["_raw_volume"] = None
    if "_raw_volume" not in tpex.columns:
        tpex["_raw_volume"] = None

    # 【V0.9.5-cache-vol】股數轉張、只保留「張」（不存原始股數）
    def _vol_to_kilos(s):
        """TradeVolume (e.g. "43019553" 股) → 張 (e.g. 43019.553)"""
        try:
            v = pd.to_numeric(s, errors="coerce")
            if pd.isna(v):
                return None
            return v / 1000.0
        except Exception:
            return None

    price = pd.concat([twse[["股票代號", "公司名稱_來源", "股價", "漲跌", "_raw_date", "_raw_volume"]],
                       tpex[["股票代號", "公司名稱_來源", "股價", "漲跌", "_raw_date", "_raw_volume"]]], ignore_index=True)
    price["股票代號"] = price["股票代號"].astype(str).str.strip()
    price["股價"] = pd.to_numeric(price["股價"], errors="coerce")
    price["漲跌"] = pd.to_numeric(price["漲跌"], errors="coerce")
    price["data_date"] = price["_raw_date"].map(_roc_to_ad)
    price["成交量_張"] = price["_raw_volume"].map(_vol_to_kilos)
    price = price.drop(columns=["_raw_date", "_raw_volume"])
    price = price.drop_duplicates("股票代號").reset_index(drop=True)
    return price


def fetch_revenue_latest(session: requests.Session, cfg: StrategyConfig) -> pd.DataFrame:
    urls = ["https://mopsfin.twse.com.tw/opendata/t187ap05_L.csv",
            "https://mopsfin.twse.com.tw/opendata/t187ap05_O.csv"]
    rev = pd.concat([fetch_csv_requests(session, u, cfg) for u in urls], ignore_index=True)

    code_col = find_col(rev.columns, ["公司代號"])
    ym_col = find_col(rev.columns, ["資料年月"])
    rev_col = find_col(rev.columns, ["營業收入-當月營收", "當月營收"])
    yoy_col = find_col(rev.columns, ["累計營業收入-前期比較增減", "前期比較增減"])
    yoy2_col = find_col(rev.columns, ["營業收入-去年同月增減", "去年同月增減"])

    if code_col is None or ym_col is None or rev_col is None:
        raise RuntimeError(f"營收欄位無法識別：{rev.columns}")

    rename_map = {code_col: "股票代號", ym_col: "年月", rev_col: "當月營收"}
    if yoy_col:
        rename_map[yoy_col] = "累計年增(%)"
    if yoy2_col:
        rename_map[yoy2_col] = "當月年增(%)"

    rev = rev.rename(columns=rename_map)
    rev["股票代號"] = rev["股票代號"].astype(str).str.strip()
    rev["年月"] = pd.to_numeric(rev["年月"], errors="coerce")

    latest_month = rev["年月"].max()
    rev = rev[rev["年月"] == latest_month].copy()

    rev["當月營收(億元)"] = to_num_series(rev["當月營收"]) / 1e8
    if "累計年增(%)" in rev.columns:
        rev["營收YoY(%)"] = to_num_series(rev["累計年增(%)"])
    elif "當月年增(%)" in rev.columns:
        rev["營收YoY(%)"] = to_num_series(rev["當月年增(%)"])
    else:
        rev["營收YoY(%)"] = 0.0

    return rev[["股票代號", "年月", "當月營收(億元)", "營收YoY(%)"]].drop_duplicates("股票代號").reset_index(drop=True)


def fetch_eps_latest(session: requests.Session, cfg: StrategyConfig) -> pd.DataFrame:
    urls = ["https://mopsfin.twse.com.tw/opendata/t187ap14_L.csv",
            "https://mopsfin.twse.com.tw/opendata/t187ap14_O.csv"]

    eps_list = []
    for url in urls:
        try:
            df = fetch_csv_requests(session, url, cfg)
            eps_list.append(df)
        except Exception as e:
            print(f"⚠️ 讀取 {url} 失敗：{e}")

    if not eps_list:
        return pd.DataFrame()

    eps = pd.concat(eps_list, ignore_index=True)

    code_col = find_col(eps.columns, ["公司代號", "證券代號"])
    year_col = find_col(eps.columns, ["年度", "西元年度"])
    q_col = find_col(eps.columns, ["季別", "季度"])
    eps_col = find_col(eps.columns, ["基本每股盈餘(元)", "基本每股盈餘", "每股盈餘"])

    if None in [code_col, year_col, q_col, eps_col]:
        print(f"❌ 找不到必要欄位")
        return pd.DataFrame()

    eps = eps.rename(columns={
        code_col: "股票代號",
        year_col: "年度",
        q_col: "季別",
        eps_col: "EPS"
    })

    eps["股票代號"] = eps["股票代號"].astype(str).str.strip()
    eps["年度"] = pd.to_numeric(eps["年度"], errors="coerce")
    eps["季別"] = pd.to_numeric(eps["季別"], errors="coerce")
    eps["EPS"] = pd.to_numeric(eps["EPS"], errors="coerce")
    eps = eps.dropna(subset=["年度", "季別", "股票代號"])

    if eps.empty:
        return pd.DataFrame()

    # 找「覆蓋率達標」的最新季，避免年初時只取到少數 Q4 公告的公司
    # 邏輯：以最大覆蓋數為基準，要求 >= 80% 才採用
    year_q_counts = eps.groupby(["年度", "季別"]).size().reset_index(name='count')
    max_count = int(year_q_counts['count'].max())
    threshold = max_count * 0.8
    candidates = year_q_counts[year_q_counts['count'] >= threshold]

    if candidates.empty:
        # 全部都不達標（罕見），退而求其次用最大覆蓋那一季
        latest_row = year_q_counts.sort_values('count', ascending=False).iloc[0]
    else:
        latest_row = candidates.sort_values(['年度', '季別'], ascending=False).iloc[0]

    latest_year = int(latest_row['年度'])
    latest_q = int(latest_row['季別'])
    latest_count = int(latest_row['count'])
    coverage_pct = latest_count / max_count * 100

    print(f"📊 EPS 最新季: {latest_year}Q{latest_q}（{latest_count}/{max_count} 筆，覆蓋率 {coverage_pct:.0f}%）")

    # ========== V0.9.4 phase4: 寫入歷史庫 ==========
    # 每天都存最新一季，累積一年後 fetch_eps_latest 就能算 YoY
    try:
        _init_eps_history_db(cfg.eps_history_db)
        rows_to_save = [
            (str(r["股票代號"]).strip(), int(r["年度"]), int(r["季別"]),
             float(r["EPS"]) if pd.notna(r["EPS"]) else None, "twse_csv")
            for _, r in eps.iterrows()
        ]
        saved = _upsert_eps_history(cfg.eps_history_db, rows_to_save)
        stats = _eps_history_stats(cfg.eps_history_db)
        print(f"💾 歷史庫: 本次存 {saved} 筆，總累計 {stats['total']} 筆 / {stats['periods']} 季")
    except Exception as e:
        print(f"⚠️ 寫入歷史庫失敗（不影響本函式結果）：{e}")

    cur = eps[(eps["年度"] == latest_year) & (eps["季別"] == latest_q)][["股票代號", "EPS"]].rename(
        columns={"EPS": "EPS本期"})

    # ========== V0.9.4 phase4: 從歷史庫查去年同期 ==========
    # TWSE CSV 只保留最新一季，必須靠歷史庫才能跨年比對
    prev_year = latest_year - 1
    prev_from_csv = eps[(eps["年度"] == prev_year) & (eps["季別"] == latest_q)][["股票代號", "EPS"]].rename(
        columns={"EPS": "EPS去年"})
    prev_from_db = _query_eps_history(cfg.eps_history_db, prev_year, latest_q)
    if not prev_from_db.empty:
        prev_from_db = prev_from_db.rename(columns={"eps": "EPS去年"})[["stock_id", "EPS去年"]]
        prev_from_db = prev_from_db.rename(columns={"stock_id": "股票代號"})
        # CSV 與 DB 合併，CSV 優先（更新）
        prev = prev_from_csv.merge(prev_from_db, on="股票代號", how="outer", suffixes=("_csv", "_db"))
        prev["EPS去年"] = prev["EPS去年_csv"].combine_first(prev["EPS去年_db"])
        prev = prev[["股票代號", "EPS去年"]]
        print(f"📂 去年同期 {prev_year}Q{latest_q}: CSV {len(prev_from_csv)} 筆 + 歷史庫 {len(prev_from_db)} 筆 → 合併 {len(prev)} 筆")
    else:
        prev = prev_from_csv
        if prev.empty:
            print(f"⚠️ 去年同期 {prev_year}Q{latest_q} 沒有資料（CSV 無、歷史庫也無）→ YoY 將全 NA")

    out = cur.merge(prev, on="股票代號", how="left")

    def safe_yoy(row):
        if pd.isna(row["EPS去年"]) or row["EPS去年"] == 0:
            return pd.NA
        return (row["EPS本期"] - row["EPS去年"]) / abs(row["EPS去年"])

    out["EPSYoY_raw"] = out.apply(safe_yoy, axis=1)
    out["EPSYoY_顯示(%)"] = out["EPSYoY_raw"].apply(
        lambda x: round(x * 100, 2) if pd.notna(x) else pd.NA
    )
    out["EPS季別"] = f"{latest_year}Q{latest_q}"

    print(f"📊 EPS 計算結果: 本期 {len(out)} 筆，有 YoY 資料 {out['EPSYoY_raw'].notna().sum()} 筆")

    return out[["股票代號", "EPS季別", "EPS本期", "EPSYoY_raw", "EPSYoY_顯示(%)"]].drop_duplicates(
        "股票代號").reset_index(drop=True)


# ==========================================================
# TWSE STOCK_DAY fetch
# ==========================================================

def safe_parse_json(r):
    text = (r.text or "").strip()
    if not text or text.startswith("<"):
        return None
    if not (text.startswith("{") or text.startswith("[")):
        return None
    try:
        return r.json()
    except Exception:
        return None


def fetch_twse_stock_day_month(session: requests.Session, cfg: StrategyConfig, stock_no: str, yyyymm01: str) -> pd.DataFrame:
    url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
    params = {"response": "json", "date": yyyymm01, "stockNo": stock_no}

    for attempt in range(1, cfg.twse_retries + 1):
        try:
            r = session.get(url, params=params, timeout=cfg.timeout)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")

            js = safe_parse_json(r)
            if js is None or js.get("stat") != "OK" or "data" not in js:
                return pd.DataFrame()

            fields = js.get("fields", [])
            data = js.get("data", [])
            if not fields or not data:
                return pd.DataFrame()

            dfm = pd.DataFrame(data, columns=fields)

            date_col = find_col(dfm.columns, ["日期"])
            vol_col = find_col(dfm.columns, ["成交股數"])
            close_col = find_col(dfm.columns, ["收盤價"])
            if date_col is None or close_col is None:
                return pd.DataFrame()

            rename_map = {date_col: "Date_roc", close_col: "Close"}
            if vol_col:
                rename_map[vol_col] = "Volume"
            dfm = dfm.rename(columns=rename_map)

            dfm["Date"] = pd.to_datetime(dfm["Date_roc"].apply(roc_to_ad))
            dfm["股票代號"] = str(stock_no).strip()
            dfm["Close"] = to_num_series(dfm["Close"])
            if "Volume" in dfm.columns:
                dfm["Volume"] = to_num_series(dfm["Volume"])
            else:
                dfm["Volume"] = pd.NA

            return dfm[["Date", "股票代號", "Close", "Volume"]].dropna(subset=["Date", "Close"])

        except Exception:
            if attempt == cfg.twse_retries:
                return pd.DataFrame()
            time.sleep(cfg.twse_backoff * attempt)
    return pd.DataFrame()


def fetch_twse_history(session: requests.Session, cfg: StrategyConfig, codes: List[str], logger: GuiLogger, history_months: int) -> pd.DataFrame:
    hist_list = []
    for code in codes:
        try:
            df = get_stock_history(session, cfg, code, logger, history_months)
            if df is not None and not df.empty:
                df["股票代號"] = code
                hist_list.append(df)
        except Exception as e:
            logger.log(f"❌ [{code}] 歷史資料錯誤: {e}")
    if not hist_list:
        return pd.DataFrame()
    return pd.concat(hist_list, ignore_index=True)


def run_tech(cfg: StrategyConfig, session: requests.Session, codes: List[str], logger: GuiLogger, history_months: int) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    hist = fetch_twse_history(session, cfg, codes, logger, history_months)
    if hist.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    parts = []
    for code, g in hist.groupby("股票代號", sort=False):
        g2 = calc_enhanced_tech_indicators(cfg, g)
        g2["股票代號"] = str(code).strip()
        parts.append(g2)

    tech_all = pd.concat(parts, ignore_index=True)
    last_day = tech_all.groupby("股票代號")["Date"].max().reset_index()
    tech_today = tech_all.merge(last_day, on=["股票代號", "Date"], how="inner")
    buy_today = tech_today[tech_today["買點"] == True].copy()

    return tech_all, tech_today, buy_today


# ==========================================================
# Backtest Functions
# ==========================================================

def event_exit_return(cfg: StrategyConfig, path_df: pd.DataFrame, entry_idx: int) -> Tuple[int, float, float, str]:
    entry_price = float(path_df.loc[entry_idx, "Close"])
    last_idx = min(entry_idx + cfg.hold_days, len(path_df) - 1)

    exit_idx = last_idx
    gross_ret = float(path_df.loc[last_idx, "Close"]) / entry_price - 1.0
    reason = "TIME_EXIT"

    for j in range(entry_idx + 1, last_idx + 1):
        px = float(path_df.loc[j, "Close"])
        rsi = float(path_df.loc[j, "RSI"]) if pd.notna(path_df.loc[j, "RSI"]) else None
        ret = px / entry_price - 1.0

        if ret <= cfg.stop_loss:
            exit_idx, gross_ret, reason = j, ret, "STOP_LOSS"
            break
        if ret >= cfg.take_profit:
            exit_idx, gross_ret, reason = j, ret, "TAKE_PROFIT"
            break
        if rsi is not None and rsi >= cfg.exit_rsi:
            exit_idx, gross_ret, reason = j, ret, "RSI_EXIT"
            break

    net_ret = (1.0 + gross_ret) * (1.0 - cfg.roundtrip_cost_pct) - 1.0
    return exit_idx, gross_ret, net_ret, reason


def max_losing_streak(returns):
    max_streak = 0
    cur = 0
    for r in returns:
        if pd.isna(r):
            continue
        if r < 0:
            cur += 1
            max_streak = max(max_streak, cur)
        else:
            cur = 0
    return int(max_streak)


def profit_factor(returns):
    r = pd.Series(returns).dropna()
    wins = r[r > 0].sum()
    losses = r[r < 0].sum()
    if losses == 0:
        return float("inf") if wins > 0 else None
    return float(wins / abs(losses))


def annualize_sharpe(cfg: StrategyConfig, daily_returns):
    r = pd.Series(daily_returns).dropna()
    if len(r) < 10:
        return None
    rf_d = cfg.risk_free_annual / cfg.trading_days
    mu = (r.mean() - rf_d) * cfg.trading_days
    sigma = r.std(ddof=1) * (cfg.trading_days ** 0.5)
    if sigma == 0:
        return None
    return float(mu / sigma)


def annualize_sortino(cfg: StrategyConfig, daily_returns):
    r = pd.Series(daily_returns).dropna()
    if len(r) < 10:
        return None
    mar_d = cfg.mar_annual / cfg.trading_days
    excess = r - mar_d
    downside = excess.copy()
    downside[downside > 0] = 0
    downside_dev = downside.std(ddof=1) * (cfg.trading_days ** 0.5)
    mu = excess.mean() * cfg.trading_days
    if downside_dev == 0:
        return None
    return float(mu / downside_dev)


def signal_level_backtest_event(cfg: StrategyConfig, tech_all: pd.DataFrame) -> pd.DataFrame:
    if tech_all is None or tech_all.empty:
        return pd.DataFrame()

    returns_net = []
    for code, g in tech_all.groupby("股票代號", sort=False):
        g = g.sort_values("Date").reset_index(drop=True)
        sig_idx = g.index[g["買點"] == True].tolist()
        if not sig_idx:
            continue
        for idx in sig_idx:
            _, _, net_ret, _ = event_exit_return(cfg, g, idx)
            returns_net.append(net_ret)

    rnet = pd.Series(returns_net).dropna()
    if rnet.empty:
        return pd.DataFrame()

    streak = max_losing_streak(rnet.values)
    pf = profit_factor(rnet.values)

    return pd.DataFrame([{
        "訊號數": int(len(rnet)),
        "事件型平均報酬_扣成本(%)": round(rnet.mean() * 100, 2),
        "事件型勝率_扣成本(%)": round((rnet > 0).mean() * 100, 2),
        "事件型中位數_扣成本(%)": round(rnet.median() * 100, 2),
        "MaxLosingStreak": int(streak),
        "ProfitFactor": round(pf, 3) if pf is not None and pf != float("inf") else pf
    }])


def build_gate_map(cfg: StrategyConfig, df_sel: pd.DataFrame) -> Dict[str, bool]:
    code = df_sel["股票代號"].astype(str).str.strip()
    gate = pd.Series([True] * len(code), index=code)
    return dict(zip(code, gate))


def portfolio_backtest_topk_event(cfg: StrategyConfig, tech_all: pd.DataFrame, score_map: dict, gate_map: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if tech_all is None or tech_all.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    df = tech_all[["Date", "股票代號", "Close", "買點", "RSI"]].copy()
    df = df.dropna(subset=["Date", "Close"])
    df["股票代號"] = df["股票代號"].astype(str).str.strip()

    score_map = {str(k).strip(): v for k, v in score_map.items()}
    df["Score"] = df["股票代號"].map(score_map).fillna(-1e18)

    by_code = {c: g.sort_values("Date").reset_index(drop=True) for c, g in df.groupby("股票代號")}
    all_dates = sorted(df["Date"].unique())

    cash = 1.0
    positions = {}
    equity_rows = []
    trade_rows = []

    entry_cost = cfg.roundtrip_cost_pct / 2
    exit_cost = cfg.roundtrip_cost_pct / 2

    for d in all_dates:
        d = pd.to_datetime(d)

        to_close = []
        for code, pos in list(positions.items()):
            g = by_code.get(code)
            if g is None:
                continue
            idx_list = g.index[g["Date"] == d].tolist()
            if not idx_list:
                continue

            cur_idx = idx_list[0]
            entry_idx = pos["entry_idx"]
            entry_price = pos["entry_price"]
            max_idx = min(entry_idx + cfg.hold_days, len(g) - 1)
            if cur_idx > max_idx:
                cur_idx = max_idx

            px = float(g.loc[cur_idx, "Close"])
            rsi = float(g.loc[cur_idx, "RSI"]) if pd.notna(g.loc[cur_idx, "RSI"]) else None
            ret = px / entry_price - 1.0

            reason = None
            if ret <= cfg.stop_loss:
                reason = "STOP_LOSS"
            elif ret >= cfg.take_profit:
                reason = "TAKE_PROFIT"
            elif (rsi is not None) and (rsi >= cfg.exit_rsi):
                reason = "RSI_EXIT"
            elif cur_idx == max_idx:
                reason = "TIME_EXIT"

            if reason is not None:
                to_close.append((code, px, ret, reason))

        for code, px, ret, reason in to_close:
            pos = positions.pop(code)
            shares = pos["shares"]
            proceeds = shares * px * (1.0 - exit_cost)
            cash += proceeds

            net_ret = (1.0 + ret) * (1.0 - cfg.roundtrip_cost_pct) - 1.0
            trade_rows.append({
                "股票代號": code,
                "進場日": pos["entry_date"].date().isoformat(),
                "進場價": pos["entry_price"],
                "出場日": d.date().isoformat(),
                "出場價": px,
                "出場原因": reason,
                "報酬(%)": round(ret * 100, 2),
                "報酬_扣成本(%)": round(net_ret * 100, 2)
            })

        if len(positions) == 0:
            cand = df[(df["Date"] == d) & (df["買點"] == True)].copy()
            if cfg.use_gate:
                cand["GateOK"] = cand["股票代號"].map(gate_map).fillna(False)
                cand = cand[cand["GateOK"] == True].copy()

            if not cand.empty:
                cand = cand.sort_values("Score", ascending=False).head(cfg.topk)
                k = len(cand)
                if k > 0:
                    alloc_each = cash / k
                    cash = 0.0
                    for _, row in cand.iterrows():
                        code = str(row["股票代號"]).strip()
                        g = by_code.get(code)
                        if g is None:
                            cash += alloc_each
                            continue
                        idx_list = g.index[g["Date"] == d].tolist()
                        if not idx_list:
                            cash += alloc_each
                            continue
                        entry_idx = idx_list[0]
                        entry_price = float(g.loc[entry_idx, "Close"])
                        alloc_after_cost = alloc_each * (1.0 - entry_cost)
                        shares = alloc_after_cost / entry_price if entry_price > 0 else 0.0
                        positions[code] = {
                            "shares": shares,
                            "entry_price": entry_price,
                            "entry_date": d,
                            "entry_idx": entry_idx
                        }

        equity = cash
        for code, pos in positions.items():
            g = by_code.get(code)
            if g is None:
                continue
            cur = g[g["Date"] == d]
            px = float(cur.iloc[0]["Close"]) if not cur.empty else pos["entry_price"]
            equity += pos["shares"] * px
        equity_rows.append({"Date": d, "Equity": equity})

    eq = pd.DataFrame(equity_rows).drop_duplicates("Date").sort_values("Date").reset_index(drop=True)
    trades = pd.DataFrame(trade_rows)

    eq["Ret"] = eq["Equity"].pct_change()
    eq["Peak"] = eq["Equity"].cummax()
    eq["Drawdown"] = eq["Equity"] / eq["Peak"] - 1
    mdd = eq["Drawdown"].min()

    sharpe = annualize_sharpe(cfg, eq["Ret"])
    sortino = annualize_sortino(cfg, eq["Ret"])

    if len(eq) >= 2:
        days = (pd.to_datetime(eq["Date"].iloc[-1]) - pd.to_datetime(eq["Date"].iloc[0])).days
        years = days / 365.25 if days > 0 else None
        cagr = (eq["Equity"].iloc[-1] ** (1 / years) - 1) if years else None
    else:
        cagr = None

    if not trades.empty and "報酬_扣成本(%)" in trades.columns:
        tr = trades["報酬_扣成本(%)"].astype(float) / 100.0
        pf = profit_factor(tr.values)
        streak = max_losing_streak(tr.values)
    else:
        pf = None
        streak = 0

    kpi = pd.DataFrame([{
        "CAGR(%)": round(cagr * 100, 2) if cagr is not None else None,
        "MDD(%)": round(mdd * 100, 2) if mdd is not None else None,
        "Sharpe": round(sharpe, 3) if sharpe is not None else None,
        "Sortino": round(sortino, 3) if sortino is not None else None,
        "Trades": int(len(trades)),
        "MaxLosingStreak": int(streak),
        "ProfitFactor": round(pf, 3) if pf is not None and pf != float("inf") else pf
    }])

    if not trades.empty and "出場原因" in trades.columns:
        reason_counts = trades["出場原因"].value_counts()
        reason_pct = trades["出場原因"].value_counts(normalize=True) * 100
        reason_stats = pd.DataFrame({
            "次數": reason_counts,
            "比例(%)": reason_pct.round(2)
        }).reset_index()
        reason_stats = reason_stats.rename(columns={"index": "出場原因"})
    else:
        reason_stats = pd.DataFrame(columns=["出場原因", "次數", "比例(%)"])

    return eq, trades, kpi, reason_stats


def performance_by_year(trades_df):
    if trades_df is None or trades_df.empty:
        return pd.DataFrame()
    df = trades_df.copy()
    date_col = find_col(df.columns, ["entry", "進場", "買進", "date"])
    if date_col is None:
        raise ValueError("找不到進場日期欄位")
    df["year"] = pd.to_datetime(df[date_col]).dt.year
    out = []
    for y, g in df.groupby("year"):
        ret_col = find_col(g.columns, ["return", "報酬", "損益", "ret", "%"])
        if ret_col is None:
            raise ValueError("找不到報酬欄位")
        returns = g[ret_col]
        out.append({
            "year": y,
            "trades": len(g),
            "win_rate(%)": round((returns > 0).mean() * 100, 2),
            "avg_return(%)": round(returns.mean() * 100, 2),
            "profit_factor": round(profit_factor(returns), 2) if profit_factor(returns) else None
        })
    return pd.DataFrame(out).sort_values("year")
# ==========================================================
# Walk-forward Analysis
# ==========================================================

def run_walk_forward(cfg: StrategyConfig, logger: GuiLogger, s: requests.Session):
    logger.log("\n" + "=" * 60)
    logger.log("📊 開始 Walk-forward 分析")
    logger.log("=" * 60)

    end_date = datetime.now()
    start_date = end_date - pd.DateOffset(years=cfg.wf_train_years + cfg.wf_test_years * 4)

    windows = []
    current_start = start_date
    window_count = 0

    while current_start + pd.DateOffset(years=cfg.wf_train_years + cfg.wf_test_years) <= end_date:
        train_end = current_start + pd.DateOffset(years=cfg.wf_train_years)
        test_end = train_end + pd.DateOffset(years=cfg.wf_test_years)
        windows.append({
            "train_start": current_start,
            "train_end": train_end,
            "test_start": train_end,
            "test_end": test_end,
            "train_start_str": current_start.strftime("%Y-%m-%d"),
            "train_end_str": train_end.strftime("%Y-%m-%d"),
            "test_start_str": train_end.strftime("%Y-%m-%d"),
            "test_end_str": test_end.strftime("%Y-%m-%d")
        })
        current_start += pd.DateOffset(years=cfg.wf_step_years)
        window_count += 1
        if window_count > 10:
            break

    if len(windows) < 2:
        logger.log("⚠️ 歷史資料不足，無法執行 Walk-forward 分析")
        return pd.DataFrame()

    results = []
    for i, window in enumerate(windows):
        logger.log(f"\n📊 Window {i + 1}/{len(windows)}")
        logger.log(f"   訓練期: {window['train_start_str']} ~ {window['train_end_str']}")
        logger.log(f"   測試期: {window['test_start_str']} ~ {window['test_end_str']}")

        try:
            tech_codes = get_codes_for_period(s, cfg, window['train_start'], window['train_end'], logger)
            test_result = quick_backtest_for_period(cfg, s, tech_codes, window['test_start'], window['test_end'], logger)

            results.append({
                "window": i + 1,
                "train_period": f"{window['train_start'].year}-{window['train_end'].year}",
                "test_period": f"{window['test_start'].year}-{window['test_end'].year}",
                "test_cagr": test_result.get('cagr', 0),
                "test_sharpe": test_result.get('sharpe', 0),
                "test_mdd": test_result.get('mdd', 0),
                "test_trades": test_result.get('trades', 0)
            })
        except Exception as e:
            logger.log(f"   ❌ Window {i + 1} 失敗: {e}")
            results.append({
                "window": i + 1,
                "train_period": f"{window['train_start'].year}-{window['train_end'].year}",
                "test_period": f"{window['test_start'].year}-{window['test_end'].year}",
                "test_cagr": 0,
                "test_sharpe": 0,
                "test_mdd": 0,
                "test_trades": 0
            })

    df_results = pd.DataFrame(results)

    logger.log("\n" + "=" * 60)
    logger.log("📈 Walk-forward 分析結果")
    logger.log("=" * 60)
    logger.log(df_results[['test_period', 'test_cagr', 'test_sharpe', 'test_mdd', 'test_trades']].to_string(index=False))

    if len(df_results) > 1:
        cagr_std = df_results['test_cagr'].std()
        sharpe_std = df_results['test_sharpe'].std()

        logger.log(f"\n📊 穩定性評估:")
        logger.log(f"   CAGR 標準差: {cagr_std:.2f}%")
        logger.log(f"   CAGR 平均值: {df_results['test_cagr'].mean():.2f}%")
        logger.log(f"   Sharpe 標準差: {sharpe_std:.3f}")
        logger.log(f"   Sharpe 平均值: {df_results['test_sharpe'].mean():.3f}")

        if cagr_std < 10:
            logger.log(f"   ✅ 策略穩定（CAGR 波動 < 10%）")
        else:
            logger.log(f"   ⚠️ 策略不穩定（CAGR 波動 > 10%）")

    return df_results


def get_codes_for_period(s, cfg, start_date, end_date, logger):
    from_cache = get_or_fetch("price", lambda: fetch_prices(s, cfg), logger)
    codes = from_cache["股票代號"].dropna().astype(str).str.strip().tolist()
    return codes[:cfg.top_n_for_tech]


def quick_backtest_for_period(cfg, s, codes, start_date, end_date, logger):
    try:
        hist = fetch_twse_history(s, cfg, codes, logger, cfg.history_months)
        if hist.empty:
            return {'cagr': 0, 'sharpe': 0, 'mdd': 0, 'trades': 0}

        hist = hist[(hist["Date"] >= start_date) & (hist["Date"] <= end_date)]
        if hist.empty:
            return {'cagr': 0, 'sharpe': 0, 'mdd': 0, 'trades': 0}

        parts = []
        for code, g in hist.groupby("股票代號", sort=False):
            g2 = calc_enhanced_tech_indicators(cfg, g)
            g2["股票代號"] = str(code).strip()
            parts.append(g2)
        tech_all = pd.concat(parts, ignore_index=True)

        score_map = {}
        eq, trades, kpi, _ = portfolio_backtest_topk_event(cfg, tech_all, score_map, {})

        if not eq.empty and len(eq) > 1:
            start_val = eq.iloc[0]["Equity"]
            end_val = eq.iloc[-1]["Equity"]
            days = (eq.iloc[-1]["Date"] - eq.iloc[0]["Date"]).days
            years = days / 365.25
            cagr = (end_val / start_val) ** (1 / years) - 1 if years > 0 else 0

            sharpe_val = kpi.iloc[0]["Sharpe"] if not kpi.empty and kpi.iloc[0]["Sharpe"] else 0
            mdd_val = kpi.iloc[0]["MDD(%)"] if not kpi.empty and kpi.iloc[0]["MDD(%)"] else 0
            trades_val = kpi.iloc[0]["Trades"] if not kpi.empty else 0

            return {'cagr': cagr * 100, 'sharpe': sharpe_val, 'mdd': mdd_val, 'trades': trades_val}

        return {'cagr': 0, 'sharpe': 0, 'mdd': 0, 'trades': 0}
    except Exception as e:
        return {'cagr': 0, 'sharpe': 0, 'mdd': 0, 'trades': 0}


# ==========================================================
# Excel 美化函數
# ==========================================================

def autosize_columns(ws, min_w=10, max_w=44):
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.value is None:
                continue
            max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = max(min_w, min(max_w, max_len + 2))


def style_header(ws, header_row):
    fill = PatternFill("solid", fgColor="1F4E79")
    font = Font(color="FFFFFF", bold=True)
    for cell in ws[header_row]:
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(horizontal="center", vertical="center")


def write_explanation(ws, lines, start_row=1, start_col=1):
    title_font = Font(bold=True, size=12)
    normal_font = Font(size=11)
    for i, line in enumerate(lines):
        c = ws.cell(row=start_row + i, column=start_col, value=line)
        c.font = title_font if i == 0 else normal_font
        c.alignment = Alignment(wrap_text=True, vertical="top")


def highlight_true(ws, header_row, col_name):
    header_cells = list(ws[header_row])
    idx = None
    for i, cell in enumerate(header_cells, 1):
        if cell.value == col_name:
            idx = i
            break
    if idx is None:
        return
    col_letter = get_column_letter(idx)
    rng = f"{col_letter}{header_row + 1}:{col_letter}{ws.max_row}"
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=["TRUE"],
                                                  fill=PatternFill("solid", fgColor="FFF2CC")))


# ==========================================================
# Pipeline (核心執行流程)
# ==========================================================

def run_pipeline(cfg: StrategyConfig, logger: GuiLogger):
    s = build_session()

    logger.log("=" * 60)
    logger.log(f"🚀 StockTool {VERSION} 開始執行")
    logger.log(f"   評分系統: {'多因子評分' if cfg.use_enhanced_score else '簡易評分'}")
    logger.log(f"   技術指標: 強化版 (MTF={cfg.use_mtf_confirmation}, 背離={cfg.use_divergence_detection})")
    logger.log("=" * 60)

    logger.log("1) 取得股價資料...")
    price = get_or_fetch("price", lambda: fetch_prices(s, cfg), logger)
    price = ensure_str_column(price, "股票代號")

    logger.log("2) 取得月營收...")
    revenue = get_or_fetch("revenue", lambda: fetch_revenue_latest(s, cfg), logger)
    revenue = ensure_str_column(revenue, "股票代號")

    logger.log("3) 取得 EPS...")
    eps_data = get_or_fetch("eps", lambda: fetch_eps_latest(s, cfg), logger)
    eps_data = ensure_str_column(eps_data, "股票代號")

    logger.log("4) 合併基本面資料...")
    df_sel = price.merge(revenue, on="股票代號", how="left")
    df_sel = df_sel.merge(eps_data, on="股票代號", how="left")
    df_sel = ensure_str_column(df_sel, "股票代號")

    if "EPSYoY_顯示(%)" in eps_data.columns:
        df_sel["EPSYoY_顯示(%)"] = df_sel["EPSYoY_顯示(%)"]
    else:
        if "EPSYoY_raw" in df_sel.columns:
            df_sel["EPSYoY_顯示(%)"] = (df_sel["EPSYoY_raw"] * 100).fillna(0).round(2)
        else:
            df_sel["EPSYoY_顯示(%)"] = 0

    df_sel["PE"] = df_sel["股價"] / df_sel["EPS本期"]
    df_sel["殖利率(估)"] = (df_sel["EPS本期"] * 0.7) / df_sel["股價"]

    # ==========================================================
    # v0.9.2：Top10 基本面回測模式
    # ==========================================================

    if cfg.use_top10_backtest:
        logger.log("=" * 60)
        logger.log("📊 啟動 Top10 基本面回測模式")
        logger.log("   ※ 直接使用 Score 最高的 10 檔股票建倉")
        logger.log("   ※ 不經過技術買點過濾（買點強制設為 True）")
        logger.log("=" * 60)

        # ========== DEBUG: 基本面資料診斷 ==========
        print("\n" + "=" * 60)
        print("🔍 [DEBUG] 基本面資料合併後診斷")
        print("=" * 60)

        print(f"\n📊 df_sel 總筆數: {len(df_sel)}")
        print(f"📊 有營收YoY的筆數: {df_sel['營收YoY(%)'].notna().sum()}")
        print(f"📊 有EPS本期(非ETF)的筆數: {df_sel['EPS本期'].notna().sum()}")
        print(f"📊 有EPSYoY_raw的筆數: {df_sel['EPSYoY_raw'].notna().sum()}")

        # 顯示前5筆有EPS資料的股票
        eps_notna = df_sel[df_sel['EPS本期'].notna()].head(5)
        if len(eps_notna) > 0:
            print(f"\n📋 有EPS資料的前5檔股票:")
            for idx, row in eps_notna.iterrows():
                print(
                    f"   {row['股票代號']} {row.get('公司名稱_來源', '')} | EPS: {row.get('EPS本期', 'N/A')} | EPS YoY: {row.get('EPSYoY_顯示(%)', 'N/A')}%")
        else:
            print(f"\n⚠️ 沒有任何股票有 EPS 資料！")
            print(f"   請檢查 fetch_eps_latest 函數是否正常運作。")

        print("\n" + "=" * 60 + "\n")
        # ========== DEBUG 結束 ==========



        if cfg.use_enhanced_score:
            df_sel = calculate_multi_factor_score(df_sel, cfg)
            logger.log(f"   因子權重: 動能1M={cfg.factor_weight_mom1:.0%} 動能3M={cfg.factor_weight_mom3:.0%} 動能6M={cfg.factor_weight_mom6:.0%} 營收={cfg.factor_weight_rev:.0%} EPS={cfg.factor_weight_eps:.0%}")
        else:
            df_sel = calculate_simple_score(df_sel, cfg)

        df_sel = df_sel.sort_values("Score", ascending=False).reset_index(drop=True)

        top10_codes = df_sel.head(10)["股票代號"].dropna().astype(str).str.strip().tolist()
        logger.log(f"   Top10 股票: {top10_codes}")

        tech_all_top10, tech_today_top10, buy_today_top10 = run_tech(cfg, s, top10_codes, logger, cfg.history_months)

        if tech_all_top10.empty:
            logger.log("❌ 無法獲取 Top10 股票的歷史資料")
            return

        tech_all_top10["買點"] = True
        tech_all_top10["買點_基礎"] = True
        tech_all_top10["確認層級"] = 3

        score_map = df_sel.set_index("股票代號")["Score"].to_dict()
        gate_map = build_gate_map(cfg, df_sel)
        eq_top10, trades_top10, pf_kpi_top10, reason_stats_top10 = portfolio_backtest_topk_event(
            cfg, tech_all_top10, score_map, gate_map
        )
        sig_summary_top10 = signal_level_backtest_event(cfg, tech_all_top10)

        logger.log("\n" + "=" * 60)
        logger.log("📊 Top10 基本面回測結果")
        logger.log("=" * 60)
        logger.log("✅ Signal-level KPI:")
        logger.log(sig_summary_top10.to_string(index=False) if not sig_summary_top10.empty else "(無訊號)")
        logger.log(f"\n✅ Portfolio-level KPI (Top{cfg.topk} 等權):")
        logger.log(pf_kpi_top10.to_string(index=False) if not pf_kpi_top10.empty else "(無投組資料)")

        out_file = f"{cfg.out_file_prefix}_Top10Backtest_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        startrow = 6
        name_map = price[["股票代號", "公司名稱_來源"]].drop_duplicates("股票代號")

        with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
            format_for_output(df_sel.head(10), sort_by_code=True).to_excel(writer, index=False, sheet_name="Top10_股票列表")
            if not eq_top10.empty:
                eq_top10.to_excel(writer, index=False, sheet_name="投組回測", startrow=startrow)
            if not trades_top10.empty:
                trades_out = trades_top10.merge(name_map, on="股票代號", how="left")
                trades_out = format_for_output(trades_out, sort_by_code=True)
                # ✅ 按進場日排序
                if "進場日" in trades_out.columns:
                    trades_out = trades_out.sort_values("進場日")
                trades_out.to_excel(writer, index=False, sheet_name="交易明細", startrow=0)
            if not pf_kpi_top10.empty:
                pf_kpi_top10.to_excel(writer, index=False, sheet_name="績效摘要", startrow=startrow)
            if not reason_stats_top10.empty:
                reason_stats_top10.to_excel(writer, index=False, sheet_name="出場原因統計")

        logger.log(f"✅ Top10 回測完成 → {out_file}")
        return

    # ==========================================================
    # 正常回測模式
    # ==========================================================

    if cfg.use_enhanced_score:
        df_sel_temp = calculate_multi_factor_score(df_sel, cfg)
        logger.log(f"   因子權重: 動能1M={cfg.factor_weight_mom1:.0%} 動能3M={cfg.factor_weight_mom3:.0%} 動能6M={cfg.factor_weight_mom6:.0%} 營收={cfg.factor_weight_rev:.0%} EPS={cfg.factor_weight_eps:.0%}")
    else:
        df_sel_temp = calculate_simple_score(df_sel, cfg)
        w_rev = cfg.simple_score_weight_rev
        w_eps = cfg.simple_score_weight_eps
        w_div = cfg.simple_score_weight_div
        w_pe = cfg.simple_score_weight_pe
        logger.log(f"   權重: 營收{w_rev:.0f}% / EPS{w_eps:.0f}% / 殖利率{w_div:.0f}% / PE{w_pe:.0f}%")

    df_sel_temp = df_sel_temp.sort_values("Score", ascending=False).reset_index(drop=True)

    logger.log(f"5) 抓取前 {cfg.top_n_for_tech} 檔股票的歷史日K...")

    if cfg.use_excel_stock_list:
        logger.log("📂 使用 Excel 指定股票清單")
        try:
            tech_codes = load_stock_list_from_excel(cfg.excel_stock_file)
        except Exception as e:
            logger.log(f"❌ Excel 選股失敗：{e}")
            return

        # ✅ v0.9.4 Excel 清單強制買點模式
        if cfg.excel_force_buy:
            logger.log("   📊 啟用 Excel 清單強制買點模式")
            logger.log("   ※ 不經過技術買點過濾（買點強制設為 True）")
    else:
        tech_codes = df_sel_temp.head(cfg.top_n_for_tech)["股票代號"].dropna().astype(str).str.strip().tolist()
    logger.log(f"   選股檔數: {len(tech_codes)}，每檔 {cfg.history_months} 個月歷史資料")

    #tech_all, tech_today, buy_today = run_tech(cfg, s, tech_codes, logger, cfg.history_months)
    tech_all, tech_today, buy_today = run_tech(cfg, s, tech_codes, logger, cfg.history_months)

    # ✅ v0.9.4 Excel 清單強制買點模式：將買點強制設為 True
    if cfg.use_excel_stock_list and cfg.excel_force_buy:
        if not tech_all.empty:
            tech_all["買點"] = True
            tech_all["買點_基礎"] = True
            tech_all["確認層級"] = 3
            logger.log("   🔧 已強制將所有日期設為買點")

    if tech_all.empty:
        logger.log("❌ 無歷史資料，請檢查網路連線")
        return

    if cfg.use_enhanced_score:
        df_sel = calculate_multi_factor_score(df_sel, cfg)
    else:
        df_sel = calculate_simple_score(df_sel, cfg)

    df_sel = df_sel.sort_values("Score", ascending=False).reset_index(drop=True)

    strong_sel = df_sel[
        (df_sel["營收YoY(%)"] > cfg.strong_revenue_yoy) &
        (df_sel["EPS本期"] > 0) &
        (df_sel["PE"] < cfg.strong_pe_max) &
        (df_sel["股價"] > cfg.strong_price_min)
    ].copy()
    top10_sel = df_sel.head(10).copy()

    logger.log("6) 執行回測...")
    gate_map = build_gate_map(cfg, df_sel)
    score_map = df_sel.set_index("股票代號")["Score"].to_dict()
    eq, trades, pf_kpi, reason_stats = portfolio_backtest_topk_event(cfg, tech_all, score_map, gate_map)
    sig_summary = signal_level_backtest_event(cfg, tech_all)

    try:
        yearly_perf = performance_by_year(trades)
        logger.log("✅ 年度績效分析：")
        if not yearly_perf.empty:
            logger.log(yearly_perf.to_string(index=False))
    except Exception as e:
        logger.log(f"⚠️ 年度績效分析失敗：{e}")
        yearly_perf = pd.DataFrame()

    wf_results = pd.DataFrame()
    if cfg.wf_enabled:
        logger.log("7) 執行 Walk-forward 分析...")
        wf_results = run_walk_forward(cfg, logger, s)

    name_map = price[["股票代號", "公司名稱_來源"]].drop_duplicates("股票代號")
    name_map = ensure_str_column(name_map, "股票代號")
    eps_disp_map = df_sel.set_index("股票代號")["EPSYoY_顯示(%)"].to_dict()

    df_out_all = format_for_output(df_sel, sort_by_code=True)
    strong_out = format_for_output(strong_sel, sort_by_code=True)
    top10_out = format_for_output(top10_sel, sort_by_code=True)

    if tech_today is None or tech_today.empty:
        tech_today_out = pd.DataFrame()
    else:
        tech_today = ensure_str_column(tech_today, "股票代號")
        tech_today_out = tech_today.merge(name_map, on="股票代號", how="left")
        tech_today_out["EPSYoY_顯示(%)"] = tech_today_out["股票代號"].map(eps_disp_map)
        tech_today_out = format_for_output(tech_today_out, sort_by_code=True)

    if buy_today is None or buy_today.empty:
        buy_today_out = pd.DataFrame([{
            "說明": "今日無符合買點條件的股票",
            "可能原因": "1. 市場震盪或下跌 2. 買點條件設定較嚴格 3. 選股檔數不足",
            "建議調整參數": "放寬 RSI_OVERSOLD / 關閉成交量過濾 / 關閉趨勢過濾 / 增加選股檔數",
            "當前 RSI_OVERSOLD": cfg.rsi_oversold,
            "當前 Volume Filter": cfg.require_volume_filter,
            "當前 Trend Filter": cfg.require_trend_filter,
            "當前 MTF Filter": cfg.use_mtf_confirmation,
            "選股檔數 (TopN)": cfg.top_n_for_tech,
            "歷史月數": cfg.history_months
        }])
        logger.log("   📭 今日無買點訊號（已建立診斷說明 Sheet）")
    else:
        buy_today = ensure_str_column(buy_today, "股票代號")
        buy_today_out = buy_today.merge(name_map, on="股票代號", how="left")
        buy_today_out["EPSYoY_顯示(%)"] = buy_today_out["股票代號"].map(eps_disp_map)
        buy_today_out = format_for_output(buy_today_out, sort_by_code=True)
        logger.log(f"   📈 今日買點數量: {len(buy_today_out)} 檔")
    # ==========================================================
    # ✅ v0.9.3 今日出場清單（計算當日需要賣出的股票）
    # ==========================================================

    exit_today_list = []

    if trades is not None and not trades.empty:
        # 獲取最新交易日
        latest_date = tech_today["Date"].max() if not tech_today.empty else datetime.now()

        # 獲取所有有進場但尚未出場的股票
        for code in tech_codes:
            code_trades = trades[trades["股票代號"] == code]
            if code_trades.empty:
                continue

            # 找出最新的出場日
            if "出場日" in code_trades.columns:
                last_exit = code_trades["出場日"].max()
                # 如果最後出場日 < 最新交易日，且還有進場記錄，表示仍在持有中
                if pd.to_datetime(last_exit) < pd.to_datetime(latest_date):
                    # 找出該股票最新的進場記錄（在最後出場日之後）
                    code_entries = code_trades[code_trades["出場日"] <= last_exit] if last_exit else code_trades
                    if not code_entries.empty:
                        latest_entry = code_entries.sort_values("進場日", ascending=False).iloc[0]
                        entry_price = latest_entry["進場價"]
                        entry_date = latest_entry["進場日"]

                        # 獲取當前價格
                        code_tech = tech_today[tech_today["股票代號"] == code]
                        if not code_tech.empty:
                            current_price = code_tech.iloc[0]["Close"]
                            ret = (current_price - entry_price) / entry_price
                            rsi = code_tech.iloc[0]["RSI"] if "RSI" in code_tech.columns else None
                            hold_days = (pd.to_datetime(latest_date) - pd.to_datetime(entry_date)).days

                            # 檢查出場條件
                            exit_reason = None
                            if ret <= cfg.stop_loss:
                                exit_reason = "STOP_LOSS"
                            elif ret >= cfg.take_profit:
                                exit_reason = "TAKE_PROFIT"
                            elif rsi is not None and rsi >= cfg.exit_rsi:
                                exit_reason = "RSI_EXIT"
                            elif hold_days >= cfg.hold_days:
                                exit_reason = "TIME_EXIT"

                            if exit_reason is not None:
                                # ✅ 獲取公司名稱
                                company_name = name_map[name_map["股票代號"] == code]["公司名稱_來源"].values
                                company_name_str = company_name[0] if len(company_name) > 0 else ""

                                exit_today_list.append({
                                    "股票代號": code,
                                    "公司名稱": company_name_str,
                                    "進場日": entry_date,
                                    "進場價": round(entry_price, 2),
                                    "今日收盤價": round(current_price, 2),
                                    "累計報酬(%)": round(ret * 100, 2),
                                    "持有天數": hold_days,
                                    "出場原因": exit_reason,
                                    "當前 RSI": round(rsi, 1) if rsi else None
                                })

    exit_today_df = pd.DataFrame(exit_today_list)

    if exit_today_df.empty:
        exit_today_df = pd.DataFrame([{
            "說明": "今日無需要出場的股票",
            "可能原因": "1. 無持股 2. 所有持倉均未觸發出場條件",
            "當前停損門檻": f"{cfg.stop_loss * 100:.1f}%",
            "當前停利門檻": f"{cfg.take_profit * 100:.1f}%",
            "當前 RSI 出場門檻": cfg.exit_rsi,
            "最大持有天數": cfg.hold_days
        }])
        logger.log("   📭 今日無出場訊號（已建立診斷說明 Sheet）")
    else:
        logger.log(f"   📤 今日出場數量: {len(exit_today_df)} 檔")

    if trades is None or trades.empty:
        trades_out = pd.DataFrame(columns=["股票代號", "公司名稱_來源", "進場日", "進場價", "出場日", "出場價", "出場原因", "報酬(%)", "報酬_扣成本(%)"])
    else:
        trades = ensure_str_column(trades, "股票代號")
        trades_out = trades.merge(name_map, on="股票代號", how="left")
        trades_out = format_for_output(trades_out, sort_by_code=True)
        if "進場日" in trades_out.columns:
            trades_out = trades_out.sort_values("進場日")

    out_file = f"{cfg.out_file_prefix}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    startrow = 6


    logger.log(f"8) 輸出 Excel: {out_file}")

    with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
        df_out_all.to_excel(writer, index=False, sheet_name="全市場_基本面")
        strong_out.to_excel(writer, index=False, sheet_name="強勢股_基本面")
        top10_out.to_excel(writer, index=False, sheet_name="Top10_基本面")

        if not tech_today_out.empty:
            tech_today_out.to_excel(writer, index=False, sheet_name="技術分析_今日", startrow=startrow)

        buy_today_out.to_excel(writer, index=False, sheet_name="技術買點_今日", startrow=startrow)
        # ✅ v0.9.3 今日出場清單
        exit_today_df.to_excel(writer, index=False, sheet_name="今日出場清單", startrow=startrow)

        if not reason_stats.empty:
            reason_stats.to_excel(writer, index=False, sheet_name="出場原因統計")

        summary_sheet = pd.concat([pd.DataFrame([{"區塊": "Signal-level"}]),
                                   sig_summary,
                                   pd.DataFrame([{"區塊": f"Portfolio-level (Top{cfg.topk})"}]),
                                   pf_kpi], ignore_index=True)
        summary_sheet.to_excel(writer, index=False, sheet_name="回測摘要", startrow=startrow)

        if not eq.empty:
            eq.to_excel(writer, index=False, sheet_name="投組回測_TopK等權", startrow=startrow)
        if not trades_out.empty:
            trades_out.to_excel(writer, index=False, sheet_name="投組交易明細", startrow=0)
        if not yearly_perf.empty:
            yearly_perf.to_excel(writer, sheet_name="年度績效", index=False)
        if not wf_results.empty:
            wf_results.to_excel(writer, sheet_name="WalkForward分析", index=False)
        # ==========================================================
        # Excel 美化（技術買點_今日、今日出場清單等）
        # ==========================================================

        # 技術買點_今日美化
        if "技術買點_今日" in writer.sheets:
            ws_buy = writer.sheets["技術買點_今日"]

            # 檢查是否有實際買點
            first_cell = ws_buy.cell(row=startrow + 1, column=1).value if ws_buy.max_row > startrow else None

            if first_cell == "說明":
                buy_explain = [
                    "【技術買點_今日】診斷說明",
                    "今日無符合買點條件的股票。",
                    "",
                    "可能的調整方式：",
                    f"  - 降低 RSI_OVERSOLD（目前為 {cfg.rsi_oversold}）",
                    f"  - 關閉「成交量過濾」require_volume_filter",
                    f"  - 關閉「趨勢過濾」require_trend_filter",
                    f"  - 關閉「多時間框架確認」use_mtf_confirmation",
                    f"  - 增加選股檔數 TopN_for_Tech（目前為 {cfg.top_n_for_tech}）",
                    "",
                    "※ 買點條件較嚴格時，可能數日無訊號，屬正常現象。"
                ]
                write_explanation(ws_buy, buy_explain, start_row=startrow + len(buy_today_out) + 2)
            else:
                buy_explain = [
                    "【技術買點_今日】說明",
                    "買點 = 超跌(過去10天RSI低於門檻) + 轉強(RSI回升或MACD翻正) + 趨勢(站穩MA20) + 成交量過濾",
                    "多時間框架確認：週線/月線趨勢確認可提高買點品質"
                ]
                write_explanation(ws_buy, buy_explain)

            header_row = startrow + 1
            style_header(ws_buy, header_row)
            ws_buy.freeze_panes = ws_buy[f"A{header_row + 1}"]
            last_col = get_column_letter(ws_buy.max_column)
            ws_buy.auto_filter.ref = f"A{header_row}:{last_col}{ws_buy.max_row}"
            autosize_columns(ws_buy)

            # 只有在有實際買點時才高亮「買點」欄位
            if first_cell != "說明" and "買點" in [cell.value for cell in ws_buy[header_row]]:
                highlight_true(ws_buy, header_row, "買點")

        # 今日出場清單美化
        if "今日出場清單" in writer.sheets:
            ws_exit = writer.sheets["今日出場清單"]

            # 檢查是否有實際出場
            first_cell = ws_exit.cell(row=startrow + 1, column=1).value if ws_exit.max_row > startrow else None

            if first_cell == "說明":
                exit_explain = [
                    "【今日出場清單】診斷說明",
                    "今日無需要出場的股票。",
                    "",
                    "出場條件：",
                    f"  - 停損：報酬 ≤ {cfg.stop_loss * 100:.1f}%",
                    f"  - 停利：報酬 ≥ {cfg.take_profit * 100:.1f}%",
                    f"  - RSI 出場：RSI ≥ {cfg.exit_rsi}",
                    f"  - 時間出場：持有 ≥ {cfg.hold_days} 天",
                    "",
                    "如果持有股票但未觸發條件，表示仍在正常持有中。"
                ]
                write_explanation(ws_exit, exit_explain, start_row=startrow + len(exit_today_df) + 2)
            else:
                exit_explain = [
                    "【今日出場清單】說明",
                    "以下股票今日觸發賣出條件，建議賣出：",
                    f"  - 停損：報酬 ≤ {cfg.stop_loss * 100:.1f}%",
                    f"  - 停利：報酬 ≥ {cfg.take_profit * 100:.1f}%",
                    f"  - RSI 出場：RSI ≥ {cfg.exit_rsi}",
                    f"  - 時間出場：持有 ≥ {cfg.hold_days} 天"
                ]
                write_explanation(ws_exit, exit_explain)

            header_row = startrow + 1
            style_header(ws_exit, header_row)
            ws_exit.freeze_panes = ws_exit[f"A{header_row + 1}"]
            last_col = get_column_letter(ws_exit.max_column)
            ws_exit.auto_filter.ref = f"A{header_row}:{last_col}{ws_exit.max_row}"
            autosize_columns(ws_exit)
    logger.log("\n" + "=" * 60)
    logger.log("📊 回測結果摘要")
    logger.log("=" * 60)
    logger.log("✅ Signal-level KPI:")
    logger.log(sig_summary.to_string(index=False) if not sig_summary.empty else "(無訊號)")
    logger.log(f"\n✅ Portfolio-level KPI (Top{cfg.topk} 等權):")
    logger.log(pf_kpi.to_string(index=False) if not pf_kpi.empty else "(無投組資料)")
    logger.log("\n✅ 出場原因統計:")
    logger.log(reason_stats.to_string(index=False) if not reason_stats.empty else "(無交易資料)")
    logger.log(f"\n✅ 完成 → {out_file}")

    # V0.9.5-tab-split-phase3 B-1：回傳 df_sel 給 GUI 顯示
    return {
        "df_sel": df_sel,
        "top10_codes": top10_codes,
        "out_file": out_file,
    }



# ==========================================================
# V0.9.4 phase2.3: 萬年曆挑選日期（純 Tkinter 原生，無額外 dependency）
# ==========================================================
class _CalendarDialog:
    """
    簡單彈出式月曆。
    使用方式：
        date_str = _CalendarDialog.pick(parent, initial="2026-06-11")
        # date_str == "YYYY-MM-DD"（str）或 None（取消）
    """
    DAY_HEADER = ["一", "二", "三", "四", "五", "六", "日"]

    def __init__(self, parent, initial: str = ""):
        self.result: Optional[str] = None

        self.win = tk.Toplevel(parent)
        self.win.withdraw()
        self.win.title("挑選日期")
        self.win.resizable(False, False)
        self.win.transient(parent)
        self.win.grab_set()
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        if initial:
            try:
                self.current = datetime.strptime(initial, "%Y-%m-%d")
            except ValueError:
                self.current = datetime.now()
        else:
            self.current = datetime.now()

        self._build()
        self.win.deiconify()
        # wait_window() blocks until win is destroyed (_select / _cancel / X).
        # GUI stays fully responsive; grab_set() makes this window modal.
        self.win.wait_window()

    def _build(self):
        win = self.win

        # ── 頂部導航列 ──
        nav = ttk.Frame(win)
        nav.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(nav, text="◀◀", width=3,
                   command=lambda: self._navigate_years(-1)).pack(side="left")
        ttk.Button(nav, text="◀", width=3,
                   command=lambda: self._navigate(-1)).pack(side="left")

        # 年份 label（點擊可直接修改年份）
        self._year_lbl = tk.Label(nav, text="", font=("Segoe UI", 9, "bold"),
                                   cursor="hand2", bg="#e8f0fe", padx=4)
        self._year_lbl.pack(side="left", padx=(4, 0))
        self._year_lbl.bind("<Button-1>", lambda e: self._open_year_dialog())

        # 月份 label（點擊可直接修改月份）
        self._month_lbl = tk.Label(nav, text="", width=10, font=("Segoe UI", 10, "bold"),
                                   cursor="hand2", bg="#fff8e1", padx=4)
        self._month_lbl.pack(side="left", padx=4, expand=True)
        self._month_lbl.bind("<Button-1>", lambda e: self._open_month_menu())

        ttk.Button(nav, text="▶", width=3,
                   command=lambda: self._navigate(1)).pack(side="right")
        ttk.Button(nav, text="▶▶", width=3,
                   command=lambda: self._navigate_years(1)).pack(side="right")

        # ── 星期抬頭 ──
        hdr = ttk.Frame(win)
        hdr.pack(fill="x", padx=8, pady=(0, 2))
        for d in self.DAY_HEADER:
            lbl = ttk.Label(hdr, text=d, width=4, anchor="center",
                             font=("Segoe UI", 8, "bold"))
            lbl.pack(side="left", padx=1)
            if d == "六":
                lbl.config(foreground="#0070c0")
            elif d == "日":
                lbl.config(foreground="#c00000")

        # ── 日按鈕區域 ──
        self._day_frame = ttk.Frame(win)
        self._day_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._render_days()

        # ── 底部按鈕 ──
        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=(0, 8))
        ttk.Button(btn_frame, text="取消", command=self._cancel).pack(side="left", padx=8)

    def _navigate_years(self, delta: int):
        """往前/往後跳一年"""
        self.current = self.current.replace(year=self.current.year + delta)
        self._render_days()

    def _navigate(self, delta: int):
        """往前/往後跳一個月"""
        y, m = self.current.year, self.current.month
        m += delta
        if m > 12:
            m, y = 1, y + 1
        elif m < 1:   # Bugfix: month=0 → 12 月（往前翻年）
            m, y = 12, y - 1
        self.current = self.current.replace(year=y, month=m)
        self._render_days()

    def _open_year_dialog(self):
        """點年份 → 彈出對話框直接輸入年份"""
        dlg = tk.Toplevel(self.win)
        dlg.overrideredirect(True)
        dlg.attributes("-topmost", True)
        rx = self._year_lbl.winfo_rootx()
        ry = self._year_lbl.winfo_rooty() + self._year_lbl.winfo_height()
        dlg.geometry(f"+{rx}+{ry}")
        tk.Label(dlg, text="年份：", font=("Segoe UI", 10)).pack(side="left")
        var = tk.StringVar(value=str(self.current.year))
        ent = tk.Entry(dlg, textvariable=var, width=6, font=("Segoe UI", 10))
        ent.pack(side="left")
        ent.focus()
        ent.select_range(0, "end")

        def commit():
            try:
                yr = int(var.get())
                if 1950 <= yr <= 2100:
                    self.current = self.current.replace(year=yr)
                    self._render_days()
            except ValueError:
                pass
            dlg.destroy()

        tk.Button(dlg, text="確定", font=("Segoe UI", 9), command=commit).pack(side="left", padx=4)
        tk.Button(dlg, text="取消", font=("Segoe UI", 9), command=dlg.destroy).pack(side="left")
        ent.bind("<Return>", lambda e: commit())
        ent.bind("<Escape>", lambda e: dlg.destroy())

    def _open_month_menu(self):
        """點月份 → 彈出 1-12 月快速選單"""
        mnu = tk.Toplevel(self.win)
        mnu.overrideredirect(True)
        mnu.attributes("-topmost", True)
        mx = self._month_lbl.winfo_rootx()
        my = self._month_lbl.winfo_rooty() + self._month_lbl.winfo_height()
        mnu.geometry(f"+{mx}+{my}")
        for m in range(1, 13):
            tk.Button(mnu, text=f"{m} 月", font=("Segoe UI", 10), width=5,
                      command=lambda month=m: self._apply_month_and_close(month, mnu)
                      ).pack(fill="x")

    def _apply_month_and_close(self, month: int, mnu: tk.Toplevel):
        self.current = self.current.replace(month=month)
        mnu.destroy()
        self._render_days()

    def _render_days(self):
        for w in self._day_frame.winfo_children():
            w.destroy()
        year, month = self.current.year, self.current.month
        self._year_lbl.config(text=f"{year} 年")
        self._month_lbl.config(text=f"{month} 月")
        first_wd = datetime(year, month, 1).weekday()
        days_in_month = (datetime(year, month + 1, 1) - datetime(year, month, 1)).days
        for _ in range(first_wd):
            ttk.Label(self._day_frame).grid(row=0, column=_, padx=1, pady=1)
        for d in range(1, days_in_month + 1):
            row = (first_wd + d - 1) // 7
            col = (first_wd + d - 1) % 7
            date_str = f"{year:04d}-{month:02d}-{d:02d}"
            btn = tk.Button(self._day_frame, text=str(d), width=4, height=1,
                           font=("Segoe UI", 9),
                           command=lambda ds=date_str: self._select(ds))
            btn.grid(row=row, column=col, padx=1, pady=1, sticky="nsew")
            wd = (first_wd + d - 1) % 7
            if wd == 5:
                btn.config(foreground="#0070c0", bg="#f0f4ff")
            elif wd == 6:
                btn.config(foreground="#c00000", bg="#fff0f0")
            else:
                btn.config(foreground="#222222", bg="#f5f5f5")
        for c in range(7):
            self._day_frame.columnconfigure(c, weight=1)

    def _select(self, date_str: str):
        self.result = date_str
        self.win.destroy()

    def _cancel(self):
        self.result = None
        self.win.destroy()

    def _on_close(self):
        self._cancel()

    @staticmethod
    def pick(parent, initial: str = "") -> Optional[str]:
        return _CalendarDialog(parent, initial).result
# ==========================================================
# GUI 主視窗
# ==========================================================

class StrategyGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"StockTool {VERSION} (Multi-Factor + Top10 Backtest + Portfolio + goodinfo)")

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

        # Tab 1：系統選股（V0.9.5 階段 1：所有參數先放這邊）
        self.select_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.select_tab, text="📊 系統選股")

        # Tab 2：回測模擬（V0.9.5 階段 1：placeholder）
        self.backtest_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.backtest_tab, text="🧪 回測模擬")

        # Tab 2：買賣記錄（V0.9.4 新增）
        self.portfolio_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.portfolio_tab, text="📒 買賣記錄")
        self._build_portfolio_tab(self.portfolio_tab)

        # Tab 3：手動選股（V0.9.5 新增）
        self.manual_select_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.manual_select_tab, text="🔍 手動選股")
        self._build_manual_select_tab(self.manual_select_tab)

        # 【V0.9.5-etf】主動式 ETF 持股 Tab
        self.etf_tab = ttk.Frame(self.notebook)

        # 【V0.9.5-etf-history】ETF 持股歷史庫初始化
        self._init_etf_history()
        self.notebook.add(self.etf_tab, text="📊 主動式 ETF")
        self._build_etf_tab(self.etf_tab)

        # V0.9.5-tab-split Phase 2：建構「回測模擬」tab 內容
        self._build_backtest_tab(self.backtest_tab)

        # 綁定 Tab 切換 → 切到買賣記錄時自動 refresh
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # V0.9.5-tab-split Phase 3：兩個 tab 用 _build_tab_layout（左 params + 右 results）
        left, self.select_tree = self._build_tab_layout(self.select_tab)
        bt_left, self.backtest_tree = self._build_tab_layout(self.backtest_tab)
        self._bt_left = bt_left

        ttk.Label(left, text="📊 系統選股參數", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 8))

        self.vars: Dict[str, tk.Variable] = {}

        # 1. 基本參數
        basic_frame = ttk.LabelFrame(left, text="📊 基本參數", padding=5)
        basic_frame.pack(fill="x", pady=5)
        self._add_entry(basic_frame, "選股檔數 (TopN)", "top_n_for_tech", tk.IntVar, self.cfg.top_n_for_tech)
        self._add_entry(basic_frame, "歷史月數", "history_months", tk.IntVar, self.cfg.history_months)
        self._add_entry(basic_frame, "回測月數", "tech_months", tk.IntVar, self.cfg.tech_months)
        self._add_entry(basic_frame, "持股檔數 (TopK)", "topk", tk.IntVar, self.cfg.topk)

        # 2. 評分系統
        score_frame = ttk.LabelFrame(left, text="⭐ 評分系統", padding=5)
        score_frame.pack(fill="x", pady=5)

        self.use_enhanced_score_var = tk.BooleanVar(value=self.cfg.use_enhanced_score)
        ttk.Radiobutton(score_frame, text="多因子評分 (動能+成長)", variable=self.use_enhanced_score_var, value=True).pack(anchor="w")
        ttk.Radiobutton(score_frame, text="簡易評分 (可調權重+門檻)", variable=self.use_enhanced_score_var, value=False).pack(anchor="w")

        weight_frame = ttk.Frame(score_frame)
        weight_frame.pack(fill="x", pady=5)
        ttk.Label(weight_frame, text="因子權重:", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self._add_entry(weight_frame, "動能1M", "factor_weight_mom1", tk.DoubleVar, self.cfg.factor_weight_mom1)
        self._add_entry(weight_frame, "動能3M", "factor_weight_mom3", tk.DoubleVar, self.cfg.factor_weight_mom3)
        self._add_entry(weight_frame, "動能6M", "factor_weight_mom6", tk.DoubleVar, self.cfg.factor_weight_mom6)
        self._add_entry(weight_frame, "營收YoY", "factor_weight_rev", tk.DoubleVar, self.cfg.factor_weight_rev)
        self._add_entry(weight_frame, "EPS YoY", "factor_weight_eps", tk.DoubleVar, self.cfg.factor_weight_eps)

        self.adv_btn = ttk.Button(score_frame, text="⚙ 簡易評分進階設定", command=self._open_simple_score_settings)
        self.adv_btn.pack(fill="x", pady=(6, 0))

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
        source_frame = ttk.LabelFrame(bt_left, text="📁 選股來源", padding=5)
        source_frame.pack(fill="x", pady=5)

        self.use_excel_var = tk.BooleanVar(value=self.cfg.use_excel_stock_list)
        ttk.Checkbutton(source_frame, text="使用 Excel 股票清單", variable=self.use_excel_var).pack(anchor="w")
        self._add_entry(source_frame, "Excel 檔案", "excel_stock_file", tk.StringVar, self.cfg.excel_stock_file)

        # ✅ v0.9.4 Excel 清單強制買點模式
        self.excel_force_buy_var = tk.BooleanVar(value=self.cfg.excel_force_buy)
        ttk.Checkbutton(
            source_frame,
            text="📊 Excel 清單強制買點模式（跳過技術買點過濾）",
            variable=self.excel_force_buy_var
        ).pack(anchor="w", pady=(5, 0))
        ttk.Label(source_frame, text="  ※ 使用 Excel 股票清單 + 不經過買點過濾（強制滿倉）", foreground="gray").pack(anchor="w")

        # v0.9.2 Top10 基本面回測開關
        self.top10_backtest_var = tk.BooleanVar(value=self.cfg.use_top10_backtest)
        ttk.Checkbutton(
            source_frame,
            text="📊 使用 Top10_基本面 進行回測（跳過技術買點）",
            variable=self.top10_backtest_var
        ).pack(anchor="w", pady=(5, 0))
        ttk.Label(source_frame, text="  ※ 直接使用評分最高的10檔股票建倉，不經過買點過濾", foreground="gray").pack(anchor="w")
        # 7. 強勢股過濾
        strong_frame = ttk.LabelFrame(left, text="💪 強勢股過濾 (報表用)", padding=5)
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

        self.save_btn = ttk.Button(btn_frame, text="💾 儲存設定", command=self._on_save_config)
        self.save_btn.pack(fill="x", pady=2)

        self.reset_btn = ttk.Button(btn_frame, text="🔄 載入預設", command=self._on_reset_config)
        self.reset_btn.pack(fill="x", pady=2)

        self.clear_btn = ttk.Button(btn_frame, text="🗑 清除控制台", command=self._on_clear_console)
        self.clear_btn.pack(fill="x", pady=2)

        # 回測模擬 tab 的按鈕（階段 C 實作執行回測、目前先 disabled）
        bt_btn_frame = ttk.Frame(bt_left)
        bt_btn_frame.pack(fill="x", pady=10)

        ttk.Label(bt_btn_frame, text="回測模擬功能、即將上線", foreground="gray").pack(fill="x", pady=2)
        self.bt_run_btn = ttk.Button(bt_btn_frame, text="▶ 執行回測模擬（階段 C 上線）", command=self._on_run, state="disabled")
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

        Args:
            parent: parent widget（select_tab 或 backtest_tab）

        Returns:
            (left_scrollable_frame, results_tree): 兩個 frame 給後續使用
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

        # 右：results Treeview（先空、之後 Phase 3B 填資料）
        right_frame = ttk.Frame(container)
        right_frame.pack(side="left", fill="both", expand=True, padx=(10, 0))

        # 標題
        title_label = ttk.Label(right_frame, text="📋 結果（執行後顯示）", font=("Segoe UI", 11, "bold"))
        title_label.pack(anchor="w", pady=(0, 5))

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

        return left_scrollable_frame, results_tree

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
        self.use_excel_var.set(self.cfg.use_excel_stock_list)
        self.volume_filter_var.set(self.cfg.require_volume_filter)
        self.mtf_var.set(self.cfg.use_mtf_confirmation)
        self.divergence_var.set(self.cfg.use_divergence_detection)
        self.wf_enabled_var.set(self.cfg.wf_enabled)
        self.top10_backtest_var.set(self.cfg.use_top10_backtest)
        self.excel_force_buy_var.set(self.cfg.excel_force_buy)

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
        self.cfg.use_excel_stock_list = self.use_excel_var.get()
        self.cfg.require_volume_filter = self.volume_filter_var.get()
        self.cfg.use_mtf_confirmation = self.mtf_var.get()
        self.cfg.use_divergence_detection = self.divergence_var.get()
        self.cfg.wf_enabled = self.wf_enabled_var.get()
        self.cfg.use_top10_backtest = self.top10_backtest_var.get()
        self.cfg.excel_force_buy = self.excel_force_buy_var.get()

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
                self.console.insert("end", msg + "\n")
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
            if current == 1:  # Tab 2 = 買賣記錄
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
            if current != 1:
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
                # 同時補上股票名稱（如果 DB 沒有的話）
                if info.get("name"):
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

        # 中間：持倉明細 Treeview
        pos_frame = ttk.LabelFrame(parent, text="🌳 持倉明細", padding=4)
        pos_frame.pack(fill="both", expand=True, padx=8, pady=4)
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

        # 最下：按鈕區
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(btn_frame, text="➕ 新增買入", command=self._open_buy_dialog).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="➖ 新增賣出", command=self._open_sell_dialog).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="💲 更新現價", command=self._update_prices_dialog).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="🗑 刪除選中", command=self._delete_selected_tx).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="🔄 重新整理", command=self._refresh_portfolio_view).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="✏️ 編輯", command=self._open_edit_tx_dialog).pack(side="left", padx=2)  # V0.9.4 phase2.3
        ttk.Button(btn_frame, text="📤 匯出 Excel", command=self._export_portfolio_excel).pack(side="right", padx=2)

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
        left_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        left_frame = ttk.LabelFrame(left_canvas, text="🔎 ETF 持股篩選", padding=8)
        left_canvas.create_window((0, 0), window=left_frame, anchor="nw")
        left_frame.bind(
            "<Configure>",
            lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all")),
        )

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
        ttk.Button(btn_row, text="📋 全選",
                   command=self._etf_select_all).pack(fill="x", pady=1)
        ttk.Button(btn_row, text="☐ 全不選",
                   command=self._etf_select_none).pack(fill="x", pady=1)
        ttk.Button(btn_row, text="📤 匯出 Excel",
                   command=self._etf_export_excel).pack(fill="x", pady=1)

        # ── 右面板：Treeview ----
        right_frame = ttk.LabelFrame(paned, text="📊 ETF 成份股持股統計（依 ETF 數排序）", padding=4)
        paned.add(right_frame, weight=1)

        cols = ("勾選", "代號", "名稱", "收盤價", "ETF數", "今日異動")
        self._etf_tree = ttk.Treeview(right_frame, columns=cols, show="headings",
                                      selectmode="none", height=25)
        col_widths = (40, 70, 130, 80, 70, 100)
        for col, w in zip(cols, col_widths):
            self._etf_tree.heading(col, text=col)
            self._etf_tree.column(col, width=w, anchor="center")

        etf_scroll_y = ttk.Scrollbar(right_frame, orient="vertical", command=self._etf_tree.yview)
        etf_scroll_x = ttk.Scrollbar(right_frame, orient="horizontal", command=self._etf_tree.xview)
        self._etf_tree.configure(yscrollcommand=etf_scroll_y.set, xscrollcommand=etf_scroll_x.set)
        self._etf_tree.pack(fill="both", expand=True)
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
        self._etf_tree.bind("<Motion>", self._on_etf_tree_hover)
        self._etf_tree.bind("<Leave>", self._on_etf_tree_leave)
        self._etf_tree.bind("<Button-1>", self._etf_toggle_check)

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
        # 【V0.9.5-cache-scrollfix 改】2026-06-19 22:12 William 反映：
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

        # 滑鼠滾輪支援
        def _on_mousewheel(event):
            left_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        left_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # 真正的內容在 left_frame 裡、embed 到 canvas
        left_frame = ttk.LabelFrame(left_canvas, text="🔎 篩選條件", padding=8)
        left_canvas.create_window((0, 0), window=left_frame, anchor="nw")
        left_frame.bind(
            "<Configure>",
            lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all")),
        )

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
        # 【V0.9.5-cache-cleanup1】2026-06-19 William 決定：
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
        ttk.Button(btn_row, text="📋 全選",
                   command=self._ms_select_all).pack(fill="x", pady=1)
        ttk.Button(btn_row, text="☐ 全不選",
                   command=self._ms_select_none).pack(fill="x", pady=1)
        ttk.Button(btn_row, text="📤 匯出 Excel",
                   command=self._ms_export_excel).pack(fill="x", pady=1)

        # ── 右面板：結果列表 ──
        right_frame = ttk.LabelFrame(paned, text="📊 篩選結果", padding=4)
        paned.add(right_frame, weight=1)

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
        self._ms_tree = ttk.Treeview(right_frame, columns=cols, show="headings",
                                     selectmode="none", height=25)
        # 14 欄（拿掉 2 個股票殖利率 + 加 1 個資料日期）：原本 15 欄 - 2 + 1 = 14
        col_widths = (40, 60, 100, 70, 70, 60, 60, 80,
                      50, 80, 60, 60, 80,
                      90)
        for col, w in zip(cols, col_widths):
            self._ms_tree.heading(col, text=col)
            self._ms_tree.column(col, width=w, anchor="center")

        ms_scroll_y = ttk.Scrollbar(right_frame, orient="vertical", command=self._ms_tree.yview)
        ms_scroll_x = ttk.Scrollbar(right_frame, orient="horizontal", command=self._ms_tree.xview)
        self._ms_tree.configure(yscrollcommand=ms_scroll_y.set, xscrollcommand=ms_scroll_x.set)
        self._ms_tree.pack(fill="both", expand=True)
        ms_scroll_y.pack(side="right", fill="y")
        ms_scroll_x.pack(side="bottom", fill="x")

        # 【V0.9.5-cache-hover 新增】2026-06-19 William 要求：
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

        # 右鍵選單
        self._ms_tree.bind("<Button-3>", self._ms_show_context_menu)

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
            # 【V0.9.5-cache-info】順手加股價更新時間到 status bar
            # 讓使用者不管在哪個 Tab 都看得到「最後更新時間」
            update_str = self._price_last_update.strftime("%Y-%m-%d %H:%M:%S")
            # 【V0.9.5-cache-info】順手顯示 cache 的 data_date（個股最後交易日）
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
            # 【V0.9.5-cache-vol-fix】2026-06-19 18:50 William 反映：
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

                added = _background_fetch_all_dividend(
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

                added = _background_fetch_all_dividend(
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

                # 【V0.9.5-cache-cleanup1】2026-06-19 William 決定：
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
            # 【V0.9.5-cache-info】加「資料日期」欄位（從 price_df.data_date）
            # 顯示個股本身的「最後交易日」、不是 cache 抓取日
            # 例：週五 13:35 抓的 cache、某些股週五暫停交易 → 顯示「2026-06-18」而不是「2026-06-19」
            data_date = str(row.get("data_date", "")).strip()
            data_date_str = data_date if data_date else "—"
            # 【V0.9.5-twser3】Treeview 從 15 欄變 13 欄（拿掉 2 個股票殖利率）
            # 【V0.9.5-cache-info】再加 1 欄「資料日期」變 14 欄
            self._ms_tree.insert("", "end", iid=code, values=(
                "☑" if self._ms_checked.get(code, False) else "☐",
                code, name, price_str, rev_str,
                stock_str, cash_div_str, cash_str,
                pe_str, vol_str,
                last_stock_str, last_cash_div_str, last_cash_str,
                data_date_str
            ), tags=(tag,))

        self._ms_status.set(f"✅ 符合條件：{len(result)} 檔（上限 {self._ms_limit_var.get()} 檔）｜排序：營收YoY > 今年股票 > 今年現金殖% > PE")

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
        """【V0.9.5-cache-hover】滑鼠移到 Treeview 任一列時
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
        """【V0.9.5-cache-hover】滑鼠離開 Treeview → 清除 hover"""
        self._clear_hover()

    def _clear_hover(self):
        """【V0.9.5-cache-hover】取消目前 hover、恢復該列原本的 checked/unchecked tag"""
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
        """點 Treeview 任一列 → toggle 勾選狀態"""
        region = self._ms_tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        column = self._ms_tree.identify_column(event.x)
        if column != "#1":  # 只有第一欄（勾選欄）可以 toggle
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

    def _ms_select_all(self):
        for item in self._ms_tree.get_children():
            self._ms_checked[item] = True
            vals = list(self._ms_tree.item(item, "values"))
            vals[0] = "☑"
            self._ms_tree.item(item, values=vals, tags=("checked",))

    def _ms_select_none(self):
        for item in self._ms_tree.get_children():
            self._ms_checked[item] = False
            vals = list(self._ms_tree.item(item, "values"))
            vals[0] = "☐"
            self._ms_tree.item(item, values=vals, tags=("unchecked",))

    def _ms_show_context_menu(self, event):
        """右鍵：全選 / 全不選"""
        menu = tk.Menu(self.manual_select_tab, tearoff=0)
        menu.add_command(label="☑ 全選", command=self._ms_select_all)
        menu.add_command(label="☐ 全不選", command=self._ms_select_none)
        menu.post(event.x_root, event.y_root)

    # ==========================================================
    # 【V0.9.5-etf】主動式 ETF Tab — Hover / Toggle / Filter / Refresh / Export
    # ==========================================================

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
                cl = cr.get("change_lots", 0) or 0
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
        """【V0.9.5-etf】點 ETF Treeview → toggle 勾選"""
        region = self._etf_tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        column = self._etf_tree.identify_column(event.x)
        if column != "#1":
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

    def _etf_select_all(self):
        for item in self._etf_tree.get_children():
            self._etf_checked[item] = True
            vals = list(self._etf_tree.item(item, "values"))
            vals[0] = "☑"
            self._etf_tree.item(item, values=vals, tags=("checked",))

    def _etf_select_none(self):
        for item in self._etf_tree.get_children():
            self._etf_checked[item] = False
            vals = list(self._etf_tree.item(item, "values"))
            vals[0] = "☐"
            self._etf_tree.item(item, values=vals, tags=("unchecked",))


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
            stock_change = (
                change_df.groupby("stock_code", as_index=False)["change_lots"]
                .sum()
                .rename(columns={"change_lots": "total_change_lots"})
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

        # 【V0.9.5-etf-history】依總異動絕對值降序（沒有異動的擺最後）
        has_change = df["total_change_lots"].abs() > 0.001
        df = pd.concat([
            df[has_change].sort_values("total_change_lots", key=lambda x: x.abs(), ascending=False),
            df[~has_change].sort_values("etf_count", ascending=False),
        ], ignore_index=True)

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

        filepath = filedialog.asksaveasfilename(
            title="匯出 ETF 成份股持股",
            defaultextension=".xlsx",
            filetypes=["Excel 活頁簿 (*.xlsx)"],
            initialfile=f"ETF成份股_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        )
        if not filepath:
            return

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
            df, _ = load_cache(get_cache_file("price"))
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

        filepath = filedialog.asksaveasfilename(
            title="匯出手動選股結果",
            defaultextension=".xlsx",
            filetypes=["Excel 活頁簿 (*.xlsx)"],
            initialfile=f"手動選股_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        )
        if not filepath:
            return

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
            # 【V0.9.5-cache-savelist-fix2】2026-06-19 22:15 William 反映：
            # 「匯出 excel 可以餵回策略參數中的選股來源嗎？可以就只要這個功能」
            # 是的：load_stock_list_from_excel 只要「股票代號」欄（find_col 找「股票/code」）
            # 這個檔案包含「股票代號」+「股票名稱」+ 其他欄位 → load 只讀代號、其它忽略
            # 所以不需要額外加「存成 Excel 股票清單」按鈕、這個檔案直接就能用。
            messagebox.showinfo(
                "匯出成功",
                f"已匯出 {len(result)} 檔\n→ {filepath}\n\n"
                f"💡 這個檔案可以直接給「策略參數 → 使用 Excel 股票清單」讀取使用\n"
                f"   （只取「股票代號」欄、其他欄位會被忽略）",
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

        stock_name = stock_txs[0].stock_name or stock_id
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
                self._positions_tree.insert("", "end", values=(
                    p.stock_id, p.stock_name,
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
                result = run_pipeline(cfg, self.logger)
                if result and "df_sel" in result:
                    # 用 after 把 GUI 更新推回主 thread
                    df_sel = result["df_sel"]
                    self.after(0, lambda df=df_sel: self._display_select_results(df))
            except Exception as e:
                self.logger.log(f"❌ 執行失敗：{e}")
                import traceback
                self.logger.log(traceback.format_exc())
            finally:
                self.run_btn.config(state="normal")

        threading.Thread(target=worker, daemon=True).start()

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
            cols = ("代號", "名稱", "股價", "Score", "營收YoY(%)", "EPSYoY(%)", "PE", "殖利率(%)")
            col_widths = (60, 100, 60, 60, 80, 80, 50, 70)
            self.select_tree.configure(columns=cols)
            for col, w in zip(cols, col_widths):
                self.select_tree.heading(col, text=col)
                self.select_tree.column(col, width=w, anchor="center")

        # 填資料（取前 60 筆、避免太慢）
        display_count = 0
        for idx, row in df_sel.head(60).iterrows():
            code = str(row.get("股票代號", "")).strip()
            if not code:
                continue
            name = str(row.get("股票名稱", row.get("名稱", "")))
            price = row.get("股價", row.get("收盤價", 0))
            score = row.get("Score", 0)
            rev_yoy = row.get("營收YoY(%)", 0)
            eps_yoy = row.get("EPSYoY_顯示(%)", row.get("EPSYoY(%)", 0))
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

            self.select_tree.insert("", "end", values=(
                code,
                name[:8] if name else "--",
                _fmt(price),
                _fmt(score, fmt=".3f"),
                _fmt(rev_yoy),
                _fmt(eps_yoy),
                _fmt(pe),
                _fmt(yld),
            ))
            display_count += 1

        self.logger.log(f"📋 已顯示 {display_count} 筆選股結果（總共 {len(df_sel)} 筆）")


if __name__ == "__main__":
    app = StrategyGUI()
    app.mainloop()
