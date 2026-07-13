param(
    [string]$RootPath = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path $RootPath).Path
$apiPython = Join-Path $root ".venv-api\Scripts\python.exe"
$apiSource = Join-Path $root "apps\api\src"
$webPath = Join-Path $root "apps\web"
$corepackHome = Join-Path $root ".corepack"

if (-not (Test-Path $apiPython)) {
    Write-Host "未找到后端 Python 环境：$apiPython" -ForegroundColor Red
    Write-Host "请先按照 README 配置 .venv-api，或让 Codex 先完成依赖安装。"
    Read-Host "按回车退出"
    exit 1
}

if (-not (Test-Path (Join-Path $webPath "package.json"))) {
    Write-Host "未找到前端项目：$webPath" -ForegroundColor Red
    Read-Host "按回车退出"
    exit 1
}

if (-not (Get-Command corepack.cmd -ErrorAction SilentlyContinue)) {
    Write-Host "未找到 Corepack，请先安装 Node.js 或启用 Corepack。" -ForegroundColor Red
    Read-Host "按回车退出"
    exit 1
}

$backendCommand = @"
`$env:PYTHONPATH = '$apiSource'
Write-Host 'coc-star API: http://127.0.0.1:8000' -ForegroundColor Cyan
& '$apiPython' -m uvicorn coc_star_api.main:app --reload --app-dir '$apiSource'
"@

$frontendCommand = @"
`$env:COREPACK_HOME = '$corepackHome'
Write-Host 'coc-star Web: http://localhost:5173' -ForegroundColor Cyan
corepack pnpm --dir '$webPath' dev
"@

Start-Process powershell.exe -WorkingDirectory $root -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command", $backendCommand
)

Start-Process powershell.exe -WorkingDirectory $root -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command", $frontendCommand
)

Write-Host "已打开后端和前端开发窗口。" -ForegroundColor Green
Write-Host "浏览器地址：http://localhost:5173"
