#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


BASE_DIR = Path(__file__).resolve().parents[1]
JORNADAS_PATH = BASE_DIR / "data" / "jornadas.json"
API_BUDGET_STATE = BASE_DIR / "data" / "api_budget_state.json"
OUTPUT_TXT = BASE_DIR / "reports" / "market_status_ultimo.txt"
OUTPUT_JSON = BASE_DIR / "data" / "market_status_ultimo.json"


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


def nombre_local(partido: Dict[str, Any]) -> str:
    return str(partido.get("home_team") or partido.get("local") or partido.get("equipo_local") or "LOCAL?")


def nombre_visitante(partido: Dict[str, Any]) -> str:
    return str(partido.get("away_team") or partido.get("visitante") or partido.get("equipo_visitante") or "VISITANTE?")


def es_fallback_bookmaker(partido: Dict[str, Any]) -> bool:
    bookmakers = partido.get("bookmakers", [])

    if not isinstance(bookmakers, list):
        return False

    for book in bookmakers:
        if not isinstance(book, dict):
            continue

        key = str(book.get("key", "")).lower()
        title = str(book.get("title", "")).lower()

        if "fallback" in key or "fallback" in title:
            return True

    return False


def es_mercado_real(partido: Dict[str, Any]) -> bool:
    momios = partido.get("momios", {})

    if not isinstance(momios, dict):
        return False

    estado = str(momios.get("estado", "")).lower().strip()

    if estado != "mercado_real_api":
        return False

    if es_fallback_bookmaker(partido):
        return False

    return True


def estado_mercado(partido: Dict[str, Any]) -> str:
    momios = partido.get("momios", {})

    if not isinstance(momios, dict):
        return "sin_momios"

    if es_mercado_real(partido):
        return "mercado_real_api"

    estado = str(momios.get("estado", "")).strip()

    if estado:
        return estado

    if es_fallback_bookmaker(partido):
        return "fallback_tecnico"

    return "momios_no_reales"


def leer_budget_the_odds() -> Dict[str, Any]:
    state = cargar_json(API_BUDGET_STATE, {})

    if not isinstance(state, dict):
        return {}

    # Formato actual de api_budget.py:
    # {"apis": {"the_odds_api": {...}}, "history": [...]}
    apis = state.get("apis")
    if isinstance(apis, dict):
        value = apis.get("the_odds_api")
        if isinstance(value, dict):
            return value

    # Soporta formatos flexibles por si api_budget.py cambia.
    for key in ["the_odds_api", "The Odds API", "odds_api"]:
        value = state.get(key)
        if isinstance(value, dict):
            return value

    return {}


def obtener_budget_resumen() -> Dict[str, Any]:
    budget = leer_budget_the_odds()

    if not budget:
        return {
            "detectado": False,
            "usado": "N/D",
            "limite": "N/D",
            "periodo": "N/D",
            "ultima_llamada": "N/D",
            "nota": "N/D",
        }

    usado = (
        budget.get("used")
        or budget.get("usado")
        or budget.get("count")
        or budget.get("requests")
        or 0
    )

    limite = (
        budget.get("limit")
        or budget.get("limite")
        or budget.get("monthly_limit")
        or 500
    )

    ultima = (
        budget.get("last_call_at")
        or budget.get("last_call")
        or budget.get("ultima_llamada")
        or budget.get("last_used_at")
        or budget.get("updated_at")
        or "N/D"
    )

    nota = (
        budget.get("note")
        or budget.get("nota")
        or budget.get("last_note")
        or "N/D"
    )

    periodo = budget.get("period_id") or budget.get("period") or budget.get("periodo") or "N/D"

    return {
        "detectado": True,
        "usado": usado,
        "limite": limite,
        "periodo": periodo,
        "ultima_llamada": ultima,
        "nota": nota,
    }


def main() -> int:
    data = cargar_json(JORNADAS_PATH, [])
    partidos = extraer_partidos(data)

    filas = []
    mercado_real = 0
    fallback = 0
    sin_momios = 0

    for partido in partidos:
        local = nombre_local(partido)
        visitante = nombre_visitante(partido)
        estado = estado_mercado(partido)
        real = es_mercado_real(partido)

        if real:
            mercado_real += 1
        elif estado == "sin_momios":
            sin_momios += 1
        else:
            fallback += 1

        filas.append(
            {
                "partido": f"{local} vs {visitante}",
                "local": local,
                "visitante": visitante,
                "estado_mercado": estado,
                "mercado_real": real,
            }
        )

    total = len(partidos)

    if total == 0:
        decision = "ERROR / SIN PARTIDOS"
        mensaje = "No se encontraron partidos en data/jornadas.json."
    elif mercado_real == total:
        decision = "POSIBLE CERRAR / REQUIERE PRE-CIERRE"
        mensaje = "Todos los partidos tienen mercado real API. Ejecutar run_bot.sh y revisar auditor pre-cierre."
    elif mercado_real > 0:
        decision = "ESPERAR / REVISAR PARCIAL"
        mensaje = "Algunos partidos tienen mercado real, pero no toda la jornada. Revisar lectura de mercado y pre-cierre."
    else:
        decision = "ESPERAR / NO ENVIAR"
        mensaje = "No hay mercado real API para la jornada. No usar fallback técnico para cerrar Survivor."

    budget = obtener_budget_resumen()

    resultado = {
        "generado_en": datetime.now().isoformat(timespec="seconds"),
        "partidos": total,
        "mercado_real": mercado_real,
        "fallback_o_no_real": fallback,
        "sin_momios": sin_momios,
        "decision": decision,
        "mensaje": mensaje,
        "the_odds_api_budget": budget,
        "detalle": filas,
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_TXT.parent.mkdir(parents=True, exist_ok=True)

    OUTPUT_JSON.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("MARKET STATUS — SURVIVOR LIGA MX")
    lines.append("-" * 70)
    lines.append(f"Generado: {resultado['generado_en']}")
    lines.append("")
    lines.append(f"Partidos: {total}")
    lines.append(f"Mercado real API: {mercado_real}/{total}")
    lines.append(f"Fallback / no real: {fallback}/{total}")
    lines.append(f"Sin momios: {sin_momios}/{total}")
    lines.append("")
    lines.append(f"Decisión: {decision}")
    lines.append(f"Mensaje: {mensaje}")
    lines.append("")
    lines.append("The Odds API Budget:")
    lines.append(f"- Usado: {budget['usado']}/{budget['limite']}")
    lines.append(f"- Periodo: {budget['periodo']}")
    lines.append(f"- Última llamada: {budget['ultima_llamada']}")
    lines.append(f"- Nota: {budget['nota']}")
    lines.append("")
    lines.append("Detalle:")
    for fila in filas:
        marca = "✅ REAL" if fila["mercado_real"] else "⚠️ NO REAL"
        lines.append(f"- {fila['partido']} | {marca} | estado={fila['estado_mercado']}")

    OUTPUT_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n".join(lines))
    print("")
    print(f"✅ Reporte: {OUTPUT_TXT}")
    print(f"✅ JSON: {OUTPUT_JSON}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
