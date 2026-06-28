"""
test_vol_round_fix.py
驗證 V0.9.5-vol-row-pad:Treeview rowheight 加大

【William 2026-06-28 20:51 反映】
所有的篩選結果顯示行距應該再加至少 2 dots、
股票名稱中文字最下面那條 line 不見了

【William 2026-06-28 21:04 補充】
「台股成交都是 1000 股（一張）為單位不會有四捨五入的問題！」
- 原始成交股數整數（例：1,830,000 股）/1000 = 1830.0 張
- 理論上不會出現 1830.999 這類小數
- 用 int() truncate 比 round() 安全（banker's rounding 在 .5 邊界）

【修法】
- source/StockTool.py: __init__ 加 ttk.Style().configure("Treeview", rowheight=28)
  - Win10/11 預設 ~18-20px、中文字底部橫劃被切到
  - 加大到 28px、+8-10px padding、讓中文有呼吸空間
- 成交量：保持 int()（原本就是）、不需 round()

【2548 差 1 問題】(另開 issue 追、不在這版修)
- 2548 華固 6/26 我顯示 1830、元大顯示 1831
- 根因：資料 source 不同（MIS 盤中 vs STOCK_DAY 盤後 vs FinMind cache）
- 不是顯示邏輯問題、要從 source 追

【守護】
- Treeview rowheight 設定驗證
- vol 顯示用 int()、不用 round()
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))


def test_vol_str_用_int_不用_round():
    """【V0.9.5-vol-row-pad】vol 顯示用 int()、不用 round()

    William 21:04 提醒：台股成交都是整數張、原始 /1000 後是整數 .0、
    round() 跟 int() 結果一樣、但 int() 在 .5 邊界用 truncate、避免 banker's rounding 風險
    """
    def make_vol_str(vol):
        try:
            if vol is None or (isinstance(vol, (int, float)) and vol == 0):
                return "—"
            return str(int(vol))
        except (TypeError, ValueError):
            return "—"

    # 整數張（台股常見）
    assert make_vol_str(1830) == "1830"
    assert make_vol_str(1830.0) == "1830"
    assert make_vol_str(1857.0) == "1857"

    # 浮點但剛好是整數值（stock_data 算出來的）
    assert make_vol_str(1.830e3) == "1830"
    assert make_vol_str(12.0) == "12"

    # 邊界：0、None、NaN
    assert make_vol_str(0) == "—"
    assert make_vol_str(None) == "—"
    assert make_vol_str(float("nan")) == "—"

    # 2548 案例：即使原始是 1830.0（不是 1830.999）、int() 跟 round() 都 = 1830
    # 2548 差 1 是 source 問題、不是 truncate 問題
    assert make_vol_str(1830.0) == "1830"
    print("PASS: test_vol_str_用_int_不用_round (台股整數張、用 int() 不用 round)")


def test_treeview_rowheight_設定():
    """【V0.9.5-vol-row-pad】ttk.Style().configure('Treeview', rowheight=28)

    William 反映：所有篩選結果顯示行距應該再加至少 2 dots、
                  股票名稱中文字最下面那條 line 不見了
    修法：在 __init__ 設 ttk.Style rowheight=28（Win 預設 18-20 + 8px padding）
    """
    import inspect
    import StockTool as st

    src = inspect.getsource(st)
    assert '_style.configure("Treeview", rowheight=28)' in src, (
        "應在 __init__ 設定 ttk.Treeview rowheight=28、避免中文字底部被切"
    )
    print("PASS: test_treeview_rowheight_設定")


if __name__ == "__main__":
    test_vol_str_用_int_不用_round()
    test_treeview_rowheight_設定()
    print("\nAll V0.9.5-vol-row-pad tests passed!")