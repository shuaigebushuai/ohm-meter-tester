# -*- coding: utf-8 -*-
"""图形界面主程序（Tkinter，Python 自带，无需安装）。"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import List, Optional, Tuple

from core import report
from core.base import Status, TestItem, TestResult
from core.engine import TestEngine
from core.registry import discover

CHECKED = "☑"
UNCHECKED = "☐"

# 不同状态用不同颜色显示
STATUS_COLORS = {
    Status.PASS.value: "#137333",
    Status.FAIL.value: "#c5221f",
    Status.ERROR.value: "#b06000",
    Status.SKIP.value: "#666666",
    Status.INFO.value: "#1a73e8",
}


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("工业主板测试平台")
        self.geometry("1000x660")
        self.minsize(840, 540)

        self.items: List[TestItem] = []
        self.results: List[Tuple[TestItem, TestResult, float]] = []
        self.log_lines: List[str] = []
        self.events: "queue.Queue[tuple]" = queue.Queue()
        self.engine: Optional[TestEngine] = None
        self.worker: Optional[threading.Thread] = None

        self._build_ui()
        self._load_tests()
        self.after(80, self._pump_events)

    # ------------------------------------------------------------------ 界面
    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self, padding=(8, 6))
        toolbar.pack(fill="x")

        ttk.Button(toolbar, text="全选", command=lambda: self._set_all(True)).pack(side="left")
        ttk.Button(toolbar, text="全不选", command=lambda: self._set_all(False)).pack(
            side="left", padx=(4, 0)
        )
        ttk.Button(toolbar, text="设置参数", command=self._edit_params).pack(side="left", padx=(4, 0))

        self.btn_run = ttk.Button(toolbar, text="▶ 开始测试", command=self._start)
        self.btn_run.pack(side="left", padx=(14, 0))
        self.btn_stop = ttk.Button(toolbar, text="■ 停止", command=self._stop, state="disabled")
        self.btn_stop.pack(side="left", padx=(4, 0))

        ttk.Button(toolbar, text="导出报告", command=self._export).pack(side="right")

        paned = ttk.Panedwindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # ---- 左侧：测试项列表 ----
        left = ttk.Labelframe(paned, text=" 测试项（点击「选择」列勾选，双击可改参数） ", padding=6)
        self.tree_tests = ttk.Treeview(left, columns=("sel", "name"), show="headings", height=18)
        self.tree_tests.heading("sel", text="选择")
        self.tree_tests.heading("name", text="测试项")
        self.tree_tests.column("sel", width=54, anchor="center", stretch=False)
        self.tree_tests.column("name", width=250, anchor="w")
        self.tree_tests.pack(fill="both", expand=True)
        self.tree_tests.bind("<Button-1>", self._on_test_click)
        self.tree_tests.bind("<Double-1>", self._on_test_double_click)
        paned.add(left, weight=1)

        # ---- 右侧：结果 + 日志 ----
        right = ttk.Frame(paned)
        paned.add(right, weight=3)

        ttk.Label(right, text="测试结果", font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w")
        cols = ("name", "status", "message", "elapsed")
        self.tree_result = ttk.Treeview(right, columns=cols, show="headings", height=11)
        for col, text, w in [
            ("name", "测试项", 220),
            ("status", "状态", 70),
            ("message", "信息", 320),
            ("elapsed", "耗时", 70),
        ]:
            self.tree_result.heading(col, text=text)
            self.tree_result.column(col, width=w, anchor="w")
        self.tree_result.pack(fill="both", expand=True, pady=(4, 8))
        for status_value, color in STATUS_COLORS.items():
            self.tree_result.tag_configure(status_value, foreground=color)

        ttk.Label(right, text="运行日志", font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w")
        self.txt_log = tk.Text(right, height=8, wrap="none", state="disabled",
                               font=("Consolas", 9))
        self.txt_log.pack(fill="both", expand=True)

        self.status = ttk.Label(self, text="就绪", anchor="w", relief="sunken", padding=(6, 3))
        self.status.pack(fill="x", side="bottom")

    # ------------------------------------------------------------------ 数据
    def _load_tests(self) -> None:
        try:
            classes = discover("tests")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("加载失败", f"无法加载测试项：\n{exc}")
            classes = []

        self.items = [cls() for cls in classes]
        for i, item in enumerate(self.items):
            # 默认全部勾选
            item.selected = True
            self.tree_tests.insert("", "end", iid=str(i), values=(CHECKED, item.title))

        if not self.items:
            messagebox.showwarning(
                "没有测试项",
                "在 tests 文件夹里还没有可用的测试项。\n请把测试项文件放进去。",
            )

    def _selected_index(self) -> Optional[int]:
        sel = self.tree_tests.selection()
        if not sel:
            return None
        return int(sel[0])

    # ------------------------------------------------------------------ 交互
    def _on_test_click(self, event) -> None:
        row = self.tree_tests.identify_row(event.y)
        col = self.tree_tests.identify_column(event.x)
        if not row or col != "#1":  # 只有点"选择"列才切换勾选
            return
        item = self.items[int(row)]
        item.selected = not item.selected
        self.tree_tests.set(row, "sel", CHECKED if item.selected else UNCHECKED)

    def _on_test_double_click(self, event) -> None:
        row = self.tree_tests.identify_row(event.y)
        if row:
            self.tree_tests.selection_set(row)
            self._edit_params()

    def _set_all(self, value: bool) -> None:
        for i, item in enumerate(self.items):
            item.selected = value
            self.tree_tests.set(str(i), "sel", CHECKED if value else UNCHECKED)

    def _edit_params(self) -> None:
        idx = self._selected_index()
        if idx is None:
            messagebox.showinfo("提示", "请先在左侧选择一个测试项。")
            return
        ParamsDialog(self, self.items[idx])

    # ------------------------------------------------------------------ 运行
    def _start(self) -> None:
        if self.worker and self.worker.is_alive():
            return

        chosen = [it for it in self.items if it.selected]
        if not chosen:
            messagebox.showinfo("提示", "请至少勾选一个测试项。")
            return

        self.results.clear()
        self.log_lines.clear()
        for row in self.tree_result.get_children():
            self.tree_result.delete(row)
        self._clear_log()

        self._set_running(True)
        self.status.config(text=f"正在测试… 共 {len(chosen)} 项")

        self.engine = TestEngine(chosen)
        self.worker = threading.Thread(target=self._run_worker, daemon=True)
        self.worker.start()

    def _run_worker(self) -> None:
        assert self.engine is not None
        self.engine.run_all(
            on_result=lambda item, res, el: self.events.put(("result", item, res, el)),
            on_log=lambda msg: self.events.put(("log", msg)),
            should_stop=lambda: self.engine.is_stopped,
        )
        self.events.put(("done", None))

    def _stop(self) -> None:
        if self.engine:
            self.engine.stop()
        self.status.config(text="正在停止…（当前项跑完后结束）")

    # 把工作线程发来的事件取出来，更新界面（Tkinter 要求界面操作在主线程）
    def _pump_events(self) -> None:
        try:
            while True:
                self._handle_event(self.events.get_nowait())
        except queue.Empty:
            pass
        self.after(80, self._pump_events)

    def _handle_event(self, evt: tuple) -> None:
        kind = evt[0]
        if kind == "log":
            self._append_log(evt[1])
        elif kind == "result":
            _, item, result, elapsed = evt
            self.results.append((item, result, elapsed))
            self.tree_result.insert(
                "", "end",
                values=(item.title, result.status.value, result.message, f"{elapsed:.2f}s"),
                tags=(result.status.value,),
            )
        elif kind == "done":
            self._set_running(False)
            passed = sum(1 for _, r, _ in self.results if r.status is Status.PASS)
            bad = sum(1 for _, r, _ in self.results if r.status in (Status.FAIL, Status.ERROR))
            self.status.config(
                text=f"完成：共 {len(self.results)} 项，合格 {passed}，不合格/错误 {bad}"
            )

    # ------------------------------------------------------------------ 日志/状态
    def _append_log(self, msg: str) -> None:
        self.log_lines.append(msg)
        self.txt_log.config(state="normal")
        self.txt_log.insert("end", msg + "\n")
        self.txt_log.see("end")
        self.txt_log.config(state="disabled")

    def _clear_log(self) -> None:
        self.txt_log.config(state="normal")
        self.txt_log.delete("1.0", "end")
        self.txt_log.config(state="disabled")

    def _set_running(self, running: bool) -> None:
        self.btn_run.config(state="disabled" if running else "normal")
        self.btn_stop.config(state="normal" if running else "disabled")

    # ------------------------------------------------------------------ 导出
    def _export(self) -> None:
        if not self.results:
            messagebox.showinfo("提示", "还没有测试结果可以导出。")
            return
        path = filedialog.asksaveasfilename(
            title="保存测试报告",
            defaultextension=".csv",
            initialfile=f"测试报告_{report.now_stamp()}.csv",
            filetypes=[("CSV 表格", "*.csv"), ("所有文件", "*.*")],
        )
        if not path:
            return
        report.export_csv(path, self.results)
        log_path = path.rsplit(".", 1)[0] + ".log"
        report.export_log(log_path, self.log_lines)
        messagebox.showinfo("导出成功", f"报告已保存：\n{path}\n\n日志已保存：\n{log_path}")


class ParamsDialog(tk.Toplevel):
    """编辑某个测试项参数的对话框。"""

    def __init__(self, master: tk.Misc, item: TestItem) -> None:
        super().__init__(master)
        self.item = item
        self.title(f"设置参数 - {item.title}")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        if item.description:
            ttk.Label(frm, text=item.description, wraplength=380, foreground="#555").grid(
                row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
            )

        self.entries = {}
        for r, (key, val) in enumerate(item.params.items(), start=1):
            ttk.Label(frm, text=str(key)).grid(row=r, column=0, sticky="w", pady=3, padx=(0, 10))
            ent = ttk.Entry(frm, width=30)
            ent.insert(0, str(val))
            ent.grid(row=r, column=1, sticky="w", pady=3)
            self.entries[key] = (ent, type(val))

        btns = ttk.Frame(frm)
        btns.grid(row=len(item.params) + 1, column=0, columnspan=2, pady=(14, 0), sticky="e")
        ttk.Button(btns, text="取消", command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(btns, text="保存", command=self._save).pack(side="right")

        self.bind("<Return>", lambda e: self._save())
        self.bind("<Escape>", lambda e: self.destroy())

        self.update_idletasks()
        self._center_on(master)

    def _center_on(self, master: tk.Misc) -> None:
        x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def _save(self) -> None:
        for key, (ent, typ) in self.entries.items():
            text = ent.get()
            try:
                if typ is int:
                    self.item.params[key] = int(text)
                elif typ is float:
                    self.item.params[key] = float(text)
                elif typ is bool:
                    self.item.params[key] = text.strip().lower() in ("1", "true", "yes", "y", "是")
                else:
                    self.item.params[key] = text
            except ValueError:
                messagebox.showerror(
                    "参数错误",
                    f"“{key}” 需要 {typ.__name__} 类型，你填的是：{text}",
                )
                return
        self.destroy()


def main() -> None:
    app = App()
    app.mainloop()
