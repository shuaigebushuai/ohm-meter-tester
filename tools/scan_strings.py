# -*- coding: utf-8 -*-
"""在二进制文件里搜索包含关键字的可打印字符串。

用法：python tools/scan_strings.py <文件> [关键字1 关键字2 ...]
"""

from __future__ import annotations

import re
import sys

DEFAULT_KW = [
    "oledb",
    "pwd",
    "password",
    "provider",
    "accdb",
    "jet",
    "dsn",
    "driver=",
    "database",
    "mscomm",
    "openport",
    "commport",
    "comport",
    "baud",
    "resist",
    "ohm",
    "select ",
    "insert into",
    "update ",
    "data source",
    "initial",
    "serial",
    "SJB",
    "DataSource",
    "SetOutput",
    "SetInput",
    "Settings",
    "COM1",
    "COM2",
    "COM3",
]


def scan(text: str, tag: str, keywords: list[str], limit: int = 300) -> None:
    found: list[str] = []
    for m in re.finditer(r"[\x20-\x7E]{5,300}", text):
        s = m.group()
        low = s.lower()
        if any(k.lower() in low for k in keywords):
            found.append(s)

    print(f"\n=== {tag}  命中 {len(found)} 条（去重前）===")
    seen: set[str] = set()
    n = 0
    for s in found:
        if s in seen:
            continue
        seen.add(s)
        n += 1
        print(f"  {s}")
        if n >= limit:
            print("  ...（已截断）")
            break


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python tools/scan_strings.py <文件> [关键字 ...]")
        return
    path = sys.argv[1]
    kw = sys.argv[2:] or DEFAULT_KW
    data = open(path, "rb").read()
    print(f"文件: {path}  大小: {len(data)} 字节")
    print(f"关键字: {kw}")

    scan(data.decode("utf-16-le", errors="ignore"), "UTF-16LE（宽字符）", kw)
    scan(data.decode("latin-1", errors="ignore"), "8位 ASCII", kw)


if __name__ == "__main__":
    main()
