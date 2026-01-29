# 为什么会出现“用的库不同”或“用别的解释器”？

## 原因简述

Windows 上可以同时存在多个 Python 安装，例如：

- **Microsoft Store 版**：`python3.13.exe`（路径如 `...\WindowsApps\python3.13.exe`）
- **python.org 安装包**：`python.exe` 或 `py.exe`
- **Anaconda / Miniconda**：`conda` 环境里的 `python.exe`
- **项目虚拟环境**：`venv\Scripts\python.exe`

终端里输入 `python` 时，系统按 **PATH 顺序** 找第一个 `python.exe`。若 PATH 里先出现的是另一个安装（例如某 venv 或 conda），就会用那个解释器；而 **pip 安装的包是“按解释器”安装的**，每个解释器有各自的 site-packages。所以会出现：

- 用 A 解释器装了 `langgraph`，用 B 解释器跑脚本 → B 里没有 `langgraph`，报 `ModuleNotFoundError`
- 用 A 跑正常，用 B 跑报错 → 本质是“两个不同的 Python”在跑

## 本项目规定：强制使用 Python 3.13.9

为避免上述不一致，本项目**强制要求使用 Python 3.13.9**：

1. **pyproject.toml**：`requires-python = "==3.13.9"`
2. **.python-version**：供 pyenv / 部分 IDE 识别，固定为 `3.13.9`
3. **运行时检查**：入口脚本（如 `run_server_fast.py`、`run_console.py`、`scripts/smoke_test.py` 等）启动时会检查当前解释器版本，若不是 3.13.9 会直接退出并提示如何切换。

## 如何保证用的是 3.13.9

- **Windows**
  - 用 Store 3.13：`python3.13 scripts/smoke_test.py` 或 `py -3.13 scripts/smoke_test.py`
  - 用指定路径：`"C:\...\Python313\python.exe" scripts/smoke_test.py`
  - 建虚拟环境：`py -3.13 -m venv venv`，再 `.\venv\Scripts\activate`，之后 `python` 即该环境
- **Linux / macOS**
  - `python3.13 scripts/smoke_test.py`
  - 或 pyenv：`pyenv install 3.13.9`，在项目目录下 `pyenv local 3.13.9`，然后 `python scripts/smoke_test.py`

安装依赖请用**同一个** 3.13.9 解释器：

```bash
python -m pip install -r requirements.txt
# 或
py -3.13 -m pip install -r requirements.txt
```

这样所有脚本和库都会固定在同一解释器下，避免“用的库不同”或“用别的解释器”的问题。
