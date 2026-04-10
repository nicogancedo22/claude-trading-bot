"""
detector.py — Detecta arbitraje usando precios reales de mercado.

Para comprar usa el ASK (precio real al que te venden).
Para vender usa el BID (precio real al que te compran).

Esto refleja el costo real de cada operación — sin el bid/ask
los números del paper trading serían más optimistas que la realidad.

Por cada activo, solo ejecuta el par con MAYOR gap rentable.
Cooldown de 3 segundos por par (asset + exchanges) para evitar duplicados.
"""

import time
from itertools import combinations

from logger import save_opportunity, save_trade
from paper_trader import evaluate, SLIPPAGE, FEE

ALERT_THRESHOLD = 100.0
TRADE_COOLDOWN  = 3.0  # segundos mínimos entre trades del mismo par

# Registro de último trade por (asset, buy_ex, sell_ex)
_last_trade_time: dict = {}


def detect_opportunities(all_prices: dict) -> None:
    for asset, exchanges in all_prices.items():
        _detect_asset(asset, exchanges)


def _detect_asset(asset: str, exchanges: dict) -> None:
    # Solo considerar exchanges con bid y ask disponibles
    available = {
        ex: data for ex, data in exchanges.items()
        if data["bid"] is not None and data["ask"] is not None
    }

    if len(available) < 2:
        return

    best = None  # (net_gap, buy_ex, sell_ex, ask_price, bid_price)

    for ex_a, ex_b in combinations(available, 2):
        # Opción 1: comprar en A (ask), vender en B (bid)
        ask_a = available[ex_a]["ask"]
        bid_b = available[ex_b]["bid"]
        gap_ab = bid_b - ask_a

        # Opción 2: comprar en B (ask), vender en A (bid)
        ask_b = available[ex_b]["ask"]
        bid_a = available[ex_a]["bid"]
        gap_ba = bid_a - ask_b

        for gap, buy_ex, sell_ex, buy_p, sell_p in [
            (gap_ab, ex_a, ex_b, ask_a, bid_b),
            (gap_ba, ex_b, ex_a, ask_b, bid_a),
        ]:
            if gap <= 0:
                continue

            avg_price = (buy_p + sell_p) / 2
            min_gap   = avg_price * (2 * SLIPPAGE + 2 * FEE)

            # Alerta visual para gaps grandes
            if gap > ALERT_THRESHOLD:
                print(
                    f"\n{'!' * 50}\n"
                    f"  ALERTA [{asset}]  {buy_ex.upper()} -> {sell_ex.upper()}"
                    f"  gap = ${gap:.2f}\n"
                    f"{'!' * 50}"
                )

            if gap > min_gap:
                if best is None or gap > best[0]:
                    best = (gap, buy_ex, sell_ex, buy_p, sell_p)

    # Ejecutar solo el mejor par, respetando cooldown
    if best:
        gap, buy_ex, sell_ex, buy_p, sell_p = best
        key = (asset, buy_ex, sell_ex)
        now = time.time()

        if now - _last_trade_time.get(key, 0) < TRADE_COOLDOWN:
            return  # demasiado pronto, esperar cooldown

        avg_price = (buy_p + sell_p) / 2
        min_gap   = avg_price * (2 * SLIPPAGE + 2 * FEE)

        print(f"\n*** OPORTUNIDAD [{asset}]: {buy_ex.upper()} -> {sell_ex.upper()} ***")
        print(f"  Compra ask {buy_ex:<10}: ${buy_p:,.6f}")
        print(f"  Venta bid  {sell_ex:<10}: ${sell_p:,.6f}")
        print(f"  Gap: ${gap:.6f}  |  Min requerido: ${min_gap:.6f}")

        save_opportunity(asset, buy_ex, sell_ex, buy_p, sell_p, gap)

        trade = evaluate(asset, buy_ex, sell_ex, buy_p, sell_p)
        if trade:
            _last_trade_time[key] = now
            save_trade(trade)

        print("-" * 48)
