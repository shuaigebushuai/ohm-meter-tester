# -*- coding: utf-8 -*-
"""SQLite 数据库：存放型号、焊盘坐标、阻值参考数据、测量记录。

选用 SQLite 的原因：
  - Python 自带，不用装任何东西（原版要装 Access 数据库引擎）
  - 单文件，备份方便，不会像 OCX 那样需要注册
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "ohm.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS pads (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT    NOT NULL,              -- 数据来源：参考 / 我的 / 初始
    model       TEXT    NOT NULL,              -- 具体型号（对应一张点位图/模板）
    seq         INTEGER,                       -- 序号：第几个脚位
    resistance  INTEGER,                       -- 参考阻值
    orientation TEXT,                          -- 芯片方位：左上/左下/右上/右下
    x1          INTEGER,                       -- 点位框左上角 x  (a)
    y1          INTEGER,                       -- 点位框左上角 y  (b)
    x2          INTEGER,                       -- 点位框右下角 x  (c)
    y2          INTEGER,                       -- 点位框右下角 y  (d)
    flag_e      INTEGER,                       -- 标记位 e
    flag_f      INTEGER                        -- 标记位 f
);
CREATE INDEX IF NOT EXISTS idx_pads_source  ON pads(source);
CREATE INDEX IF NOT EXISTS idx_pads_model   ON pads(model);
CREATE INDEX IF NOT EXISTS idx_pads_lookup  ON pads(source, model, seq);

CREATE TABLE IF NOT EXISTS measurements (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    time       TEXT    NOT NULL,
    source     TEXT,
    model      TEXT    NOT NULL,
    seq        INTEGER,
    reference  INTEGER,
    measured   INTEGER,
    result     TEXT,                           -- PASS / FAIL / 无参考
    note       TEXT
);
CREATE INDEX IF NOT EXISTS idx_meas_model ON measurements(model);
"""


def connect(path: Optional[Path] = None) -> sqlite3.Connection:
    """打开数据库，自动创建目录和表结构。"""
    db_path = Path(path) if path else DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


# ---------------------------------------------------------------- 查询封装
def list_sources(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT DISTINCT source FROM pads ORDER BY source").fetchall()
    return [r["source"] for r in rows]


def list_models(conn: sqlite3.Connection, source: Optional[str] = None,
                keyword: str = "") -> list[dict]:
    """列出型号及各自脚位数。keyword 用于搜索过滤。"""
    sql = ("SELECT source, model, COUNT(*) AS cnt, SUM(resistance) AS total "
           "FROM pads WHERE 1=1")
    args: list = []
    if source:
        sql += " AND source = ?"
        args.append(source)
    if keyword:
        sql += " AND model LIKE ?"
        args.append(f"%{keyword}%")
    sql += " GROUP BY source, model ORDER BY model"
    return [dict(r) for r in conn.execute(sql, args).fetchall()]


def get_pads(conn: sqlite3.Connection, source: Optional[str], model: str) -> list[dict]:
    """取出某个型号下的全部脚位，按序号排序。

    source 为 None 时代表"自动"：合并所有来源，同一序号优先取"参考"数据。
    """
    rows = conn.execute(
        "SELECT * FROM pads WHERE model=? ORDER BY seq, id",
        (model,),
    ).fetchall()

    if source:
        out = [dict(r) for r in rows if r["source"] == source]
        return out

    # 自动模式：按序号去重，参考 > 我的 > 初始
    def rank(r: sqlite3.Row) -> int:
        return {"参考": 0, "我的": 1}.get(r["source"], 2)

    best: dict[int, dict] = {}
    for r in rows:
        seq = r["seq"] if r["seq"] is not None else -1
        cur = best.get(seq)
        if cur is None or rank(r) < rank(cur):
            best[seq] = dict(r)
    return [best[k] for k in sorted(best)]


def find_reference(conn: sqlite3.Connection, model: str, seq: int,
                   source: Optional[str] = None) -> Optional[dict]:
    """查找某个脚位的参考阻值（可在多个来源之间兜底）。"""
    if source:
        row = conn.execute(
            "SELECT * FROM pads WHERE model=? AND seq=? AND source=? LIMIT 1",
            (model, seq, source),
        ).fetchone()
        if row:
            return dict(row)
    row = conn.execute(
        "SELECT * FROM pads WHERE model=? AND seq=? "
        "ORDER BY CASE source WHEN '参考' THEN 0 WHEN '我的' THEN 1 ELSE 2 END "
        "LIMIT 1",
        (model, seq),
    ).fetchone()
    return dict(row) if row else None


def save_measurement(conn: sqlite3.Connection, *, source: str, model: str,
                     seq: int, reference: Optional[int], measured: Optional[int],
                     result: str, note: str = "") -> int:
    """保存一条测量记录。"""
    cur = conn.execute(
        "INSERT INTO measurements "
        "(time, source, model, seq, reference, measured, result, note) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), source, model, seq,
         reference, measured, result, note),
    )
    conn.commit()
    return cur.lastrowid or 0


def insert_pads(conn: sqlite3.Connection, rows: Iterable[tuple]) -> int:
    """批量写入焊盘数据。rows 的字段顺序见 SQL。"""
    cur = conn.executemany(
        "INSERT INTO pads (source, model, seq, resistance, orientation, "
        "x1, y1, x2, y2, flag_e, flag_f) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    return cur.rowcount or 0


def clear_source(conn: sqlite3.Connection, source: str) -> int:
    cur = conn.execute("DELETE FROM pads WHERE source=?", (source,))
    conn.commit()
    return cur.rowcount or 0
