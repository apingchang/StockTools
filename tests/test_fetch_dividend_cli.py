"""
test_fetch_dividend_cli.py
驗證 scripts/fetch_dividend.py 的 CLI 股號解析邏輯。

【情境】
V0.9.5+ 提供「🎯 指定股補抓」App 內按鈕，但對話中也要能用 CLI 跑。
William 11:21 問「我怎麼告訴你我的指定股票？」，腳本要能正確解析各種格式。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

# 把 scripts/ 加進 import path
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)

import fetch_dividend as fd  # noqa: E402


def test_parse_codes_空格分隔():
    """python fetch_dividend.py 3188 2330 2317"""
    args = ["3188", "2330", "2317"]
    assert fd.parse_codes(args) == ["3188", "2330", "2317"]


def test_parse_codes_英文逗號():
    """python fetch_dividend.py 3188,2330,2317"""
    args = ["3188,2330,2317"]
    assert fd.parse_codes(args) == ["3188", "2330", "2317"]


def test_parse_codes_中文逗號():
    """python fetch_dividend.py "3188，2330，2317\""""
    args = ["3188，2330，2317"]
    assert fd.parse_codes(args) == ["3188", "2330", "2317"]


def test_parse_codes_混合分隔():
    """python fetch_dividend.py "3188, 2330，2317\""""
    args = ["3188,", "2330，2317"]
    assert fd.parse_codes(args) == ["3188", "2330", "2317"]


def test_parse_codes_跳過空白():
    """多餘空白 / 空字串應跳過"""
    args = ["3188", "", "  ", "2330"]
    assert fd.parse_codes(args) == ["3188", "2330"]


def test_parse_codes_換行分隔():
    """python fetch_dividend.py "3188\\n2330\\n2317\""""
    args = ["3188\n2330\n2317"]
    assert fd.parse_codes(args) == ["3188", "2330", "2317"]


def test_parse_codes_空list():
    """空 list 應回空 list（不是拋例外）"""
    assert fd.parse_codes([]) == []


def test_parse_codes_單一股號():
    assert fd.parse_codes(["2330"]) == ["2330"]


def test_main_無參數_應exit_code_2():
    """不給股號 → exit 2 + 顯示 usage"""
    import subprocess
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "fetch_dividend.py")],
        capture_output=True, text=True,
    )
    assert result.returncode == 2, f"應 exit 2，實際: {result.returncode}"
    assert "用法" in result.stdout


def test_main_模擬對話中呼叫():
    """模擬 William 在對話中說「補抓 3188, 2330, 2454」
    → 對應 subprocess: python fetch_dividend.py 3188 2330 2454
    → 因 FinMind 額度已用完（commit 後 11:30 實測），會 exit 1
    → 但至少要看到「📋 收到 3 檔股號」這行
    """
    import subprocess
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "fetch_dividend.py"),
         "3188", "2330", "2454"],
        capture_output=True, text=True,
    )
    # FinMind 額度已用 → exit 1
    assert "📋 收到 3 檔股號" in result.stdout
    assert "3188" in result.stdout
    assert "2330" in result.stdout
    assert "2454" in result.stdout
    # exit code 應該是 0（全部完成）或 1（FinMind 402）
    assert result.returncode in (0, 1), f"應為 0 或 1，實際: {result.returncode}"


if __name__ == "__main__":
    test_parse_codes_空格分隔()
    print("✅ test_parse_codes_空格分隔 passed")
    test_parse_codes_英文逗號()
    print("✅ test_parse_codes_英文逗號 passed")
    test_parse_codes_中文逗號()
    print("✅ test_parse_codes_中文逗號 passed")
    test_parse_codes_混合分隔()
    print("✅ test_parse_codes_混合分隔 passed")
    test_parse_codes_跳過空白()
    print("✅ test_parse_codes_跳過空白 passed")
    test_parse_codes_換行分隔()
    print("✅ test_parse_codes_換行分隔 passed")
    test_parse_codes_空list()
    print("✅ test_parse_codes_空list passed")
    test_parse_codes_單一股號()
    print("✅ test_parse_codes_單一股號 passed")
    test_main_無參數_應exit_code_2()
    print("✅ test_main_無參數_應exit_code_2 passed")
    test_main_模擬對話中呼叫()
    print("✅ test_main_模擬對話中呼叫 passed")
    print("\n🎉 All CLI tests passed!")
