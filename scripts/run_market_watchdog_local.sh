#!/usr/bin/env bash
#
# run_market_watchdog_local.sh — Survivor Liga MX
#
# Lanzador local del Market Watchdog (pensado para cron/launchd).
# - Usa SIEMPRE $HOME/Projects/survivor-ligamx-bot (NO Desktop).
# - Carga .env si existe (no imprime secretos).
# - Escribe la salida a reports/market_watchdog_launchd.log.
# - No cierra picks ni cambia el estado operativo.
#
set -uo pipefail

PROJECT_DIR="$HOME/Projects/survivor-ligamx-bot"

if [ ! -d "$PROJECT_DIR" ]; then
  echo "ERROR: no existe el proyecto en $PROJECT_DIR" >&2
  exit 1
fi

cd "$PROJECT_DIR"

mkdir -p reports
LOG="reports/market_watchdog_launchd.log"

# Cargar variables de entorno sin exponerlas en logs.
if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

{
  echo "=================================================="
  echo "Market Watchdog local — $(date)"
  echo "Proyecto: $PROJECT_DIR"
  echo "--------------------------------------------------"
  # Ejecuta el watchdog. Pasa cualquier argumento extra recibido por este script.
  python3 src/market_watchdog.py "$@"
  echo "Fin: $(date)"
} >> "$LOG" 2>&1

echo "OK: salida agregada a $PROJECT_DIR/$LOG"
