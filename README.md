# 供应商年度分析系统

本项目用于处理与“后勤库房--所有供货商2018年-2025年供货系统原始明细表.xlsx”同格式的 Excel 文件，自动生成：

- 供应商-年度项目数/供货金额汇总 + 环比（表 A）
- 年度项目数/供货品种/总金额汇总（表 B）
- 年度供货金额环比（排除指定供应商，表 C）
- 可视化图表（供应商分图 + 年度趋势）
- 双版本 PDF 报告（简报型 + 完整型）

## 本地运行（开发）

```bash
uv sync --group dev
uv run streamlit run app.py --server.port 8501
```

打开 [http://localhost:8501](http://localhost:8501)。

## CLI 导出

```bash
uv run python -m src.cli report --input <Excel路径> --output <输出目录>
```

默认会导出：

- `供应商年度分析简报.pdf`
- `供应商年度分析完整报告.pdf`
- `供应商年度分析结果.xlsx`
- `表A_供应商年度汇总.csv`
- `表B_年度总览.csv`
- `表C_年度金额环比_排除指定供应商.csv`

可选开关：`--brief` `--full` `--excel` `--csv`。

若以 wheel/installer 方式安装，也可使用：

```bash
supplier-analysis report --input <Excel路径> --output <输出目录>
```

## Windows 便携包构建

GitHub Actions 工作流：`.github/workflows/windows-build.yml`

- 触发：`workflow_dispatch` 与 `push tag(v*)`
- 流程：安装依赖 -> 运行测试 -> PyInstaller `--onedir` 打包 -> zip artifact 上传
- 产物命名：`supplier-analysis-v{version}-win64-{YYYYMMDD}.zip`

## 启动器

`launcher.py` / `src/launcher.py` 用于便携 EXE 场景：

- 自动探测可用端口（默认从 `8501` 开始）
- 自动打开浏览器（支持 `--no-browser`）
- 主进程退出时自动回收 Streamlit 子进程

## 字体

PDF 优先使用 `assets/fonts/NotoSansCJKsc-Regular.otf`（开源字体）。

- CI 在构建时自动下载字体并打包到便携目录
- 本地若未提供字体，将回退为 ReportLab 的 `STSong-Light`
