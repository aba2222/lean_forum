<#
.SYNOPSIS
    一条命令把 Lean Forum 在本地跑起来。

.DESCRIPTION
    从「刚 clone 下来什么都没有」一路做到「浏览器里能打开」：

        venv（没有就建） -> 依赖（没装/变了就装） -> 建迁移 -> 执行迁移 -> 起服务

    之所以把环境准备也包进来，是因为这个仓库有几个坑：

      1. migrations/ 在 .gitignore 里，刚 clone 下来根本没有迁移文件，
         不先 makemigrations 就连表都建不出来；
      2. PATH 上的 `python` 未必是能用的那个（常见的是 3.8 而且没有 Django），
         所以必须显式挑一个 3.10+ 的解释器来建 venv；
      3. DEBUG 不设成 1，/static/ 下的编辑器资源全是 404，页面看起来像坏了。

    默认会自己把环境补齐；想只启动、一点环境都不动，加 -NoSetup。

.PARAMETER Port
    监听端口，默认 8000。

.PARAMETER Address
    监听地址，默认 127.0.0.1（只有本机能访问）。
    想让手机或局域网其它设备打开，用 -Address 0.0.0.0。

.PARAMETER VenvPath
    虚拟环境目录，默认项目下的 venv。

.PARAMETER PythonPath
    用哪个解释器来建 venv。不填就按 py -3.12 / py -3.11 / py -3.10 / python3 / python
    的顺序找一个 3.10 以上的。

.PARAMETER NoSetup
    不建 venv、不装依赖、不动数据库，只用现有环境启动。

.PARAMETER Test
    只跑测试，不启动服务器。

.PARAMETER Superuser
    顺便建一个超级用户（用户名 admin）。密码用 -AdminPassword 指定，
    不指定就随机生成并打印出来。已经有了就不重复建。

.PARAMETER AdminPassword
    配合 -Superuser 使用。

.PARAMETER NoReload
    关掉自动重载，改代码不会自动重启（调试加载问题时有用）。

.EXAMPLE
    .\dev.ps1
    最常用的一条：环境缺什么补什么，然后在 http://127.0.0.1:8000 起服务。

.EXAMPLE
    .\dev.ps1 -Superuser
    连同后台账号一起准备好，方便直接进 /admin/ 看数据。

.EXAMPLE
    .\dev.ps1 -Test
    只跑测试。

.EXAMPLE
    .\dev.ps1 -Port 9000 -Address 0.0.0.0
    换个端口，并允许局域网访问。

.NOTES
    这个文件必须存成「UTF-8 带 BOM」。Windows PowerShell 5.1 在没有 BOM 时
    会按系统 ANSI 代码页（简体中文下是 GBK）读脚本，里面的中文会变成乱码，
    甚至直接把脚本解析坏掉。
#>
[CmdletBinding()]
param(
    [int]$Port = 8000,
    [string]$Address = '127.0.0.1',
    [string]$VenvPath = 'venv',
    [string]$PythonPath = '',
    [switch]$NoSetup,
    [switch]$Test,
    [switch]$Superuser,
    [string]$AdminPassword = '',
    [switch]$NoReload
)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

#: 依赖清单，装了之后按它的哈希判断要不要重装
$RequirementsFile = Join-Path $PSScriptRoot 'requirements.txt'
$VenvRoot = if ([System.IO.Path]::IsPathRooted($VenvPath)) { $VenvPath } else { Join-Path $PSScriptRoot $VenvPath }

function Write-Step($text) { Write-Host "==> $text" -ForegroundColor Cyan }
function Write-Ok($text)   { Write-Host "  + $text" -ForegroundColor Green }
function Write-Warn($text) { Write-Host "  ! $text" -ForegroundColor Yellow }
function Write-Err($text)  { Write-Host "  x $text" -ForegroundColor Red }

function Exit-Witherror($text, $hint) {
    Write-Err $text
    if ($hint) {
        Write-Host ''
        Write-Host $hint -ForegroundColor Yellow
    }
    exit 1
}

