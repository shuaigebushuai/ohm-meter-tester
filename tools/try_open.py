# -*- coding: utf-8 -*-
"""试着用不同的连接串打开 Access 数据库，确认是不是被加了密码。

用法：python tools/try_open.py <文件路径> [...]
"""

from __future__ import annotations

import sys

import pyodbc

DRIVER = "Microsoft Access Driver (*.mdb, *.accdb)"

# 尝试几种连接方式
ATTEMPTS = [
    ("无 PWD", "DRIVER={%s};DBQ={path};" % DRIVER),
    ("PWD 为空", "DRIVER={%s};DBQ={path};PWD=;" % DRIVER),
]


def main() -> None:
    paths = sys.argv[1:]
    if not paths:
        print("用法: python tools/try_open.py <accdb路径> [...]")
        return

    for path in paths:
        print("=" * 72)
        print(f"文件: {path}")
        for label, tpl in ATTEMPTS:
            conn_str = tpl.format(path=path)
            try:
                conn = pyodbc.connect(conn_str, autocommit=True)
                cur = conn.cursor()
                tables = [
                    r.table_name
                    for r in cur.tables(tableType="TABLE")
                    if not r.table_name.startswith("MSys")
                ]
                print(f"  [{label}] 成功！表: {sorted(tables)}")
                conn.close()
            except Exception as exc:  # noqa: BLE001
                print(f"  [{label}] 失败: {exc}")


if __name__ == "__main__":
    main()
