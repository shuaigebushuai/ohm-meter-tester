# -*- coding: utf-8 -*-
"""阻值仪界面冒烟测试：不点鼠标，程序化地走一遍完整流程。

用法：python tools/smoke_zzy.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import db, rules  # noqa: E402
from ui.ohmmeter import OhmmeterApp  # noqa: E402


def main() -> None:
    app = OhmmeterApp()
    app.update_idletasks()

    print("1) 数据源:", db.list_sources(app.conn))
    print("2) 初始型号候选数:", len(app._model_names))

    # 用真实型号做流程测试
    hits = db.list_models(app.conn, None, "真我gtneo")
    assert hits, "没有找到测试用型号"
    model = hits[0]["model"]
    print(f"3) 选中型号: {model}  ({hits[0]['cnt']} 脚)")

    app._load_model(model)
    app.update_idletasks()
    print(f"   加载焊盘数: {len(app.pads)}   画布矩形数: {len(app.rects)}")
    assert len(app.pads) > 0, "没有加载到焊盘"
    assert len(app.rects) == len(app.pads), "矩形数量与焊盘不一致"

    # 判定规则自检
    print("4) 判定规则自检:")
    for ref, mea in [(3249, 3249), (3249, 100), (0, 0), (0, 500),
                     (500, 520), (500, 100), (None, 100), (500, None)]:
        j = rules.judge(ref, mea, 30)
        print(f"   参考={ref} 实测={mea} -> {j.result:6} {j.message}")

    # 走一遍填值流程
    app._select_index(0)
    app.var_measured.set("520")
    app._fill_measured()
    print("5) 第 1 脚填 520 后判定:",
          app.results.get(app.pads[0]["seq"]))

    app._demo_fill()
    counts = Counter(v[0] for v in app.results.values())
    print("6) 演示数据判定分布:", dict(counts))
    assert len(app.results) > 0

    # 缩放 / 拟合 / 切换脚位
    app._zoom(1.5)
    app._fit()
    app._step(1)
    app._step(-1)
    app.update_idletasks()
    print("7) 缩放、拟合、前后切换均正常。当前脚位序号:",
          app.pads[app.current]["seq"])

    rows = app._rows_ready()
    print(f"8) 待保存/导出行数: {len(rows)}")
    assert rows

    # 保存入库
    saved = db.save_measurement(app.conn, source="测试", model=model,
                                seq=rows[0]["序号"],
                                reference=rows[0]["参考阻值"],
                                measured=rows[0]["实测阻值"],
                                result=rows[0]["判定"], note="smoke")
    print(f"   写入 measurements，id={saved}")
    app.conn.execute("DELETE FROM measurements WHERE note='smoke'")
    app.conn.commit()

    app.destroy()
    print("\n全部通过 ✔")


if __name__ == "__main__":
    main()
