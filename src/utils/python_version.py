"""
强制使用 Python 3.13.9，避免因系统存在多个解释器导致依赖/行为不一致。
"""

import sys

REQUIRED_VERSION = (3, 13, 9)


def check_python_version() -> None:
    """要求当前解释器为 Python 3.13.9，否则退出并打印说明。"""
    vi = sys.version_info
    if (vi.major, vi.minor, vi.micro) != REQUIRED_VERSION:
        required_str = ".".join(map(str, REQUIRED_VERSION))
        current_str = f"{vi.major}.{vi.minor}.{vi.micro}"
        msg = (
            f"本项目要求使用 Python {required_str}，当前为 {current_str}。\n"
            "请使用指定解释器运行，例如：\n"
            f"  Windows: py -3.13 或 python3.13 或指定完整路径\n"
            f"  Linux/macOS: python3.13 或 pyenv/venv 使用 3.13.9\n"
            f"创建虚拟环境: python3.13 -m venv venv 然后 .\\venv\\Scripts\\activate (Windows) 或 source venv/bin/activate (Unix)"
        )
        print(msg, file=sys.stderr)
        sys.exit(1)
