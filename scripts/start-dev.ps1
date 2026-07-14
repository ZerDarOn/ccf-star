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
Write-Host 'coc-star Web: http://127.0.0.1:5173' -ForegroundColor Cyan
corepack pnpm --dir '$webPath' dev
"@

function Wait-TcpPort([string]$HostName, [int]$Port, [int]$Attempts = 30) {
    for ($attempt = 0; $attempt -lt $Attempts; $attempt++) {
        $client = New-Object System.Net.Sockets.TcpClient
        try {
            $async = $client.BeginConnect($HostName, $Port, $null, $null)
            if ($async.AsyncWaitHandle.WaitOne(1000) -and $client.Connected) {
                $client.Close()
                return $true
            }
        } finally {
            $client.Close()
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

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
Write-Host "等待前端服务监听 127.0.0.1:5173…" -ForegroundColor Cyan

$cloudflared = Get-Command cloudflared.exe -ErrorAction SilentlyContinue
$cloudflaredPath = if ($null -ne $cloudflared) { $cloudflared.Source } else { Join-Path $env:USERPROFILE "cloudflared.exe" }
if (-not (Test-Path $cloudflaredPath)) {
    $cloudflaredPath = $null
}
if ($null -ne $cloudflaredPath) {
    if (Wait-TcpPort "127.0.0.1" 5173) {
        $tunnelCommand = "Write-Host 'coc-star 公网隧道启动中…' -ForegroundColor Magenta; & '$cloudflaredPath' tunnel --url http://127.0.0.1:5173"
        Start-Process powershell.exe -WorkingDirectory $root -ArgumentList @(
            "-NoExit",
            "-ExecutionPolicy", "Bypass",
            "-Command", $tunnelCommand
        )
        Write-Host "已启动 Cloudflare 临时隧道窗口；请在该窗口复制 trycloudflare.com 地址。" -ForegroundColor Magenta
    } else {
        Write-Host "前端未能在 30 秒内监听 127.0.0.1:5173，已跳过隧道。请检查前端窗口。" -ForegroundColor Red
    }
} else {
    Write-Host "未检测到 cloudflared，已跳过公网隧道。安装后再次运行即可自动开启。" -ForegroundColor Yellow
    Write-Host "安装方式：winget install Cloudflare.cloudflared" -ForegroundColor Yellow
}
