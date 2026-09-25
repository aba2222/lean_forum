<#
.SYNOPSIS
    一键启动 Lean Forum 开发服务器。

.DESCRIPTION
    用项目内的 venv 启动 Django 开发服务器，并自动设置 DEBUG=1。

    为什么一定要设置 DEBUG：/static/ 下的静态资源依赖它由 runserver 直接提供，
    不设置的话 Markdown 编辑器与洛谷渲染器都加载不出来。

    默认只监听 127.0.0.1，不对外网暴露；需要手机或局域网其它设备访问时用 -Address 0.0.0.0。

.PARAMETER Port
    监听端口，默认 8000。

.PARAMETER Address
    监听地址，默认 127.0.0.1。

.PARAMETER Migrate
    启动前先执行 makemigrations + migrate（首次运行或拉到大改动后用）。

.PARAMETER Test
    只跑测试，不启动服务器。

.EXAMPLE
    .\dev.ps1
    默认在 http://127.0.0.1:8000 启动。

.EXAMPLE
    .\dev.ps1 -Port 8000 -Migrate
    先建迁移再启动（首次运行）。

.EXAMPLE
    .\dev.ps1 -Test
    只跑测试。
#>
param(
    [int]$Port = 8000,
    [string]$Address = '127.0.0.1',
    [switch]$Migrate,
    [switch]$Test
)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

function Write-Step($text) { Write-Host "==> $text" -ForegroundColor Cyan }
function Write-Warn($text) { Write-Host "!!  $text" -ForegroundColor Yellow }
function Write-Err($text) { Write-Host "XX  $text" -ForegroundColor Red }

# 1) 解释器：用项目内的 venv，不要依赖 PATH 上的 python
#    （机器上 `python` 很可能是另一个没装 Django 的版本）
$python = Join-Path $PSScriptRoot 'venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    Write-Err "找不到虚拟环境：$python"
    Write-Host ''
    Write-Host '请先创建它（需要 Python 3.10 以上）：' -ForegroundColor Yellow
    Write-Host '  py -3.12 -m venv venv'
    Write-Host '  .\venv\Scripts\python.exe -m pip install -r requirements.txt'
    exit 1
}

$version = & $python -c "import sys; print('%d.%d' % sys.version_info[:2])"
Write-Step "Python $version ($python)"

& $python -c "import django" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Err '这个 venv 里没有 Django，先装依赖：'
    Write-Host '  .\venv\Scripts\python.exe -m pip install -r requirements.txt'
    exit 1
}

# 2) 静态检查：先跑 check，配置有问题就不必启动到一半才报错
Write-Step 'Django check'
& $python manage.py check

# 3) 迁移：默认只提示，不擅自改数据库
if ($Migrate) {
    Write-Step 'makemigrations + migrate'
    & $python manage.py makemigrations
    if ($LASTEXITCODE -ne 0) { Write-Err 'makemigrations 失败'; exit 1 }
    & $python manage.py migrate
    if ($LASTEXITCODE -ne 0) { Write-Err 'migrate 失败'; exit 1 }
} else {
    $pending = & $python manage.py migrate --plan 2>&1 | Select-String -Pattern '^\s+\w'
    if ($pending) {
        Write-Warn '有未执行的迁移，建议先跑：.\dev.ps1 -Migrate'
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'db.sqlite3'))) {
    Write-Warn '还没有 db.sqlite3，先跑 .\dev.ps1 -Migrate 初始化数据库'
}

# 4) 跑测试
if ($Test) {
    Write-Step '运行测试'
    $env:DEBUG = '1'
    & $python manage.py test
    exit $LASTEXITCODE
}

# 5) 启动
$env:DEBUG = '1'
$env:PYTHONUNBUFFERED = '1'

Write-Host ''
Write-Step "启动开发服务器： http://${Address}:$Port/"
Write-Host '    Ctrl+C 停止' -ForegroundColor DarkGray
Write-Host ''

& $python manage.py runserver "${Address}:${Port}"
