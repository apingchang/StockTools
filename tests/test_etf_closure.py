"""【V0.9.5-etf-gui fix】closure trap 守護

2026-06-19 23:37 William 反映：
- 開 App 後 ETF 開機抓取 thread 拋例外 → NameError: cannot access free variable 'e'
- 根因：except Exception as e → self.after(0, lambda: ... str(e))
  except 區塊結束後、Python 把 e 變數釋放掉
  after 0ms 後 callback 跑時找不到 e

修法：lambda 用 default arg 鎖住變數值
  self.after(0, lambda err=str(e): self._x(None, err))
"""
import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

# 這個 test 不需要 import StockTool、純 logic 驗證


def test_closure_default_arg_locks_value():
    """【核心守護】closure default arg 能鎖住當下值、不受 except 範圍釋放影響"""

    captured = {}

    def after(ms, callback):
        captured["cb"] = callback
        # 模擬延遲 callback
        callback()

    def simulate_except_block():
        try:
            raise ValueError("simulated ETF fetch failure")
        except Exception as e:
            # 模擬我們修過的寫法：lambda err=str(e)
            after(0, lambda err=str(e): captured.__setitem__("result", err))

    simulate_except_block()
    assert captured["result"] == "simulated ETF fetch failure", (
        f"closure 沒鎖住 e、實際: {captured.get('result')!r}"
    )


def test_closure_default_arg_normal_lambda_will_fail():
    """【反向驗證】沒用 default arg 的 lambda、except 結束後會 NameError"""

    captured = {}

    def after(ms, callback):
        # 不立刻呼叫、模擬 after(0, ...) 延遲
        captured["cb"] = callback

    def simulate_except_block():
        try:
            raise ValueError("test failure")
        except Exception as e:
            # 沒用 default arg 的寫法 → bug
            def _bad_cb():
                captured["result"] = str(e)
            after(0, _bad_cb)

    simulate_except_block()
    # 現在模擬 after 真正 callback（except 區塊已結束、e 被釋放）
    try:
        captured["cb"]()
        raised = None
    except NameError as ex:
        raised = ex

    assert raised is not None and "free variable" in str(raised), (
        f"沒鎖住 e 的 lambda 應該 raise NameError、實際: {raised!r}"
    )


def test_dataclass_arg_locks_agg_df():
    """【核心守護】agg_df/long_df 等 DataFrame 也用 default arg 鎖住"""

    import pandas as pd

    captured = {}

    def after(ms, callback):
        captured["cb"] = callback

    # 模擬 worker 結尾
    agg_df = pd.DataFrame({"a": [1, 2, 3]})
    long_df = pd.DataFrame({"b": [4, 5, 6]})

    # 修過的寫法
    after(0, lambda a=agg_df, l=long_df: captured.update(a=a, l=l))

    captured["cb"]()
    import pandas.testing as pdt
    pdt.assert_frame_equal(captured["a"], agg_df)
    pdt.assert_frame_equal(captured["l"], long_df)