import os
from datetime import datetime

# Resolve path relative to the project root (one level above src/)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(_PROJECT_ROOT, "logs", "opportunities.txt")


def save_opportunity(price_a: float, price_b: float, gap: float) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = (
        f"{timestamp} | "
        f"Precio A: {price_a:.2f} | "
        f"Precio B: {price_b:.2f} | "
        f"Diferencia: {gap:.2f}\n"
    )
    with open(LOG_FILE, "a", encoding="utf-8") as file:
        file.write(line)
