<p align="center">
  <strong>TextToSolid</strong><br/>
  <em>Zero-dependency, pure-Python parametric solid modeling engine</em><br/>
  Turn text into watertight 3D solids — a small DSL, a BSP CSG kernel, STL/OBJ/SVG exporters and an agent JSON protocol.
</p>

<p align="center">
  🌐 <b>Language</b>:
  <a href="#zh-cn">简体中文</a> ·
  <a href="#zh-tw">繁體中文</a> ·
  <a href="#en">English</a>
</p>

<p align="center">
  <img alt="License MIT" src="https://img.shields.io/badge/license-MIT-blue.svg"/>
  <img alt="Python 3.9+" src="https://img.shields.io/badge/python-3.9%2B-blue.svg"/>
  <img alt="Dependencies none" src="https://img.shields.io/badge/dependencies-none-success.svg"/>
  <img alt="CI" src="https://github.com/gitstq/TextToSolid/actions/workflows/ci.yml/badge.svg"/>
</p>

---

<a id="zh-cn"></a>

## 简体中文

### 🎉 项目介绍

**TextToSolid** 是一个**零依赖、纯 Python 标准库**实现的参数化实体建模引擎。它让你用一段文本直接生成**水密（watertight）3D 实体**，可导出为 STL / OBJ，并渲染 SVG 预览。

- 🎯 **解决痛点**：无需安装 OpenCASCADE / build123d / FreeCAD 等重型内核，也不依赖任何第三方包，`pip install` 都不需要，克隆即可运行。
- 💡 **自研差异化**：核心是一条小型 **文本 DSL** + 自研 **BSP CSG 布尔内核**（并 / 差 / 交）+ 完整导出器 + 面向 AI Agent 的 **JSON 协议**。灵感来自 GitHub Trending 项目 `TEXT-TO-CAD`，但改用**纯 Python 网格级**方案，与该账号「Zero Dependencies」系列一脉相承。
- 🤖 **Agent 友好**：AI Agent 不必解析自然语言，直接产出结构化 JSON 即可得到精确实体。

### ✨ 核心特性

- 🧱 **8 种参数化图元**：`box` / `sphere` / `cylinder` / `cone` / `torus` / `wedge` / `tube` / `pyramid`，均支持 `at=` 偏移与 `color=` 上色。
- 🔧 **几何变换**：`translate` / `rotate` / `scale`（均匀或按轴）/ `mirror`。
- ➕ **BSP CSG 布尔**：`union` / `difference` / `intersection`，结果水密、带顶点焊接与绕序修复。
- 🔁 **轮廓建模**：`polygon` / `circle` / `square` / `rect` + `extrude`（挤出）与 `revolve`（旋转扫成），支持部分角度。
- 📐 **安全表达式**：`let` 变量、四则运算、`^` 幂、`sin/cos/sqrt/...` 函数、`pi`/`e` 常量，绝不用 `eval`。
- 🌀 **`repeat` 阵列**：按旋转/平移增量批量复制（轻松画齿轮、法兰孔）。
- 📤 **导出**：二进制/ASCII STL、OBJ（含顶点色）、SVG 正交预览。
- 🧪 **Agent JSON 协议**：`build_from_spec()` + `model_info()` 测量报告，直接喂给 LLM 工作流。
- 🩺 **打印校验**：水密性、非流形边、退化面、体积/表面积一键检测。
- 🪶 **真正零依赖**：只用标准库。

### 🚀 快速开始

**环境要求**：Python 3.9+（无任何第三方依赖）。

```bash
git clone https://github.com/gitstq/TextToSolid.git
cd TextToSolid
```

命令行用法（`python -m texttosolid`，别名为 `t2s`）：

```bash
# 从 DSL 文件构建并导出 STL
python -m texttosolid build examples/bracket.t2s -o bracket.stl

# 打印测量信息（尺寸、体积、水密性、可打印性）
python -m texttosolid info examples/gear.t2s

# 打印前校验（水密 + 无退化面 + 有体积）
python -m texttosolid check examples/vase.t2s

# 渲染 SVG 预览
python -m texttosolid preview examples/gear.t2s -o gear.svg

# 构建内置示例 / 列出内置示例
python -m texttosolid examples
python -m texttosolid example gear -o gear.stl
```

### 📖 详细使用指南

**DSL 速览**（详见 `examples/*.t2s`）：

```text
let t = 4
difference {
    union {
        box(40, 20, t)
        translate(0, 0, t/2 + 15) { box(40, 20, 30) }
    }
    repeat(4, rotate=(0, 0, 90)) {
        translate(28, 0, 0) { cylinder(r=1.7, h=t*3) }
    }
}
```

**Python API**：

```python
from texttosolid import box, translate, cylinder, subtract

part = subtract(
    box(20, 20, 10),
    translate(cylinder(r=3, h=40), 0, 0, 0),
)
part.save("part.stl")            # 或 export.save(part, "part.stl")
print(part.volume(), part.is_watertight())
```

**Agent JSON 协议**（AI 直接产出即可）：

