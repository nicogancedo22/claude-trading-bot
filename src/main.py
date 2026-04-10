import time

from data_sources import get_prices
from detector import detect_opportunities
from logger import save_gaps
from paper_trader import summary_line

SUMMARY_INTERVAL = 10  # segundos


def main():
    print("Iniciando bot - conectando a Binance, Kraken, Coinbase, OKX, Bybit...")
    print("Activos  : BTC, ETH, SOL, DOGE, XRP, ADA, SHIB\n")
    last_summary = time.time()
    last_prices  = None

    while True:
        all_prices = get_prices()

        # Verificar que al menos un activo tenga 2 exchanges listos
        any_ready = any(
            sum(1 for data in prices.values() if data["bid"] is not None) >= 2
            for prices in all_prices.values()
        )

        if not any_ready:
            ready_exchanges = set()
            for prices in all_prices.values():
                ready_exchanges.update(ex for ex, data in prices.items() if data["bid"] is not None)
            status = ", ".join(ready_exchanges) if ready_exchanges else "ninguno"
            print(f"  Esperando streams... ({status} listo)    ", end="\r")
            time.sleep(0.5)
            continue

        # Solo detectar si los precios cambiaron desde el último ciclo
        if all_prices == last_prices:
            time.sleep(0.1)
            continue
        last_prices = all_prices

        detect_opportunities(all_prices)

        if time.time() - last_summary >= SUMMARY_INTERVAL:
            save_gaps(all_prices)
            print(summary_line(all_prices))
            last_summary = time.time()


if __name__ == "__main__":
    main()
