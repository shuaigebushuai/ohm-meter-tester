# AGENTS.md

给 AI 编码助手（OpenCode 等）看的项目说明。请先读本文件，再动手改代码。

## 项目是什么

一个面向**电子维修工程师**的桌面工具，包含两个独立程序：

| 程序 | 入口 | 作用 |
|---|---|---|
| 阻值仪 | `main_zzy.py` → `ui/ohmmeter.py` | 主力：选型号 → 点位图 → 测阻值 → 自动对比标红 → 保存/导出 |
| 通用测试平台 | `main.py` → `ui/app.py` | 模块化测试框架（串口/电压/接口…），测试项自动发现 |

- 语言：**Python 3.14**，界面用 **Tkinter**（标准库，无需安装）
- 全部界面文本、注释、文档均为**简体中文**
- 运行平台：**Windows**（有中文路径）

## 运行方式

```sh
python main_zzy.py     # 阻值仪
python main.py         # 通用测试平台
```

依赖见 `requirements.txt`：`pyserial`、`Pillow`、`pyodbc`、`bleak`（都是可选增强，缺了会降级/提示）。

## 目录结构

```
core/                 共用内核
  db.py               SQLite 读写（型号/脚位/参考阻值/测量记录）
  rules.py            阻值判定规则（PASS/FAIL/NOREF）
  fluke.py            Fluke Connect 蓝牙(BLE)协议解码 + 客户端
  base.py             测试平台基类：TestItem / TestResult / TestContext / Status
  engine.py           测试执行引擎（顺序执行、异常捕获、回调）
  registry.py         自动发现 tests/ 下的 TestItem 子类
  report.py           CSV / 日志导出
ui/
  ohmmeter.py         阻值仪界面（主力，最大文件）
  app.py              通用测试平台界面（含参数对话框）
tests/                测试平台的“测试项”，放进去自动被发现
tools/                维护/导入/分析用的一次性小工具
data/ohm.db           SQLite 数据库（厂商数据 + 用户数据，约 29MB）
```

## 关键约定（改代码时请遵守）

1. **风格**：每个文件顶部 `# -*- coding: utf-8 -*-`；`from __future__ import annotations`；带类型标注；用 `@dataclass` 表示纯数据。
2. **中文优先**：docstring、注释、`message`、界面文本一律中文。不要改写成英文。
3. **异常处理**：宽泛捕获处保留 `# noqa: BLE001` 注释（项目有意这么做，别删）。
4. **界面与逻辑分离**：业务逻辑放 `core/`，`ui/` 只管展示与交互。Tkinter 界面更新只在主线程，后台线程通过 `queue` + `after()` 回传（见 `ui/app.py`）。
5. **不写死密钥**：数据库密码走环境变量 `ACCDB_PWD`，绝不写进代码或文档。

### 数据库（`core/db.py`）

- `pads` 表：`source`（`参考` / `我的` / `初始`）、`model`、`seq`（脚位序号）、`resistance`、坐标 `x1 y1 x2 y2` 等。
- `measurements` 表：一条条测量记录。
- **数据来源优先级：`参考` > `我的` > `初始`**（见 `get_pads` / `find_reference`）。改动查询时保持这个兜底顺序。
- 字段名用英文，含义用中文注释。

### 判定规则（`core/rules.py`）

- `reference >= 3000` → 视为**开路点**，实测需 `>= 2500`
- `reference == 0` → 视为**短路/接地点**，实测需 `<= 10`
- 其它 → 实测需落在 `reference ± 容差%`（界面可调，默认 ±30）
- 结果常量：`PASS` / `FAIL` / `NOREF`。**不要**随意改这些阈值，它们来自对厂商数据的统计。

### 新增一个测试项（测试平台）

在 `tests/` 新建 `.py`，定义一个继承 `TestItem` 的类，实现 `run(self, ctx) -> TestResult`，
可选覆盖 `default_params()` / `setup()` / `teardown()`。`registry.discover()` 会自动发现，**无需改任何清单**。
参考现成例子：`tests/t_demo_power.py`（无硬件）、`tests/t_serial_loopback.py`（串口）。

> 注意：`tests/` 里是**测试项类**，不是 pytest 用例；文件名 `t_*.py` 有意避开 pytest 的默认收集规则。

## 常用命令

```sh
python main_zzy.py              # 手动看阻值仪界面
python tools/smoke_zzy.py       # 阻值仪界面冒烟测试
python tools/fluke_scan.py      # 扫描 Fluke 蓝牙表
python tools/fluke_read.py      # 读取 Fluke 实时数值
ruff format .                   # 格式化（已配置）
ruff check .                    # 静态检查
basedpyright                    # 类型检查
```

导入厂商数据（需要 `ACCDB_PWD` 环境变量，密码不在此公开）：

```sh
python tools/import_accdb.py "Database1.accdb" "Database2.accdb"
```

## 待办 / 已知缺口

- **串口通信**：接上阻值仪硬件，实时读数 → 自动填入 → 自动判定 → 自动跳下一脚（核心缺口）。
- 把 Fluke 蓝牙读数接进阻值仪界面（协议解码已就绪，见 `core/fluke.py`）。

## 提交 / 协作注意

- 仓库是**公开**的，`README` 与文档中**不得**出现数据库密码、token、内部路径等敏感信息。
- 数据库 `data/ohm.db` 体积较大（约 29MB），提交前想清楚是否必要。
