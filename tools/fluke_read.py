# -*- coding: utf-8 -*-
"""连接 Fluke Connect 万用表并实时显示读数。

用法：
    python tools/fluke_read.py                # 自动扫描并连接
    python tools/fluke_read.py <蓝牙地址>      # 指定地址（用 fluke_scan 得到）

按 Ctrl+C 退出。
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.fluke import FlukeClient, Reading  # noqa: E402


def show(rd: Reading) -> None:
    val = "—" if rd.value is None else f"{rd.value}"
    print(f"  读数: {rd.text:<20} 数值={val:<12} 功能={rd.function:<8} "
          f"状态={rd.state} {('(' + rd.attribute + ')') if rd.attribute else ''}")


async def main() -> None:
    cli = FlukeClient()
    addr = sys.argv[1] if len(sys.argv) > 1 else ""

    if not addr:
        print("扫描中…（请确保万用表无线已开启）")
        found = await cli.find(timeout=20)
        if not found:
            print("没找到 Fluke 设备。请先运行：python tools/fluke_scan.py")
            return
        addr, name, rssi = found[0]
        print(f"选择设备：{name} {addr} 信号{rssi}")

    await cli.connect(addr, on_reading=show, on_log=lambda m: print(m))
    print("\n正在接收读数（把表笔放到被测点上）。按 Ctrl+C 退出。\n")
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await cli.disconnect()
        print("\n已断开。")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
