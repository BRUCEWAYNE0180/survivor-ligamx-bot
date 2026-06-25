#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import requests

try:
    from api_budget import can_call as budget_can_call
    from api_budget import record_call as budget_record_call
    from api_budget import write_report as budget_write_report
except Exception:
    budget_can_call = None
    budget_record_call = None
    budget_write_report = None


BASE_DIR = Path(__file__).resolve().parents[1]
JORNADAS_PATH = BASE_DIR / "data" / "jornadas.json"


COORDENADAS_ESTADIOS = {
    "Estadio Victoria": {"lat": 21.8853, "lon": -102.2916},
    "Estadio Caliente": {"lat": 32.5012, "lon": -116.9667},
    "Estadio Libertad Financiera": {"lat": 22.1253, "lon": -100.9308},
    "Estadio León": {"lat": 21.1167, "lon": -101.6563},
    "Estadio Olímpico Benito Juárez": {"lat": 31.7386, "lon": -106.4869},
    "Estadio Olímpico Universitario": {"lat": 19.3319, "lon": -99.1925},
    "Estadio Akron": {"lat": 20.6817, "lon": -103.4626},
    "Estadio BBVA": {"lat": 25.6689, "lon": -100.2442},
    "Estadio Corregidora": {"lat": 20.5772, "lon": -100.3667},
    "Estadio Banorte": {"lat": 19.3030, "lon": -99.1500},
    "Estadio Nemesio Díez Riega": {"lat": 19.2876, "lon": -99.6661},
    "Estadio Universitario": {"lat": 25.7232, "lon": -100.3110},
    "Estadio Corona": {"lat": 25.5772, "lon": -103.3678},
    "Estadio Hidalgo": {"lat": 20.1011, "lon": -98.7553},
    "Estadio Cuauhtémoc": {"lat": 19.0777, "lon": -98.1646},
}


def cargar_jornadas() -> list[dict[str, Any]]:
    if not JORNADAS_PATH.exists():
        raise FileNotFoundError(f"No existe {JORNADAS_PATH}")

    data = json.loads(JORNADAS_PATH.read_text(encoding="utf-8"))

    if isinstance(data, list):
        return [p for p in data if isinstance(p, dict)]

    if isinstance(data, dict) and isinstance(data.get("partidos"), list):
        return [p for p in data["partidos"] if isinstance(p, dict)]

    raise ValueError("data/jornadas.json debe ser lista o contener {'partidos': [...]}.")


def guardar_jornadas(partidos: list[dict[str, Any]]) -> None:
    JORNADAS_PATH.write_text(
        json.dumps(partidos, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def describir_codigo_clima(codigo: int) -> str:
    if codigo == 0:
        return "Despejado"
    if codigo in (1, 2, 3):
        return "Parcialmente nublado"
    if 45 <= codigo <= 48:
        return "Niebla"
    if 51 <= codigo <= 67:
        return "Llovizna / lluvia"
    if 71 <= codigo <= 77:
        return "Nieve"
    if 80 <= codigo <= 82:
        return "Chubascos"
    if 95 <= codigo <= 99:
        return "Tormenta"
    return "Condición no clasificada"


def obtener_clima_open_meteo(coordenadas: Dict[str, float]) -> Dict[str, Any]:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": coordenadas["lat"],
        "longitude": coordenadas["lon"],
        "current_weather": "true",
        "timezone": "America/Mexico_City",
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    data = response.json()
    clima_actual = data.get("current_weather", {})

    if not isinstance(clima_actual, dict) or "temperature" not in clima_actual:
        raise ValueError(f"Respuesta sin current_weather válido: {data}")

    temperatura = float(clima_actual.get("temperature"))
    codigo = int(clima_actual.get("weathercode", 0))

    return {
        "real": True,
        "fuente": "Open-Meteo API",
        "temperatura_c": temperatura,
        "descripcion": describir_codigo_clima(codigo),
        "weathercode": codigo,
    }


def aplicar_clima_fallback(partido: Dict[str, Any], motivo: str) -> None:
    partido["clima_temperatura_c"] = 20.0
    partido["clima_estado"] = "Fallback técnico / clima no disponible"
    partido["clima_real"] = False
    partido["clima"] = {
        "real": False,
        "fuente": "fallback_tecnico",
        "temperatura_c": 20.0,
        "descripcion": "Fallback técnico / clima no disponible",
        "motivo": motivo,
        "nota": "No usar clima como señal fuerte.",
    }


def aplicar_clima_real(partido: Dict[str, Any], clima: Dict[str, Any]) -> None:
    partido["clima_temperatura_c"] = clima["temperatura_c"]
    partido["clima_estado"] = clima["descripcion"]
    partido["clima_real"] = True
    partido["clima"] = clima


def obtener_clima_estadios() -> None:
    print("\n⛅ Bot: Extrayendo reporte de clima en tiempo real para cada estadio...")

    partidos = cargar_jornadas()
    reales = 0
    fallback = 0

    for partido in partidos:
        local = partido.get("local") or partido.get("home_team") or "LOCAL?"
        estadio = partido.get("estadio") or partido.get("estadio_nombre") or ""

        if not estadio or estadio not in COORDENADAS_ESTADIOS:
            motivo = f"Sin coordenadas para estadio: {estadio or 'NO DETECTADO'}"
            print(f"⚠️ Clima fallback para {local}: {motivo}")
            aplicar_clima_fallback(partido, motivo)
            fallback += 1
            continue

        if budget_can_call is not None:
            permitido, mensaje_budget = budget_can_call(
                "open_meteo",
                units=1,
                min_interval_minutes=0,
            )

            if not permitido:
                motivo = f"Open-Meteo bloqueado por presupuesto: {mensaje_budget}"
                print(f"⚠️ Clima fallback para {local}: {motivo}")
                aplicar_clima_fallback(partido, motivo)
                fallback += 1
                continue

        try:
            clima = obtener_clima_open_meteo(COORDENADAS_ESTADIOS[estadio])
            aplicar_clima_real(partido, clima)
            reales += 1

            if budget_record_call is not None:
                budget_record_call(
                    "open_meteo",
                    units=1,
                    note=f"contexto clima estadio={estadio}",
                )

            print(f"🏟️ {estadio} ({local}): {clima['temperatura_c']}°C | {clima['descripcion']} | REAL")
        except Exception as exc:
            motivo = str(exc)
            print(f"⚠️ Clima fallback para {local}: {motivo}")
            aplicar_clima_fallback(partido, motivo)
            fallback += 1

    guardar_jornadas(partidos)

    print("✅ Bot: Clima procesado en data/jornadas.json")
    print(f"   Real Open-Meteo: {reales}")
    print(f"   Fallback técnico: {fallback}")
    if budget_write_report is not None:
        budget_write_report()

    if fallback:
        print("⚠️ Nota: clima fallback no debe usarse como señal fuerte.")


if __name__ == "__main__":
    obtener_clima_estadios()
