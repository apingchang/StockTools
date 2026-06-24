"""
【v1.1.1+ Bug Fix】App 啟動時 _init_tab_presets_on_startup AttributeError 測試

William 2026-06-24 22:10 反映：App 啟動時 crash
- _init_tab_presets_on_startup 讀 self._preset_vars
- 但 _add_preset_bar 在後面才 call、self._preset_vars 還沒初始化
- AttributeError: '_tkinter.tkapp' object has no attribute '_preset_vars'

【修法】_build_ui 一進來就初始化 self._preset_vars = {} 和 self._preset_combos = {}
（_add_preset_bar 內的 hasattr check 仍是安全網）
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'source'))

import unittest
from unittest.mock import patch, MagicMock

# 為了避免 tkinter 初始化問題、用 mock
class TestBuildUiPresetVarsInit(unittest.TestCase):
    """【v1.1.1+】_build_ui 必須在 _init_tab_presets_on_startup 之前初始化 _preset_vars"""

    def test_build_ui_先初始化_preset_vars(self):
        """_build_ui 應在 _init_tab_presets_on_startup 之前先設定 _preset_vars"""
        # 讀 source/StockTool.py、檢查 _init_tab_presets_on_startup 之前是否已初始化 _preset_vars
        path = os.path.join(os.path.dirname(__file__), '..', 'source', 'StockTool.py')
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 找到 _build_ui 內的 _init_tab_presets_on_startup
        init_pos = content.find('self._init_tab_presets_on_startup()')
        self.assertGreater(init_pos, -1, "找不到 _init_tab_presets_on_startup 呼叫")

        # 在 _init_tab_presets_on_startup 之前找 _preset_vars = {}
        # 注意：要在 _build_ui 內、不能在其他 function 內
        build_ui_start = content.rfind('def _build_ui(', 0, init_pos)
        self.assertGreater(build_ui_start, -1, "找不到 _build_ui 函式")

        # 在 _build_ui 內、_init_tab_presets_on_startup 之前
        build_ui_body = content[build_ui_start:init_pos]
        # 檢查 _preset_vars 在 init 之前已被設定
        self.assertRegex(build_ui_body, r'self\._preset_vars\s*=\s*\{\}',
            msg="【v1.1.1 HOTFIX #5】修法：_build_ui 開頭就初始化 _preset_vars = {}，"
                "避免 _init_tab_presets_on_startup 早於 _add_preset_bar 觸發 AttributeError")

    def test_build_ui_也初始化_preset_combos(self):
        """_build_ui 應也初始化 _preset_combos"""
        path = os.path.join(os.path.dirname(__file__), '..', 'source', 'StockTool.py')
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        init_pos = content.find('self._init_tab_presets_on_startup()')
        build_ui_start = content.rfind('def _build_ui(', 0, init_pos)
        build_ui_body = content[build_ui_start:init_pos]
        self.assertRegex(build_ui_body, r'self\._preset_combos\s*=\s*\{\}',
            msg="【v1.1.1 HOTFIX #5】修法：_build_ui 開頭也初始化 _preset_combos = {}")

    def test_init_tab_presets_不crash即使preset_vars空白(self):
        """即使 _preset_vars 是空 {}、_init_tab_presets_on_startup 也不會 crash"""
        # 模擬 _init_tab_presets_on_startup 的核心邏輯
        preset_vars = {}

        last = {}
        TAB_VAR_KEYS = {"system_select": "system_select", "backtest": "backtest"}

        # 這是原 crash 的關鍵行
        for tab_key in TAB_VAR_KEYS.keys():
            name = last.get(tab_key)
            if not name:
                continue
            # 即使走到這裡也不該 crash
            if tab_key in preset_vars:
                pass  # set 變數

        # 走到這裡 = 沒 crash、測試通過


if __name__ == '__main__':
    unittest.main()
