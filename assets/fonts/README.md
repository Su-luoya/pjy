# Fonts

构建产物默认优先使用 `NotoSansCJKsc-Regular.otf` 作为中文嵌入字体。

- 本仓库不直接提交大体积字体文件。
- GitHub Actions 构建流程会在打包前自动下载开源字体并放入本目录。
- 若本地开发机本目录无字体文件，报告模块会回退到 `STSong-Light`（ReportLab CID 字体）。
