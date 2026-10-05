# -*- coding: utf-8 -*-
"""阻值仪主界面：选型号 → 显示点位图 → 高亮当前脚位 → 对比判定 → 保存/导出。

流程说明（给使用者）：
  1. 左上角输入关键字搜索型号，选中一个型号
  2. 中间会画出这个型号的所有脚位方框
  3. 点方框或用「上一脚/下一脚」切换；黄色=当前脚位
  4. 在右侧输入实测阻值，点「填入」得到判定结果
  5. 绿色=合格，红色=标红可疑，灰色=没有参考数据
  6. 全部测完点「保存记录」或「导出CSV」
"""
from __future__ import annotations

import csv
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from core import db, rules

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except Exception:  # noqa: BLE001
    HAS_PIL = False

FONT_UI = ("Microsoft YaHei UI", 10)
FONT_BIG = ("Microsoft YaHei UI", 26, "bold")

COL_NORMAL = "#dbe4f0"
COL_CURRENT = "#ffd400"
COL_OK = "#3fcf6b"
COL_FAIL = "#ff4438"
COL_NOREF = "#aab0ba"
COL_EDGE = "#4a5462"

SOURCE_AUTO = "自动（参考优先）"


class OhmmeterApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("阻值仪 · 点位测量")
        self.geometry("1280x800")
        self.minsize(1000, 660)

        self.conn = db.connect()
        self.model: str = ""
        self.pads: list[dict] = []
        self.current: int = -1
        self.measured: dict[int, int] = {}
        self.results: dict[int, tuple[str, str]] = {}
        self.rects: dict[int, int] = {}
        self.texts: dict[int, int] = {}
        self.scale: float = 1.0
        self.bg_image = None
        self.bg_photo = None
        self._photo_cache: dict[float, object] = {}
        self._model_names: list[str] = []

        self._build_ui()
        self._refresh_models()
        self._update_info()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        # ---- 顶部工具栏 ----
        bar = ttk.Frame(self, padding=(8, 6))
        bar.pack(fill="x")

        ttk.Label(bar, text="数据源:").pack(side="left")
        self.var_source = tk.StringVar(value=SOURCE_AUTO)
        srcs = [SOURCE_AUTO] + db.list_sources(self.conn)
        self.combo_source = ttk.Combobox(bar, values=srcs, state="readonly", width=16)
        self.combo_source.set(SOURCE_AUTO)
        self.combo_source.pack(side="left", padx=(4, 14))
        self.combo_source.bind("<<ComboboxSelected>>", lambda e: self._refresh_models())

        ttk.Label(bar, text="搜索型号:").pack(side="left")
        self.var_keyword = tk.StringVar()
        ent = ttk.Entry(bar, textvariable=self.var_keyword, width=26)
        ent.pack(side="left", padx=(4, 4))
        ent.bind("<Return>", lambda e: self._refresh_models())
        ttk.Button(bar, text="搜索", command=self._refresh_models).pack(side="left")

        ttk.Label(bar, text="  型号:").pack(side="left")
        self.combo_model = ttk.Combobox(bar, state="readonly", width=34)
        self.combo_model.pack(side="left", padx=(4, 4))
        self.combo_model.bind("<<ComboboxSelected>>", lambda e: self._on_model_selected())

        ttk.Button(bar, text="打开点位图", command=self._open_image).pack(side="left", padx=(10, 0))
        ttk.Button(bar, text="适应窗口", command=lambda: self._fit()).pack(side="left", padx=(4, 0))
        ttk.Button(bar, text="放大", command=lambda: self._zoom(1.25)).pack(side="left", padx=(4, 0))
        ttk.Button(bar, text="缩小", command=lambda: self._zoom(0.8)).pack(side="left", padx=(4, 0))

        # ---- 中间：左图右信息 ----
        paned = ttk.Panedwindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        # 左：点位图画布
        left = ttk.Labelframe(paned, text=" 点位图（点方框选脚位）", padding=4)
        paned.add(left, weight=3)
        cf = ttk.Frame(left)
        cf.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(cf, bg="#1e222b", highlightthickness=0,
                                cursor="hand2")
        vsb = ttk.Scrollbar(cf, orient="vertical", command=self.canvas.yview)
        hsb = ttk.Scrollbar(cf, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        cf.rowconfigure(0, weight=1)
        cf.columnconfigure(0, weight=1)
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Button-4>", lambda e: self._zoom(1.15))
        self.canvas.bind("<Button-5>", lambda e: self._zoom(0.87))

        legend = ttk.Frame(left)
        legend.pack(fill="x", pady=(4, 0))
        for text, color in [("当前", COL_CURRENT), ("合格", COL_OK),
                            ("标红", COL_FAIL), ("无参考", COL_NOREF),
                            ("待测", COL_NORMAL)]:
            lb = tk.Canvas(legend, width=16, height=16, bg="white",
                           highlightthickness=0)
            lb.create_rectangle(0, 0, 15, 15, fill=color, outline="#333")
            lb.pack(side="left", padx=(0, 3))
            ttk.Label(legend, text=text).pack(side="left", padx=(0, 10))

        # 右：信息与操作
        right = ttk.Frame(paned)
        paned.add(right, weight=2)

        info = ttk.LabelFrame(right, text=" 当前脚位 ", padding=10)
        info.pack(fill="x")
        ttk.Label(info, text="序号", font=FONT_UI).grid(row=0, column=0, sticky="w")
        self.lbl_seq = ttk.Label(info, text="—", font=FONT_BIG, foreground="#000")
        self.lbl_seq.grid(row=1, column=0, sticky="w")

        ttk.Label(info, text="参考阻值", font=FONT_UI).grid(row=0, column=1,
                                                           sticky="w", padx=(18, 0))
        self.lbl_ref = ttk.Label(info, text="—", font=FONT_BIG, foreground="#0a6")
        self.lbl_ref.grid(row=1, column=1, sticky="w", padx=(18, 0))

        ttk.Label(info, text="实测阻值(Ω)", font=FONT_UI).grid(row=2, column=0,
                                                              sticky="w", pady=(8, 0))
        f = ttk.Frame(info)
        f.grid(row=3, column=0, columnspan=2, sticky="w", pady=(2, 0))
        self.var_measured = tk.StringVar()
        ttk.Entry(f, textvariable=self.var_measured, width=10, font=FONT_UI).pack(side="left")
        ttk.Button(f, text="填入", command=self._fill_measured).pack(side="left", padx=(5, 0))
        ttk.Button(f, text="清除本脚", command=self._clear_one).pack(side="left", padx=(5, 0))

        ttk.Label(info, text="容差 ±%", font=FONT_UI).grid(row=2, column=1,
                                                           sticky="w", padx=(18, 0))
        self.var_tol = tk.IntVar(value=30)
        ttk.Spinbox(info, from_=1, to=200, textvariable=self.var_tol, width=6,
                    command=self._rejudge).grid(row=3, column=1, sticky="w",
                                                padx=(18, 0), pady=(2, 0))

        self.lbl_result = ttk.Label(info, text="—", font=("Microsoft YaHei UI", 20, "bold"))
        self.lbl_result.grid(row=4, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.lbl_detail = ttk.Label(info, text="", foreground="#555", wraplength=320)
        self.lbl_detail.grid(row=5, column=0, columnspan=2, sticky="w")

        # 按钮
        btns = ttk.Frame(right, padding=(0, 8, 0, 0))
        btns.pack(fill="x")
        ttk.Button(btns, text="◀ 上一脚",
                   command=lambda: self._step(-1)).pack(side="left")
        ttk.Button(btns, text="下一脚 ▶",
                   command=lambda: self._step(1)).pack(side="left", padx=(4, 0))
        ttk.Button(btns, text="填入并跳到下一脚",
                   command=self._fill_and_next).pack(side="left", padx=(4, 0))

        btns2 = ttk.Frame(right, padding=(0, 6, 0, 0))
        btns2.pack(fill="x")
        ttk.Button(btns2, text="保存记录", command=self._save).pack(side="left")
        ttk.Button(btns2, text="导出CSV", command=self._export).pack(side="left", padx=(4, 0))
        ttk.Button(btns2, text="清除全部记录",
                   command=self._clear_all).pack(side="left", padx=(4, 0))

        btns3 = ttk.Frame(right, padding=(0, 6, 0, 0))
        btns3.pack(fill="x")
        ttk.Button(btns3, text="生成演示数据（无硬件时预览标红效果）",
                   command=self._demo_fill).pack(side="left")

        # 结果表
        self.tree = ttk.Treeview(right, columns=("seq", "ref", "mea", "res", "msg"),
                                 show="headings", height=14)
        for col, text, w, anchor in [("seq", "序号", 54, "center"),
                                     ("ref", "参考", 76, "e"),
                                     ("mea", "实测", 76, "e"),
                                     ("res", "结果", 62, "center"),
                                     ("msg", "说明", 176, "w")]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=w, anchor=anchor)
        self.tree.pack(fill="both", expand=True, pady=(8, 0))
        self.tree.tag_configure("PASS", foreground="#137333")
        self.tree.tag_configure("FAIL", foreground="#c5221f")
        self.tree.tag_configure("NOREF", foreground="#8a8f98")
        self.tree.bind("<Double-1>", self._on_tree_dbl)

        # ---- 状态栏 ----
        self.status = ttk.Label(self, anchor="w", relief="sunken", padding=(6, 3))
        self.status.pack(fill="x", side="bottom")
        self._set_status("就绪。先搜索并选择一个型号。")

    # ------------------------------------------------------------- 型号列表
    def _refresh_models(self) -> None:
        src = self.var_source.get()
        kw = self.var_keyword.get().strip()
        source = None if src == SOURCE_AUTO else src
        items = db.list_models(self.conn, source, kw)
        self._model_names = [m["model"] for m in items]
        shown = [f"{m['model']}  ({m['cnt']}脚)" for m in items[:800]]
        self.combo_model["values"] = shown
        if len(items) > 800:
            self._set_status(f"匹配 {len(items)} 个型号，列表只显示前 800 个，请加关键字缩小范围。")
        else:
            self._set_status(f"匹配 {len(items)} 个型号。选一个开始测量。")

    def _on_model_selected(self) -> None:
        idx = self.combo_model.current()
        if idx < 0 or idx >= len(self._model_names):
            return
        self._load_model(self._model_names[idx])

    # ------------------------------------------------------------- 加载型号
    def _load_model(self, model: str) -> None:
        src = self.var_source.get()
        source = None if src == SOURCE_AUTO else src
        self.model = model
        self.pads = db.get_pads(self.conn, source, model)
        self.current = -1
        self.measured.clear()
        self.results.clear()
        self._rebuild_tree()
        self._redraw()
        if self.pads:
            self._select_index(0)
        self._update_info()
        self._set_status(
            f"已加载【{model}】，共 {len(self.pads)} 个脚位。"
            + ("" if HAS_PIL else "（未安装 Pillow，无法打开 JPG 点位图）")
        )

    def _rebuild_tree(self) -> None:
        t = self.tree
        for r in t.get_children():
            t.delete(r)
        for i, p in enumerate(self.pads):
            t.insert("", "end", iid=str(i),
                     values=(p["seq"], rules.fmt_ohm(p["resistance"]), "", "", ""))

    # ------------------------------------------------------------- 画布
    def _zoom(self, factor: float) -> None:
        self.scale = max(0.15, min(6.0, self.scale * factor))
        self._redraw()

    def _fit(self) -> None:
        if not self.pads:
            return
        w = max((p["x2"] or 0) for p in self.pads)
        h = max((p["y2"] or 0) for p in self.pads)
        if self.bg_image is not None:
            w = max(w, self.bg_image.width)
            h = max(h, self.bg_image.height)
        cw = max(self.canvas.winfo_width(), 200)
        ch = max(self.canvas.winfo_height(), 200)
        if w and h:
            self.scale = max(0.15, min(6.0, min(cw / w, ch / h)))
        self._redraw()

    def _on_wheel(self, event) -> None:
        if event.state & 0x0004:  # Ctrl：缩放
            self._zoom(1.15 if event.delta > 0 else 0.87)
        else:                     # 普通：滚动
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def _get_scaled_photo(self):
        if self.bg_image is None:
            return None
        s = self.scale
        if s in self._photo_cache:
            return self._photo_cache[s]
        w = max(1, int(self.bg_image.width * s))
        h = max(1, int(self.bg_image.height * s))
        photo = ImageTk.PhotoImage(self.bg_image.resize((w, h), Image.LANCZOS))
        self._photo_cache[s] = photo
        return photo

    def _redraw(self) -> None:
        c = self.canvas
        c.delete("all")
        self.rects.clear()
        self.texts.clear()
        if not self.pads:
            c.configure(scrollregion=(0, 0, 10, 10))
            return

        s = self.scale
        max_x = max((p["x2"] or 0) for p in self.pads)
        max_y = max((p["y2"] or 0) for p in self.pads)
        if self.bg_image is not None:
            max_x = max(max_x, self.bg_image.width)
            max_y = max(max_y, self.bg_image.height)

        if self.bg_image is not None:
            photo = self._get_scaled_photo()
            if photo:
                self.bg_photo = photo
                c.create_image(0, 0, image=photo, anchor="nw")

        for i, p in enumerate(self.pads):
            x1 = (p["x1"] or 0) * s
            y1 = (p["y1"] or 0) * s
            x2 = (p["x2"] or 0) * s
            y2 = (p["y2"] or 0) * s
            if x2 <= x1:
                x2 = x1 + 4 * s
            if y2 <= y1:
                y2 = y1 + 4 * s
            rect = c.create_rectangle(
                x1, y1, x2, y2, width=1.4, outline=COL_EDGE)
            c.tag_bind(rect, "<Button-1>",
                       lambda e, k=i: self._select_index(k))
            self.rects[i] = rect

            if (x2 - x1) >= 15 and p["seq"] is not None:
                tid = c.create_text((x1 + x2) / 2, (y1 + y2) / 2,
                                    text=str(p["seq"]), fill="#1b1f27",
                                    font=("Arial", max(6, int(8 * min(s, 1.6)))))
                c.tag_bind(tid, "<Button-1>",
                           lambda e, k=i: self._select_index(k))
                self.texts[i] = tid

        self._update_colors()
        bbox = c.bbox("all")
        if bbox:
            c.configure(scrollregion=bbox)

    def _state_of(self, i: int) -> str:
        if i == self.current:
            return "current"
        p = self.pads[i]
        res = self.results.get(p["seq"])
        if res:
            if res[0] == rules.PASS:
                return "ok"
            if res[0] == rules.FAIL:
                return "fail"
            return "norefs"
        if p["resistance"] is None:
            return "norefs"
        return "normal"

    _COLORS = {
        "current": COL_CURRENT,
        "ok": COL_OK,
        "fail": COL_FAIL,
        "norefs": COL_NOREF,
        "normal": COL_NORMAL,
    }

    def _update_colors(self) -> None:
        for i, rid in self.rects.items():
            st = self._state_of(i)
            color = self._COLORS[st]
            edge = "#101010" if st == "current" else COL_EDGE
            width = 2.6 if st == "current" else 1.4
            self.canvas.itemconfigure(rid, fill=color, outline=edge, width=width)
            self.canvas.tag_raise(rid)
        for i, tid in self.texts.items():
            self.canvas.tag_raise(tid)

    # ------------------------------------------------------------- 选择
    def _select_index(self, i: int) -> None:
        if not self.pads or i < 0 or i >= len(self.pads):
            return
        self.current = i
        self._update_colors()
        self._update_info()
        self._select_tree_row(i)
        self._scroll_to(i)
        p = self.pads[i]
        self.var_measured.set("" if p["seq"] not in self.measured
                              else str(self.measured[p["seq"]]))

    def _step(self, delta: int) -> None:
        if not self.pads:
            return
        i = self.current + delta if self.current >= 0 else 0
        i = max(0, min(len(self.pads) - 1, i))
        self._select_index(i)

    def _select_tree_row(self, i: int) -> None:
        iid = str(i)
        if self.tree.exists(iid):
            self.tree.selection_set(iid)
            self.tree.see(iid)

    def _on_tree_dbl(self, _event) -> None:
        sel = self.tree.selection()
        if sel:
            self._select_index(int(sel[0]))

    def _scroll_to(self, i: int) -> None:
        p = self.pads[i]
        s = self.scale
        cx = ((p["x1"] or 0) + (p["x2"] or 0)) / 2 * s
        cy = ((p["y1"] or 0) + (p["y2"] or 0)) / 2 * s
        bbox = self.canvas.bbox("all")
        if not bbox:
            return
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        cw = max(self.canvas.winfo_width(), 1)
        ch = max(self.canvas.winfo_height(), 1)
        if tw > cw:
            self.canvas.xview_moveto(max(0.0, min(1.0, (cx - cw / 2) / tw)))
        if th > ch:
            self.canvas.yview_moveto(max(0.0, min(1.0, (cy - ch / 2) / th)))

    # ------------------------------------------------------------- 测量/判定
    def _fill_measured(self) -> bool:
        if not self.pads or self.current < 0:
            messagebox.showinfo("提示", "请先选择一个型号和脚位。")
            return False
        text = self.var_measured.get().strip()
        if text == "":
            messagebox.showinfo("提示", "请先输入实测阻值。")
            return False
        try:
            value = int(round(float(text)))
        except ValueError:
            messagebox.showerror("输入错误", f"实测阻值要填数字，你填的是：{text}")
            return False

        seq = self.pads[self.current]["seq"]
        self.measured[seq] = value
        self._judge_one(self.current)
        self._update_tree_row(self.current)
        self._update_colors()
        self._update_info()
        return True

    def _fill_and_next(self) -> None:
        if self._fill_measured():
            self._step(1)

    def _clear_one(self) -> None:
        if self.current < 0:
            return
        seq = self.pads[self.current]["seq"]
        self.measured.pop(seq, None)
        self.results.pop(seq, None)
        self.var_measured.set("")
        self._update_tree_row(self.current)
        self._update_colors()
        self._update_info()

    def _clear_all(self) -> None:
        if not self.pads:
            return
        if not messagebox.askyesno("确认", "清除当前型号的全部实测记录？"):
            return
        self.measured.clear()
        self.results.clear()
        for i in range(len(self.pads)):
            self._update_tree_row(i)
        self._update_colors()
        self._update_info()

    def _judge_one(self, i: int) -> tuple[str, str]:
        p = self.pads[i]
        seq = p["seq"]
        ref = p["resistance"]
        mea = self.measured.get(seq)
        j = rules.judge(ref, mea, self.var_tol.get())
        self.results[seq] = (j.result, j.message)
        return j.result, j.message

    def _rejudge(self) -> None:
        if not self.pads:
            return
        for i in range(len(self.pads)):
            seq = self.pads[i]["seq"]
            if seq in self.measured:
                self._judge_one(i)
                self._update_tree_row(i)
        self._update_colors()
        self._update_info()

    def _demo_fill(self) -> None:
        """无硬件时生成演示数据：大部分合格，少部分故意跑偏以便预览标红。"""
        import random
        if not self.pads:
            return
        for i, p in enumerate(self.pads):
            ref = p["resistance"]
            if ref is None:
                continue
            roll = random.random()
            if ref == 0:
                value = 0 if roll < 0.75 else random.randint(50, 400)
            elif ref >= rules.OPEN_REFERENCE:
                value = ref if roll < 0.75 else random.randint(0, 800)
            else:
                value = int(ref * random.uniform(0.9, 1.1)) if roll < 0.75 \
                    else int(ref * random.choice([0.3, 1.8, 2.6]))
            seq = p["seq"]
            self.measured[seq] = value
            self._judge_one(i)
            self._update_tree_row(i)
        self._update_colors()
        self._update_info()
        self._set_status(f"已生成 {len(self.measured)} 条演示数据（仅用于预览标红效果）。")

    # ------------------------------------------------------------- 界面刷新
    def _update_tree_row(self, i: int) -> None:
        iid = str(i)
        if not self.tree.exists(iid):
            return
        p = self.pads[i]
        seq = p["seq"]
        ref = p["resistance"]
        mea = self.measured.get(seq)
        res = self.results.get(seq)
        tag = ""
        if res:
            tag = res[0] if res[0] in ("PASS", "FAIL", "NOREF") else ""
        self.tree.item(iid, values=(
            seq,
            rules.fmt_ohm(ref),
            "—" if mea is None else f"{mea}",
            "" if not res else {"PASS": "合格", "FAIL": "标红",
                                "NOREF": "无参考"}[res[0]],
            "" if not res else res[1],
        ), tags=(tag,) if tag else ())

    def _update_info(self) -> None:
        if not self.pads or self.current < 0:
            self.lbl_seq.configure(text="—")
            self.lbl_ref.configure(text="—")
            self.lbl_result.configure(text="—", foreground="#666")
            self.lbl_detail.configure(text="")
            self._set_status("未选择型号。")
            return
        p = self.pads[self.current]
        seq = p["seq"]
        ref = p["resistance"]
        self.lbl_seq.configure(text=str(seq))
        self.lbl_ref.configure(text=rules.fmt_ohm(ref))
        res = self.results.get(seq)
        if not res:
            self.lbl_result.configure(text="待测量", foreground="#666")
            self.lbl_detail.configure(text="输入实测阻值后点「填入」")
        else:
            kind, msg = res
            color = {"PASS": "#0a8a2a", "FAIL": "#d0021b",
                     "NOREF": "#8a8f98"}[kind]
            text = {"PASS": "合格 PASS", "FAIL": "标红 FAIL",
                    "NOREF": "无参考"}[kind]
            self.lbl_result.configure(text=text, foreground=color)
            self.lbl_detail.configure(text=msg)

        total = len(self.pads)
        done = sum(1 for p2 in self.pads if p2["seq"] in self.measured)
        ok = sum(1 for v in self.results.values() if v[0] == rules.PASS)
        bad = sum(1 for v in self.results.values() if v[0] == rules.FAIL)
        self._set_status(
            f"型号【{self.model}】  进度 {self.current + 1}/{total}"
            f"   已测 {done}   合格 {ok}   标红 {bad}"
        )

    def _set_status(self, text: str) -> None:
        self.status.configure(text="  " + text)

    # ------------------------------------------------------------- 图片
    def _open_image(self) -> None:
        if not HAS_PIL:
            messagebox.showwarning(
                "缺少组件",
                "还没有安装 Pillow 图片库。\n"
                "请在命令行运行：pip install Pillow")
            return
        path = filedialog.askopenfilename(
            title="选择点位图",
            filetypes=[("图片", "*.jpg *.jpeg *.png *.bmp *.webp"),
                       ("所有文件", "*.*")])
        if not path:
            return
        try:
            self.bg_image = Image.open(path).convert("RGB")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("打开失败", f"无法打开图片：\n{exc}")
            return
        self._photo_cache.clear()
        self.bg_photo = None
        self._redraw()
        self._set_status(f"已加载点位图：{path}")

    # ------------------------------------------------------------- 保存/导出
    def _rows_ready(self) -> list[dict]:
        out = []
        for p in self.pads:
            seq = p["seq"]
            if seq not in self.measured:
                continue
            res = self.results.get(seq, ("", ""))
            out.append({
                "序号": seq,
                "参考阻值": p["resistance"],
                "实测阻值": self.measured[seq],
                "判定": {"PASS": "合格", "FAIL": "标红", "NOREF": "无参考"}.get(
                    res[0], ""),
                "说明": res[1],
                "型号": self.model,
            })
        return out

    def _save(self) -> None:
        rows = self._rows_ready()
        if not rows:
            messagebox.showinfo("提示", "还没有可保存的测量记录。")
            return
        for r in rows:
            db.save_measurement(
                self.conn,
                source=self.var_source.get(),
                model=self.model,
                seq=r["序号"],
                reference=r["参考阻值"],
                measured=r["实测阻值"],
                result=r["判定"],
                note=r["说明"],
            )
        messagebox.showinfo("已保存", f"已保存 {len(rows)} 条测量记录。")

    def _export(self) -> None:
        rows = self._rows_ready()
        if not rows:
            messagebox.showinfo("提示", "还没有可导出的测量记录。")
            return
        path = filedialog.asksaveasfilename(
            title="导出测量结果",
            defaultextension=".csv",
            initialfile=f"{self.model}_测量结果.csv",
            filetypes=[("CSV 表格", "*.csv"), ("所有文件", "*.*")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        messagebox.showinfo("导出成功", f"已导出 {len(rows)} 条记录：\n{path}")


def main() -> None:
    app = OhmmeterApp()
    app.mainloop()
