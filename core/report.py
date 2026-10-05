# -*- coding: utf-8 -*-
"""结果导出：CSV 报告 + 文本日志。"""

from __future__ import annotations

import csv
import datetime as _dt
from typing import List, Tuple

from .base import TestItem, TestResult


def now_stamp() -> str:
    """返回形如 20260505_143000 的时间戳，用于给报告文件命名。"""
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def export_csv(path: str, rows: List[Tuple[TestItem, TestResult, float]]) -> None:
    """把测试结果导出为 CSV（Excel 可直接打开）。"""
    stamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # utf-8-sig 让 Excel 正确识别中文
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["测试项", "状态", "信息", "实测值", "耗时(秒)", "记录时间"])
        for item, result, elapsed in rows:
            writer.writerow(
                [
                    item.title,
                    result.status.value,
                    result.message,
                    "" if result.value is None else result.value,
                    f"{elapsed:.2f}",
                    stamp,
                ]
            )


def export_log(path: str, lines: List[str]) -> None:
    """把运行日志保存为文本文件。"""
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
