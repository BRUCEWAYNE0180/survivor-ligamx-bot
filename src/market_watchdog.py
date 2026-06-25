#!/usr/bin/env python3
"""
Market Watchdog — Survivor Liga MX (v1.34.0)

Vigía ligero e independiente del mercado real (momios) de la jornada actual.

v1.32.0 — Disponibilidad de mercado:
- Revisa si YA existe mercado real API para la jornada actual SIN correr el bot
  completo y SIN gastar API innecesariamente.
- Respeta el presupuesto y cooldown de The Odds API (api_budget.py).
- Avisa por Telegram SOLO cuando la disponibilidad de mercado cambia de forma
  significativa (por ejemplo 0/9 -> >0/9, o parcial -> 9/9), evitando spam.

v1.33.0 — Movimiento de momios (1X2):
- Una vez que existe mercado real, guarda snapshots de momios 1X2 (local/empate/
  visitante) por partido y los compara contra el snapshot previo.
- Convierte momios a probabilidad implícita (sin vig) cuando es posible.
- Clasifica el movimiento por puntos de probabilidad implícita:
    * NORMAL    (< 5 pts)   -> solo se guarda, sin Telegram.
    * IMPORTANTE (5 a 8 pts) -> se reporta; Telegram opcional.
    * DRASTICO  (>= 8 pts)  -> Telegram.
    * Cambio de favorito     -> Telegram más fuerte.
- Evita Telegram duplicado del mismo movimiento salvo que empeore materialmente.

v1.34.0 — Multi-mercado:
- Además de 1X2 / Moneyline, monitorea (cuando The Odds API los publica):
    * Totals / Over-Under (preferente Over/Under 2.5).
    * BTTS / Ambos Anotan (Sí/No).
    * Hándicap / Spread principal (línea + precio).
    * Draw No Bet / Empate No Acción.
- Si un mercado opcional no está disponible, se reporta "mercado no disponible"
  y se continúa de forma segura (no se fuerza ningún mercado).
- Clasificación: NORMAL / IMPORTANTE / DRASTICO y CRITICO (cambio de favorito o
  lado, flip de Over/Under o BTTS, o movimiento mayor de línea de hándicap).
- Interpretación Survivor:
    * 1X2 / ML es el mercado primario.
    * Over/Under y BTTS son contexto de volatilidad/riesgo.
    * Hándicap y Draw No Bet son señales de fuerza/contexto.

Reglas operativas (no cambian):
- NO cierra ni envía un pick de Survivor automáticamente.
- La decisión final (CERRAR) la controla auditor_pre_cierre.py / Real Data Gate.
- Disponibilidad: etiquetas CERRAR / ESPERAR / CAMBIAR / NO ENVIAR. El watchdog
  nunca emite CERRAR; como máximo marca READY_FOR_FULL_AUDIT.
- Movimiento de momios (cualquier mercado): etiqueta AUDITAR / NO ENVIAR
  AUTOMÁTICO, nunca CERRAR.
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
        equipos_coinciden,
        evento_coincide,
        fetch_odds,
        leer_env_si_existe,
        normalizar,
        normalizar_bookmakers,
    )
except Exception:  # pragma: no cover
    equipos_coinciden = None
    evento_coincide = None
    fetch_odds = None
    leer_env_si_existe = None
    normalizar = None
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
TELEGRAM_IMPORTANTE_ENV = os.getenv("ODDS_WATCHDOG_TELEGRAM_IMPORTANTE", "0").strip() in {"1", "true", "True", "yes"}

# Estados de disponibilidad de mercado.
ST_SIN_PARTIDOS = "SIN_PARTIDOS"
ST_NINGUNO = "NINGUNO"
ST_PARCIAL = "PARCIAL"
ST_COMPLETO = "COMPLETO"

# Etiquetas operativas (español).
OP_NO_ENVIAR = "ESPERAR / NO ENVIAR"
OP_CAMBIAR = "CAMBIAR / REVISAR"
OP_AUDITAR = "AUDITAR / NO ENVIAR AUTOMÁTICO"

# Estados de watchdog para el reporte/estado persistido.
WD_SIN_PARTIDOS = "SIN_PARTIDOS"
WD_ESPERAR = "ESPERAR"
WD_READY = "READY_FOR_FULL_AUDIT"

# Clasificación de movimiento de momios (puntos de probabilidad implícita).
MOV_NORMAL = "NORMAL"
MOV_IMPORTANTE = "IMPORTANTE"
MOV_DRASTICO = "DRASTICO"
MOV_CRITICO = "CRITICO"

UMBRAL_IMPORTANTE = 5.0   # >= 5 pts
UMBRAL_DRASTICO = 8.0     # >= 8 pts
MATERIAL_WORSEN_PTS = 3.0  # cuánto debe empeorar para re-alertar el mismo movimiento
UMBRAL_LINEA_HANDICAP = 0.5  # movimiento mayor de línea de hándicap (medio gol)

LINEA_TOTALS_PREFERIDA = float(os.getenv("ODDS_WATCHDOG_TOTALS_LINE", "2.5"))

SEVERIDAD = {MOV_NORMAL: 0, MOV_IMPORTANTE: 1, MOV_DRASTICO: 2, MOV_CRITICO: 3}

EMPATE_NOMBRES = {"draw", "empate", "tie", "x", "tablas"}
OVER_NOMBRES = {"over", "mas", "más", "alta"}
UNDER_NOMBRES = {"under", "menos", "baja"}
SI_NOMBRES = {"yes", "si", "sí"}
NO_NOMBRES = {"no"}

ETIQUETA_FAVORITO = {"home": "Local", "draw": "Empate", "away": "Visitante"}
ETIQUETA_LADO = {
    "home": "Local",
    "draw": "Empate",
    "away": "Visitante",
    "over": "Over",
    "under": "Under",
    "yes": "Sí",
    "no": "No",
}
ETIQUETA_MERCADO = {
    "1x2": "1X2 / Moneyline",
    "totals": "Over/Under",
    "btts": "BTTS / Ambos Anotan",
    "spreads": "Hándicap / Spread",
    "dnb": "Draw No Bet / Empate No Acción",
}
# Mercados opcionales (secundarios). 1X2 es el primario.
MERCADOS_OPCIONALES = ["totals", "btts", "spreads", "dnb"]
# Campo que indica el "lado favorito" de cada mercado.
CAMPO_LADO = {
    "1x2": "favorito",
    "totals": "lado",
    "btts": "lado",
    "spreads": "favorito",
    "dnb": "favorito",
}


# ---------------------------------------------------------------------------
# Helpers de normalización tolerantes (degradan si sync_odds_api no está).
# ---------------------------------------------------------------------------
def _norm(texto: Any) -> str:
    if normalizar is not None:
        return normalizar(str(texto or ""))
    return str(texto or "").strip().lower()


def _coincide_equipo(a: str, b: str) -> bool:
    if equipos_coinciden is not None:
        return equipos_coinciden(a, b)
    return _norm(a) == _norm(b)


def _es_empate(nombre: str) -> bool:
    return _norm(nombre) in EMPATE_NOMBRES


def _es_over(nombre: str) -> bool:
    return _norm(nombre) in OVER_NOMBRES


def _es_under(nombre: str) -> bool:
    return _norm(nombre) in UNDER_NOMBRES


def _es_si(nombre: str) -> bool:
    return _norm(nombre) in SI_NOMBRES


def _es_no(nombre: str) -> bool:
    return _norm(nombre) in NO_NOMBRES


def _promedio(valores: List[float]) -> Optional[float]:
    valores = [v for v in valores if isinstance(v, (int, float))]
    if not valores:
        return None
    return sum(valores) / len(valores)


def clave_partido(home: str, away: str) -> str:
    return f"{_norm(home)}|{_norm(away)}"


# ---------------------------------------------------------------------------
# Disponibilidad de mercado (v1.32.0) — lógica pura.
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
    Decide si hay un cambio significativo de DISPONIBILIDAD que amerite Telegram.

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
# Movimiento de momios (v1.33.0) — lógica pura.
# ---------------------------------------------------------------------------
def odds_a_prob_implicita(home: float, draw: float, away: float) -> Optional[Dict[str, float]]:
    """
    Convierte momios decimales 1X2 a probabilidad implícita normalizada (sin vig),
    en puntos porcentuales (0-100). Devuelve None si los momios no son válidos.
    """
    try:
        h = float(home)
        d = float(draw)
        a = float(away)
    except (TypeError, ValueError):
        return None

    if h <= 0 or d <= 0 or a <= 0:
        return None

    inv = {"home": 1.0 / h, "draw": 1.0 / d, "away": 1.0 / a}
    suma = inv["home"] + inv["draw"] + inv["away"]

    if suma <= 0:
        return None

    return {k: (v / suma) * 100.0 for k, v in inv.items()}


def favorito_de_prob(prob: Dict[str, float]) -> Optional[str]:
    """Devuelve la clave (home/draw/away) con mayor probabilidad implícita."""
    if not prob:
        return None
    return max(prob, key=lambda k: prob[k])


def clasificar_movimiento(delta_pts: float) -> str:
    """Clasifica el movimiento por puntos de probabilidad implícita."""
    if delta_pts >= UMBRAL_DRASTICO:
        return MOV_DRASTICO
    if delta_pts >= UMBRAL_IMPORTANTE:
        return MOV_IMPORTANTE
    return MOV_NORMAL


def extraer_1x2_de_bookmakers(
    bookmakers: List[Dict[str, Any]],
    home_name: str,
    away_name: str,
) -> Optional[Dict[str, float]]:
    """
    Extrae momios 1X2 (decimales) promediando los bookmakers que publican un
    mercado h2h completo (local, empate, visitante). Devuelve None si no hay.
    """
    homes: List[float] = []
    draws: List[float] = []
    aways: List[float] = []

    for book in bookmakers or []:
        if not isinstance(book, dict):
            continue

        for market in book.get("markets", []) or []:
            if not isinstance(market, dict) or market.get("key") != "h2h":
                continue

            h = d = a = None
            for outcome in market.get("outcomes", []) or []:
                if not isinstance(outcome, dict):
                    continue

                price = outcome.get("price")
                if price is None:
                    continue
                try:
                    price = float(price)
                except (TypeError, ValueError):
                    continue

                nombre = str(outcome.get("name", ""))
                if _es_empate(nombre):
                    d = price
                elif _coincide_equipo(nombre, home_name):
                    h = price
                elif _coincide_equipo(nombre, away_name):
                    a = price

            if h and d and a:
                homes.append(h)
                draws.append(d)
                aways.append(a)

    if homes and draws and aways:
        return {
            "home": sum(homes) / len(homes),
            "draw": sum(draws) / len(draws),
            "away": sum(aways) / len(aways),
        }

    return None


def snapshot_partido(home: str, away: str, bookmakers: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    odds = extraer_1x2_de_bookmakers(bookmakers, home, away)
    if not odds:
        return None

    prob = odds_a_prob_implicita(odds["home"], odds["draw"], odds["away"])
    if not prob:
        return None

    return {
        "partido": f"{home} vs {away}",
        "odds": {k: round(v, 4) for k, v in odds.items()},
        "prob": {k: round(v, 2) for k, v in prob.items()},
        "favorito": favorito_de_prob(prob),
    }


def evaluar_movimiento_partido(base: Dict[str, Any], cur: Dict[str, Any]) -> Dict[str, Any]:
    """Compara dos snapshots del mismo partido y describe el movimiento."""
    deltas: Dict[str, float] = {}
    base_prob = base.get("prob", {})
    cur_prob = cur.get("prob", {})

    for k in ("home", "draw", "away"):
        try:
            deltas[k] = abs(float(cur_prob.get(k, 0.0)) - float(base_prob.get(k, 0.0)))
        except (TypeError, ValueError):
            deltas[k] = 0.0

    max_delta = max(deltas.values()) if deltas else 0.0
    fav_prev = base.get("favorito")
    fav_cur = cur.get("favorito")
    flip = fav_prev is not None and fav_cur is not None and fav_prev != fav_cur

    return {
        "partido": cur.get("partido") or base.get("partido"),
        "max_delta_pts": max_delta,
        "deltas": deltas,
        "clasificacion": clasificar_movimiento(max_delta),
        "favorito_prev": fav_prev,
        "favorito_cur": fav_cur,
        "favorito_flip": flip,
    }


def decidir_alerta_movimiento(
    mov: Dict[str, Any],
    prev_alerta: Optional[Dict[str, Any]],
    incluir_importante: bool = False,
) -> Tuple[bool, Optional[str]]:
    """
    Decide si un movimiento de momios amerita Telegram, con prevención de
    duplicados. Devuelve (enviar_telegram, tipo_alerta).

    tipo_alerta in {"DRASTICO", "IMPORTANTE", "FLIP", None}.
    """
    clasif = mov.get("clasificacion", MOV_NORMAL)
    flip = bool(mov.get("favorito_flip"))

    # ¿Es candidato a Telegram?
    worthy = flip or clasif == MOV_DRASTICO or (incluir_importante and clasif == MOV_IMPORTANTE)
    if not worthy:
        return False, None

    tipo = "FLIP" if flip else clasif

    # Sin alerta previa: se envía.
    if not prev_alerta:
        return True, tipo

    prev_clasif = prev_alerta.get("clasificacion", MOV_NORMAL)
    prev_delta = float(prev_alerta.get("max_delta_pts", 0.0) or 0.0)
    prev_fav = prev_alerta.get("favorito_cur")

    # Cambio de favorito hacia uno distinto al ya alertado -> siempre se envía.
    if flip and prev_fav != mov.get("favorito_cur"):
        return True, "FLIP"

    # Escaló la severidad respecto a lo último alertado.
    if SEVERIDAD.get(clasif, 0) > SEVERIDAD.get(prev_clasif, 0):
        return True, tipo

    # Misma severidad pero el movimiento empeoró materialmente.
    if float(mov.get("max_delta_pts", 0.0)) >= prev_delta + MATERIAL_WORSEN_PTS:
        return True, tipo

    # Mismo movimiento, sin empeorar -> duplicado, se suprime.
    return False, None


def evaluar_movimientos(
    prev_baseline: Optional[Dict[str, Any]],
    prev_alertas: Optional[Dict[str, Any]],
    cur_snap: Dict[str, Any],
    incluir_importante: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
    """
    Compara el snapshot actual contra el baseline previo y decide alertas.

    Devuelve (nuevo_baseline, nuevo_alertas, movimientos).
    - nuevo_baseline: snapshots actuales (comparación contra la corrida previa).
    - nuevo_alertas: último movimiento alertado por partido (anti-duplicado).
    - movimientos: lista evaluada (incluye clasificación y si dispara Telegram).
    """
    prev_baseline = dict(prev_baseline) if isinstance(prev_baseline, dict) else {}
    prev_alertas = dict(prev_alertas) if isinstance(prev_alertas, dict) else {}

    nuevo_baseline: Dict[str, Any] = {}
    nuevo_alertas: Dict[str, Any] = {}
    movimientos: List[Dict[str, Any]] = []

    for key, cur in cur_snap.items():
        # Siempre guardamos el snapshot actual (comparación consecutiva).
        nuevo_baseline[key] = cur

        base = prev_baseline.get(key)
        if not base:
            # Primera observación del partido: no hay movimiento que evaluar.
            continue

        mov = evaluar_movimiento_partido(base, cur)
        enviar, tipo = decidir_alerta_movimiento(mov, prev_alertas.get(key), incluir_importante)
        mov["telegram"] = enviar
        mov["tipo_alerta"] = tipo
        movimientos.append(mov)

        if enviar:
            nuevo_alertas[key] = {
                "clasificacion": mov["clasificacion"],
                "max_delta_pts": mov["max_delta_pts"],
                "favorito_cur": mov["favorito_cur"],
                "alerta_en": datetime.now().isoformat(timespec="seconds"),
            }
        elif mov["clasificacion"] == MOV_NORMAL and not mov["favorito_flip"]:
            # Movimiento estabilizado: limpiamos el registro para que un futuro
            # movimiento drástico se trate como nuevo (no como duplicado).
            nuevo_alertas.pop(key, None)
        else:
            # Movimiento elevado pero ya alertado/no-Telegram: conservamos registro.
            if key in prev_alertas:
                nuevo_alertas[key] = prev_alertas[key]

    return nuevo_baseline, nuevo_alertas, movimientos


def construir_snapshot(
    partidos: List[Dict[str, Any]],
    eventos: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Construye el snapshot de momios 1X2 de la jornada.

    - Si `eventos` viene (consulta en vivo), usa la respuesta API (sin modificar
      jornadas.json).
    - Si no, usa los bookmakers guardados en jornadas.json, solo para partidos
      con mercado real.
    """
    snap: Dict[str, Any] = {}

    for partido in partidos:
        home = nombre_local(partido)
        away = nombre_visitante(partido)

        if eventos is not None:
            if evento_coincide is None or normalizar_bookmakers is None:
                continue
            match = next((e for e in eventos if evento_coincide(partido, e)), None)
            if match is None:
                continue
            bookmakers = normalizar_bookmakers(match)
        else:
            if not es_mercado_real(partido):
                continue
            bookmakers = partido.get("bookmakers", [])

        snap_partido = snapshot_partido(home, away, bookmakers)
        if snap_partido is None:
            continue

        snap[clave_partido(home, away)] = snap_partido

    return snap


