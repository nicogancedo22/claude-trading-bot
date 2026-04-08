from logger import save_opportunity

THRESHOLD = 0.3


def detect_opportunity(price_a: float, price_b: float) -> None:
    gap = price_b - price_a

    if abs(gap) > THRESHOLD:
        print("🔥 Oportunidad detectada!")
        print(f"Precio A: {price_a:.2f}")
        print(f"Precio B: {price_b:.2f}")
        print(f"Diferencia: {gap:.2f}")
        print("--------------------------")

        save_opportunity(price_a, price_b, gap)
