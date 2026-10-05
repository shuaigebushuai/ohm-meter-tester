# -*- coding: utf-8 -*-
"""把厂商的 Access 阻值库导入到本软件的 SQLite 数据库。

用法（可以一次传多个文件，来源标签按文件名自动判断）：
    python tools/import_accdb.py "H:\\阻值仪\\SJB\\Database1.accdb" ^
                                  "H:\\阻值仪\\SJB\\Database2.accdb"

需要环境变量 ACCDB_PWD（Access 打开密码）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pyodbc

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import db  # noqa: E402

DRIVER = "Microsoft Access Driver (*.mdb, *.accdb)"
VALID_SOURCES = {"参考", "我的", "初始"}


def label_for(stem: str) -> str:
    """根据文件名判断来源标签。Database1=用户自己的，Database2=厂商参考。"""
    s = stem.lower().strip()
    if s.endswith("1") or "database1" in s:
        return "我的"
    if s.endswith("2") or "database2" in s:
        return "参考"
    return "初始"


def open_accdb(path: str) -> pyodbc.Connection:
    conn_str = f"DRIVER={{{DRIVER}}};DBQ={path};"
    pwd = os.environ.get("ACCDB_PWD", "")
    if pwd:
        conn_str += f"pwd={pwd};"
    return pyodbc.connect(conn_str, autocommit=True)


def read_rows(path: str) -> list[tuple]:
    """从 accdb 读出所有焊盘行。"""
    conn = open_accdb(path)
    cur = conn.cursor()
    cur.execute("SELECT 序号,阻值,具体型号,芯片方位,a,b,c,d,e,f FROM Database1")
    out: list[tuple] = []
    for r in cur.fetchall():
        out.append((
            r[2],          # model 具体型号
            r[0],          # seq   序号
            r[1],          # resistance 阻值
            r[3],          # orientation 芯片方位
            r[4], r[5], r[6], r[7],   # x1,y1,x2,y2 = a,b,c,d
            r[8], r[9],    # flag_e, flag_f
        ))
    conn.close()
    return out


def main() -> None:
    paths = [p for p in sys.argv[1:] if p.strip()]
    if not paths:
        print(__doc__)
        return

    if not os.environ.get("ACCDB_PWD"):
        print("警告：没有设置环境变量 ACCDB_PWD，数据库若加密将无法打开。")

    conn = db.connect()
    total = 0
    for path in paths:
        if not os.path.exists(path):
            print(f"  [跳过] 文件不存在: {path}")
            continue
        label = label_for(Path(path).stem)
        print(f"\n读取 {path}")
        try:
            rows = read_rows(path)
        except Exception as exc:  # noqa: BLE001
            print(f"  [失败] {exc}")
            continue

        print(f"  来源标签 = {label}   读到 {len(rows)} 行")
        print("  清空旧的同来源数据…", end="")
        removed = db.clear_source(conn, label)
        print(f" 删除 {removed} 行")

        payload = [(label,) + r for r in rows]
        written = db.insert_pads(conn, payload)
        print(f"  [完成] 写入 {written} 行")
        total += written

    models = conn.execute("SELECT COUNT(DISTINCT model) FROM pads").fetchone()[0]
    total_now = conn.execute("SELECT COUNT(*) FROM pads").fetchone()[0]
    print("\n" + "=" * 60)
    print(f"合计写入: {total} 行")
    print(f"数据库总行数: {total_now}   不同型号: {models}")
    print(f"数据库文件: {db.DB_PATH}")
    conn.close()


if __name__ == "__main__":
    main()
