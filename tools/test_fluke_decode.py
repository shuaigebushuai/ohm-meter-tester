# -*- coding: utf-8 -*-
"""用协议文档里的真实报文样本，离线验证 Fluke 解码器。

用法：python tools/test_fluke_decode.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.fluke import decode_ascii, decode_binary  # noqa: E402

# (十六进制报文, 期望文本子串)
BINARY_CASES = [
    ("0103000208220000", "76.9"),  # 76.9 °F
    ("340000c6020b0000", "-0.052"),  # -0.052 mV DC
    ("ffff7f00000c0000", None),  # 无效（无读数）
    ("ffff9f420f2d0000", "OL"),  # 超量程 OL
    ("ffff3f220b280000", None),  # 自动量程时空档
    ("881300060b2a0000", "5.000"),  # 5.000 Ω 低阻
    ("d50100040b270008", "4.69"),  # 4.69 Ω 通断，蜂鸣（短路属性）
]

ASCII_CASES = [
    ("00202020392e3220560020206463202020", "9.2 V"),  # 9.2 V DC
    ("00202020302e3720410020206463202020", "0.7 A"),  # 0.7 A DC
    ("00202020302e3075460020202020202020", "0.0uF"),  # 0.0 µF
]


def main() -> None:
    ok = 0
    bad = 0
    print("==== 二进制读数解码 ====")
    for hexstr, expect in BINARY_CASES:
        data = bytes.fromhex(hexstr)
        rd = decode_binary(data)
        if rd is None:
            print(f"  {hexstr} -> 解码失败")
            bad += 1
            continue
        good = (expect is None) or (expect in rd.text)
        ok += good
        bad += not good
        flag = "✔" if good else "✘"
        print(
            f"  {flag} {hexstr} -> 文本={rd.text!r} 数值={rd.value} "
            f"单位={rd.unit!r} 功能={rd.function!r} 状态={rd.state}"
            f"{' 属性=' + rd.attribute if rd.attribute else ''}"
        )
        if expect is not None and not good:
            print(f"      期望包含: {expect}")

    print("\n==== 文本显示解码 ====")
    for hexstr, expect in ASCII_CASES:
        data = bytes.fromhex(hexstr)
        rd = decode_ascii(data)
        text_compact = rd.text.replace(" ", "")
        good = expect.replace(" ", "") in text_compact
        ok += good
        bad += not good
        flag = "✔" if good else "✘"
        print(f"  {flag} {hexstr} -> {rd.text!r}")
        if not good:
            print(f"      期望包含: {expect}")

    print(f"\n结果：通过 {ok}，失败 {bad}")
    if bad:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
