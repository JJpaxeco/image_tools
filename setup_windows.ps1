$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

if (-not (Test-Path .\.venv)) { py -3.12 -m venv .venv }
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\requirements.txt
New-Item -ItemType Directory -Force -Path .\input, .\output, .\ai\realesrgan\models | Out-Null
Write-Host 'Ambiente preparado.' -ForegroundColor Green
Write-Host 'Agora baixe o Real-ESRGAN-ncnn-vulkan e extraia o executável + models em .\ai\realesrgan\' -ForegroundColor Yellow
