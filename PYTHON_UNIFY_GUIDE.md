# Python 统一化指南：仅保留 Python 3.13.9

当前检测到的解释器：
- **Python 3.15.0a2**：`D:\Software_applications\specialtys\development_language\python3.15\`
- **Python 3.13.9**：Microsoft Store 版（`WindowsApps\PythonSoftwareFoundation.Python.3.13_...`）

目标：卸载 3.15 等无关解释器，使 **python** / **python3** 均指向 **3.13.9**。

---

## 方案一：保留 Store 3.13.9，仅卸载 3.15 并改 PATH（推荐）

### 步骤 1：卸载 Python 3.15

任选一种方式：

**方式 A - 设置里卸载**
1. 按 `Win + I` 打开「设置」
2. 应用 → 已安装的应用
3. 搜索「Python 3.15」或「Python」
4. 找到 **Python 3.15**（路径在 D 盘的那个），点击 ⋮ → 卸载

**方式 B - 控制面板**
1. 控制面板 → 程序和功能
2. 找到 **Python 3.15.x**（发布者或路径含 `development_language\python3.15`）
3. 右键 → 卸载

**方式 C - 命令行（若已安装 winget）**
```powershell
# 查看名称
winget list --name Python

# 卸载 Python 3.15（名称以实际列表为准，例如 Python.Python.3.15）
winget uninstall "Python 3.15"  --silent
# 或
winget uninstall Python.Python.3.15  --silent
```

### 步骤 2：让「python」指向 3.13.9（改 PATH）

卸载 3.15 后，若 Store 3.13 已安装，通常会有：
- `python3.13.exe` → 已可用
- `python.exe` / `python3.exe` → 可能是 Store 的“应用执行别名”，会打开 Store 或启动 3.13

**2.1 检查当前「python」指向**
```powershell
# 卸载 3.15 之后重新打开 PowerShell，执行：
where.exe python
python --version
```
若已显示 `Python 3.13.9`，则无需改 PATH。

**2.2 若「python」仍指向别处或不存在**

把 **3.13.9 所在目录** 和 **其 Scripts 目录** 加到用户 PATH 最前面：

1. 找到 Store 版 3.13.9 的安装目录，例如：
   ```
   C:\Users\bigda\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\
   ```
   （以你本机实际路径为准，可用 `py -3.13 -c "import sys; print(sys.executable)"` 查看）

2. 设置环境变量（PowerShell **以当前用户**）：
   ```powershell
   $py313 = "C:\Users\bigda\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0"
   $scripts = "$py313\Scripts"
   $path = [Environment]::GetEnvironmentVariable("Path", "User")
   # 若已存在则先去掉再添加，避免重复
   $path = ($path -split ";" | Where-Object { $_ -notlike "*python3.15*" -and $_ -notlike "*Python313*" }) -join ";"
   [Environment]::SetEnvironmentVariable("Path", "$py313;$scripts;$path", "User")
   ```
   然后 **关闭并重新打开** PowerShell，再执行 `python --version` 应为 3.13.9。

---

## 方案二：改用 python.org 完整安装 3.13.9（不用 Store）

若希望用官方安装包、便于管理 PATH 和 pip：

### 步骤 1：卸载不需要的版本

- 卸载 **Python 3.15**（同方案一步骤 1）
- 可选：在「设置 → 应用」里卸载 **Python 3.13 (Microsoft Store)**，避免和 python.org 版混淆

### 步骤 2：安装 python.org 3.13.9

1. 打开 https://www.python.org/downloads/release/python-3139/
2. 下载 **Windows installer (64-bit)**（或 32-bit 按需）
3. 运行安装程序：
   - 勾选 **「Add python.exe to PATH」**
   - 选择 **「Customize installation」** 可勾选 pip、py launcher 等
   - 安装路径可用默认，例如 `C:\Users\bigda\AppData\Local\Programs\Python\Python313\`
4. 安装完成后，**新开 PowerShell**：
   ```powershell
   python --version   # 应为 Python 3.13.9
   python -m pip install --upgrade pip
   ```

### 步骤 3：为本项目安装依赖

```powershell
cd C:\Users\bigda\Desktop\ailiyunAgent
python -m pip install -r requirements.txt
```

### 步骤 4：关闭 Store 的「应用执行别名」（避免误用 Store 的 python）

1. 设置 → 应用 → 高级应用设置 → 应用执行别名
2. 将 **「应用程序安装程序 - python.exe」** 和 **「python3.exe」** 设为 **关**，这样在终端输入 `python` 时只会用 PATH 里的 3.13.9。

---

## 验证统一结果

在新开的 PowerShell 中执行：

```powershell
python --version
python3 --version
py -0p
where.exe python
```

期望：
- `python --version` 与 `python3 --version` 均为 **Python 3.13.9**
- `py -0p` 仅列出 3.13（或 3.13 为默认）
- `where python` 只出现一个 3.13.9 的路径

然后在本项目目录运行：

```powershell
cd C:\Users\bigda\Desktop\ailiyunAgent
python scripts/smoke_test.py
```

应能通过版本检查并正常跑通。

---

## 小结

| 目标           | 操作 |
|----------------|------|
| 卸载 3.15      | 设置/控制面板/winget 卸载 Python 3.15 |
| 默认用 3.13.9 | 方案一：保留 Store 3.13.9，改 PATH；或 方案二：安装 python.org 3.13.9 并勾选「Add to PATH」 |
| 避免混用      | 关闭 Store 的「应用执行别名」中 python.exe / python3.exe（若用方案二） |

按上述步骤操作后，你的环境即为「仅使用完整的 Python 3.13.9」的同一套解释器。
