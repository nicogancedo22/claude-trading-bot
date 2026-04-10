"""
paper_trader.py — Simulación realista de arbitraje entre exchanges.

Modelo de capital distribuido:
  - Capital total ficticio: $1,000 USDT por exchange en USDT + holdings pre-cargados
  - Cada exchange arranca con $100 USDT y 1 TRADE_SIZE de cada activo en crypto
  - Para ejecutar A->B: A necesita USDT (compra), B necesita el activo (vende)
  - El trade es simultáneo en ambos exchanges
  - No se simula rebalanceo automático entre exchanges
"""

import json
import os
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional

INITIAL_USDT_PER_EXCHANGE = 100.0
TRADE_SIZE                = 100.0
SLIPPAGE                  = 0.0005
FEE                       = 0.001

EXCHANGES = ["binance", "kraken", "coinbase", "okx", "bybit"]
ASSETS    = ["BTC", "ETH", "SOL", "DOGE", "XRP", "ADA", "SHIB"]

REFERENCE_PRICES = {
    "BTC":  83_000.0,
    "ETH":   1_600.0,
    "SOL":     120.0,
    "DOGE":      0.17,
    "XRP":       2.1,
    "ADA":       0.65,
    "SHIB":      0.0000059,
}

_INITIAL_USDT_TOTAL = INITIAL_USDT_PER_EXCHANGE * len(EXCHANGES)

_PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), "..", "logs", "portfolio.json")


def _initial_portfolio() -> dict:
    exchanges = {}
    for ex in EXCHANGES:
        holdings = {
            asset: round(TRADE_SIZE / REFERENCE_PRICES[asset], 8)
            for asset in ASSETS
        }
        exchanges[ex] = {
            "usdt":     INITIAL_USDT_PER_EXCHANGE,
            "holdings": holdings,
        }
    return {
        "exchanges": exchanges,
        "trades":    [],
    }


def _load_portfolio() -> dict:
    try:
        with open(_PORTFOLIO_FILE) as f:
            data = json.load(f)
        if "exchanges" in data:
            return data
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError):
        pass
    return _initial_portfolio()


def _save_portfolio(data: dict) -> None:
    os.makedirs(os.path.dirname(_PORTFOLIO_FILE), exist_ok=True)
    with open(_PORTFOLIO_FILE, "w") as f:
        json.dump(data, f, indent=2)


@dataclass
class Trade:
    timestamp:     str
    asset:         str
    buy_exchange:  str
    sell_exchange: str
    price_buy:     float
    price_sell:    float
    exec_buy:      float
    exec_sell:     float
    quantity:      float
    gross_pnl:     float
    fee_cost:      float
    net_pnl:       float
    capital_after: float


@dataclass
class Portfolio:
    exchanges:  dict  = field(default_factory=dict)
    trades:     list  = field(default_factory=list)
    last_trade: Optional[Trade] = None

    @property
    def total_usdt(self) -> float:
        return sum(ex["usdt"] for ex in self.exchanges.values())

    @property
    def total_pnl(self) -> float:
        return self.total_usdt - _INITIAL_USDT_TOTAL

    @property
    def trade_count(self) -> int:
        return len(self.trades)


_data      = _load_portfolio()
_portfolio = Portfolio(
    exchanges = _data["exchanges"],
    trades    = [],
)


