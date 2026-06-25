#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


BASE_DIR = Path(__file__).resolve().parents[1]
JORNADAS_PATH = BASE_DIR / "data" / "jornadas.json"
OUTPUT_TXT = BASE_DIR / "reports" / "lectura_mercado_ultimo.txt"
OUTPUT_JSON = BASE_DIR / "data" / "lectura_mercado_ultimo.json"


def cargar_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def extraer_partidos(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return [p for p in data if isinstance(p, dict)]
    if isinstance(data, dict) and isinstance(data.get("partidos"), list):
        return [p for p in data["partidos"] if isinstance(p, dict)]
    return []


def nombre_partido(partido: Dict[str, Any]) -> str:
    local = partido.get("home_team") or partido.get("local") or "LOCAL?"
    visitante = partido.get("away_team") or partido.get("visitante") or "VISITANTE?"
    return f"{local} vs {visitante}"


def mercado_real_api(partido: Dict[str, Any]) -> bool:
    momios = partido.get("momios", {})
    if not isinstance(momios, dict):
        return False
    return str(momios.get("estado", "")).lower() == "mercado_real_api"


def implied_prob(decimal_price: float) -> float:
    if decimal_price <= 1:
        return 0.0
    return 100.0 / decimal_price


def recolectar_outcomes(partido: Dict[str, Any], market_key: str) -> List[Dict[str, Any]]:
    resultados = []
    bookmakers = partido.get("bookmakers", [])

    if not isinstance(bookmakers, list):
        return resultados

    for bookmaker in bookmakers:
        if not isinstance(bookmaker, dict):
            continue

        title = bookmaker.get("title", "Bookmaker")
        markets = bookmaker.get("markets", [])

        if not isinstance(markets, list):
            continue

        for market in markets:
            if not isinstance(market, dict):
                continue

            if market.get("key") != market_key:
                continue

            outcomes = market.get("outcomes", [])

            if not isinstance(outcomes, list):
                continue

            for outcome in outcomes:
                if not isinstance(outcome, dict):
                    continue

                item = dict(outcome)
                item["_bookmaker"] = title
                item["_market"] = market_key
                resultados.append(item)

    return resultados


def mejor_por_nombre(outcomes: List[Dict[str, Any]]) -> Dict[str, List[float]]:
    data: Dict[str, List[float]] = {}

    for outcome in outcomes:
        name = str(outcome.get("name", ""))
        try:
            price = float(outcome.get("price"))
        except Exception:
            continue

        if not name or price <= 1:
            continue

        data.setdefault(name, []).append(price)

    return data


def promedio(values: List[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def analizar_h2h(partido: Dict[str, Any]) -> Dict[str, Any]:
    outcomes = recolectar_outcomes(partido, "h2h")
    agrupado = mejor_por_nombre(outcomes)

    if not agrupado:
        return {
            "disponible": False,
            "lectura": "Sin mercado 1X2 real disponible.",
        }

    filas = []
    for name, prices in agrupado.items():
        avg_price = promedio(prices)
        filas.append(
            {
                "seleccion": name,
                "momio_promedio": round(avg_price, 3),
                "prob_implicita": round(implied_prob(avg_price), 1),
                "bookmakers": len(prices),
            }
        )

    filas.sort(key=lambda x: x["prob_implicita"], reverse=True)

    favorito = filas[0]

    return {
        "disponible": True,
        "favorito": favorito["seleccion"],
        "filas": filas,
        "lectura": f"El mercado 1X2 ve como favorito a {favorito['seleccion']} ({favorito['prob_implicita']}% implícito bruto).",
    }


def analizar_totals(partido: Dict[str, Any]) -> Dict[str, Any]:
    outcomes = recolectar_outcomes(partido, "totals")

    if not outcomes:
        return {
            "disponible": False,
            "lectura": "Sin Over/Under real disponible.",
        }

    por_punto: Dict[str, Dict[str, List[float]]] = {}

    for outcome in outcomes:
        name = str(outcome.get("name", ""))
        point = str(outcome.get("point", "sin_linea"))

        try:
            price = float(outcome.get("price"))
        except Exception:
            continue

        por_punto.setdefault(point, {}).setdefault(name, []).append(price)

    mejores = []

    for point, lados in por_punto.items():
        over_avg = promedio(lados.get("Over", []))
        under_avg = promedio(lados.get("Under", []))

        if over_avg and under_avg:
            over_prob = implied_prob(over_avg)
            under_prob = implied_prob(under_avg)

            if over_prob > under_prob:
                sesgo = "OVER"
                lectura = f"El mercado se inclina al Over {point}."
            elif under_prob > over_prob:
                sesgo = "UNDER"
                lectura = f"El mercado se inclina al Under {point}."
            else:
                sesgo = "PAREJO"
                lectura = f"El mercado ve parejo el total {point}."

            mejores.append(
                {
                    "linea": point,
                    "over_momio_promedio": round(over_avg, 3),
                    "under_momio_promedio": round(under_avg, 3),
                    "over_prob_implicita": round(over_prob, 1),
                    "under_prob_implicita": round(under_prob, 1),
                    "sesgo": sesgo,
                    "lectura": lectura,
                }
            )

    if not mejores:
        return {
            "disponible": False,
            "lectura": "Over/Under apareció, pero no se pudo leer completo.",
        }

    # Prioriza línea 2.5 si existe; si no, la primera.
    elegido = next((x for x in mejores if x["linea"] == "2.5"), mejores[0])

    return {
        "disponible": True,
        "principal": elegido,
        "lineas": mejores,
        "lectura": elegido["lectura"],
    }


def analizar_btts(partido: Dict[str, Any]) -> Dict[str, Any]:
    outcomes = recolectar_outcomes(partido, "btts")
    agrupado = mejor_por_nombre(outcomes)

    if not agrupado:
        return {
            "disponible": False,
            "lectura": "Sin mercado Ambos Anotan BTTS real disponible.",
        }

    filas = []

    for name, prices in agrupado.items():
        avg_price = promedio(prices)
        filas.append(
            {
                "seleccion": name,
                "momio_promedio": round(avg_price, 3),
                "prob_implicita": round(implied_prob(avg_price), 1),
                "bookmakers": len(prices),
            }
        )

    filas.sort(key=lambda x: x["prob_implicita"], reverse=True)

    favorito = filas[0]

    return {
        "disponible": True,
        "favorito": favorito["seleccion"],
        "filas": filas,
        "lectura": f"BTTS se inclina a {favorito['seleccion']} ({favorito['prob_implicita']}% implícito bruto).",
    }


def analizar_partido(partido: Dict[str, Any]) -> Dict[str, Any]:
    real = mercado_real_api(partido)

    if not real:
        bloqueado = {
            "disponible": False,
            "lectura": "Sin mercado real API; lectura bloqueada para evitar interpretar fallback técnico.",
        }

        return {
            "partido": nombre_partido(partido),
            "mercado_real_api": False,
            "h2h": bloqueado,
            "totals": bloqueado,
            "btts": bloqueado,
            "lectura_general": (
                "Sin mercado real API. No interpretar 1X2, Over/Under ni Ambos Anotan. "
                "El Real Data Gate debe mantener ESPERAR / NO ENVIAR."
            ),
        }

    h2h = analizar_h2h(partido)
    totals = analizar_totals(partido)
    btts = analizar_btts(partido)

    lecturas = [
        "Mercado real API detectado.",
        h2h["lectura"],
        totals["lectura"],
        btts["lectura"],
    ]

    return {
        "partido": nombre_partido(partido),
        "mercado_real_api": True,
        "h2h": h2h,
        "totals": totals,
        "btts": btts,
        "lectura_general": " ".join(lecturas),
    }

def escribir_txt(resultados: List[Dict[str, Any]]) -> None:
    OUTPUT_TXT.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("LECTURA DE MERCADO — CASINO / MOMIOS")
    lines.append("-" * 60)
    lines.append(f"Generado: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")

    for r in resultados:
        lines.append(r["partido"])
        lines.append(f"Mercado real API: {'Sí' if r['mercado_real_api'] else 'No'}")
        lines.append(f"1X2: {r['h2h']['lectura']}")
        lines.append(f"Over/Under: {r['totals']['lectura']}")
        lines.append(f"Ambos anotan: {r['btts']['lectura']}")
        lines.append(f"Lectura general: {r['lectura_general']}")
        lines.append("")

    OUTPUT_TXT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    data = cargar_json(JORNADAS_PATH, [])
    partidos = extraer_partidos(data)

    resultados = [analizar_partido(p) for p in partidos]

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(
            {
                "generado_en": datetime.now().isoformat(timespec="seconds"),
                "resultados": resultados,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    escribir_txt(resultados)

    print("📈 LECTURA DE MERCADO")
    print("=" * 60)
    for r in resultados:
        print(f"{r['partido']}: {r['lectura_general']}")
    print(f"✅ Texto guardado: {OUTPUT_TXT}")
    print(f"✅ JSON guardado: {OUTPUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
