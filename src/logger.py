import os
from datetime import datetime
from itertools import combinations

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE   = os.path.join(_PROJECT_ROOT, "logs", "opportunities.txt")
TRADE_FILE = os.path.join(_PROJECT_ROOT, "logs", "trades.txt")
GAPS_FILE  = os.path.join(_PROJECT_ROOT, "logs", "gaps.txt")


def _fmt_price(price: float) -> str:
    """Formatea un precio con suficientes decimales para activos de bajo valor."""
    if price < 0.01:
        return f"{price:.8f}"
    elif price < 1:
        return f"{price:.6f}"
    else:
        return f"{price:.2f}"


def save_opportunity(
    asset: str,
    buy_exchange: str, sell_exchange: str,
    buy_price: float, sell_price: float,
    gap: float,
) -> None:
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = (
        f"{ts} | {asset} | "
        f"BUY {buy_exchange}: {_fmt_price(buy_price)} | "
        f"SELL {sell_exchange}: {_fmt_price(sell_price)} | "
        f"gap={_fmt_price(gap)}\n"
    )
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)


def save_gaps(all_prices: dict) -> None:
    """
    all_prices: {"BTC": {"binance": {"bid": float|None, "ask": float|None}, ...}, ...}
    """
    ts    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    parts = []
    for asset, exchanges in all_prices.items():
        mids = {}
        for ex, data in exchanges.items():
            if data["bid"] is not None and data["ask"] is not None:
                mids[ex] = (data["bid"] + data["ask"]) / 2
        if len(mids) < 2:
            continue
        for ex_a, ex_b in combinations(mids, 2):
            gap = abs(mids[ex_b] - mids[ex_a])
            parts.append(f"{asset} {ex_a}/{ex_b}: ${gap:.6f}")
    if not parts:
        return
    line = f"{ts} | {' | '.join(parts)}\n"
    with open(GAPS_FILE, "a", encoding="utf-8") as f:
        f.write(line)


def save_trade(trade) -> None:
    line = (
        f"{trade.timestamp} | {trade.asset} | "
        f"{trade.buy_exchange}->{trade.sell_exchange} | "
        f"buy={_fmt_price(trade.exec_buy)} sell={_fmt_price(trade.exec_sell)} | "
        f"qty={trade.quantity:.6f} {trade.asset} | "
        f"bruto=${trade.gross_pnl:.4f} fees=${trade.fee_cost:.4f} neto=${trade.net_pnl:.4f} | "
        f"capital=${trade.capital_after:.2f}\n"
    )
    with open(TRADE_FILE, "a", encoding="utf-8") as f:
        f.write(line)