def construir_mensaje_movimiento(movimientos_tel: List[Dict[str, Any]], hay_flip: bool) -> str:
    cabecera = "📊 WATCHDOG MOVIMIENTO DE MOMIOS — SURVIVOR LIGA MX"
    titulo = "🔄 CAMBIO DE FAVORITO DETECTADO" if hay_flip else "🚨 MOVIMIENTO DRÁSTICO DE MOMIOS"

    lineas = [
        cabecera,
        "=" * 40,
        titulo,
        "",
        f"Etiqueta operativa: {OP_AUDITAR}",
        "",
    ]

    for m in movimientos_tel:
        lineas.append(
            f"- {m['partido']}: {m['clasificacion']} (Δ {m['max_delta_pts']:.1f} pts prob.)"
        )
        if m.get("favorito_flip"):
            prev = ETIQUETA_FAVORITO.get(m.get("favorito_prev"), m.get("favorito_prev"))
            cur = ETIQUETA_FAVORITO.get(m.get("favorito_cur"), m.get("favorito_cur"))
            lineas.append(f"    Favorito: {prev} -> {cur}")

    lineas += [
        "",
        "Acción: AUDITAR manualmente. NO se envía pick automático.",
        "La decisión final (CERRAR) la controla auditor_pre_cierre.py / Real Data Gate.",
        f"Generado: {datetime.now().isoformat(timespec='seconds')}",
    ]

    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Multi-mercado (v1.34.0) — lógica pura.
