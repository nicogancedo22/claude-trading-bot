"""
data_sources.py — WebSocket feeds para 5 exchanges × 7 activos en paralelo

Exchanges : Binance, Kraken, Coinbase, OKX, Bybit
Activos   : BTC, ETH, SOL, DOGE, XRP, ADA, SHIB

Cada exchange/activo almacena bid y ask por separado.
El detector usa ask para comprar y bid para vender — precio real de mercado.

get_prices() devuelve:
    {
        "BTC": {
            "binance":  {"bid": float|None, "ask": float|None},
            "kraken":   {"bid": float|None, "ask": float|None},
            ...
        },
        ...
    }
"""

import copy
import json
import threading
import websocket

# ---------------------------------------------------------------------------
# Estado compartido
# ---------------------------------------------------------------------------

ASSETS    = ["BTC", "ETH", "SOL", "DOGE", "XRP", "ADA", "SHIB"]
EXCHANGES = ["binance", "kraken", "coinbase", "okx", "bybit"]

_prices: dict = {
    asset: {ex: {"bid": None, "ask": None} for ex in EXCHANGES}
    for asset in ASSETS
}
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Binance — combined stream (@bookTicker)
# ---------------------------------------------------------------------------

_BINANCE_URL = (
    "wss://stream.binance.com:9443/stream"
    "?streams=btcusdt@bookTicker/ethusdt@bookTicker/solusdt@bookTicker"
    "/dogeusdt@bookTicker/xrpusdt@bookTicker/adausdt@bookTicker/shibusdt@bookTicker"
)

_BINANCE_STREAM_ASSET = {
    "btcusdt@bookticker":  "BTC",
    "ethusdt@bookticker":  "ETH",
    "solusdt@bookticker":  "SOL",
    "dogeusdt@bookticker": "DOGE",
    "xrpusdt@bookticker":  "XRP",
    "adausdt@bookticker":  "ADA",
    "shibusdt@bookticker": "SHIB",
}


def _on_binance(ws, msg):
    data   = json.loads(msg)
    stream = data.get("stream", "").lower()
    asset  = _BINANCE_STREAM_ASSET.get(stream)
    if asset is None:
        return
    payload = data.get("data", {})
    if "b" in payload and "a" in payload:
        with _lock:
            _prices[asset]["binance"]["bid"] = float(payload["b"])
            _prices[asset]["binance"]["ask"] = float(payload["a"])


# ---------------------------------------------------------------------------
# Kraken v2 — multi-symbol ticker
# ---------------------------------------------------------------------------

_KRAKEN_URL = "wss://ws.kraken.com/v2"
_KRAKEN_SUB = json.dumps({
    "method": "subscribe",
    "params": {"channel": "ticker", "symbol": [
        "BTC/USDT", "ETH/USDT", "SOL/USDT",
        "DOGE/USDT", "XRP/USDT", "ADA/USDT", "SHIB/USDT",
    ]},
})

_KRAKEN_SYMBOL_ASSET = {
    "BTC/USDT":  "BTC",
    "ETH/USDT":  "ETH",
    "SOL/USDT":  "SOL",
    "DOGE/USDT": "DOGE",
    "XRP/USDT":  "XRP",
    "ADA/USDT":  "ADA",
    "SHIB/USDT": "SHIB",
}


def _on_kraken_open(ws):
    ws.send(_KRAKEN_SUB)


def _on_kraken(ws, msg):
    data = json.loads(msg)
    if data.get("channel") == "ticker" and data.get("type") in ("snapshot", "update"):
        for t in data.get("data", []):
            asset = _KRAKEN_SYMBOL_ASSET.get(t.get("symbol", ""))
            if asset and "bid" in t and "ask" in t:
                with _lock:
                    _prices[asset]["kraken"]["bid"] = float(t["bid"])
                    _prices[asset]["kraken"]["ask"] = float(t["ask"])


# ---------------------------------------------------------------------------
# Coinbase Exchange — multi product_ids ticker
# ---------------------------------------------------------------------------

_COINBASE_URL = "wss://ws-feed.exchange.coinbase.com"
_COINBASE_SUB = json.dumps({
    "type": "subscribe",
    "channels": [{"name": "ticker", "product_ids": [
        "BTC-USD", "ETH-USD", "SOL-USD",
        "DOGE-USD", "XRP-USD", "ADA-USD", "SHIB-USD",
    ]}],
})

_COINBASE_PRODUCT_ASSET = {
    "BTC-USD":  "BTC",
    "ETH-USD":  "ETH",
    "SOL-USD":  "SOL",
    "DOGE-USD": "DOGE",
    "XRP-USD":  "XRP",
    "ADA-USD":  "ADA",
    "SHIB-USD": "SHIB",
}


def _on_coinbase_open(ws):
    ws.send(_COINBASE_SUB)


