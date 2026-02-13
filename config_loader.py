from pathlib import Path
import yaml


def load_config(path: str) -> dict:
    p = Path(path)
    return yaml.safe_load(p.read_text())