# ---------------------------------------------------------------------------
def prob_dos_vias(odd_a: Any, odd_b: Any) -> Optional[Tuple[float, float]]:
    """Convierte dos momios decimales a probabilidad implícita normalizada (sin vig)."""
    try:
        a = float(odd_a)
        b = float(odd_b)
    except (TypeError, ValueError):
        return None

    if a <= 0 or b <= 0:
        return None

    ia, ib = 1.0 / a, 1.0 / b
    suma = ia + ib
    if suma <= 0:
        return None

    return (ia / suma) * 100.0, (ib / suma) * 100.0


def extraer_totals_de_bookmakers(
    bookmakers: List[Dict[str, Any]],
    linea: float = LINEA_TOTALS_PREFERIDA,
) -> Optional[Dict[str, Any]]:
    """
    Extrae Over/Under promediando bookmakers. Prefiere la línea indicada
    (p. ej. 2.5); si no existe, usa la línea más cercana disponible.
    """
    por_linea: Dict[float, Dict[str, List[float]]] = {}

    for book in bookmakers or []:
        if not isinstance(book, dict):
            continue
        for market in book.get("markets", []) or []:
            if not isinstance(market, dict) or market.get("key") != "totals":
                continue

            tmp: Dict[float, Dict[str, float]] = {}
            for outcome in market.get("outcomes", []) or []:
                if not isinstance(outcome, dict):
                    continue
                price = outcome.get("price")
                point = outcome.get("point")
                if price is None or point is None:
                    continue
                try:
                    price = float(price)
                    point = float(point)
                except (TypeError, ValueError):
                    continue
                nombre = str(outcome.get("name", ""))
                slot = tmp.setdefault(point, {})
                if _es_over(nombre):
                    slot["over"] = price
                elif _es_under(nombre):
                    slot["under"] = price

            for point, vals in tmp.items():
                if "over" in vals and "under" in vals:
                    d = por_linea.setdefault(point, {"over": [], "under": []})
                    d["over"].append(vals["over"])
                    d["under"].append(vals["under"])

    if not por_linea:
        return None

    if linea in por_linea:
        usado = linea
    else:
        usado = min(por_linea, key=lambda p: (abs(p - linea), -len(por_linea[p]["over"])))

    over = _promedio(por_linea[usado]["over"])
    under = _promedio(por_linea[usado]["under"])
    if over is None or under is None:
        return None

    return {"point": usado, "odds": {"over": over, "under": under}}


