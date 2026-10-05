# -*- coding: utf-8 -*-
"""分析阻值数据库：型号分布、标志位含义、坐标规律。

用法：
    python tools/analyze_db.py <accdb路径> [型号关键字]
密码通过环境变量 ACCDB_PWD 传入。
"""
from __future__ import annotations

import os
import sys
from collections import Counter

import pyodbc

DRIVER = "Microsoft Access Driver (*.mdb, *.accdb)"


def connect(path: str) -> pyodbc.Connection:
    conn_str = f"DRIVER={{{DRIVER}}};DBQ={path};"
    pwd = os.environ.get("ACCDB_PWD", "")
    if pwd:
        conn_str += f"pwd={pwd};"
    return pyodbc.connect(conn_str, autocommit=True)


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python tools/analyze_db.py <accdb> [型号关键字]")
        return
    path = sys.argv[1]
    kw = sys.argv[2] if len(sys.argv) > 2 else None

    conn = connect(path)
    cur = conn.cursor()
    cur.execute(
        "SELECT 编号,序号,阻值,具体型号,芯片方位,a,b,c,d,e,f FROM Database1"
    )
    rows = [tuple(r) for r in cur.fetchall()]
    print(f"总行数: {len(rows)}")

    models = Counter(r[3] for r in rows)
    print(f"\n不同【具体型号】数量: {len(models)}")
    print("前 60 个型号:")
    for name, cnt in models.most_common(60):
        print(f"   {cnt:>6}  {name}")

    print("\n【e 列】取值分布:", dict(Counter(r[9] for r in rows)))
    print("【f 列】取值分布:", dict(Counter(r[10] for r in rows)))
    print("【芯片方位】取值分布(前15):", dict(Counter(r[4] for r in rows).most_common(15)))

    # 选一个型号，逐行看 a/b/c/d 的规律（是不是坐标）
    target = None
    if kw:
        for name in models:
            if kw in str(name):
                target = name
                break
    if target is None:
        target = models.most_common(1)[0][0]
    print(f"\n===== 模型明细: {target} =====")
    sub = [r for r in rows if r[3] == target]
    sub.sort(key=lambda r: r[1])
    print(f"{'序号':>5} {'阻值':>7} {'方位':>6}  {'a':>5} {'b':>5} {'c':>5} {'d':>5} {'e':>4} {'f':>4}")
    for r in sub[:80]:
        print(f"{r[1]:>5} {str(r[2]):>7} {str(r[4]):>6}  {str(r[5]):>5} {str(r[6]):>5} {str(r[7]):>5} {str(r[8]):>5} {str(r[9]):>4} {str(r[10]):>4}")
    if len(sub) > 80:
        print(f"  ... 共 {len(sub)} 行")

    # a/c 差值与 b/d 差值的分布 -> 判断是不是矩形框
    widths = Counter()
    heights = Counter()
    for r in rows:
        try:
            widths[int(r[7]) - int(r[5])] += 1
            heights[int(r[8]) - int(r[6])] += 1
        except (TypeError, ValueError):
            pass
    print("\n(a,c) 宽度 = c-a 分布(前10):", widths.most_common(10))
    print("(b,d) 高度 = d-b 分布(前10):", heights.most_common(10))

    conn.close()


if __name__ == "__main__":
    main()
