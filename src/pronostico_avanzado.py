#!/usr/bin/env python3
"""
pronostico_avanzado.py — Orquestador de pronósticos (Survivor Liga MX).

Une las distintas fuentes, cada una en su rol:
- Histórico de resultados (TheSportsDB / data) -> fuerza de equipos (Poisson).
- Momios reales (The Odds API en data/jornadas.json) -> probabilidad de mercado.
- Modelo + mercado se MEZCLAN (ensemble) para el pronóstico final.

Para cada partido entrega: 1X2, Over/Under, BTTS, marcador probable y el
"no perder" para Survivor. Degrada de forma segura: si falta el histórico usa
solo el mercado; si falta el mercado usa solo el modelo; si faltan ambos lo
marca como sin datos.

Sin red propia (lee archivos ya generados por otros módulos). NO cierra ni
envía picks. Decisión operativa: ESPERAR / NO ENVIAR.
"""
from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

try:
    from odds_math import probabilidades_sin_vig
    from poisson_model import calcular_fuerzas, pronostico as pronostico_modelo, combinar_con_mercado
except ImportError:  # pragma: no cover
    from src.odds_math import probabilidades_sin_vig
    from src.poisson_model import calcular_fuerzas, pronostico as pronostico_modelo, combinar_con_mercado

BASE_DIR = Path(__file__).resolve().parents[1]
JORNADAS_PATH = BASE_DIR / "data" / "jornadas.json"
HISTORICO_PATH = BASE_DIR / "data" / "resultados_historicos.json"

DEC_ESPERAR = "ESPERAR / NO ENVIAR"
_DRAW = ("draw", "empate", "x", "tie")


def _norm(texto: str) -> str:
    base = unicodedata.normalize("NFKD", str(texto or "")).lower()
    base = "".join(c for c in base if not unicodedata.combining(c))
    return " ".join(base.split())


def cargar_json(path: Path, default: Any) -> Any:
    if not Path(path).exists():
        return default
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def nombre_local(p: Dict[str, Any]) -> str:
    return str(p.get("home_team") or p.get("local") or p.get("equipo_local") or "")


def nombre_visitante(p: Dict[str, Any]) -> str:
    return str(p.get("away_team") or p.get("visitante") or p.get("equipo_visitante") or "")