def extraer_btts_de_bookmakers(bookmakers: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Extrae BTTS (Sí/No) promediando bookmakers."""
    yes: List[float] = []
    no: List[float] = []

    for book in bookmakers or []:
        if not isinstance(book, dict):
            continue
        for market in book.get("markets", []) or []:
            if not isinstance(market, dict) or market.get("key") not in {"btts", "both_teams_to_score"}:
                continue
            y = n = None
            for outcome in market.get("outcomes", []) or []:
                if not isinstance(outcome, dict):
                    continue
                price = outcome.get("price")
                if price is None:
                    continue
                try:
                    price = float(price)
                except (TypeError, ValueError):
                    continue
                nombre = str(outcome.get("name", ""))
                if _es_si(nombre):
                    y = price
                elif _es_no(nombre):
                    n = price
            if y and n:
                yes.append(y)
                no.append(n)

    y = _promedio(yes)
    n = _promedio(no)
    if y is None or n is None:
        return None

    return {"odds": {"yes": y, "no": n}}


def extraer_spread_de_bookmakers(
    bookmakers: List[Dict[str, Any]],
    home_name: str,
    away_name: str,
) -> Optional[Dict[str, Any]]:
    """Extrae el hándicap/spread principal (línea del local + precios)."""
    h_prices: List[float] = []
    a_prices: List[float] = []
    h_points: List[float] = []

    for book in bookmakers or []:
        if not isinstance(book, dict):
            continue
        for market in book.get("markets", []) or []:
            if not isinstance(market, dict) or market.get("key") not in {"spreads", "handicap"}:
                continue
            h = a = None
            hp = None
            for outcome in market.get("outcomes", []) or []:
                if not isinstance(outcome, dict):
                    continue
                price = outcome.get("price")
                if price is None:
                    continue
                try:
                    price = float(price)
                except (TypeError, ValueError):
                    continue
                nombre = str(outcome.get("name", ""))
                if _coincide_equipo(nombre, home_name):
                    h = price
                    hp = outcome.get("point")
                elif _coincide_equipo(nombre, away_name):
                    a = price
            if h and a:
                h_prices.append(h)
                a_prices.append(a)
                if hp is not None:
                    try:
                        h_points.append(float(hp))
                    except (TypeError, ValueError):
                        pass

    hp_avg = _promedio(h_prices)
    ap_avg = _promedio(a_prices)
    if hp_avg is None or ap_avg is None:
        return None

    point = _promedio(h_points)
    return {"point": point, "odds": {"home": hp_avg, "away": ap_avg}}


def extraer_dnb_de_bookmakers(
    bookmakers: List[Dict[str, Any]],
    home_name: str,
    away_name: str,
) -> Optional[Dict[str, Any]]:
    """Extrae Draw No Bet / Empate No Acción (2 vías: local/visitante)."""
    h_prices: List[float] = []
    a_prices: List[float] = []

    for book in bookmakers or []:
        if not isinstance(book, dict):
            continue
        for market in book.get("markets", []) or []:
            if not isinstance(market, dict) or market.get("key") not in {"draw_no_bet", "dnb"}:
                continue
            h = a = None
            for outcome in market.get("outcomes", []) or []:
                if not isinstance(outcome, dict):
                    continue
                price = outcome.get("price")
                if price is None:
                    continue
                try:
                    price = float(price)
                except (TypeError, ValueError):
                    continue
                nombre = str(outcome.get("name", ""))
                if _es_empate(nombre):
                    continue  # DNB no debería traer empate; por seguridad lo ignoramos
                if _coincide_equipo(nombre, home_name):
                    h = price
                elif _coincide_equipo(nombre, away_name):
                    a = price
            if h and a:
                h_prices.append(h)
                a_prices.append(a)

    h = _promedio(h_prices)
    a = _promedio(a_prices)
    if h is None or a is None:
        return None

    return {"odds": {"home": h, "away": a}}


def _mercado_dos_vias(odds: Dict[str, float], k1: str, k2: str) -> Optional[Dict[str, Any]]:
    pr = prob_dos_vias(odds.get(k1), odds.get(k2))
    if pr is None:
        return None
    prob = {k1: round(pr[0], 2), k2: round(pr[1], 2)}
    return {
        "odds": {k1: round(float(odds[k1]), 4), k2: round(float(odds[k2]), 4)},
        "prob": prob,
        "lado": favorito_de_prob(prob),
    }


def snapshot_partido_multi(
    home: str,
    away: str,
    bookmakers: List[Dict[str, Any]],
    linea_totals: float = LINEA_TOTALS_PREFERIDA,
) -> Optional[Dict[str, Any]]:
    """
    Construye el snapshot multi-mercado de un partido. Solo incluye los mercados
    que The Odds API publica; los ausentes simplemente no aparecen.
    """
    mercados: Dict[str, Any] = {}

    # 1X2 / Moneyline (primario).
    o1 = extraer_1x2_de_bookmakers(bookmakers, home, away)
    if o1:
        prob = odds_a_prob_implicita(o1["home"], o1["draw"], o1["away"])
        if prob:
            mercados["1x2"] = {
                "odds": {k: round(v, 4) for k, v in o1.items()},
                "prob": {k: round(v, 2) for k, v in prob.items()},
                "favorito": favorito_de_prob(prob),
            }

    # Totals / Over-Under (contexto de volatilidad).
    t = extraer_totals_de_bookmakers(bookmakers, linea_totals)
    if t:
        m = _mercado_dos_vias(t["odds"], "over", "under")
        if m:
            m["point"] = t["point"]
            mercados["totals"] = m

    # BTTS / Ambos Anotan (contexto de volatilidad).
    b = extraer_btts_de_bookmakers(bookmakers)
    if b:
        m = _mercado_dos_vias(b["odds"], "yes", "no")
        if m:
            mercados["btts"] = m

    # Hándicap / Spread (fuerza/contexto).
    sp = extraer_spread_de_bookmakers(bookmakers, home, away)
    if sp:
        m = _mercado_dos_vias(sp["odds"], "home", "away")
        if m:
            m["favorito"] = m.pop("lado")
            m["point"] = sp["point"]
            mercados["spreads"] = m

    # Draw No Bet / Empate No Acción (fuerza/contexto, secundario).
    dnb = extraer_dnb_de_bookmakers(bookmakers, home, away)
    if dnb:
        m = _mercado_dos_vias(dnb["odds"], "home", "away")
        if m:
            m["favorito"] = m.pop("lado")
            mercados["dnb"] = m

    if not mercados:
        return None

    return {"partido": f"{home} vs {away}", "mercados": mercados}


def construir_snapshot_multi(
    partidos: List[Dict[str, Any]],
    eventos: Optional[List[Dict[str, Any]]] = None,
    linea_totals: float = LINEA_TOTALS_PREFERIDA,
) -> Dict[str, Any]:
    """
    Construye el snapshot multi-mercado de la jornada.

    - Si `eventos` viene (consulta en vivo), usa la respuesta RAW de The Odds API
      (con todas las market keys), sin modificar jornadas.json.
    - Si no, usa los bookmakers guardados en jornadas.json (solo partidos con
      mercado real). En producción esos bookmakers pueden venir normalizados, por
      lo que los mercados opcionales pueden reportarse como no disponibles.
    """
    snap: Dict[str, Any] = {}

    for partido in partidos:
        home = nombre_local(partido)
        away = nombre_visitante(partido)

        if eventos is not None:
            if evento_coincide is None:
                continue
            match = next((e for e in eventos if evento_coincide(partido, e)), None)
            if match is None:
                continue
            bookmakers = match.get("bookmakers", [])  # RAW: conserva todas las keys
        else:
            if not es_mercado_real(partido):
                continue
            bookmakers = partido.get("bookmakers", [])

        sp = snapshot_partido_multi(home, away, bookmakers, linea_totals)
        if sp is None:
            continue

        snap[clave_partido(home, away)] = sp

    return snap


def resumen_disponibilidad_mercados(cur_snap: Dict[str, Any]) -> Dict[str, int]:
    """Cuenta en cuántos partidos está disponible cada mercado."""
    counts: Dict[str, int] = {"1x2": 0, "totals": 0, "btts": 0, "spreads": 0, "dnb": 0}
    for s in cur_snap.values():
        for mercado in s.get("mercados", {}):
            counts[mercado] = counts.get(mercado, 0) + 1
    return counts


def evaluar_movimiento_mercado(mercado: str, base_m: Dict[str, Any], cur_m: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compara dos snapshots de un mismo mercado y describe el movimiento.

    CRITICO si hay flip de favorito/lado o (en hándicap) movimiento mayor de línea.
    """
    base_prob = base_m.get("prob", {}) or {}
    cur_prob = cur_m.get("prob", {}) or {}

    claves = set(base_prob) | set(cur_prob)
    deltas: Dict[str, float] = {}
    for k in claves:
        try:
            deltas[k] = abs(float(cur_prob.get(k, 0.0)) - float(base_prob.get(k, 0.0)))
        except (TypeError, ValueError):
            deltas[k] = 0.0

    max_delta = max(deltas.values()) if deltas else 0.0
    clasif = clasificar_movimiento(max_delta)

    campo = CAMPO_LADO.get(mercado, "favorito")
    lado_prev = base_m.get(campo)
    lado_cur = cur_m.get(campo)
    flip = lado_prev is not None and lado_cur is not None and lado_prev != lado_cur

    linea_prev = base_m.get("point")
    linea_cur = cur_m.get("point")
    linea_move = None
    if linea_prev is not None and linea_cur is not None:
        try:
            linea_move = abs(float(linea_cur) - float(linea_prev))
        except (TypeError, ValueError):
            linea_move = None

    # Hándicap: movimiento mayor de línea => CRITICO.
    if mercado == "spreads" and linea_move is not None and linea_move >= UMBRAL_LINEA_HANDICAP:
        clasif = MOV_CRITICO

    # Flip de favorito/lado en cualquier mercado => CRITICO.
    if flip:
        clasif = MOV_CRITICO

    return {
        "mercado": mercado,
        "max_delta_pts": max_delta,
        "deltas": deltas,
        "clasificacion": clasif,
        "flip": flip,
        "lado_prev": lado_prev,
        "lado_cur": lado_cur,
        "linea_prev": linea_prev,
        "linea_cur": linea_cur,
        "linea_move": linea_move,
    }


def decidir_alerta_mercado(
    mov: Dict[str, Any],
    prev_alerta: Optional[Dict[str, Any]],
    incluir_importante: bool = False,
) -> Tuple[bool, Optional[str]]:
    """
    Decide si un movimiento de mercado amerita Telegram, con anti-duplicado.
    Devuelve (enviar_telegram, tipo_alerta in {DRASTICO, CRITICO, IMPORTANTE, None}).
    """
    clasif = mov.get("clasificacion", MOV_NORMAL)
    flip = bool(mov.get("flip"))

    worthy = clasif in (MOV_DRASTICO, MOV_CRITICO) or (incluir_importante and clasif == MOV_IMPORTANTE)
    if not worthy:
        return False, None

    tipo = clasif

    if not prev_alerta:
        return True, tipo

    prev_clasif = prev_alerta.get("clasificacion", MOV_NORMAL)
    prev_delta = float(prev_alerta.get("max_delta_pts", 0.0) or 0.0)
    prev_lado = prev_alerta.get("lado_cur")
    prev_linea = prev_alerta.get("linea_cur")

    # Flip hacia un lado distinto al ya alertado -> siempre se envía.
    if flip and prev_lado != mov.get("lado_cur"):
        return True, MOV_CRITICO

    # Escaló la severidad respecto a lo último alertado.
    if SEVERIDAD.get(clasif, 0) > SEVERIDAD.get(prev_clasif, 0):
        return True, tipo

    # Misma severidad pero el movimiento de probabilidad empeoró materialmente.
    if float(mov.get("max_delta_pts", 0.0)) >= prev_delta + MATERIAL_WORSEN_PTS:
        return True, tipo

    # Hándicap: nueva línea que se movió materialmente respecto a la ya alertada.
    if (
        mov.get("linea_cur") is not None
        and prev_linea is not None
    ):
        try:
            if abs(float(mov["linea_cur"]) - float(prev_linea)) >= UMBRAL_LINEA_HANDICAP:
                return True, tipo
        except (TypeError, ValueError):
            pass

    # Mismo movimiento, sin empeorar -> duplicado, se suprime.
    return False, None


def evaluar_movimientos_multi(
    prev_baseline: Optional[Dict[str, Any]],
    prev_alertas: Optional[Dict[str, Any]],
    cur_snap: Dict[str, Any],
    incluir_importante: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
    """
    Compara el snapshot multi-mercado actual contra el baseline previo.

    Devuelve (nuevo_baseline, nuevo_alertas, movimientos).
    - nuevo_baseline: snapshots actuales por partido (comparación consecutiva).
    - nuevo_alertas: anti-duplicado por partido -> por mercado.
    - movimientos: lista evaluada (cada item es un movimiento por mercado).
    """
    prev_baseline = dict(prev_baseline) if isinstance(prev_baseline, dict) else {}
    prev_alertas = dict(prev_alertas) if isinstance(prev_alertas, dict) else {}

    nuevo_baseline: Dict[str, Any] = {}
    nuevo_alertas: Dict[str, Any] = {}
    movimientos: List[Dict[str, Any]] = []

    for key, cur in cur_snap.items():
        nuevo_baseline[key] = cur  # siempre guardamos el snapshot actual

        base = prev_baseline.get(key)
        if not base or not base.get("mercados"):
            continue  # primera observación del partido

        cur_mercados = cur.get("mercados", {})
        base_mercados = base.get("mercados", {})
        prev_alertas_partido = prev_alertas.get(key, {}) if isinstance(prev_alertas.get(key), dict) else {}
        alertas_partido: Dict[str, Any] = {}

        for mercado, cur_m in cur_mercados.items():
            base_m = base_mercados.get(mercado)
            if not base_m:
                continue  # mercado recién disponible: no hay con qué comparar

            mov = evaluar_movimiento_mercado(mercado, base_m, cur_m)
            mov["partido"] = cur.get("partido", key)

            prev_alerta_m = prev_alertas_partido.get(mercado)
            enviar, tipo = decidir_alerta_mercado(mov, prev_alerta_m, incluir_importante)
            mov["telegram"] = enviar
            mov["tipo_alerta"] = tipo
            movimientos.append(mov)

            if enviar:
                alertas_partido[mercado] = {
                    "clasificacion": mov["clasificacion"],
                    "max_delta_pts": mov["max_delta_pts"],
                    "lado_cur": mov["lado_cur"],
                    "linea_cur": mov["linea_cur"],
                    "alerta_en": datetime.now().isoformat(timespec="seconds"),
                }
            elif mov["clasificacion"] == MOV_NORMAL and not mov["flip"]:
                # Estabilizado: no conservamos registro (futuro movimiento = nuevo).
                pass
            elif mercado in prev_alertas_partido:
                # Movimiento elevado ya alertado/no-Telegram: conservamos registro.
                alertas_partido[mercado] = prev_alertas_partido[mercado]

        if alertas_partido:
            nuevo_alertas[key] = alertas_partido

    return nuevo_baseline, nuevo_alertas, movimientos


def construir_mensaje_multi(movimientos_tel: List[Dict[str, Any]]) -> str:
    cabecera = "📊 WATCHDOG MULTI-MERCADO — SURVIVOR LIGA MX"
    hay_critico = any(m.get("clasificacion") == MOV_CRITICO for m in movimientos_tel)
    titulo = "🛑 MOVIMIENTO CRÍTICO MULTI-MERCADO" if hay_critico else "🚨 MOVIMIENTO DRÁSTICO MULTI-MERCADO"

    lineas = [
        cabecera,
        "=" * 40,
        titulo,
        "",
        f"Etiqueta operativa: {OP_AUDITAR}",
        "",
    ]

    # Agrupamos por partido para legibilidad.
    por_partido: Dict[str, List[Dict[str, Any]]] = {}
    for m in movimientos_tel:
        por_partido.setdefault(m.get("partido", "?"), []).append(m)

    for partido, movs in por_partido.items():
        lineas.append(f"• {partido}")
        for m in movs:
            etq = ETIQUETA_MERCADO.get(m["mercado"], m["mercado"])
            linea = f"   - {etq}: {m['clasificacion']} (Δ {m['max_delta_pts']:.1f} pts prob.)"
            if m.get("flip"):
                prev = ETIQUETA_LADO.get(m.get("lado_prev"), m.get("lado_prev"))
                cur = ETIQUETA_LADO.get(m.get("lado_cur"), m.get("lado_cur"))
                linea += f" | FLIP {prev}->{cur}"
            if m["mercado"] == "spreads" and m.get("linea_move"):
                linea += f" | línea {m.get('linea_prev')}->{m.get('linea_cur')}"
            lineas.append(linea)

    lineas += [
        "",
        "Interpretación Survivor:",
        "- 1X2 / ML: mercado primario.",
        "- Over/Under y BTTS: contexto de volatilidad/riesgo.",
        "- Hándicap y Draw No Bet: señales de fuerza/contexto.",
        "",
        "Acción: AUDITAR manualmente. NO se envía pick automático.",
        "La decisión final (CERRAR) la controla auditor_pre_cierre.py / Real Data Gate.",
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
    movimientos: Optional[List[Dict[str, Any]]] = None,
    movimiento_enviado: bool = False,
    resumen_mercados: Optional[Dict[str, int]] = None,
    partidos_con_snapshot: int = 0,
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
        f"Alerta disponibilidad: {alerta_tipo or 'ninguna'} "
        f"({'enviada' if alerta_enviada else 'no enviada'})",
    ]

    # Disponibilidad de mercados (1X2 primario; opcionales secundarios).
    lineas.append("")
    lineas.append("Disponibilidad de mercados:")
    if resumen_mercados:
        lineas.append(f"- 1X2 / Moneyline (primario): {resumen_mercados.get('1x2', 0)}/{partidos_con_snapshot}")
        for mk in MERCADOS_OPCIONALES:
            n = resumen_mercados.get(mk, 0)
            etq = ETIQUETA_MERCADO.get(mk, mk)
            if n > 0:
                lineas.append(f"- {etq}: {n}/{partidos_con_snapshot}")
            else:
                lineas.append(f"- {etq}: mercado no disponible")
    else:
        lineas.append("- Sin mercado real / sin snapshot; no se evalúan mercados opcionales.")

    # Movimiento multi-mercado.
    lineas.append("")
    lineas.append("Movimiento de mercados:")
    if movimientos:
        for m in movimientos:
            etq = ETIQUETA_MERCADO.get(m["mercado"], m["mercado"])
            extra = ""
            if m.get("flip"):
                prev = ETIQUETA_LADO.get(m.get("lado_prev"), m.get("lado_prev"))
                cur = ETIQUETA_LADO.get(m.get("lado_cur"), m.get("lado_cur"))
                extra += f" | FLIP {prev}->{cur}"
            if m["mercado"] == "spreads" and m.get("linea_move"):
                extra += f" | línea {m.get('linea_prev')}->{m.get('linea_cur')}"
            tg = " | TELEGRAM" if m.get("telegram") else ""
            lineas.append(
                f"- {m['partido']} [{etq}]: {m['clasificacion']} "
                f"(Δ {m['max_delta_pts']:.1f} pts){extra}{tg}"
            )
        lineas.append(
            f"Alerta movimiento: {'enviada' if movimiento_enviado else 'no enviada'} "
            f"(etiqueta {OP_AUDITAR})."
        )
    else:
        lineas.append("- Sin snapshot previo comparable o sin mercado real; no se evalúa movimiento.")

    lineas += [
        "",
        "Notas:",
        "- El watchdog NO cierra ni envía picks automáticamente.",
        "- 1X2/ML es el mercado primario; O/U y BTTS son contexto de volatilidad;",
        "  hándicap y Draw No Bet son señales de fuerza/contexto.",
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
) -> Tuple[Optional[Tuple[int, int]], Optional[List[Dict[str, Any]]], str]:
    """
    Intenta una consulta en vivo a The Odds API respetando budget/cooldown.

    Devuelve ((disponibles, total) | None, eventos | None, motivo).
    None => usar estado local.
    """
    if fetch_odds is None or evento_coincide is None or normalizar_bookmakers is None:
        return None, None, "sync_odds_api no disponible; se usa estado local"

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
            return None, None, f"presupuesto/cooldown: {mensaje}"

    try:
        eventos = fetch_odds()
    except Exception as exc:
        # No se rota ni se gasta crédito si la llamada falló antes de éxito;
        # solo registramos motivo (sin secretos).
        return None, None, f"fallo consulta API: {type(exc).__name__}: {exc}"

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

    return contar_mercado_live(partidos, eventos), eventos, f"consulta en vivo OK (eventos={len(eventos)})"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Watchdog de mercado real y movimiento de momios Survivor Liga MX (no cierra ni envía picks)."
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
        "--no-movimiento",
        action="store_true",
        help="Desactiva el seguimiento de movimiento de momios (solo disponibilidad).",
    )
    parser.add_argument(
        "--telegram-importante",
        action="store_true",
        help="También envía Telegram para movimientos IMPORTANTES (5-8 pts).",
    )
    parser.add_argument(
        "--totals-line",
        type=float,
        default=LINEA_TOTALS_PREFERIDA,
        help=f"Línea preferida de Over/Under a monitorear (default {LINEA_TOTALS_PREFERIDA}).",
    )
    parser.add_argument(
        "--cooldown",
        type=int,
        default=DEFAULT_COOLDOWN_MIN,
        help=f"Cooldown en minutos para la consulta en vivo (default {DEFAULT_COOLDOWN_MIN}).",
    )
    args = parser.parse_args()

    incluir_importante = args.telegram_importante or TELEGRAM_IMPORTANTE_ENV

    print("🐶 MARKET WATCHDOG — SURVIVOR LIGA MX (v1.34.0)")
    print("=" * 60)

    data = cargar_json(JORNADAS_PATH, [])
    partidos = extraer_partidos(data)

    # Conteo base desde el estado local (sin costo de API).
    disponibles, total = contar_mercado_local(partidos)
    fuente = "local"
    eventos_live: Optional[List[Dict[str, Any]]] = None

    # Consulta en vivo opcional, respetando budget/cooldown.
    if not args.no_api and total > 0:
        resultado_live, eventos_live, motivo = chequear_mercado_live(partidos, args.cooldown, args.force)
        if resultado_live is not None:
            disponibles, total = resultado_live
            fuente = "live"
            print(f"🎰 {motivo}")
        else:
            eventos_live = None
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
    prev_baseline = previo.get("mercados_baseline") if isinstance(previo.get("mercados_baseline"), dict) else {}
    prev_alertas = previo.get("mercados_alertas") if isinstance(previo.get("mercados_alertas"), dict) else {}

    tipo_alerta = decidir_alerta(prev_disponibles, prev_estado, disponibles, estado)

    print("")
    print(f"Mercado real API: {disponibles}/{total}")
    print(f"Disponibilidad: {estado}")
    print(f"Status watchdog: {wd_status}")
    print(f"Etiqueta operativa: {etiqueta}")

    # --- Alerta de DISPONIBILIDAD (v1.32.0) ---
    alerta_enviada = False
    if tipo_alerta is not None:
        mensaje = construir_mensaje_telegram(tipo_alerta, disponibles, total, estado, fuente)
        if args.dry_run or args.no_telegram:
            print(f"🔔 Cambio de disponibilidad ({tipo_alerta}); Telegram omitido (--dry-run/--no-telegram).")
        else:
            alerta_enviada, motivo_tg = enviar_telegram(mensaje)
            if alerta_enviada:
                print(f"📨 Telegram disponibilidad enviado: {tipo_alerta}")
            else:
                print(f"⚠️ Telegram disponibilidad no enviado ({tipo_alerta}): {motivo_tg}")
    else:
        print("🔕 Sin cambios significativos de disponibilidad; no se envía Telegram.")

    # --- Seguimiento MULTI-MERCADO (v1.34.0) ---
    movimientos: List[Dict[str, Any]] = []
    movimiento_enviado = False
    nuevo_baseline = prev_baseline
    nuevo_alertas = prev_alertas
    resumen_mkts: Dict[str, int] = {}
    n_snapshot = 0

    evaluar_mov = (not args.no_movimiento) and disponibles > 0

    if evaluar_mov:
        cur_snap = construir_snapshot_multi(
            partidos,
            eventos_live if fuente == "live" else None,
            args.totals_line,
        )
        resumen_mkts = resumen_disponibilidad_mercados(cur_snap)
        n_snapshot = len(cur_snap)

        if cur_snap:
            nuevo_baseline, nuevo_alertas, movimientos = evaluar_movimientos_multi(
                prev_baseline, prev_alertas, cur_snap, incluir_importante
            )

            # Disponibilidad de mercados opcionales (no se fuerza ninguno).
            print(f"📦 Mercados: 1X2 {resumen_mkts.get('1x2', 0)}/{n_snapshot} (primario)")
            for mk in MERCADOS_OPCIONALES:
                n = resumen_mkts.get(mk, 0)
                etq = ETIQUETA_MERCADO.get(mk, mk)
                if n > 0:
                    print(f"   - {etq}: {n}/{n_snapshot}")
                else:
                    print(f"   - {etq}: mercado no disponible")

            movimientos_tel = [m for m in movimientos if m.get("telegram")]

            if movimientos:
                peor = max(movimientos, key=lambda m: SEVERIDAD.get(m["clasificacion"], 0))
                etqp = ETIQUETA_MERCADO.get(peor["mercado"], peor["mercado"])
                print(
                    f"📊 Movimiento: {len(movimientos)} comparaciones; peor = "
                    f"{etqp} {peor['clasificacion']} (Δ {peor['max_delta_pts']:.1f} pts)."
                )
            else:
                print("📊 Movimiento: snapshot inicial guardado (sin baseline previo).")

            if movimientos_tel:
                mensaje_mov = construir_mensaje_multi(movimientos_tel)
                if args.dry_run or args.no_telegram:
                    print(
                        f"🔔 Movimiento relevante en {len(movimientos_tel)} mercado(s); "
                        "Telegram omitido (--dry-run/--no-telegram)."
                    )
                else:
                    movimiento_enviado, motivo_mov = enviar_telegram(mensaje_mov)
                    if movimiento_enviado:
                        print(f"📨 Telegram movimiento enviado ({len(movimientos_tel)} mercado(s)).")
                    else:
                        print(f"⚠️ Telegram movimiento no enviado: {motivo_mov}")
            else:
                print("🔕 Movimiento de mercados sin cambios DRASTICO/CRITICO para Telegram.")
        else:
            print("📊 Movimiento: no se pudo extraer ningún mercado (sin datos comparables).")
    elif args.no_movimiento:
        print("➡️ Seguimiento de movimiento desactivado (--no-movimiento).")
    else:
        print("📊 Movimiento: sin mercado real (0 disponibles); no se evalúa.")

    # --- Persistencia de estado ---
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
        "mercados_baseline": nuevo_baseline or {},
        "mercados_alertas": nuevo_alertas or {},
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
            movimientos,
            movimiento_enviado,
            resumen_mkts,
            n_snapshot,
        )
        print(f"✅ Estado guardado: {STATE_PATH}")
        print(f"✅ Reporte: {OUTPUT_TXT}")
    else:
        print("🧪 --dry-run: no se guardó estado ni reporte.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
