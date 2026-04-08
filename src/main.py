import time

from data_sources import get_price_source_a, get_price_source_b
from detector import detect_opportunity


def main():
    print("Iniciando bot...\n")

    while True:
        price_a = get_price_source_a()
        price_b = get_price_source_b()

        detect_opportunity(price_a, price_b)

        time.sleep(1)


if __name__ == "__main__":
    main()