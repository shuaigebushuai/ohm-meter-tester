# -*- coding: utf-8 -*-
"""扫描附近的 Fluke Connect 蓝牙设备。

用法：
    python tools/fluke_scan.py [扫描秒数]

使用前请把万用表开机，并打开它的"无线/Fluke Connect"（屏幕出现无线图标）。
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.fluke import SERVICE_READING, FlukeClient  # noqa: E402


async def main() -> None:
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0
    print(f"正在扫描 BLE 设备 {seconds:.0f} 秒 …（请开启万用表无线并靠近电脑）")

    # 先打印所有设备，方便排查
    from bleak import BleakScanner

    seen: dict[str, tuple] = {}

    def cb(device, adv) -> None:
        seen[device.address] = (device, adv)

    scanner = BleakScanner(detection_callback=cb)
    await scanner.start()
    await asyncio.sleep(seconds)
    await scanner.stop()

    print(f"\n共发现 {len(seen)} 个 BLE 设备：\n")
    target = SERVICE_READING.lower()
    flukes = []
    for addr, (dev, adv) in sorted(seen.items()):
        name = adv.local_name or dev.name or ""
        uuids = [u.lower() for u in (adv.service_uuids or [])]
        rssi = adv.rssi
        hit = target in uuids or "fluke" in name.lower() or \
            name.strip().upper().endswith("FC")
        mark = "   <===== 疑似 Fluke" if hit else ""
        print(f"  {addr}  信号={rssi:>4}  名称={name!r}")
        if uuids:
            print(f"        服务: {uuids}")
        if hit:
            flukes.append((addr, name, rssi))

    print()
    if flukes:
        print("找到疑似 Fluke 设备：")
        for a, n, r in flukes:
            print(f"  {a}  {n}  信号 {r}")
        print(f"\n下一步：python tools/fluke_read.py {flukes[0][0]}")
    else:
        print("没找到 Fluke。请确认：")
        print("  1) 万用表已开机")
        print("  2) 已打开无线/Fluke Connect（屏幕有无线图标）")
        print("  3) 电脑蓝牙已打开，距离 1 米内")
        print("  4) 没有被手机 Fluke Connect App 占用（先关掉手机 App）")


if __name__ == "__main__":
    asyncio.run(main())
