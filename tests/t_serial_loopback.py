# -*- coding: utf-8 -*-
"""示例测试项 2：串口回环测试。

做法：用一根线把被测串口的 TX 和 RX 短接（或用回环插头），
发什么字符串就应该原样收回来，一致则 PASS。

需要安装串口库 pyserial（命令：pip install pyserial）。
如果没装，这一项会显示 ERROR 提示，不影响其它测试项。
"""
from __future__ import annotations

from core.base import Status, TestContext, TestItem, TestResult


class SerialLoopbackTest(TestItem):
    title = "串口回环测试"
    description = "短接串口 TX/RX，发送数据并校验收到的数据是否一致。"

    @classmethod
    def default_params(cls) -> dict:
        return {
            "端口": "COM1",
            "波特率": 9600,
            "发送内容": "LOOPBACK-TEST",
            "超时秒": 1,
        }

    def run(self, ctx: TestContext) -> TestResult:
        try:
            import serial  # pyserial
        except ImportError:
            return TestResult(
                Status.ERROR,
                "未安装 pyserial，请先运行命令：pip install pyserial",
            )

        port = str(self.params.get("端口", "COM1"))
        baud = int(self.params.get("波特率", 9600))
        payload = str(self.params.get("发送内容", "LOOPBACK")).encode("ascii", "ignore")
        timeout = float(self.params.get("超时秒", 1))

        try:
            with serial.Serial(port, baud, timeout=timeout) as ser:
                ser.reset_input_buffer()
                ser.write(payload)
                ser.flush()
                received = ser.read(len(payload))
        except Exception as exc:  # noqa: BLE001
            return TestResult(Status.ERROR, f"打开串口失败：{exc}")

        if received == payload:
            return TestResult(
                Status.PASS,
                f"{port} 回环正常，收到 {received!r}",
                value=received.decode("ascii", "replace"),
            )
        return TestResult(
            Status.FAIL,
            f"{port} 回环不符：发送 {payload!r}，收到 {received!r}",
            detail=f"发送 {len(payload)} 字节，收到 {len(received)} 字节",
        )