def extraer_partidos(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return [p for p in data if isinstance(p, dict)]
    if isinstance(data, dict) and isinstance(data.get("partidos"), list):
        return [p for p in data["partidos"] if isinstance(p, dict)]
    return []


def _es_bookmaker_real(bm: Dict[str, Any]) -> bool:
    return "fallback" not in _norm(bm.get("key")) and "fallback" not in _norm(bm.get("title"))


def cuotas_promedio_1x2(partido: Dict[str, Any]) -> Optional[List[float]]:
    """Promedio de cuotas 1X2 entre casas reales. None si no hay mercado real."""
    local, visita = nombre_local(partido), nombre_visitante(partido)
    nl, nv = _norm(local), _norm(visita)
    acc = {"l": [], "e": [], "v": []}

    for bm in partido.get("bookmakers", []):
        if not isinstance(bm, dict) or not _es_bookmaker_real(bm):
            continue
        for market in bm.get("markets", []):
            if not isinstance(market, dict) or market.get("key") != "h2h":
                continue
            got: Dict[str, float] = {}
            for o in market.get("outcomes", []):
                if not isinstance(o, dict):
                    continue
                n = _norm(o.get("name", ""))
                price = o.get("price")
                if not isinstance(price, (int, float)) or float(price) <= 1.0:
                    continue
                if n in _DRAW:
                    got["e"] = float(price)
                elif n and (n == nl or n in nl or nl in n):
                    got["l"] = float(price)
                elif n and (n == nv or n in nv or nv in n):
                    got["v"] = float(price)
            if {"l", "e", "v"} <= set(got):
                acc["l"].append(got["l"]); acc["e"].append(got["e"]); acc["v"].append(got["v"])

    if not acc["l"]:
        return None
    return [sum(acc[k]) / len(acc[k]) for k in ("l", "e", "v")]


def probabilidades_mercado(partido: Dict[str, Any]) -> Optional[List[float]]:
    """Probabilidades 1X2 SIN vig desde los momios reales. None si no hay mercado."""
    cuotas = cuotas_promedio_1x2(partido)
    if cuotas is None:
        return None
    return probabilidades_sin_vig(cuotas)


def _equipo_conocido(nombre: str, fuerzas: Optional[Dict[str, Any]]) -> bool:
    return bool(fuerzas) and _norm(nombre) in fuerzas.get("equipos", {})


def pronostico_partido(
    partido: Dict[str, Any],
    fuerzas: Optional[Dict[str, Any]],
    peso_modelo: float = 0.5,
) -> Dict[str, Any]:
    """Pronóstico final de un partido combinando modelo (Poisson) y mercado."""
    local, visita = nombre_local(partido), nombre_visitante(partido)

    mercado = probabilidades_mercado(partido)

    modelo_pred = None
    if fuerzas and _equipo_conocido(local, fuerzas) and _equipo_conocido(visita, fuerzas):
        modelo_pred = pronostico_modelo(local, visita, fuerzas)

    if modelo_pred and mercado:
        modelo_1x2 = [
            modelo_pred["prob_local_pct"] / 100.0,
            modelo_pred["prob_empate_pct"] / 100.0,
            modelo_pred["prob_visitante_pct"] / 100.0,
        ]
        final = combinar_con_mercado(modelo_1x2, mercado, peso_modelo)
        fuente = "modelo+mercado"
    elif mercado:
        final = mercado
        fuente = "solo_mercado"
    elif modelo_pred:
        final = [
            modelo_pred["prob_local_pct"] / 100.0,
            modelo_pred["prob_empate_pct"] / 100.0,
            modelo_pred["prob_visitante_pct"] / 100.0,
        ]
        fuente = "solo_modelo"
    else:
        return {
            "local": local, "visitante": visita,
            "status": "sin_datos", "fuente": "ninguna",
            "decision": DEC_ESPERAR,
        }

    etiquetas = ("Gana Local", "Empate", "Gana Visitante")
    idx = max(range(3), key=lambda i: final[i])

    resultado = {
        "local": local,
        "visitante": visita,
        "status": "ok",
        "fuente": fuente,
        "peso_modelo": peso_modelo if fuente == "modelo+mercado" else None,
        "prob_local_pct": round(final[0] * 100, 2),
        "prob_empate_pct": round(final[1] * 100, 2),
        "prob_visitante_pct": round(final[2] * 100, 2),
        "pick_1x2": etiquetas[idx],
        "no_perder_local_pct": round((final[0] + final[1]) * 100, 2),
        "no_perder_visitante_pct": round((final[2] + final[1]) * 100, 2),
        "decision": DEC_ESPERAR,
    }

    # Over/Under y BTTS vienen del modelo (el mercado 1X2 no los provee).
    if modelo_pred:
        resultado.update({
            "prob_over_pct": modelo_pred["prob_over_pct"],
            "prob_under_pct": modelo_pred["prob_under_pct"],
            "pick_ou": modelo_pred["pick_ou"],
            "prob_btts_si_pct": modelo_pred["prob_btts_si_pct"],
            "pick_btts": modelo_pred["pick_btts"],
            "marcador_mas_probable": modelo_pred["marcador_mas_probable"],
        })

    return resultado


def generar_pronosticos(
    partidos: Sequence[Dict[str, Any]],
    historico: Sequence[Dict[str, Any]],
    peso_modelo: float = 0.5,
) -> List[Dict[str, Any]]:
    """Genera el pronóstico de todos los partidos. Calcula fuerzas si hay histórico."""
    fuerzas = None
    if historico:
        try:
            fuerzas = calcular_fuerzas(historico)
        except ValueError:
            fuerzas = None
    return [pronostico_partido(p, fuerzas, peso_modelo) for p in partidos]


def render_reporte(filas: Sequence[Dict[str, Any]]) -> str:
    con_datos = [f for f in filas if f.get("status") == "ok"]
    lineas = [
        "# PRONÓSTICO AVANZADO — SURVIVOR LIGA MX",
        "",
        "Fuentes: histórico (fuerza de equipos) + momios reales (mercado).",
        f"Partidos con pronóstico: {len(con_datos)}/{len(filas)}",
        "",
    ]
    for f in filas:
        if f.get("status") != "ok":
            lineas.append(f"- {f['local']} vs {f['visitante']} | SIN DATOS (esperar mercado)")
            continue
        linea = (
            f"- {f['local']} vs {f['visitante']} [{f['fuente']}] | "
            f"{f['pick_1x2']} | "
            f"L {f['prob_local_pct']}% / E {f['prob_empate_pct']}% / V {f['prob_visitante_pct']}%"
        )
        if "pick_ou" in f:
            linea += f" | {f['pick_ou']} 2.5 ({f['prob_over_pct']}%)"
        if "pick_btts" in f:
            linea += f" | BTTS {f['pick_btts']} ({f['prob_btts_si_pct']}%)"
        if "marcador_mas_probable" in f:
            linea += f" | marcador {f['marcador_mas_probable']}"
        lineas.append(linea)
    lineas += [
        "",
        "SURVIVOR (no perder):",
    ]
    for f in con_datos:
        lineas.append(
            f"- {f['local']}: {f['no_perder_local_pct']}% | "
            f"{f['visitante']}: {f['no_perder_visitante_pct']}%"
        )
    lineas += [
        "",
        "DECISIÓN GENERAL:",
        f"- {DEC_ESPERAR}.",
        "- Pronóstico informativo. No cierra ni envía picks.",
    ]
    return "\n".join(lineas) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Pronóstico avanzado Liga MX.")
    parser.add_argument("--jornadas", default=str(JORNADAS_PATH))
    parser.add_argument("--historico", default=str(HISTORICO_PATH))
    parser.add_argument("--peso-modelo", type=float, default=0.5,
                        help="0=solo mercado, 1=solo modelo (default 0.5).")
    parser.add_argument("--output", default=str(BASE_DIR / "reports" / "pronostico_avanzado.txt"))
    args = parser.parse_args()

    partidos = extraer_partidos(cargar_json(Path(args.jornadas), []))
    historico = cargar_json(Path(args.historico), [])
    if not isinstance(historico, list):
        historico = extraer_partidos(historico)

    if not partidos:
        print("⚠️ No hay partidos en jornadas.json. Corre src/sync_odds_api.py primero.")
        return 1

    filas = generar_pronosticos(partidos, historico, args.peso_modelo)
    reporte = render_reporte(filas)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(reporte, encoding="utf-8")

    print(reporte)
    print(f"📄 Reporte: {out}")
    print(f"Decisión: {DEC_ESPERAR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
