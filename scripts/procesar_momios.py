#!/usr/bin/env python3
"""
procesar_momios.py — Análisis de momios reales (Survivor Liga MX).

Lee los momios que el bot ya bajó de The Odds API (data/jornadas.json),
calcula por partido:
  - cuotas promedio 1X2 entre las casas reales (ignora fallback técnico),
  - margen de la casa (overround / vig),
  - probabilidades sin vig,
y exporta un CSV + un resumen de texto.

Fuente: SOLO datos ya presentes en data/jornadas.json (provenientes de
The Odds API vía src/sync_odds_api.py). NO hace red, NO scraping, NO bypass.
NO cierra ni envía picks. Decisión operativa: ESPERAR / NO ENVIAR.

Uso:
    python3 scripts/procesar_momios.py
    python3 scripts/procesar_momios.py --input data/jornadas.json \
        --output-csv reports/momios_analisis.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from odds_math import margen_casa_pct, probabilidades_sin_vig  # noqa: E402

DEC_ESPERAR = "ESPERAR / NO ENVIAR"
_DRAW = ("draw", "empate", "x", "tie")


def _norm(texto: str) -> str:
    base = unicodedata.normalize("NFKD", str(texto or "")).lower()
    base = "".join(c for c in base if not unicodedata.combining(c))
    return " ".join(base.split())


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
    """Excluye los bookmakers de fallback técnico (sin mercado real)."""
    key = _norm(bm.get("key"))
    title = _norm(bm.get("title"))
    return "fallback" not in key and "fallback" not in title


def _clasificar_outcome(name: str, local: str, visitante: str) -> Optional[str]:
    n = _norm(name)
    if n in _DRAW:
        return "empate"
    nl, nv = _norm(local), _norm(visitante)
    if n and (n == nl or n in nl or nl in n):
        return "local"
    if n and (n == nv or n in nv or nv in n):
        return "visitante"
    return None


def analizar_partido(partido: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Devuelve el análisis 1X2 promediado entre casas reales, o None si no hay
    mercado real completo (1X2) disponible.
    """
    local = nombre_local(partido)
    visitante = nombre_visitante(partido)

    acc: Dict[str, List[float]] = {"local": [], "empate": [], "visitante": []}
    casas = 0

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
                cat = _clasificar_outcome(o.get("name", ""), local, visitante)
                price = o.get("price")
                if cat and isinstance(price, (int, float)) and float(price) > 1.0:
                    got[cat] = float(price)
            if {"local", "empate", "visitante"} <= set(got):
                acc["local"].append(got["local"])
                acc["empate"].append(got["empate"])
                acc["visitante"].append(got["visitante"])
                casas += 1

    if casas == 0:
        return None

    prom = {k: round(sum(v) / len(v), 3) for k, v in acc.items()}
    cuotas = [prom["local"], prom["empate"], prom["visitante"]]
    p_local, p_empate, p_visita = probabilidades_sin_vig(cuotas)

    return {
        "fecha": str(partido.get("fecha", "")),
        "hora": str(partido.get("hora", "")),
        "local": local,
        "visitante": visitante,
        "casas_contadas": casas,
        "cuota_local": prom["local"],
        "cuota_empate": prom["empate"],
        "cuota_visitante": prom["visitante"],
        "prob_local_pct": round(p_local * 100, 2),
        "prob_empate_pct": round(p_empate * 100, 2),
        "prob_visitante_pct": round(p_visita * 100, 2),
        "margen_casa_pct": margen_casa_pct(cuotas),
    }


def analizar_jornada(partidos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    filas = []
    for p in partidos:
        fila = analizar_partido(p)
        if fila is not None:
            filas.append(fila)
    return filas


CAMPOS_CSV = [
    "fecha", "hora", "local", "visitante", "casas_contadas",
    "cuota_local", "cuota_empate", "cuota_visitante",
    "prob_local_pct", "prob_empate_pct", "prob_visitante_pct",
    "margen_casa_pct",
]


def exportar_csv(filas: List[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS_CSV)
        writer.writeheader()
        for fila in filas:
            writer.writerow({k: fila.get(k, "") for k in CAMPOS_CSV})


def render_resumen(filas: List[Dict[str, Any]], total_partidos: int) -> str:
    lineas = [
        "# ANÁLISIS DE MOMIOS — SURVIVOR LIGA MX",
        "",
        "Fuente: data/jornadas.json (The Odds API). Sin red, sin scraping.",
        f"Partidos con mercado real 1X2: {len(filas)}/{total_partidos}",
        "",
    ]
    if filas:
        for r in filas:
            lineas.append(
                f"- {r['local']} vs {r['visitante']} | "
                f"{r['cuota_local']}/{r['cuota_empate']}/{r['cuota_visitante']} | "
                f"prob: {r['prob_local_pct']}% / {r['prob_empate_pct']}% / "
                f"{r['prob_visitante_pct']}% | margen casa: {r['margen_casa_pct']}%"
            )
    else:
        lineas.append("(Sin mercado real 1X2 todavía. The Odds API aún no publica Liga MX.)")
    lineas += [
        "",
        "DECISIÓN GENERAL:",
        f"- {DEC_ESPERAR}.",
        "- Análisis solo informativo de mercado. No cierra ni envía picks.",
    ]
    return "\n".join(lineas) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Análisis de momios reales Liga MX.")
    parser.add_argument("--input", default=str(BASE_DIR / "data" / "jornadas.json"))
    parser.add_argument("--output-csv", default=str(BASE_DIR / "reports" / "momios_analisis.csv"))
    parser.add_argument("--output-txt", default=str(BASE_DIR / "reports" / "momios_analisis.txt"))
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"⚠️ No existe {input_path}. Corre primero src/sync_odds_api.py.")
        return 1

    data = json.loads(input_path.read_text(encoding="utf-8"))
    partidos = extraer_partidos(data)
    filas = analizar_jornada(partidos)

    csv_path = Path(args.output_csv)
    exportar_csv(filas, csv_path)

    resumen = render_resumen(filas, len(partidos))
    txt_path = Path(args.output_txt)
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path.write_text(resumen, encoding="utf-8")

    print(resumen)
    print(f"💾 CSV: {csv_path}")
    print(f"📄 Resumen: {txt_path}")
    print(f"Decisión: {DEC_ESPERAR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