function Get-VenvPython($root) {
    $candidates = @(
        (Join-Path $root 'Scripts\python.exe'),   # Windows
        (Join-Path $root 'bin\python')            # Unix 布局，兼容在 WSL/git-bash 里跑
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    return $null
}

function Get-PythonVersion($exe) {
    if (-not $exe) { return $null }
    try {
        $raw = & $exe -c "import sys; print('%d.%d.%d' % sys.version_info[:3])" 2>$null
    } catch {
        return $null
    }
    if ($LASTEXITCODE -ne 0 -or -not $raw) { return $null }
    # py 启动器在没有匹配版本时会往 stdout 写一行提示，过滤掉
    $text = ($raw | Select-Object -First 1).ToString().Trim()
    if ($text -notmatch '^\d+\.\d+\.\d+$') { return $null }
    return $text
}

function Test-PythonUsable($exe) {
    $version = Get-PythonVersion $exe
    if (-not $version) { return $false }
    $parts = $version.Split('.')
    $major = [int]$parts[0]
    $minor = [int]$parts[1]
    if ($major -gt 3) { return $true }
    if ($major -eq 3 -and $minor -ge 10) { return $true }
    return $false
}

# 找一个够新的解释器来建 venv。
# 不能直接用 PATH 上的 python —— 它很可能是 3.8（本项目要 3.10+）。
function Find-SystemPython() {
    if ($PythonPath) {
        if (-not (Test-Path -LiteralPath $PythonPath)) {
            Exit-Witherror "指定的解释器不存在：$PythonPath"
        }
        if (-not (Test-PythonUsable $PythonPath)) {
            Exit-Witherror "指定的解释器版本太旧或不可用：$PythonPath（本项目需要 Python 3.10 以上）"
        }
        return $PythonPath
    }

    $probes = @()
    $launcher = Get-Command 'py' -ErrorAction SilentlyContinue
    if ($launcher) {
        foreach ($tag in @('3.13', '3.12', '3.11', '3.10')) {
            $probes += , @('py', @("-$tag"))
        }
        $probes += , @('py', @('-3'))
    }
    foreach ($name in @('python3', 'python')) {
        if (Get-Command $name -ErrorAction SilentlyContinue) {
            $probes += , @($name, @())
        }
    }

    $rejected = @()
    foreach ($probe in $probes) {
        $name = $probe[0]
        $extra = $probe[1]
        try {
            $raw = & $name @extra -c "import sys; print(sys.executable); print('%d.%d.%d' % sys.version_info[:3])" 2>$null
        } catch {
            continue
        }
        if ($LASTEXITCODE -ne 0 -or -not $raw) { continue }
        $lines = @($raw | Where-Object { $_.ToString().Trim() -ne '' })
        if ($lines.Count -lt 2) { continue }
        $exe = $lines[0].ToString().Trim()
        $version = $lines[1].ToString().Trim()
        if ($version -notmatch '^\d+\.\d+\.\d+$') { continue }

        if (Test-PythonUsable $exe) { return $exe }
        $rejected += "$exe ($version)"
    }

    $hint = "请装一个 Python 3.10 以上，或用 -PythonPath 指定它的位置。"
    if ($rejected.Count -gt 0) {
        $hint = "找到的解释器都太旧：" + ($rejected -join '、') + "`n$hint"
    }
    Exit-Witherror '找不到 Python 3.10 以上的解释器。' $hint
}

function Install-Dependencies($venvPython) {
    Write-Step '安装依赖'
    & $venvPython -m pip install --disable-pip-version-check -r $RequirementsFile
    if ($LASTEXITCODE -ne 0) {
        Exit-Witherror 'pip install 失败。' '网络不通时可以先配好代理，或手动执行：' + "`n  $venvPython -m pip install -r requirements.txt"
    }
    Write-Ok '依赖装好了'
}

function Get-RequirementsHash() {
    if (-not (Test-Path -LiteralPath $RequirementsFile)) { return '' }
    return (Get-FileHash -LiteralPath $RequirementsFile -Algorithm SHA256).Hash
}

# ---------------------------------------------------------------- 环境准备

Write-Host ''
Write-Host '  Lean Forum 本地开发' -ForegroundColor White
Write-Host '  -------------------' -ForegroundColor DarkGray

$venvPython = Get-VenvPython $VenvRoot
$venvVersion = Get-PythonVersion $venvPython

if (-not $venvPython) {
    if ($NoSetup) {
        Exit-Witherror "没有虚拟环境：$VenvRoot" '去掉 -NoSetup，让脚本自己建；或者先手动建一个。'
    }

    Write-Step "建虚拟环境：$VenvRoot"
    $systemPython = Find-SystemPython
    Write-Ok "用 $systemPython ($(Get-PythonVersion $systemPython))"

    & $systemPython -m venv $VenvRoot
    if ($LASTEXITCODE -ne 0) {
        Exit-Witherror '创建虚拟环境失败。'
    }

    $venvPython = Get-VenvPython $VenvRoot
    if (-not $venvPython) {
        Exit-Witherror "虚拟环境建好了但找不到解释器：$VenvRoot"
    }
    Write-Ok '虚拟环境就绪'

    # 刚建出来的环境里一定没有依赖
    Install-Dependencies $venvPython
} else {
    Write-Ok "虚拟环境：$venvPython ($venvVersion)"

    if (-not $NoSetup) {
        # 依赖对不对，用 requirements.txt 的哈希判断：
        # 只看「能不能 import django」会漏掉「加了新依赖但没重装」的情况
        $stampFile = Join-Path $VenvRoot '.requirements.sha256'
        $currentHash = Get-RequirementsHash
        $installedHash = ''
        if (Test-Path -LiteralPath $stampFile) {
            $installedHash = (Get-Content -LiteralPath $stampFile -Raw).Trim()
        }

        if ($currentHash -and $currentHash -ne $installedHash) {
            Install-Dependencies $venvPython
            Set-Content -LiteralPath $stampFile -Value $currentHash -NoNewline -Encoding ASCII
        } else {
            & $venvPython -c "import django" 2>$null
            if ($LASTEXITCODE -ne 0) {
                Install-Dependencies $venvPython
                if ($currentHash) {
                    Set-Content -LiteralPath $stampFile -Value $currentHash -NoNewline -Encoding ASCII
                }
            } else {
                Write-Ok '依赖已是最新'
            }
        }
    }
}

# 从这一步开始一律用 venv 里的解释器，不碰 PATH 上的 python
Write-Step 'Django check'
& $venvPython manage.py check
if ($LASTEXITCODE -ne 0) {
    Exit-Witherror 'check 没过，先修上面的报错。'
}

# ---------------------------------------------------------------- 数据库

if (-not $NoSetup) {
    # 这个仓库把 migrations/ 放进了 .gitignore，所以刚 clone 下来一个迁移文件都没有。
    #
    # 必须显式写上 app 名：不带参数的 makemigrations 会跳过「连 migrations
    # 目录都还不存在」的 app，结果 forum 一张表都不建，起来一访问就是
    # no such table。带上 app 名才会老老实实生成 0001_initial。
    Write-Step '准备数据库（生成迁移 + 执行迁移）'
    & $venvPython manage.py makemigrations forum md_editor --noinput
    if ($LASTEXITCODE -ne 0) {
        Exit-Witherror 'makemigrations 失败。'
    }

    & $venvPython manage.py migrate --noinput
    if ($LASTEXITCODE -ne 0) {
        Exit-Witherror 'migrate 失败。'
    }
    Write-Ok '数据库就绪'
}

if ($Superuser) {
    Write-Step '超级用户'
    $exists = & $venvPython manage.py shell -c "from django.contrib.auth.models import User; print(User.objects.filter(is_superuser=True).count())" 2>$null
    $count = 0
    if ($exists) { [void][int]::TryParse((@($exists)[-1]).ToString().Trim(), [ref]$count) }

    if ($count -gt 0) {
        Write-Ok "已经有 $count 个超级用户，跳过"
    } else {
        if (-not $AdminPassword) {
            $bytes = New-Object byte[] 12
            [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
            $AdminPassword = [Convert]::ToBase64String($bytes).Replace('/', 'A').Replace('+', 'B').TrimEnd('=')
        }
        $env:DJANGO_SUPERUSER_USERNAME = 'admin'
        $env:DJANGO_SUPERUSER_PASSWORD = $AdminPassword
        $env:DJANGO_SUPERUSER_EMAIL = 'admin@example.com'
        & $venvPython manage.py createsuperuser --noinput 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Ok '已创建 admin'
            Write-Host "     用户名 admin    密码 $AdminPassword" -ForegroundColor Yellow
            Write-Host '     （这是本地开发账号，别用在线上）' -ForegroundColor DarkGray
        } else {
            Write-Warn '创建失败（可能用户名 admin 已被占用），可以手动跑 manage.py createsuperuser'
        }
        Remove-Item Env:\DJANGO_SUPERUSER_USERNAME, Env:\DJANGO_SUPERUSER_PASSWORD, Env:\DJANGO_SUPERUSER_EMAIL -ErrorAction SilentlyContinue
    }
}

# ---------------------------------------------------------------- 跑起来

# 必须设：不设的话 /static/ 下的编辑器等资源由谁提供就不确定了，页面会一片 404
$env:DEBUG = '1'
$env:PYTHONUNBUFFERED = '1'

if ($Test) {
    Write-Step '运行测试'
    Write-Host ''
    & $venvPython manage.py test
    exit $LASTEXITCODE
}

$serverArgs = @('manage.py', 'runserver', "${Address}:${Port}")
if ($NoReload) { $serverArgs += '--noreload' }

Write-Host ''
Write-Host "  服务器地址： http://${Address}:${Port}/" -ForegroundColor Green
Write-Host "  管理后台：   http://${Address}:${Port}/admin/" -ForegroundColor DarkGray
Write-Host '  Ctrl+C 停止' -ForegroundColor DarkGray
Write-Host ''

& $venvPython @serverArgs