```python
from texttosolid import build_from_spec, model_info

spec = {"shapes": [
    {"op": "box", "w": 40, "d": 20, "h": 4},
    {"op": "difference", "shapes": [
        {"op": "cylinder", "r": 3, "h": 12},
    ]},
]}
mesh = build_from_spec(spec)
info = model_info(mesh)   # triangles / volume / watertight / printable / bbox ...
```

CLI 参数（`build`/`preview`）：`--width/--height/--yaw/--pitch` 控制 SVG 预览视角；`--ascii` 输出 ASCII STL；`--spec` 强制按 JSON 解析输入。

### 💡 设计思路与迭代规划

- 🧠 **理念**：用最小、可读的文本语法覆盖常见机械件（支架、齿轮、壳体、旋转体），布尔内核追求「结果一定水密」。
- 🧱 **技术选型**：BSP 树布尔运算久经考验；纯标准库保证可移植、零供应链风险。
- 🛣️ **后续计划**：曲面细分与网格抽稀、STEP/3MF 导出、G-code 切片预览、约束求解式参数化、Web 预览页。

### 📦 打包与部署指南

本项目为**工具库**，无需打包/发布 Release：

- 作为库使用：直接把 `texttosolid/` 目录加入你的项目，或 `pip install -e .`（提供 `pyproject.toml`）。
- 作为 CLI 使用：`python -m texttosolid ...`。
- 兼容环境：Python 3.9–3.12，Windows / macOS / Linux，CI 已矩阵验证。
- 导出格式：`.stl`（二进制/ASCII）、`.obj`、`.svg`。

### 🤝 贡献指南

