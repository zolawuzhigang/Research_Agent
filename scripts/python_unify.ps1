# Python 统一化辅助脚本：检测当前解释器，并将 PATH 调整为优先使用 Python 3.13.9
# 用法：在项目根目录执行  .\scripts\python_unify.ps1
# 注意：本脚本不会卸载任何程序，仅修改用户 PATH。卸载请按 PYTHON_UNIFY_GUIDE.md 在设置中操作。

$ErrorActionPreference = "Stop"
$RequiredVersion = "3.13.9"

function Get-PythonVersion($exe) {
    try {
        $out = & $exe --version 2>&1
        if ($out -match "Python (\d+\.\d+\.\d+)") { return $Matches[1] }
        return $null
    } catch { return $null }
}

Write-Host "=== Python 环境检测 ===" -ForegroundColor Cyan

# 1. 通过 py launcher 检测已安装版本
Write-Host "`n[1] 通过 py -0p 检测到的版本：" -ForegroundColor Yellow
try {
    $pyList = py -0p 2>&1
    $pyList | ForEach-Object { Write-Host "  $_" }
} catch { Write-Host "  (py 不可用)" }

# 2. PATH 中的 python
Write-Host "`n[2] PATH 中的 python 解析结果：" -ForegroundColor Yellow
$pythons = @(Get-Command python -ErrorAction SilentlyContinue)
if (-not $pythons) { $pythons = @(Get-Command python3 -ErrorAction SilentlyContinue) }
foreach ($p in $pythons) {
    $ver = Get-PythonVersion $p.Source
    $verStr = if ($ver) { $ver } else { "未知" }
    $ok = if ($ver -eq $RequiredVersion) { " [符合 3.13.9]" } else { " [非 3.13.9，建议不再优先使用]" }
    Write-Host "  $($p.Source)  -> $verStr$ok"
}

# 3. 查找 3.13.9
Write-Host "`n[3] 查找 Python $RequiredVersion：" -ForegroundColor Yellow
$py313Path = $null
try {
    $py313Path = (py -3.13 -c "import sys; print(sys.executable)" 2>$null)
    if ($py313Path) {
        $v = Get-PythonVersion $py313Path
        if ($v -eq $RequiredVersion) {
            Write-Host "  已找到: $py313Path"
        } else {
            Write-Host "  找到 3.13: $py313Path (版本 $v)"
            $py313Path = $null
        }
    }
} catch {}
if (-not $py313Path) {
    # 常见 Store 路径
    $storeBase = "$env:LOCALAPPDATA\Microsoft\WindowsApps"
    $pattern = "$storeBase\PythonSoftwareFoundation.Python.3.13_*\python.exe"
    $found = Get-Item $pattern -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) {
        $v = Get-PythonVersion $found.FullName
        if ($v -eq $RequiredVersion) {
            $py313Path = $found.FullName
            Write-Host "  已找到 (Store): $py313Path"
        }
    }
}
if (-not $py313Path) {
    Write-Host "  未找到 Python $RequiredVersion。请先安装 3.13.9（Store 或 python.org）。"
}

# 4. 建议操作
Write-Host "`n=== 建议操作 ===" -ForegroundColor Cyan
Write-Host "1. 卸载 Python 3.15：在「设置 → 应用 → 已安装的应用」中搜索 Python，卸载 Python 3.15。"
Write-Host "2. 将 3.13.9 置于 PATH 最前：若上面已找到 3.13.9，可运行下面命令（会修改用户 PATH）：" -ForegroundColor Gray
if ($py313Path) {
    $dir = [System.IO.Path]::GetDirectoryName($py313Path)
    $scripts = Join-Path $dir "Scripts"
    if (-not (Test-Path $scripts)) { $scripts = $null }
    Write-Host ""
    Write-Host "  # 在 PowerShell 中执行（可选）：" -ForegroundColor DarkGray
    Write-Host "  `$py = '$dir'" -ForegroundColor DarkGray
    if ($scripts) { Write-Host "  `$scr = '$scripts'" -ForegroundColor DarkGray }
    Write-Host "  `$path = [Environment]::GetEnvironmentVariable('Path','User')" -ForegroundColor DarkGray
    Write-Host "  # 去掉 PATH 中 python3.15 相关项" -ForegroundColor DarkGray
    Write-Host "  `$path = (`$path -split ';' | Where-Object { `$_ -notmatch 'python3\.15|Python3\.15' }) -join ';'" -ForegroundColor DarkGray
    if ($scripts) {
        Write-Host "  [Environment]::SetEnvironmentVariable('Path', \"`$py;`$scr;`$path\", 'User')" -ForegroundColor DarkGray
    } else {
        Write-Host "  [Environment]::SetEnvironmentVariable('Path', \"`$py;`$path\", 'User')" -ForegroundColor DarkGray
    }
    Write-Host "  # 然后关闭并重新打开终端，执行 python --version" -ForegroundColor DarkGray
} else {
    Write-Host "  （未找到 3.13.9，请先安装后再运行本脚本或按 PYTHON_UNIFY_GUIDE.md 操作）"
}
Write-Host "`n详细步骤见：PYTHON_UNIFY_GUIDE.md" -ForegroundColor Green
