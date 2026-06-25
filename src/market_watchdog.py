#!/usr/bin/env python3
"""
Market Watchdog — Survivor Liga MX (v1.32.0)

Vigía ligero del mercado real (momios) de la jornada actual.

Objetivo:
- Revisar si YA existe mercado real API para la jornada actual SIN correr el bot
  completo y SIN gastar API innecesariamente.
- Respetar el presupuesto y cooldown de The Odds API (api_budget.py).
- Avisar por Telegram SOLO cuando la disponibilidad de mercado cambia de forma
  significativa (por ejemplo 0/9 -> >0/9, o parcial -> 9/9), evitando spam.
- NO cierra ni envía un pick de Survivor automáticamente. La decisión final
  sigue siendo de auditor_pre_cierre.py / Real Data Gate.

Etiquetas operativas (español): CERRAR / ESPERAR / CAMBIAR / NO ENVIAR.
El watchdog nunca emite CERRAR: como máximo marca READY_FOR_FULL_AUDIT cuando
todo el mercado real está disponible, dejando el cierre al auditor pre-cierre.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Reutilizamos la lógica existente del proyecto. Cuando se ejecuta como
# `python3 src/market_watchdog.py`, el directorio src/ queda en sys.path, así
# que estos imports planos resuelven a los módulos hermanos.
from market_status import (
    cargar_json,
    es_mercado_real,
    extraer_partidos,
    nombre_local,
    nombre_visitante,
)

try:
    from api_budget import can_call as budget_can_call
    from api_budget import record_call as budget_record_call
    from api_budget import write_report as budget_write_report
except Exception:  # pragma: no cover - api_budget siempre debería existir
    budget_can_call = None
    budget_record_call = None
    budget_write_report = None

try:
    from sync_odds_api import (
        evento_coincide,
        fetch_odds,
        leer_env_si_existe,
        normalizar_bookmakers,
    )
except Exception:  # pragma: no cover
    evento_coincide = None
    fetch_odds = None
    leer_env_si_existe = None
    normalizar_bookmakers = None

try:
    from telegram_notifier import dividir_texto, enviar_mensaje
except Exception:  # pragma: no cover
    dividir_texto = None
    enviar_mensaje = None


BASE_DIR = Path(__file__).resolve().parents[1]
JORNADAS_PATH = BASE_DIR / "data" / "jornadas.json"
STATE_PATH = BASE_DIR / "data" / "watchdog_state.json"
OUTPUT_TXT = BASE_DIR / "reports" / "market_watchdog_ultimo.txt"

DEFAULT_COOLDOWN_MIN = int(os.getenv("ODDS_WATCHDOG_MIN_INTERVAL_MINUTES", "180"))

# Estados de disponibilidad de mercado.
ST_SIN_PARTIDOS = "SIN_PARTIDOS"
ST_NINGUNO = "NINGUNO"
ST_PARCIAL = "PARCIAL"
ST_COMPLETO = "COMPLETO"

# Etiquetas operativas (español).
OP_NO_ENVIAR = "ESPERAR / NO ENVIAR"
OP_CAMBIAR = "CAMBIAR / REVISAR"

# Estados de watchdog para el reporte/estado persistido.
WD_SIN_PARTIDOS = "SIN_PARTIDOS"
WD_ESPERAR = "ESPERAR"
WD_READY = "READY_FOR_FULL_AUDIT"


# ---------------------------------------------------------------------------
# Lógica pura (sin efectos secundarios) — fácil de testear.
# ---------------------------------------------------------------------------
def contar_mercado_local(partidos: List[Dict[str, Any]]) -> Tuple[int, int]:
    """Cuenta partidos con mercado real (estado guardado en jornadas.json)."""
    total = len(partidos)
    disponibles = sum(1 for p in partidos if es_mercado_real(p))
    return disponibles, total


def contar_mercado_live(
    partidos: List[Dict[str, Any]],
    eventos: List[Dict[str, Any]],
) -> Tuple[int, int]:
    """
    Cuenta cuántos partidos de la jornada tienen mercado real en la respuesta
    en vivo de The Odds API, sin modificar jornadas.json.
    """
    total = len(partidos)
    disponibles = 0

    for partido in partidos:
        match = None
        for evento in eventos:
            if evento_coincide(partido, evento):
                match = evento
                break

        if match is None:
            continue

        if normalizar_bookmakers(match):
            disponibles += 1

    return disponibles, total


def clasificar_disponibilidad(disponibles: int, total: int) -> str:
    if total <= 0:
        return ST_SIN_PARTIDOS
    if disponibles <= 0:
        return ST_NINGUNO
    if disponibles >= total:
        return ST_COMPLETO
    return ST_PARCIAL


def etiqueta_operativa(estado: str) -> str:
    """El watchdog jamás autoriza CERRAR; como máximo deja READY_FOR_FULL_AUDIT."""
    # En todos los casos el watchdog mantiene NO ENVIAR salvo pérdida de mercado.
    if estado == ST_COMPLETO:
        return OP_NO_ENVIAR
    return OP_NO_ENVIAR


def status_watchdog(estado: str) -> str:
    if estado == ST_SIN_PARTIDOS:
        return WD_SIN_PARTIDOS
    if estado == ST_COMPLETO:
        return WD_READY
    return WD_ESPERAR


def decidir_alerta(
    prev_disponibles: int,
    prev_estado: str,
    disponibles: int,
    estado: str,
) -> Optional[str]:
    """
    Decide si hay un cambio significativo que amerite Telegram.

    Devuelve el tipo de alerta, o None si no se debe enviar nada.
    Tipos: MERCADO_APARECIO, MERCADO_AUMENTO, MERCADO_DISMINUYO, MERCADO_COMPLETO.
    """
    # Sin partidos cargados: nunca alertamos (no es información de mercado).
    if estado == ST_SIN_PARTIDOS:
        return None

    # Sin cambios reales -> no spam.
    if disponibles == prev_disponibles and estado == prev_estado:
        return None

    # Mercado completo recién alcanzado -> alerta más fuerte.
    if estado == ST_COMPLETO and prev_estado != ST_COMPLETO:
        return "MERCADO_COMPLETO"

    # Apareció mercado por primera vez (de 0 a algo).
    if prev_disponibles == 0 and disponibles > 0:
        return "MERCADO_APARECIO"

    # Aumentó el mercado real disponible.
    if disponibles > prev_disponibles:
        return "MERCADO_AUMENTO"

    # Disminuyó (mercado se retiró) -> requiere revisar / posible CAMBIAR.
    if disponibles < prev_disponibles:
        return "MERCADO_DISMINUYO"

    return None


def construir_mensaje_telegram(
    tipo: str,
    disponibles: int,
    total: int,
    estado: str,
    fuente: str,
) -> str:
    cabecera = "📡 WATCHDOG MERCADO — SURVIVOR LIGA MX"
    marcador = f"Mercado real API: {disponibles}/{total}"
    fuente_txt = "consulta en vivo (The Odds API)" if fuente == "live" else "estado local (sin gastar API)"

    if tipo == "MERCADO_COMPLETO":
        titulo = "🚨 MERCADO COMPLETO DISPONIBLE"
        cuerpo = (
            f"Ya hay mercado real para TODA la jornada ({disponibles}/{total}).\n"
            f"Status: {WD_READY}.\n"
            "Siguiente paso: ejecutar run_bot.sh y revisar auditor_pre_cierre.py.\n"
            "NO se cierra ni se envía pick automáticamente."
        )
        etiqueta = OP_NO_ENVIAR
    elif tipo == "MERCADO_APARECIO":
        titulo = "✅ MERCADO REAL DETECTADO"
        cuerpo = (
            f"Apareció mercado real ({disponibles}/{total}), antes 0.\n"
            "Aún parcial: seguir esperando o revisar lectura de mercado."
        )
        etiqueta = OP_NO_ENVIAR
    elif tipo == "MERCADO_AUMENTO":
        titulo = "📈 MÁS MERCADO REAL DISPONIBLE"
        cuerpo = (
            f"Aumentó el mercado real disponible ({disponibles}/{total}).\n"
            "Todavía no es jornada completa."
        )
        etiqueta = OP_NO_ENVIAR
    elif tipo == "MERCADO_DISMINUYO":
        titulo = "⚠️ MERCADO REAL DISMINUYÓ"
        cuerpo = (
            f"Bajó la cantidad de mercado real ({disponibles}/{total}).\n"
            "Revisar: posible CAMBIAR o esperar nueva publicación."
        )
        etiqueta = OP_CAMBIAR
    else:
        titulo = "ℹ️ CAMBIO DE MERCADO"
        cuerpo = f"Cambio detectado ({disponibles}/{total})."
        etiqueta = OP_NO_ENVIAR

    lineas = [
        cabecera,
        "=" * 40,
        titulo,
        "",
        marcador,
        f"Fuente: {fuente_txt}",
        f"Etiqueta operativa: {etiqueta}",
        "",
        cuerpo,
        "",
        "Recordatorio: la decisión final (CERRAR) la controla auditor_pre_cierre.py / Real Data Gate.",
        f"Generado: {datetime.now().isoformat(timespec='seconds')}",
    ]

    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Efectos secundarios: estado local, reporte, Telegram, API.
# ---------------------------------------------------------------------------
def cargar_estado_previo() -> Dict[str, Any]:
    estado = cargar_json(STATE_PATH, {})
    if not isinstance(estado, dict):
        return {}
    return estado


def guardar_estado(estado: Dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(estado, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def escribir_reporte(
    disponibles: int,
    total: int,
    estado: str,
    wd_status: str,
    etiqueta: str,
    fuente: str,
    alerta_tipo: Optional[str],
    alerta_enviada: bool,
) -> None:
    OUTPUT_TXT.parent.mkdir(parents=True, exist_ok=True)

    fuente_txt = "consulta en vivo (The Odds API)" if fuente == "live" else "estado local (sin gastar API)"

    lineas = [
        "MARKET WATCHDOG — SURVIVOR LIGA MX",
        "-" * 70,
        f"Generado: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"Mercado real API: {disponibles}/{total}",
        f"Disponibilidad: {estado}",
        f"Status watchdog: {wd_status}",
        f"Etiqueta operativa: {etiqueta}",
        f"Fuente del conteo: {fuente_txt}",
        "",
        f"Alerta Telegram: {alerta_tipo or 'ninguna'} "
        f"({'enviada' if alerta_enviada else 'no enviada'})",
        "",
        "Notas:",
        "- El watchdog NO cierra ni envía picks automáticamente.",
        "- La decisión final (CERRAR) la controla auditor_pre_cierre.py / Real Data Gate.",
        "- Sin mercado real, la decisión operativa es ESPERAR / NO ENVIAR.",
    ]

    OUTPUT_TXT.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def enviar_telegram(texto: str) -> Tuple[bool, str]:
    """Envía el aviso por Telegram. No imprime secretos. Devuelve (ok, motivo)."""
    if enviar_mensaje is None or dividir_texto is None:
        return False, "telegram_notifier no disponible"

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        return False, "Telegram no configurado (faltan TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID)"

    try:
        for parte in dividir_texto(texto):
            enviar_mensaje(token, chat_id, parte)
        return True, "enviado"
    except Exception as exc:  # no exponemos token; solo el tipo/razón
        return False, f"error al enviar Telegram: {type(exc).__name__}: {exc}"


def chequear_mercado_live(
    partidos: List[Dict[str, Any]],
    cooldown_min: int,
    forzar: bool,
) -> Tuple[Optional[Tuple[int, int]], str]:
    """
    Intenta una consulta en vivo a The Odds API respetando budget/cooldown.

    Devuelve ((disponibles, total) | None, motivo). None => usar estado local.
    """
    if fetch_odds is None or evento_coincide is None or normalizar_bookmakers is None:
        return None, "sync_odds_api no disponible; se usa estado local"

    if leer_env_si_existe is not None:
        leer_env_si_existe()

    intervalo = 0 if forzar else cooldown_min

    if budget_can_call is not None:
        permitido, mensaje = budget_can_call(
            "the_odds_api",
            units=1,
            min_interval_minutes=intervalo,
        )
        if not permitido:
            return None, f"presupuesto/cooldown: {mensaje}"

    try:
        eventos = fetch_odds()
    except Exception as exc:
        # No se rota ni se gasta crédito si la llamada falló antes de éxito;
        # solo registramos motivo (sin secretos).
        return None, f"fallo consulta API: {type(exc).__name__}: {exc}"

    if budget_record_call is not None:
        budget_record_call(
            "the_odds_api",
            units=1,
            note=f"market_watchdog eventos={len(eventos)} forzar={forzar}",
        )
    if budget_write_report is not None:
        try:
            budget_write_report()
        except Exception:
            pass

    return contar_mercado_live(partidos, eventos), f"consulta en vivo OK (eventos={len(eventos)})"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Watchdog de mercado real Survivor Liga MX (no cierra ni envía picks)."
    )
    parser.add_argument(
        "--no-api",
        action="store_true",
        help="No consulta The Odds API; solo lee el estado local de jornadas.json.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Salta el cooldown del watchdog, pero respeta el límite mensual del budget.",
    )
    parser.add_argument(
        "--no-telegram",
        action="store_true",
        help="Calcula y guarda estado, pero no envía Telegram.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="No guarda estado ni envía Telegram; solo imprime el diagnóstico.",
    )
    parser.add_argument(
        "--cooldown",
        type=int,
        default=DEFAULT_COOLDOWN_MIN,
        help=f"Cooldown en minutos para la consulta en vivo (default {DEFAULT_COOLDOWN_MIN}).",
    )
    args = parser.parse_args()

    print("🐶 MARKET WATCHDOG — SURVIVOR LIGA MX")
    print("=" * 60)

    data = cargar_json(JORNADAS_PATH, [])
    partidos = extraer_partidos(data)

    # Conteo base desde el estado local (sin costo de API).
    disponibles, total = contar_mercado_local(partidos)
    fuente = "local"

    # Consulta en vivo opcional, respetando budget/cooldown.
    if not args.no_api and total > 0:
        resultado_live, motivo = chequear_mercado_live(partidos, args.cooldown, args.force)
        if resultado_live is not None:
            disponibles, total = resultado_live
            fuente = "live"
            print(f"🎰 {motivo}")
        else:
            print(f"⏸️ {motivo}")
            print("➡️ Se usa el estado de mercado local sin gastar API.")
    elif args.no_api:
        print("➡️ Modo --no-api: solo estado local de jornadas.json.")

    estado = clasificar_disponibilidad(disponibles, total)
    wd_status = status_watchdog(estado)
    etiqueta = etiqueta_operativa(estado)

    # Estado previo para detectar cambios significativos.
    previo = cargar_estado_previo()
    prev_disponibles = int(previo.get("disponibles", 0) or 0)
    prev_estado = str(previo.get("disponibilidad", ST_NINGUNO) or ST_NINGUNO)

    tipo_alerta = decidir_alerta(prev_disponibles, prev_estado, disponibles, estado)

    print("")
    print(f"Mercado real API: {disponibles}/{total}")
    print(f"Disponibilidad: {estado}")
    print(f"Status watchdog: {wd_status}")
    print(f"Etiqueta operativa: {etiqueta}")

    alerta_enviada = False
    motivo_telegram = "sin cambios significativos" if tipo_alerta is None else ""

    if tipo_alerta is not None:
        mensaje = construir_mensaje_telegram(tipo_alerta, disponibles, total, estado, fuente)
        if args.dry_run or args.no_telegram:
            motivo_telegram = "omitido (--dry-run/--no-telegram)"
            print(f"🔔 Cambio detectado ({tipo_alerta}); Telegram {motivo_telegram}.")
        else:
            alerta_enviada, motivo_telegram = enviar_telegram(mensaje)
            if alerta_enviada:
                print(f"📨 Telegram enviado: {tipo_alerta}")
            else:
                print(f"⚠️ Telegram no enviado ({tipo_alerta}): {motivo_telegram}")
    else:
        print("🔕 Sin cambios significativos de mercado; no se envía Telegram.")

    nuevo_estado = {
        "actualizado_en": datetime.now().isoformat(timespec="seconds"),
        "disponibles": disponibles,
        "total": total,
        "disponibilidad": estado,
        "status_watchdog": wd_status,
        "etiqueta_operativa": etiqueta,
        "fuente": fuente,
        "ultimo_alerta_tipo": tipo_alerta if alerta_enviada else previo.get("ultimo_alerta_tipo"),
        "ultimo_alerta_en": (
            datetime.now().isoformat(timespec="seconds")
            if alerta_enviada
            else previo.get("ultimo_alerta_en")
        ),
    }

    if not args.dry_run:
        guardar_estado(nuevo_estado)
        escribir_reporte(
            disponibles,
            total,
            estado,
            wd_status,
            etiqueta,
            fuente,
            tipo_alerta,
            alerta_enviada,
        )
        print(f"✅ Estado guardado: {STATE_PATH}")
        print(f"✅ Reporte: {OUTPUT_TXT}")
    else:
        print("🧪 --dry-run: no se guardó estado ni reporte.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
