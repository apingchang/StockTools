"""V0.9.5-tab-split-phase3 Commit B-1: 系統選股結果 Treeview 守護

驗證：
- run_pipeline 結尾有 return result dict（含 df_sel, top10_codes, out_file）
- _on_run 接收 result、用 after(0) 顯示在 Treeview
- _display_select_results 把 df_sel 寫入 select_tree
- select_tree 預設有空 Treeview、欄位在第一筆資料寫入時設定
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
STOCKTOOL_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "StockTool.py"
)


def test_run_pipeline_returns_df_sel():
    """run_pipeline 結尾必須 return dict 含 df_sel"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # 找 run_pipeline 結尾、要有 return 包含 df_sel
    assert '"df_sel"' in content, (
        "❌ run_pipeline 沒回傳 df_sel！\n"
        "Phase 3 B-1：run_pipeline 結尾應 return {'df_sel': df_sel, ...}"
    )

    # 找 run_pipeline 結尾的 return
    import re
    # 找「✅ 完成 → {out_file}」附近、有 return 含 df_sel
    # 用 regex 容忍空白、避免中文標點 escape 問題
    # 「out_file}」加一個 } 來避開 out_file_prefix
    pattern = r'out_file\}\".{0,300}return\s*\{[^}]*"df_sel"'
    m = re.search(pattern, content, re.DOTALL)
    assert m, (
        "❌ run_pipeline 結尾沒在「✅ 完成」後 return df_sel！\n"
        "應為：\n"
        "  logger.log(f'\\n✅ 完成 → {out_file}')\n"
        "  return {'df_sel': df_sel, ...}"
    )
    print("✅ run_pipeline 結尾 return {df_sel, ...}")


def test_on_run_calls_display_results():
    """_on_run 必須用 after(0) 呼叫 _display_select_results"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    assert "self.after(0" in content, "❌ _on_run 沒用 self.after(0)"
    assert "_display_select_results" in content, "❌ 缺少 _display_select_results method"
    print("✅ _on_run 用 after(0) 呼叫 _display_select_results")


def test_display_select_results_method_exists():
    """必須有 _display_select_results method"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    assert "def _display_select_results" in content, (
        "❌ 缺少 _display_select_results method"
    )
    print("✅ 有 _display_select_results method")


def test_select_tree_attribute_exists():
    """self.select_tree 必須存在（_build_ui 內設定）"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    assert "self.select_tree" in content, (
        "❌ 缺少 self.select_tree 屬性！\n"
        "Phase 3 B-1：_build_ui 內必須建 Treeview 並存為 self.select_tree"
    )
    print("✅ self.select_tree 屬性存在")


def test_backtest_tree_attribute_exists():
    """self.backtest_tree 必須存在（為 Phase C 預留）"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    assert "self.backtest_tree" in content, (
        "❌ 缺少 self.backtest_tree 屬性！\n"
        "Phase 3 B-1：_build_ui 內必須建 backtest_tab 的 Treeview（先空、Phase C 填）"
    )
    print("✅ self.backtest_tree 屬性存在")


def test_tab_layout_helper_exists():
    """_build_tab_layout helper 必須存在（Phase 3 改名 _build_left_frame）"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    assert "def _build_tab_layout" in content, "❌ 缺少 _build_tab_layout helper"
    # 不應再有舊的 _build_left_frame
    assert "def _build_left_frame" not in content, (
        "❌ 還有 _build_left_frame（已廢棄、Phase 3 改名為 _build_tab_layout）"
    )
    print("✅ 有 _build_tab_layout helper、無舊 _build_left_frame")


def test_display_select_results_no_locale_comma():
    """_display_select_results 不應在 Treeview cell 用千分位（避免 locale bug）"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # 找 _display_select_results method 範圍
    m_start = content.find("def _display_select_results")
    assert m_start > 0
    m_end = content.find("\n    def ", m_start + 1)
    body = content[m_start:m_end] if m_end > 0 else content[m_start:]

    # 不應在 body 內用 `:,.Xf` 格式（會被 Tkinter 當歐洲小數點）
    import re
    bad = re.findall(r":,[0-9]*\.[0-9]*f", body)
    assert not bad, (
        f"❌ _display_select_results 內有千分位格式：{bad}\n"
        f"Phase 3 B-1：Treeview cell 不能用千分位（會被 locale 當歐洲小數點）"
    )
    print("✅ _display_select_results 無千分位（無 locale bug）")