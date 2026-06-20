# 一次性:为原生 Worker 准备 Python venv + 依赖 + Chromium。
# 用法:  .\setup_workers.ps1

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$venv = Join-Path $backend ".venv"

Write-Host "[*] 创建 venv ..." -ForegroundColor Cyan
if (-not (Test-Path $venv)) {
    python -m venv $venv
}
$py = Join-Path $venv "Scripts\python.exe"

Write-Host "[*] 安装依赖(可配置 pip 国内源加速)..." -ForegroundColor Cyan
& $py -m pip install --upgrade pip
# 如需国内源:加 -i https://pypi.tuna.tsinghua.edu.cn/simple
& $py -m pip install -r (Join-Path $backend "requirements.txt")

Write-Host "[*] 安装 Playwright Chromium ..." -ForegroundColor Cyan
& $py -m playwright install chromium

Write-Host "[OK] 完成。下一步:" -ForegroundColor Green
Write-Host "  1) 为每个账号登录 Google:  .\login_profile.ps1 acc1"
Write-Host "  2) 启动 Worker:            .\run_workers.ps1"
