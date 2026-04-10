"""
news_monitor.py — Monitor de noticias en tiempo real vía RSS.

Fuentes  : CoinDesk, CoinTelegraph
Keywords : hack, sec, listing, partnership, crash, surge
Activos  : BTC (bitcoin), ETH (ethereum), SOL (solana)

Corre en un hilo daemon. pop_new_alerts() devuelve y vacía las alertas pendientes.
Polling cada 60 segundos para no saturar los servidores RSS.
"""

import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
]

KEYWORDS = ["hack", "sec", "listing", "partnership", "crash", "surge"]

ASSET_TERMS = {
    "BTC": ["bitcoin", "btc"],
    "ETH": ["ethereum", "eth"],
    "SOL": ["solana", "sol"],
}

POLL_INTERVAL = 60  # segundos

_pending_alerts: list = []
_seen_guids:     set  = set()
_lock = threading.Lock()

_last_poll: dict[str, str] = {}   # url → "HH:MM:SS" del último polling exitoso
_thread: threading.Thread | None = None


# ---------------------------------------------------------------------------
# Fetch + parse RSS
# ---------------------------------------------------------------------------

def _fetch(url: str) -> bytes | None:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ArbitrageBot/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read()
    except Exception as e:
        print(f"[news] error fetching {url}: {e}")
        return None


def _parse_items(xml_bytes: bytes) -> list[dict]:
    items = []
    try:
        root    = ET.fromstring(xml_bytes)
        channel = root.find("channel")
        if channel is None:
            return items
        for item in channel.findall("item"):
            title = (item.findtext("title") or "").strip()
            guid  = item.findtext("guid") or item.findtext("link") or title
            if title:
                items.append({"title": title, "guid": guid})
    except ET.ParseError:
        pass
    return items


# ---------------------------------------------------------------------------
# Clasificación de artículo
# ---------------------------------------------------------------------------

def _classify(title: str) -> dict | None:
    lower = title.lower()

    found_keywords = [kw for kw in KEYWORDS if kw in lower]
    if not found_keywords:
        return None

    found_assets = [
        asset for asset, terms in ASSET_TERMS.items()
        if any(term in lower for term in terms)
    ]
    if not found_assets:
        return None

    return {"title": title, "keywords": found_keywords, "assets": found_assets}


# ---------------------------------------------------------------------------
# Hilo de polling
# ---------------------------------------------------------------------------

def _poll():
    while True:
        for url in FEEDS:
            data = _fetch(url)
            _last_poll[url] = datetime.now().strftime("%H:%M:%S")
            if not data:
                continue
            for item in _parse_items(data):
                if item["guid"] in _seen_guids:
                    continue
                _seen_guids.add(item["guid"])

                result = _classify(item["title"])
                if result:
                    ts    = datetime.now().strftime("%H:%M:%S")
                    alert = {
                        "time":     ts,
                        "title":    result["title"],
                        "keywords": result["keywords"],
                        "assets":   result["assets"],
                    }
                    with _lock:
                        _pending_alerts.append(alert)

                    assets_str   = ", ".join(result["assets"])
                    keywords_str = ", ".join(result["keywords"])
                    print(f"\n[NEWS {ts}] [{assets_str}] {result['title']}")
                    print(f"  keywords: {keywords_str}")

        time.sleep(POLL_INTERVAL)


_thread = threading.Thread(target=_poll, daemon=True, name="news-monitor")
_thread.start()


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def pop_new_alerts() -> list[dict]:
    """Devuelve y vacía las alertas pendientes."""
    with _lock:
        alerts = list(_pending_alerts)
        _pending_alerts.clear()
    return alerts


def get_status() -> dict:
    """Estado del hilo de noticias y último polling por feed."""
    alive = _thread is not None and _thread.is_alive()
    polls = {}
    for url in FEEDS:
        label = "CoinDesk" if "coindesk" in url else "CoinTelegraph"
        polls[label] = _last_poll.get(url, "-")
    return {"alive": alive, "last_poll": polls}
