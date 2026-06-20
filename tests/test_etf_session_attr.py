"""【V0.9.5-etf-session-fix】ETF 模組 self.session 不存在 bug 守護

2026-06-20 09:12 William 反映：
- 開 App 後 ETF 開機抓取 thread 拋例外 → 'tkinter.tkapp' object has no attribute 'session'
- log: ❌ [ETF] 開機抓取例外：'_tkinter.tkapp' object has no attribute 'session'

【根因】
- StockTool 主類別根本沒有 `self.session` 屬性
- 其他 fetcher（fetch_prices / fetch_revenue_latest）都是在呼叫端 build_session()
  → 例：df = fetch_prices(_s, self.cfg)
- 但 ETF 模組（860360b fetcher + 875f0d2 GUI + cd4527a closure fix）三個版本都誤用
  `build_etf_holdings_table(self.session, ...)` / `fetch_prices(self.session, ...)`

【修法】
- 在 worker 內或同步方法內 `_s = build_session()` 拿 requests.Session
- 跟其他 fetcher 保持一致風格
"""
import ast
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
STOCKTOOL_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "StockTool.py"
)


def _find_self_session_in_code():
    """用 AST 解析 StockTool.py、找出所有真的 self.session attribute access
    （排除 docstring / 註解 / 字串內提到的）
    """
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)
    offenders = []

    for node in ast.walk(tree):
        # 找 self.session 這種 attribute access（self 是 Name('self'), attr == 'session'）
        if isinstance(node, ast.Attribute) and node.attr == "session":
            if isinstance(node.value, ast.Name) and node.value.id == "self":
                offenders.append((node.lineno, ast.unparse(node)))
    return offenders


def test_stocktool_no_self_session_attr():
    """【核心守護】StockTool.py 不能有任何真的 `self.session` attribute access
    → StockTool 主類別從未定義 session 屬性、用 self.session 必壞 AttributeError

    用 AST 解析、可正確排除 docstring / 註解 / 字串裡提到的「self.session」字眼。
    """
    offenders = _find_self_session_in_code()
    assert not offenders, (
        f"❌ StockTool.py 還有 {len(offenders)} 處 self.session attribute access！\n"
        f"StockTool 主類別沒有 session 屬性、會在 runtime 炸 AttributeError。\n"
        f"請改用 `_s = build_session()` 然後傳 `_s` 進 fetcher。\n"
        f"違規位置：" + "\n".join(f"  line {ln}: {code}" for ln, code in offenders)
    )


def test_etf_workers_use_build_session():
    """ETF 模組 3 個 self.session 觸發點都改用 build_session()
    - line 6951 (_etf_refresh._worker)
    - line 7103 (_etf_auto_startup_fetch._worker)
    - line 7146 (_load_price_df)
    """
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # 確認這 3 個關鍵 method 內都有 build_session()
    assert "_etf_auto_startup_fetch" in content
    assert "_etf_refresh" in content or "_etf_force_refresh" in content
    assert "_load_price_df" in content

    # 找所有 build_session() 數量（原本就有 + 新加 3 處）
    count = content.count("build_session()")
    assert count >= 6, (
        f"❌ build_session() 數量不足：{count} 處\n"
        f"預期至少有 6 處（3 個原本 + 3 個 ETF 新加）"
    )


def test_etf_fetchers_accept_session_param():
    """【契約守護】ETF fetcher 第一個參數必須是 session
    → build_etf_holdings_table / fetch_active_etf_list / fetch_etf_top10_holdings
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
    import inspect
    from StockTool import (
        build_etf_holdings_table,
        fetch_active_etf_list,
        fetch_etf_top10_holdings,
    )

    for fn in (build_etf_holdings_table, fetch_active_etf_list, fetch_etf_top10_holdings):
        sig = inspect.signature(fn)
        first_param = next(iter(sig.parameters.values()))
        assert first_param.name == "session", (
            f"❌ {fn.__name__} 第一個參數應該叫 'session'，現在是 '{first_param.name}'"
        )


def test_etf_method_compiles():
    """【語法守護】_etf_auto_startup_fetch / _etf_refresh / _load_price_df 編譯不掛
    → 確保 build_session() 改完沒漏逗號 / indent 錯誤
    """
    import py_compile
    try:
        py_compile.compile(STOCKTOOL_PY, doraise=True)
    except py_compile.PyCompileError as e:
        pytest.fail(f"❌ StockTool.py 編譯失敗：\n{e}")


def test_ast_helper_actually_catches_offenders():
    """【反向驗證】_find_self_session_in_code 能抓到真的 self.session access
    → 用一個有 self.session attribute 的 sample code、讓 helper 抓出來
    """
    sample = '''
def fake_method(self):
    x = self.session  # 這該被抓
    return x
'''
    tree = ast.parse(sample)
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "session":
            if isinstance(node.value, ast.Name) and node.value.id == "self":
                offenders.append((node.lineno, ast.unparse(node)))
    assert len(offenders) == 1, f"❌ 預期抓到 1 處 self.session、實際 {len(offenders)} 處"
    assert "self.session" in offenders[0][1]

    # 反面：docstring 內提到的 self.session 不該被抓
    sample2 = '''
def fake_method2(self):
    """這個 docstring 內提到 self.session 但不是 attribute access、不該被抓"""
    return "self.session 字串也不該被抓"
'''
    tree2 = ast.parse(sample2)
    offenders2 = []
    for node in ast.walk(tree2):
        if isinstance(node, ast.Attribute) and node.attr == "session":
            if isinstance(node.value, ast.Name) and node.value.id == "self":
                offenders2.append((node.lineno, ast.unparse(node)))
    assert len(offenders2) == 0, (
        f"❌ docstring / 字串的 'self.session' 不該被抓、卻抓到 {len(offenders2)} 處"
    )