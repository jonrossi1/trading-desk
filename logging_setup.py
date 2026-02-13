# logging_setup.py
import logging
from pathlib import Path

def setup_logging(
    log_file: str = "logs/desk.log",
    level: int = logging.INFO,
):
    # Ensure log directory exists
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),
        ],
    )
