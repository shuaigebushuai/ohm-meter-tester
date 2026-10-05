# -*- coding: utf-8 -*-
"""测试执行引擎：按顺序执行选中的测试项，负责捕获异常、计时、回调。"""

from __future__ import annotations

import time
import traceback
from typing import Callable, List, Optional

from .base import Status, TestContext, TestItem, TestResult


class TestEngine:
    """把一组测试项按顺序跑一遍。"""

    def __init__(self, items: List[TestItem]) -> None:
        self.items = items
        self._stop = False

    def stop(self) -> None:
        """请求停止：当前测试项跑完后不再继续下一项。"""
        self._stop = True

    @property
    def is_stopped(self) -> bool:
        return self._stop

    def run_all(
        self,
        on_result: Optional[Callable[[TestItem, TestResult, float], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> None:
        """依次执行所有测试项。

        on_result: 每测完一项回调 (测试项, 结果, 耗时秒)
        on_log:    每写一条日志回调 (文本)
        should_stop: 返回 True 时提前结束
        """
        ctx = TestContext(logger=on_log)

        for index, item in enumerate(self.items, start=1):
            if (should_stop and should_stop()) or self._stop:
                if on_log:
                    on_log("已收到停止指令，终止剩余测试。")
                break

            if on_log:
                on_log(f"[{index}/{len(self.items)}] ▶ 开始：{item.title}")

            ctx.params = item.params
            start = time.perf_counter()
            try:
                item.setup(ctx)
                result = item.run(ctx)
                if not isinstance(result, TestResult):
                    result = TestResult(Status.ERROR, "测试项没有返回 TestResult")
            except Exception as exc:  # noqa: BLE001
                result = TestResult(
                    Status.ERROR,
                    f"执行异常：{exc}",
                    detail=traceback.format_exc(),
                )
            finally:
                try:
                    item.teardown(ctx)
                except Exception as exc:  # noqa: BLE001
                    if on_log:
                        on_log(f"   （清理时出错：{exc}）")

            elapsed = time.perf_counter() - start
            if on_result:
                on_result(item, result, elapsed)
            if on_log:
                on_log(f"   ↳ {result.status.value}  {result.message}  ({elapsed:.2f}s)")
