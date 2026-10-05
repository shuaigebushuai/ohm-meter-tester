# -*- coding: utf-8 -*-
"""阻值判定规则：参考值 vs 实测值 -> PASS / FAIL / 无参考。

从数据观察到的规律（来自厂商参考库）：
  - 阻值 = 0        → 该点是接地/短路点，实测也应接近 0
  - 阻值 ~3200 左右 → 明显是万用表的"开路/OL"读数，实测也应是开路
  - 其它           → 按容差百分比比较
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# 阻值大于等于该值视为"开路"（厂商库里的读数上限大约 3249）
OPEN_REFERENCE = 3000
# 参考是短路点时，实测不超过该值算通过
SHORT_LIMIT = 10
# 参考是开路点时，实测不小于该值算通过
OPEN_MEASURED_MIN = 2500

PASS = "PASS"
FAIL = "FAIL"
NO_REF = "NOREF"


@dataclass
class Judge:
    result: str  # PASS / FAIL / NOREF
    message: str  # 给人看的一句话
    detail: str = ""


def fmt_ohm(value: Optional[int]) -> str:
    if value is None:
        return "—"
    return f"{value} Ω"


def judge(reference: Optional[int], measured: Optional[int], tol_percent: int = 30) -> Judge:
    """对比参考阻值与实测阻值。"""
    if measured is None:
        return Judge(NO_REF, "尚未测得数值")

    if reference is None:
        return Judge(NO_REF, "该脚位没有参考数据")

    # 参考值是开路点
    if reference >= OPEN_REFERENCE:
        if measured >= OPEN_MEASURED_MIN:
            return Judge(PASS, "开路点，实测亦为开路")
        return Judge(FAIL, f"参考为开路，实测却只有 {measured} Ω（可能短路/漏电）")

    # 参考值是短路点
    if reference == 0:
        if measured <= SHORT_LIMIT:
            return Judge(PASS, "短路点，实测正常")
        return Judge(FAIL, f"参考为 0 Ω，实测 {measured} Ω（该点不通）")

    # 普通点：按容差比较
    low = reference * (100 - tol_percent) / 100
    high = reference * (100 + tol_percent) / 100
    if low <= measured <= high:
        return Judge(PASS, f"{measured} Ω 在 {reference} Ω ±{tol_percent}% 内")
    return Judge(
        FAIL,
        f"实测 {measured} Ω，参考 {reference} Ω（允许 {low:.0f}~{high:.0f}）",
        detail=f"偏 {'高' if measured > high else '低'} "
        f"{abs(measured - reference) / max(reference, 1) * 100:.0f}%",
    )
