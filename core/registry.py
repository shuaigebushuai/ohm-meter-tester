# -*- coding: utf-8 -*-
"""自动发现 tests/ 目录下的所有测试项。

只要把新的测试项文件放进 tests/ 文件夹，这个函数就会自动找到它，
不需要你去改任何"清单"或"配置"。
"""
from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import List, Type

from .base import TestItem


def discover(package_name: str = "tests") -> List[Type[TestItem]]:
    """扫描包内所有模块，返回其中定义的所有 TestItem 子类。"""
    found: List[Type[TestItem]] = []
    package = importlib.import_module(package_name)
    for info in pkgutil.iter_modules(package.__path__):
        try:
            module = importlib.import_module(f"{package_name}.{info.name}")
        except Exception as exc:  # noqa: BLE001
            print(f"[警告] 跳过无法加载的测试模块 {info.name}: {exc}")
            continue
        for _, obj in inspect.getmembers(module, inspect.isclass):
            # 只收集"本模块自己定义"的 TestItem 子类，忽略 import 进来的
            if (
                issubclass(obj, TestItem)
                and obj is not TestItem
                and obj.__module__ == module.__name__
            ):
                found.append(obj)
    return found
