# -*- coding: utf-8 -*-
"""测试框架的基础定义：测试项基类、结果、上下文。

要新增一个测试项，只写一个类继承 TestItem，然后实现 run() 方法即可。
框架会自动发现它，并出现在界面列表里。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class Status(str, Enum):
    """测试结果状态。"""

    PASS = "PASS"  # 合格
    FAIL = "FAIL"  # 不合格
    SKIP = "SKIP"  # 跳过
    ERROR = "ERROR"  # 执行出错（例如设备没连上、参数不对）
    INFO = "INFO"  # 仅提示，不做合格判定


@dataclass
class TestResult:
    """一个测试项跑完后返回的结果。"""

    status: Status
    message: str = ""  # 一行说明，会显示在结果表里
    value: Any = None  # 实测值（可选），会写入报告
    detail: str = ""  # 详细内容（可选），例如异常堆栈


@dataclass
class TestContext:
    """测试运行时共享的上下文。"""

    params: dict = field(default_factory=dict)
    logger: Optional[Callable[[str], None]] = None

    def log(self, msg: str) -> None:
        """写一行运行日志（会显示在界面右下角）。"""
        if self.logger is not None:
            self.logger(msg)


class TestItem:
    """所有测试项的基类。"""

    #: 显示在界面上的名称
    title: str = "未命名测试"
    #: 一句话说明这个测试项做什么
    description: str = ""

    def __init__(self) -> None:
        # 参数可以在界面上通过"设置参数"修改
        self.params: dict = dict(self.default_params())
        # 是否被勾选（由界面控制）
        self.selected: bool = True

    @classmethod
    def default_params(cls) -> dict:
        """返回默认参数。子类可覆盖，例如：
        return {"端口": "COM3", "上限": 5.25}
        """
        return {}

    def setup(self, ctx: TestContext) -> None:
        """测试前的准备工作（如打开串口、上电）。可选实现。"""

    def run(self, ctx: TestContext) -> TestResult:
        """执行测试，必须返回一个 TestResult。子类必须实现。"""
        raise NotImplementedError

    def teardown(self, ctx: TestContext) -> None:
        """测试后的清理工作（如关闭串口、断电）。可选实现。"""
