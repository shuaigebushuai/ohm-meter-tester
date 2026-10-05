# -*- coding: utf-8 -*-
"""查看 Access (.accdb / .mdb) 数据库的结构与样例数据。

用法：
    python tools/inspect_accdb.py  H:\\阻值仪\\SJB\\Database1.accdb
"""
from __future__ import annotations

import os
import sys

import pyodbc

DRIVER = "Microsoft Access Driver (*.mdb, *.accdb)"


def connect(path: str):
    """打开数据库。密码通过环境变量 ACCDB_PWD 传入。"""
    conn_str = f"DRIVER={{{DRIVER}}};DBQ={path};"
    pwd = os.environ.get("ACCDB_PWD", "")
    if pwd:
        conn_str += f"pwd={pwd};"
    return pyodbc.connect(conn_str, autocommit=True)


def show(path: str, max_tables: int = 40, sample_rows: int = 3) -> None:
    print("=" * 70)
    print(f"文件: {path}")
    conn = connect(path)
    cur = conn.cursor()

    tables = []
    for row in cur.tables(tableType="TABLE"):
        name = row.table_name
        if name.startswith("MSys"):  # 跳过 Access 系统表
            continue
        tables.append(name)
    tables.sort()

    print(f"用户表数量: {len(tables)}  -> {tables}")

    for t in tables[:max_tables]:
        print("-" * 70)
        try:
            cols = list(cur.columns(table=t))
            col_names = [c.column_name for c in cols]
            col_types = [
                f"{c.column_name}({c.type_name}"
                + (f"/{c.column_size}" if c.column_size else "")
                + ")"
                for c in cols
            ]
            print(f"表 [{t}]  列: {col_names}")

            try:
                cur.execute(f'SELECT COUNT(*) FROM "{t}"')
                cnt = cur.fetchone()[0]
                print(f"  行数: {cnt}")
            except Exception as exc:  # noqa: BLE001
                print(f"  行数查询失败: {exc}")
                cnt = None

            if col_names:
                try:
                    cur.execute(f'SELECT TOP {sample_rows} * FROM "{t}"')
                    rows = cur.fetchmany(sample_rows)
                    for r in rows:
                        vals = list(r)
                        # 太长的值截断，避免刷屏
                        shown = [repr(v)[:40] for v in vals]
                        print(f"    {shown}")
                except Exception as exc:  # noqa: BLE001
                    print(f"  读取样例失败: {exc}")

            print(f"  字段定义: {col_types}")
        except Exception as exc:  # noqa: BLE001
            print(f"表 [{t}] 读取失败: {exc}")

    conn.close()


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python tools/inspect_accdb.py <accdb路径> [...更多文件]")
        return
    for path in sys.argv[1:]:
        try:
            show(path)
        except Exception as exc:  # noqa: BLE001
            print(f"打开失败 {path}: {exc}")
            print("  提示：确认已安装 64 位 Access 数据库驱动，且 Python 是 64 位。")


if __name__ == "__main__":
    main()
