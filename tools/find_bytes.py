# -*- coding: utf-8 -*-
"""在二进制文件里按字节精确搜索关键字（支持中文）。

用法：python tools/find_bytes.py <文件> 关键字1 关键字2 ...
每个关键字会分别用 UTF-16LE / GBK / ASCII 三种编码去匹配并计数。
"""
from __future__ import annotations

import sys


def count(hay: bytes, needle: bytes) -> int:
    n = 0
    i = hay.find(needle)
    while i != -1:
        n += 1
        i = hay.find(needle, i + 1)
    return n


def main() -> None:
    if len(sys.argv) < 3:
        print("用法: python tools/find_bytes.py <文件> 关键字1 关键字2 ...")
        return
    path = sys.argv[1]
    keys = sys.argv[2:]
    data = open(path, "rb").read()
    print(f"文件: {path}  ({len(data)} 字节)\n")

    encodings = [("UTF-16LE", "utf-16-le"), ("GBK", "gbk"), ("ASCII", "latin-1")]
    for key in keys:
        parts = []
        for tag, enc in encodings:
            try:
                c = count(data, key.encode(enc))
            except UnicodeEncodeError:
                c = 0
            if c:
                parts.append(f"{tag}={c}")
        print(f"  {'有 ' if parts else '无 '} {key!r:28} " + (", ".join(parts) if parts else ""))


if __name__ == "__main__":
    main()
