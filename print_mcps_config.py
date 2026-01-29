from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.config_loader import get_config


def main() -> None:
    cfg = get_config()
    print("config_path:", cfg.config_path)
    print("raw mcps section:", cfg.get_section("mcps"))


if __name__ == "__main__":
    main()