欢迎 PR！请遵循 [Angular 提交规范](https://www.conventionalcommits.org/)（`feat/fix/docs/refactor/...`），并确保 `python -m compileall -q texttosolid tests` 与单元测试通过。详见 [`CONTRIBUTING.md`](CONTRIBUTING.md)。

### 📄 开源协议

本项目基于 [MIT License](LICENSE)。

---

<a id="zh-tw"></a>

## 繁體中文

### 🎉 專案介紹

**TextToSolid** 是一個**零依賴、純 Python 標準函式庫**實現的參數化實體建模引擎。你用一段文字即可產生**水密（watertight）3D 實體**，並匯出為 STL / OBJ、渲染 SVG 預覽。

- 🎯 **解決痛點**：無需安裝 OpenCASCADE / build123d / FreeCAD 等重型核心，也不依賴任何第三方套件，連 `pip install` 都不需要，複製即可執行。
- 💡 **自研差異化**：核心是一條小型**文字 DSL** + 自研 **BSP CSG 布林核心**（聯集/差集/交集）+ 完整匯出器 + 面向 AI Agent 的 **JSON 協定**。靈感來自 GitHub Trending 專案 `TEXT-TO-CAD`，改用**純 Python 網格級**方案。
- 🤖 **Agent 友善**：AI 不必解析自然語言，直接產出結構化 JSON 即可得到精確實體。

### ✨ 核心特性

- 🧱 **8 種參數化圖元**：`box`/`sphere`/`cylinder`/`cone`/`torus`/`wedge`/`tube`/`pyramid`，支援 `at=` 偏移與 `color=` 上色。
- 🔧 **幾何變換**：`translate`/`rotate`/`scale`（均勻或分軸）/`mirror`。
- ➕ **BSP CSG 布林**：`union`/`difference`/`intersection`，結果水密、含頂點焊接與環序修正。
- 🔁 **輪廓建模**：`polygon`/`circle`/`square`/`rect` + `extrude` 與 `revolve`，支援部分角度。
- 📐 **安全運算式**：`let` 變數、四則運算、`^` 次方、`sin/cos/sqrt/...` 函式、`pi`/`e` 常數，絕不使用 `eval`。
- 🌀 **`repeat` 陣列**：依旋轉/平移增量批次複製（輕鬆繪製齒輪、法蘭孔）。
- 📤 **匯出**：二進位/ASCII STL、OBJ（含頂點色）、SVG 正交預覽。
- 🧪 **Agent JSON 協定**：`build_from_spec()` + `model_info()` 量測報告。
- 🩺 **列印校驗**：水密性、非流形邊、退化面、體積/表面積一鍵檢測。
- 🪶 **真正零依賴**：僅使用標準函式庫。

### 🚀 快速開始

**環境需求**：Python 3.9+（無任何第三方依賴）。

```bash
git clone https://github.com/gitstq/TextToSolid.git
cd TextToSolid
python -m texttosolid build examples/bracket.t2s -o bracket.stl
python -m texttosolid info examples/gear.t2s
```

### 📖 詳細使用指南

DSL 範例、Python API 與 Agent JSON 協定請參考上方「简体中文」章節，語法完全相同。

### 💡 設計思路與迭代規劃

以最小、易讀的文字語法覆蓋常見機械件；布林核心追求「結果必定水密」；純標準庫確保可移植、零供應鏈風險。後續將加入曲面細分、STEP/3MF 匯出、G-code 切片預覽等。

### 📦 打包與部署指南

屬**工具庫**，無需打包/發布 Release。可將 `texttosolid/` 目錄直接加入專案，或以 `python -m texttosolid` 當作 CLI 使用。相容 Python 3.9–3.12、Windows/macOS/Linux。

### 🤝 貢獻指南

請遵循 Angular 提交規範，並確保通過語法檢查與單元測試。詳見 [`CONTRIBUTING.md`](CONTRIBUTING.md)。

### 📄 開源協定

基於 [MIT License](LICENSE)。

---

<a id="en"></a>

## English

### 🎉 Introduction

**TextToSolid** is a **zero-dependency, pure-Python** parametric solid modeling
engine. Turn a snippet of text into a **watertight 3D solid**, then export to
STL / OBJ or render an SVG preview.

- 🎯 **Problem solved**: no OpenCASCADE / build123d / FreeCAD, no third-party
  packages — clone and run.
- 💡 **Differentiation**: a compact **text DSL** + a from-scratch **BSP CSG
  kernel** (union / difference / intersection) + full exporters + an
  **agent JSON protocol**. Inspired by the trending `TEXT-TO-CAD` project,
  reimagined as a pure-Python, mesh-level engine.
- 🤖 **Agent-friendly**: an LLM can skip natural-language parsing and emit
  structured JSON to get an exact solid.

### ✨ Core features

- 🧱 **8 parametric primitives**: `box`, `sphere`, `cylinder`, `cone`, `torus`,
  `wedge`, `tube`, `pyramid` — all with `at=` offset and `color=` support.
- 🔧 **Transforms**: `translate`, `rotate`, `scale` (uniform or per-axis), `mirror`.
- ➕ **BSP CSG booleans**: `union`, `difference`, `intersection` producing
  watertight output with vertex welding and winding repair.
- 🔁 **Profile modeling**: `polygon`, `circle`, `square`, `rect` + `extrude`
  and `revolve` (partial angles supported).
- 📐 **Safe expressions**: `let` bindings, arithmetic, `^` power, math
  functions, `pi`/`e` constants — never `eval`.
- 🌀 **`repeat` arrays**: rotate/translate incremental copies (gears, bolt
  circles).
- 📤 **Export**: binary/ASCII STL, OBJ (with vertex colors), SVG preview.
- 🧪 **Agent JSON protocol**: `build_from_spec()` + `model_info()` report.
- 🩺 **Print checks**: watertightness, non-manifold edges, degenerate faces,
  volume/area in one call.
- 🪶 **Truly zero dependencies**: standard library only.

### 🚀 Quick start

**Requirements**: Python 3.9+ (no third-party dependencies).

```bash
git clone https://github.com/gitstq/TextToSolid.git
cd TextToSolid

# Build & export
python -m texttosolid build examples/bracket.t2s -o bracket.stl

# Measurements
python -m texttosolid info examples/gear.t2s

# Printability check
python -m texttosolid check examples/vase.t2s

# SVG preview
python -m texttosolid preview examples/gear.t2s -o gear.svg
```

### 📖 Usage guide

**DSL example** (see `examples/*.t2s`):

```text
let t = 4
difference {
    union {
        box(40, 20, t)
        translate(0, 0, t/2 + 15) { box(40, 20, 30) }
    }
    repeat(4, rotate=(0, 0, 90)) {
        translate(28, 0, 0) { cylinder(r=1.7, h=t*3) }
    }
}
```

**Python API**:

```python
from texttosolid import box, translate, cylinder, subtract

part = subtract(box(20, 20, 10), translate(cylinder(r=3, h=40), 0, 0, 0))
part.save("part.stl")
print(part.volume(), part.is_watertight())
```

**Agent JSON protocol**:

```python
from texttosolid import build_from_spec, model_info

spec = {"shapes": [
    {"op": "box", "w": 40, "d": 20, "h": 4},
    {"op": "difference", "shapes": [{"op": "cylinder", "r": 3, "h": 12}]},
]}
mesh = build_from_spec(spec)
info = model_info(mesh)   # triangles / volume / watertight / printable / bbox ...
```

CLI options (`build`/`preview`): `--width/--height/--yaw/--pitch` control the
SVG camera; `--ascii` writes ASCII STL; `--spec` forces JSON parsing.

### 💡 Design & roadmap

Minimal, readable syntax for common mechanical parts; the boolean kernel aims
for guaranteed watertight results; standard library only for portability.
Roadmap: mesh decimation/refinement, STEP/3MF export, G-code preview, a web
viewer, constraint-driven parametric modeling.

### 📦 Packaging & deployment

This is a **library/tool** project — no Release packaging required. Drop the
`texttosolid/` folder into your project or `pip install -e .` (a
`pyproject.toml` is provided). Compatible with Python 3.9–3.12 on
Windows/macOS/Linux. Export formats: `.stl` (binary/ASCII), `.obj`, `.svg`.

### 🤝 Contributing

Please follow the [Angular commit convention](https://www.conventionalcommits.org/)
and keep `python -m compileall -q texttosolid tests` plus the unit tests green.
See [`CONTRIBUTING.md`](CONTRIBUTING.md).

### 📄 License

Released under the [MIT License](LICENSE).
