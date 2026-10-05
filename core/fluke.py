# -*- coding: utf-8 -*-
"""Fluke Connect 蓝牙(BLE)协议：常量与解码。

协议参考：社区逆向文档（jwanga/fluke-connect-client 的 docs/PROTOCOL.md）

  - 服务基址 UUID: B698xxxx-7562-11E2-B50D-00163E46F8FE
  - 读取服务 1800 下有两个特征：
      * 2901  文本显示  17 字节 = 1 字节格式 + 16 字节 ASCII
      * 290f  二进制读数  8 或 16 字节（主显示 + 副显示）
  - 设备信息用标准 SIG 服务 180A（型号 2A24 等）

二进制 8 字节记录的位布局（小端）：

  第 0 个字(32位):  0-20 尾数  21-24 状态  25-27 小数位
                    28-30 数量级  31 符号
  第 1 个字(32位):  0-7 单位  8-15 功能  16-22 量程
                    23-25 十进制档  26-30 属性  31 捕获标志

  显示值 = (符号) 尾数 / 10^小数位 ，再乘以数量级前缀的单位。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

BASE = "b698{:04x}-7562-11e2-b50d-00163e46f8fe"


def u16(slot: int) -> str:
    return BASE.format(slot)


# 服务/特征
SERVICE_READING = u16(0x1800)      # 读取
CHAR_ASCII = u16(0x2901)           # 文本显示
CHAR_BINARY = u16(0x290F)          # 二进制读数
SERVICE_CONNECTION = u16(0x1801)
SERVICE_UNDOC = u16(0x1805)

# 标准 SIG 设备信息服务
SERVICE_DEVINFO = "0000180a-0000-1000-8000-00805f9b34fb"
CHAR_MODEL = "00002a24-0000-1000-8000-00805f9b34fb"
CHAR_SERIAL = "00002a25-0000-1000-8000-00805f9b34fb"
CHAR_FW = "00002a26-0000-1000-8000-00805f9b34fb"
CHAR_SW = "00002a28-0000-1000-8000-00805f9b34fb"
CHAR_MFG = "00002a29-0000-1000-8000-00805f9b34fb"

MAGNITUDES = {0: "", 1: "G", 2: "M", 3: "k", 4: "m", 5: "u", 6: "n", 7: "p"}

STATES = {
    0: "正常", 1: "空白", 2: "未激活", 3: "无效", 4: "超量程(OL)",
    5: "AD过载", 6: "热电偶开路", 7: "放电", 8: "表笔", 9: "大于",
    10: "缺相", 11: "错误", 12: "小于", 13: "空",
}

UNITS = {
    0: "", 1: "V AC", 2: "V DC", 3: "A AC", 4: "A DC", 5: "Hz", 6: "%RH",
    7: "°C", 8: "°F", 9: "°R", 10: "K", 11: "Ω", 12: "S", 13: "占空%",
    14: "s", 15: "F", 16: "dB", 17: "dBm", 18: "W", 19: "J", 20: "H",
    22: "psi", 28: "bar", 29: "Pa", 33: "V AC+DC", 34: "A AC+DC",
    35: "%", 36: "V/Hz", 37: "g", 44: "TΩ",
}

FUNCTIONS = {
    0: "", 1: "mV AC", 2: "V AC", 3: "V AC+DC", 7: "V AC LoZ",
    8: "mV AC 低通", 9: "V AC 低通", 10: "uV DC", 11: "mV DC", 12: "V DC",
    13: "mA AC", 14: "A AC", 15: "A AC+DC", 19: "uA DC", 20: "mA DC",
    21: "A DC", 34: "温度", 35: "°F", 36: "°C", 37: "°R", 38: "K",
    39: "通断", 40: "电阻", 41: "电导", 42: "低阻", 43: "相位",
    44: "A AC 浪涌", 45: "电容", 46: "二极管", 47: "V/Hz",
    50: "uA AC",
}

ATTRIBUTES = {
    0: "", 1: "开路", 2: "短路", 3: "毛刺", 4: "二极管好",
    5: "下降沿", 6: "上升沿", 7: "大电流", 8: "危险电压", 9: "低阻",
}

NO_VALUE_MASK = 0x1FFFFF


@dataclass
class Reading:
    value: Optional[float]     # 数值
    text: str                  # 显示文本，如 "5.000 Ω"
    unit: str = ""
    function: str = ""
    state: str = ""
    attribute: str = ""
    negative: bool = False
    raw: bytes = b""


def decode_binary(data: bytes) -> Optional[Reading]:
    """解码二进制读数特征（8 或 16 字节，取前 8 字节主显示）。"""
    if len(data) < 8:
        return None
    w0 = int.from_bytes(data[0:4], "little")
    w1 = int.from_bytes(data[4:8], "little")

    mantissa = w0 & NO_VALUE_MASK
    state = (w0 >> 21) & 0xF
    decimals = (w0 >> 25) & 0x7
    magnitude = (w0 >> 28) & 0x7
    sign = (w0 >> 31) & 0x1

    unit_code = w1 & 0xFF
    func_code = (w1 >> 8) & 0xFF
    attribute = (w1 >> 26) & 0x1F

    unit = UNITS.get(unit_code, f"unit{unit_code}")
    func = FUNCTIONS.get(func_code, f"func{func_code}")
    state_text = STATES.get(state, f"state{state}")
    attr_text = ATTRIBUTES.get(attribute, "")

    if mantissa == NO_VALUE_MASK or state in (3, 4, 5, 11, 13):
        return Reading(None, "OL" if state == 4 else state_text,
                       unit, func, state_text, attr_text, bool(sign), bytes(data))

    value = mantissa / (10 ** decimals)
    if sign:
        value = -value
    text = f"{value:.{decimals}f} {MAGNITUDES.get(magnitude, '')}{unit}".strip()
    return Reading(value, text, unit, func, state_text, attr_text,
                   bool(sign), bytes(data))


def decode_ascii(data: bytes) -> Optional[Reading]:
    """解码文本显示特征（17 字节 = 1 格式字节 + 16 ASCII）。"""
    if len(data) < 17:
        return None
    raw = data[1:17].decode("ascii", "replace")

    def seg(a: int, b: int) -> str:
        return raw[a:b].replace("\x00", " ").strip()

    reading = seg(0, 6)
    mult = seg(6, 7)
    unit = seg(7, 11)
    acdc = seg(11, 13)
    if reading == "":
        return Reading(None, "（空）", unit, "", "", "", False, bytes(data))
    text = f"{reading} {mult}{unit}".replace("  ", " ").strip()
    if acdc:
        text += f" {acdc}"
    # 尽量把文本转成数字
    value: Optional[float] = None
    try:
        value = float(reading.replace("OL", ""))
    except ValueError:
        pass
    return Reading(value, text, unit, "", "", "", False, bytes(data))


def decode(data: bytes) -> Optional[Reading]:
    """自动判断是 ASCII 特征还是二进制特征。"""
    if len(data) == 17:
        return decode_ascii(data)
    if len(data) in (8, 16):
        return decode_binary(data)
    return None


# --------------------------------------------------------------- BLE 客户端
class FlukeClient:
    """连接 Fluke Connect 万用表并订阅读数。

    用法：
        cli = FlukeClient()
        addr = await cli.find(timeout=20)
        await cli.connect(addr, on_reading=print)
    """

    def __init__(self) -> None:
        self.client = None
        self.address: str = ""
        self.device_name: str = ""

    async def find(self, timeout: float = 20.0) -> list[tuple[str, str, int]]:
        """扫描附近的 Fluke Connect 设备，返回 [(地址, 名称, 信号强度)]。"""
        from bleak import BleakScanner

        found: dict[str, tuple[str, str, int]] = {}
        target = SERVICE_READING.lower()

        def cb(device, adv) -> None:
            name = adv.local_name or device.name or ""
            uuids = [u.lower() for u in (adv.service_uuids or [])]
            is_fluke = target in uuids or "fluke" in name.lower() \
                or name.strip().upper().endswith("FC") or "3000" in name
            if is_fluke:
                found[device.address] = (device.address, name, adv.rssi)

        scanner = BleakScanner(detection_callback=cb)
        await scanner.start()
        import asyncio
        await asyncio.sleep(timeout)
        await scanner.stop()
        return sorted(found.values(), key=lambda x: -x[2])

    async def connect(self, address: str, on_reading=None,
                      on_log=None) -> None:
        """连接并订阅读数。on_reading(Reading) 会被反复调用。"""
        from bleak import BleakClient

        def log(msg: str) -> None:
            if on_log:
                on_log(msg)

        self.address = address
        self.client = BleakClient(address, timeout=30.0)
        await self.client.connect()
        log(f"已连接 {address}")

        # 读设备信息
        for label, cuuid in [("型号", CHAR_MODEL), ("序列号", CHAR_SERIAL),
                             ("固件", CHAR_FW), ("软件", CHAR_SW),
                             ("厂商", CHAR_MFG)]:
            try:
                raw = await self.client.read_gatt_char(cuuid)
                log(f"  {label}: {raw.decode('utf-8', 'replace').strip(chr(0)).strip()}")
            except Exception:  # noqa: BLE001
                pass

        # 列出服务
        log("  GATT 服务/特征：")
        for service in self.client.services:
            log(f"    [服务] {service.uuid}")
            for ch in service.characteristics:
                log(f"        {ch.uuid}  {ch.properties}")

        def make_cb(kind: str):
            def _cb(_sender, data: bytearray) -> None:
                rd = decode(bytes(data))
                if rd and on_reading:
                    on_reading(rd)
            return _cb

        subscribed = False
        for cuuid, kind in [(CHAR_BINARY, "二进制"), (CHAR_ASCII, "文本")]:
            try:
                await self.client.start_notify(cuuid, make_cb(kind))
                log(f"  已订阅 {kind} 读数特征 {cuuid}")
                subscribed = True
            except Exception as exc:  # noqa: BLE001
                log(f"  订阅失败 {cuuid}: {exc}")
        if not subscribed:
            log("  [!] 没有订阅到任何读数特征，设备可能型号不同。")

    async def disconnect(self) -> None:
        if self.client:
            try:
                await self.client.disconnect()
            except Exception:  # noqa: BLE001
                pass
