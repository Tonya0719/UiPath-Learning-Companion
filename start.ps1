$ErrorActionPreference = 'Stop'
$launchScript = Join-Path $PSScriptRoot 'launch.py'
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'

if (Test-Path -LiteralPath $venvPython) {
    & $venvPython $launchScript
    exit $LASTEXITCODE
}

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py $launchScript
    exit $LASTEXITCODE
}

if (Get-Command python -ErrorAction SilentlyContinue) {
    & python $launchScript
    exit $LASTEXITCODE
}

throw '未找到 Python。请先安装 Python 3.10+，或在本目录创建 .venv。'
