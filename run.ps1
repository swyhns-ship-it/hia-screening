# 本机启动脚本:在脚本所在目录跑 streamlit。
# 用法:右键「使用 PowerShell 运行」,或终端 .\run.ps1
# 若被「禁止运行脚本」拦:一次性 Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# 优先用本目录 .venv,否则用 PATH 里的 python
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

& $py -m streamlit run app.py
