# 在 Windows 宿主机原生运行出图/出视频 Worker(需要浏览器跑 reCAPTCHA)。
# 前提:postgres/redis/minio/backend 已用 docker compose 启动;已执行 setup_workers.ps1 建好 venv。
#
# 用法:  .\run_workers.ps1
# 说明:  会打开两个窗口,分别消费 image 与 video 队列(Windows 下用 solo 池最稳)。

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$venvPy = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Error "未找到 venv,请先运行 .\setup_workers.ps1"
}

# 连接 docker 暴露在 localhost 的服务(覆盖 .env 里的容器内主机名)
$envVars = @{
    POSTGRES_HOST       = "localhost"
    POSTGRES_PORT       = "5432"
    POSTGRES_USER       = "flow"
    POSTGRES_PASSWORD   = "flow_pass"
    POSTGRES_DB         = "flow2api"
    REDIS_HOST          = "localhost"
    REDIS_PORT          = "6379"
    REDIS_DB            = "0"
    S3_ENDPOINT         = "http://localhost:9000"
    S3_PUBLIC_ENDPOINT  = "http://localhost:9000"
    S3_ACCESS_KEY       = "minioadmin"
    S3_SECRET_KEY       = "minioadmin"
    S3_BUCKET           = "flow2api"
    # 各账号 Chrome Profile 根目录(Windows 本地路径)
    FLOW_PROFILES_DIR   = (Join-Path $root "flow_profiles")
    FLOW_HEADLESS       = "true"
    FLOW_USE_CURL       = "true"
}
foreach ($k in $envVars.Keys) { [Environment]::SetEnvironmentVariable($k, $envVars[$k], "Process") }
New-Item -ItemType Directory -Force -Path $envVars["FLOW_PROFILES_DIR"] | Out-Null

$backend = Join-Path $root "backend"

Write-Host "[*] 启动 video 队列 Worker(新窗口)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$backend'; & '$venvPy' -m celery -A app.workers.celery_app worker -Q video -P solo -n video@%computername% -l info"
)

Write-Host "[*] 启动 image 队列 Worker(当前窗口)..." -ForegroundColor Cyan
Set-Location $backend
& $venvPy -m celery -A app.workers.celery_app worker -Q image -P solo -n image@$env:COMPUTERNAME -l info
