$ErrorActionPreference = "Stop"

$version = (uv run python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
$dateTag = Get-Date -Format 'yyyyMMdd'

if (-not (Test-Path "assets/fonts/NotoSansCJKsc-Regular.otf")) {
  New-Item -ItemType Directory -Path assets/fonts -Force | Out-Null
  $fontUrl = 'https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf'
  Invoke-WebRequest -Uri $fontUrl -OutFile assets/fonts/NotoSansCJKsc-Regular.otf
}

uv sync --frozen --group dev
uv run pytest -q

uv run pyinstaller launcher.py --noconfirm --clean --onedir --name supplier-analysis `
  --collect-all streamlit `
  --collect-all kaleido `
  --collect-submodules src `
  --add-data "assets;assets"

$artifactName = "supplier-analysis-v$version-win64-$dateTag"
Compress-Archive -Path "dist/supplier-analysis/*" -DestinationPath "dist/$artifactName.zip" -Force

Write-Host "Build complete: dist/$artifactName.zip"