def evaluate(
    asset: str,
    buy_exchange: str,
    sell_exchange: str,
    buy_price: float,
    sell_price: float,
) -> Optional[Trade]:
    buy_ex_data  = _portfolio.exchanges.get(buy_exchange)
    sell_ex_data = _portfolio.exchanges.get(sell_exchange)

    if buy_ex_data is None or sell_ex_data is None:
        print(f"  [RECHAZADO] exchange desconocido: {buy_exchange} o {sell_exchange}")
        return None

    exec_buy  = buy_price  * (1 + SLIPPAGE)
    exec_sell = sell_price * (1 - SLIPPAGE)

    quantity  = TRADE_SIZE / exec_buy
    cost_buy  = TRADE_SIZE * (1 + FEE)
    proceeds  = quantity * exec_sell * (1 - FEE)
    fee_cost  = TRADE_SIZE * FEE + quantity * exec_sell * FEE
    gross_pnl = quantity * exec_sell - TRADE_SIZE
    net_pnl   = proceeds - TRADE_SIZE

    usdt_disponible  = buy_ex_data["usdt"]
    asset_disponible = sell_ex_data["holdings"].get(asset, 0.0)

    if usdt_disponible < cost_buy:
        print(
            f"  [RECHAZADO] {buy_exchange} no tiene suficiente USDT "
            f"(necesita ${TRADE_SIZE:.2f}, tiene ${usdt_disponible:.2f})"
        )
        return None

    if asset_disponible < quantity:
        print(
            f"  [RECHAZADO] {sell_exchange} no tiene suficiente {asset} "
            f"(necesita {quantity:.6f}, tiene {asset_disponible:.6f})"
        )
        return None

    print(f"  exec_buy={exec_buy:.4f}  exec_sell={exec_sell:.4f}  qty={quantity:.6f} {asset}")
    print(f"  bruto=${gross_pnl:.4f}  fees=${fee_cost:.4f}  neto=${net_pnl:.4f}")

    if net_pnl <= 0:
        print(f"  [RECHAZADO] no rentable tras costos (${net_pnl:.4f})")
        return None

    buy_ex_data["usdt"]                        -= cost_buy
    buy_ex_data["holdings"].setdefault(asset, 0.0)
    buy_ex_data["holdings"][asset]             += quantity

    sell_ex_data["holdings"][asset]            -= quantity
    sell_ex_data["usdt"]                       += proceeds

    total_usdt = _portfolio.total_usdt

    trade = Trade(
        timestamp     = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        asset         = asset,
        buy_exchange  = buy_exchange,
        sell_exchange = sell_exchange,
        price_buy     = buy_price,
        price_sell    = sell_price,
        exec_buy      = exec_buy,
        exec_sell     = exec_sell,
        quantity      = quantity,
        gross_pnl     = gross_pnl,
        fee_cost      = fee_cost,
        net_pnl       = net_pnl,
        capital_after = total_usdt,
    )
    _portfolio.trades.append(trade)
    _portfolio.last_trade = trade

    _data["exchanges"] = _portfolio.exchanges
    _data["trades"].append(asdict(trade))
    _save_portfolio(_data)

    print(f"  [EJECUTADO] neto=${net_pnl:.4f} | USDT total=${total_usdt:.2f}")
    return trade


def get_portfolio() -> Portfolio:
    return _portfolio


def summary_line(all_prices: dict = None) -> str:
    p    = _portfolio
    sign = "+" if p.total_pnl >= 0 else ""

    prices_block = ""
    if all_prices:
        for asset, exchanges in all_prices.items():
            prices_block += f"  {asset}:\n"
            for ex, data in exchanges.items():
                bid = data.get("bid")
                ask = data.get("ask")
                if bid is None or ask is None:
                    val = "conectando..."
                else:
                    mid = (bid + ask) / 2
                    if mid < 0.0001:
                        val = f"${mid:.8f}"
                    elif mid < 0.01:
                        val = f"${mid:.6f}"
                    elif mid < 1:
                        val = f"${mid:.4f}"
                    else:
                        val = f"${mid:,.2f}"
                prices_block += f"    {ex.capitalize():<10}: {val}\n"

    balances_block = "  Balances USDT por exchange:\n"
    for ex, data in p.exchanges.items():
        balances_block += f"    {ex.capitalize():<10}: ${data['usdt']:,.2f}\n"

    last = "ninguna"
    if p.last_trade:
        t    = p.last_trade
        last = f"{t.timestamp}  [{t.asset}] {t.buy_exchange}->{t.sell_exchange}  neto=${t.net_pnl:.4f}"

    return (
        f"\n{'='*58}\n"
        f"  RESUMEN  {datetime.now().strftime('%H:%M:%S')}\n"
        f"{prices_block}"
        f"{balances_block}"
        f"  USDT total  : ${p.total_usdt:,.2f}\n"
        f"  P&L total   : {sign}${p.total_pnl:.4f}\n"
        f"  Operaciones : {p.trade_count}\n"
        f"  Ultima op   : {last}\n"
        f"{'='*58}\n"
    )
