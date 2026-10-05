# -*- coding: utf-8 -*-
"""示例测试项 1：电源电压检测（模拟数据，不需要任何真实硬件）。

它的作用是让你先看看界面跑起来是什么样。
真正使用时，只要把 _read_voltage() 换成你实际设备的读数即可
（例如换成万用表、采集卡、USB 采集模块读取的值）。
"""

from __future__ import annotations

import random
import time

from core.base import Status, TestContext, TestItem, TestResult


class PowerVoltageTest(TestItem):
    title = "电源电压检测（示例）"
    description = "检查单路电源电压是否在允许范围内。当前为模拟数据。"

    @classmethod
    def default_params(cls) -> dict:
        return {
            "标称电压": 5.0,
            "下限": 4.75,
            "上限": 5.25,
        }

    def _read_voltage(self) -> float:
        """读取电压。这里返回模拟值，真机上替换为实际读数。"""
        nominal = float(self.params.get("标称电压", 5.0))
        return round(nominal + random.uniform(-0.15, 0.15), 3)

    def run(self, ctx: TestContext) -> TestResult:
        time.sleep(0.3)  # 模拟读数需要一点点时间
        voltage = self._read_voltage()
        low = float(self.params.get("下限", 0))
        high = float(self.params.get("上限", 999))
        ok = low <= voltage <= high
        return TestResult(
            status=Status.PASS if ok else Status.FAIL,
            message=f"实测 {voltage:.3f} V（允许范围 {low} ~ {high} V）",
            value=voltage,
        )
