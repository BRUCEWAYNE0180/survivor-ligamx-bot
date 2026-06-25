# Comandos — Survivor Liga MX Bot

Todos los comandos se ejecutan desde la raíz del proyecto. Requieren un archivo
`.env` con las llaves necesarias (nunca se versiona).

## Bot completo

```bash
./run_bot.sh
```

Ejecuta toda la cadena: normalizar jornada, sincronizar momios reales, noticias
IA, riesgo, reglas, auditoría, pick ajustado, **auditor pre-cierre (Real Data
Gate)**, lectura de mercado, presupuesto de APIs y reporte/Telegram final.

## Estado de mercado (sin gastar API)

```bash
python3 src/market_status.py
```

## Presupuesto de APIs

```bash
python3 src/api_budget.py report
```

## Market Watchdog (v1.32.0)

Vigía ligero del mercado real de la jornada actual. **No corre el bot completo,
no cierra ni envía picks.** Avisa por Telegram solo cuando la disponibilidad de
mercado cambia de forma significativa (evita spam). Cuando el mercado está
completo marca `READY_FOR_FULL_AUDIT`, nunca `CERRAR`.

```bash
# Revisión normal (puede hacer 1 consulta en vivo si budget/cooldown lo permiten)
python3 src/market_watchdog.py

# Solo estado local, sin tocar The Odds API (no gasta presupuesto)
python3 src/market_watchdog.py --no-api

# Saltar cooldown del watchdog (respeta el límite mensual del budget)
python3 src/market_watchdog.py --force

# Calcular y guardar estado, pero sin enviar Telegram
python3 src/market_watchdog.py --no-telegram

# Diagnóstico sin guardar estado ni enviar Telegram
python3 src/market_watchdog.py --dry-run
```

Variables de entorno relevantes:

- `ODDS_WATCHDOG_MIN_INTERVAL_MINUTES`: cooldown del watchdog (default `180`).
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`: destino de las alertas Telegram.

Archivos que produce (en carpetas locales ignoradas por git):

- `data/watchdog_state.json`: último estado para detectar cambios.
- `reports/market_watchdog_ultimo.txt`: reporte legible de la última corrida.

## Tests

```bash
python3 -m unittest tests.test_market_watchdog
```
