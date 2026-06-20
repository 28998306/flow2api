# 为某个账号的 Chrome Profile 登录 Google(有头浏览器)。登录完成后关闭窗口即可。
# 用法:  .\login_profile.ps1 acc1
param(
    [Parameter(Mandatory = $true)][string]$ProfileName
)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$py = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Error "未找到 venv,请先运行 .\setup_workers.ps1" }

$profilesDir = Join-Path $root "flow_profiles"
New-Item -ItemType Directory -Force -Path $profilesDir | Out-Null
$profilePath = Join-Path $profilesDir $ProfileName

$code = @"
import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(r'$profilePath', headless=False,
            args=['--disable-blink-features=AutomationControlled'])
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto('https://labs.google/fx/tools/flow')
        print('>>> 请在浏览器里完成 Google 登录并进入 Flow,然后关闭浏览器窗口...')
        try:
            await page.wait_for_event('close', timeout=600000)
        except Exception:
            pass
        await ctx.close()
asyncio.run(main())
"@
& $py -c $code
Write-Host "[OK] Profile '$ProfileName' 登录流程结束。" -ForegroundColor Green