def _on_coinbase(ws, msg):
    data = json.loads(msg)
    if data.get("type") == "ticker" and "best_bid" in data and "best_ask" in data:
        asset = _COINBASE_PRODUCT_ASSET.get(data.get("product_id", ""))
        if asset:
            with _lock:
                _prices[asset]["coinbase"]["bid"] = float(data["best_bid"])
                _prices[asset]["coinbase"]["ask"] = float(data["best_ask"])


# ---------------------------------------------------------------------------
# OKX — public WebSocket ticker
# ---------------------------------------------------------------------------

_OKX_URL = "wss://ws.okx.com:8443/ws/v5/public"
_OKX_INSTRUMENTS = [
    "BTC-USDT", "ETH-USDT", "SOL-USDT",
    "DOGE-USDT", "XRP-USDT", "ADA-USDT", "SHIB-USDT",
]
_OKX_SUB = json.dumps({
    "op": "subscribe",
    "args": [{"channel": "tickers", "instId": inst} for inst in _OKX_INSTRUMENTS],
})

_OKX_INST_ASSET = {
    "BTC-USDT":  "BTC",
    "ETH-USDT":  "ETH",
    "SOL-USDT":  "SOL",
    "DOGE-USDT": "DOGE",
    "XRP-USDT":  "XRP",
    "ADA-USDT":  "ADA",
    "SHIB-USDT": "SHIB",
}


def _on_okx_open(ws):
    ws.send(_OKX_SUB)


def _on_okx(ws, msg):
    data = json.loads(msg)
    if data.get("event") == "subscribe":
        return
    for item in data.get("data", []):
        asset = _OKX_INST_ASSET.get(item.get("instId", ""))
        if asset and "bidPx" in item and "askPx" in item:
            try:
                with _lock:
                    _prices[asset]["okx"]["bid"] = float(item["bidPx"])
                    _prices[asset]["okx"]["ask"] = float(item["askPx"])
            except ValueError:
                pass


# ---------------------------------------------------------------------------
# Bybit — public WebSocket ticker
# ---------------------------------------------------------------------------

_BYBIT_URL = "wss://stream.bybit.com/v5/public/spot"
_BYBIT_TOPICS = [
    "tickers.BTCUSDT", "tickers.ETHUSDT", "tickers.SOLUSDT",
    "tickers.DOGEUSDT", "tickers.XRPUSDT", "tickers.ADAUSDT", "tickers.SHIBUSDT",
]
_BYBIT_SUB = json.dumps({
    "op": "subscribe",
    "args": _BYBIT_TOPICS,
})

_BYBIT_SYMBOL_ASSET = {
    "BTCUSDT":  "BTC",
    "ETHUSDT":  "ETH",
    "SOLUSDT":  "SOL",
    "DOGEUSDT": "DOGE",
    "XRPUSDT":  "XRP",
    "ADAUSDT":  "ADA",
    "SHIBUSDT": "SHIB",
}


def _on_bybit_open(ws):
    ws.send(_BYBIT_SUB)


def _on_bybit(ws, msg):
    data = json.loads(msg)
    if data.get("op") == "subscribe":
        return
    item = data.get("data", {})
    asset = _BYBIT_SYMBOL_ASSET.get(item.get("symbol", ""))
    if asset and "bid1Price" in item and "ask1Price" in item:
        try:
            bid = float(item["bid1Price"])
            ask = float(item["ask1Price"])
            if bid > 0 and ask > 0:
                with _lock:
                    _prices[asset]["bybit"]["bid"] = bid
                    _prices[asset]["bybit"]["ask"] = ask
        except ValueError:
            pass


# ---------------------------------------------------------------------------
# Runner genérico con reconexión automática
# ---------------------------------------------------------------------------

def _on_error(ws, error):
    name = threading.current_thread().name
    print(f"[{name}] error: {error}")


def _on_close(ws, code, msg):
    pass


def _run_ws(url: str, on_message, on_open=None):
    while True:
        ws = websocket.WebSocketApp(
            url,
            on_open=on_open,
            on_message=on_message,
            on_error=_on_error,
            on_close=_on_close,
        )
        ws.run_forever(reconnect=5)


# ---------------------------------------------------------------------------
# Arrancar los 5 hilos
# ---------------------------------------------------------------------------

_STREAMS = [
    ("ws-binance",  _BINANCE_URL,  _on_binance,  None),
    ("ws-kraken",   _KRAKEN_URL,   _on_kraken,   _on_kraken_open),
    ("ws-coinbase", _COINBASE_URL, _on_coinbase, _on_coinbase_open),
    ("ws-okx",      _OKX_URL,      _on_okx,      _on_okx_open),
    ("ws-bybit",    _BYBIT_URL,    _on_bybit,     _on_bybit_open),
]

for _name, _url, _on_msg, _on_open in _STREAMS:
    threading.Thread(
        target=_run_ws, args=(_url, _on_msg, _on_open),
        daemon=True, name=_name,
    ).start()


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def get_prices() -> dict:
    """
    Devuelve snapshot actual con bid y ask por exchange:
        {"BTC": {"binance": {"bid": float|None, "ask": float|None}, ...}, ...}
    """
    with _lock:
        return copy.deepcopy(_prices)
