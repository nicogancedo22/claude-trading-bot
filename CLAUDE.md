# CLAUDE AGENT 1.0 — Bot de Arbitraje

## Contexto del proyecto
Bot de trading en Python que detecta desbalances de precio del mismo activo entre exchanges (arbitraje triangular). Desarrollado por Nicolas, 19 años, emprendedor. Objetivo: operar en tiempo real cuando precio de exchange A != precio exchange B para el mismo activo.

## Estructura
```
src/
  main.py           → loop principal (time.sleep(1)), resumen cada 10s con noticias
  data_sources.py   → 5 conexiones WebSocket (una por exchange, 7 activos cada una)
  detector.py       → detecta arbitraje por activo, alerta si gap > $100, evalúa si gap > min_gap
  logger.py         → guarda oportunidades, gaps y trades en logs/
  paper_trader.py   → simulación de trades con capital ficticio ($1,000 USDT)
  news_monitor.py   → monitor RSS en hilo daemon, detecta keywords por activo
logs/
  opportunities.txt → historial de oportunidades detectadas (con activo)
  trades.txt        → historial de trades ejecutados en papel
  gaps.txt          → snapshot de gaps cada 10 segundos
```

## Estado actual
- **Precios en tiempo real** vía WebSocket (5 exchanges × 7 activos = 35 feeds, 5 conexiones)
- **Exchanges**: Binance, Kraken, Coinbase, OKX, Bybit
- **Activos**: BTC/USDT, ETH/USDT, SOL/USDT, DOGE/USDT, XRP/USDT, ADA/USDT, SHIB/USDT
- Binance usa combined stream (`btcusdt@bookTicker/...` por activo)
- Kraken, Coinbase, OKX y Bybit usan una sola conexión con multi-symbol subscription
- Detecta gaps > `avg_price * (2 * SLIPPAGE + 2 * FEE)` como oportunidad rentable
- Alerta visual en consola para gaps > $100
- Paper trading con capital de $1,000 USDT, tamaño fijo $100 por trade
- Monitor de noticias RSS (CoinDesk, CoinTelegraph) — polling cada 60s
- Resumen en consola cada 10 segundos con precios, P&L y noticias recientes

## Parámetros de paper trading
- `INITIAL_USDT_PER_EXCHANGE` = $100 USDT por exchange (5 exchanges = $500 total)
- `TRADE_SIZE`      = $100 USDT fijo por operación
- `SLIPPAGE`        = 0.05% por lado (ya incluido en exec_buy/exec_sell)
- `FEE`             = 0.10% por lado (taker, aplicado sobre costo y ganancias)
- `cost_buy`        = `TRADE_SIZE * (1 + FEE)` — slippage ya en exec_buy
- `min_gap`         = `avg_price * (2 * SLIPPAGE + 2 * FEE)` = ~0.30% del precio

## Monitor de noticias
- Keywords detectados: `hack`, `sec`, `listing`, `partnership`, `crash`, `surge`
- Activos monitoreados: BTC (bitcoin/btc), ETH (ethereum/eth), SOL (solana/sol), DOGE, XRP, ADA, SHIB
- Alerta inmediata en consola al detectar noticia relevante
- Las alertas acumuladas aparecen en el resumen cada 10s (máx. 5 más recientes)

## Decisiones de arquitectura
- Modular: cada archivo tiene una sola responsabilidad
- `data_sources.py` es el único archivo a modificar para cambiar fuentes de datos
- Una conexión WebSocket por exchange (no por activo) — más eficiente
- `get_prices()` devuelve `{"BTC": {"binance": {"bid": float|None, "ask": float|None}, ...}, ...}`
- `news_monitor.py` corre en hilo daemon independiente, no bloquea el loop principal
- No ejecuta órdenes reales — solo detecta, simula y loguea

## Próximos pasos (en orden)
1. Evaluar ejecución real de órdenes (conectar API keys de exchanges)
2. Ajustar `TRADE_SIZE` dinámicamente según volatilidad o tamaño del gap
3. Agregar más activos o exchanges según donde aparezcan las mejores oportunidades
4. Considerar latencia de red para priorizar exchange más cercano al ejecutar

## Notas importantes
- El arbitraje real en microsegundos requiere colocación física cerca del exchange; a escala actual apuntar a diferencias que duren segundos
- CoinTelegraph puede dar timeout (bloquea user-agents de bots) — el código lo reintenta automáticamente cada 60s
- Kraken v2 WebSocket: el campo `symbol` en la respuesta es `"BTC/USDT"` (con slash)
- Coinbase usa `"BTC-USD"` (con guión) que se trata como equivalente a USDT
- Bug corregido (2026-04-09): el slippage se aplicaba dos veces en paper_trader — en `exec_buy`/`exec_sell` Y en `cost_buy`/`proceeds`. Fix: `cost_buy = TRADE_SIZE * (1 + FEE)` y `proceeds = quantity * exec_sell * (1 - FEE)`. También corregido el chequeo de saldo (`< cost_buy` en vez de `< TRADE_SIZE`) que causaba USDT negativo.
