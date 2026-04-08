import random


# --- Simulated sources (replace each function body with a real API call) ---

def get_price_source_a() -> float:
    return 100 + random.uniform(-1, 1)


def get_price_source_b() -> float:
    return 100 + random.uniform(-1, 1) + 0.4
