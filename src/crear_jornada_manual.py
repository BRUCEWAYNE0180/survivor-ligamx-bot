#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
JORNADAS_PATH = DATA_DIR / "jornadas.json"
CONFIG_SURVIVOR_PATH = DATA_DIR / "config_survivor.json"


ESTADIOS_LIGA_MX = {
    "america": ("Estadio Ciudad de los Deportes", "Ciudad de México"),
    "club america": ("Estadio Ciudad de los Deportes", "Ciudad de México"),
    "chivas": ("Estadio Akron", "Guadalajara"),
    "guadalajara": ("Estadio Akron", "Guadalajara"),
    "cruz azul": ("Estadio Ciudad de los Deportes", "Ciudad de México"),
    "pumas": ("Estadio Olímpico Universitario", "Ciudad de México"),
    "pumas unam": ("Estadio Olímpico Universitario", "Ciudad de México"),
    "tigres": ("Estadio Universitario", "San Nicolás de los Garza"),
    "monterrey": ("Estadio BBVA", "Guadalupe"),
    "rayados": ("Estadio BBVA", "Guadalupe"),
    "toluca": ("Estadio Nemesio Diez", "Toluca"),
    "tijuana": ("Estadio Caliente", "Tijuana"),
    "xolos": ("Estadio Caliente", "Tijuana"),
    "atlas": ("Estadio Jalisco", "Guadalajara"),
    "leon": ("Estadio León", "León"),
    "pachuca": ("Estadio Hidalgo", "Pachuca"),
    "santos": ("Estadio TSM Corona", "Torreón"),
    "santos laguna": ("Estadio TSM Corona", "Torreón"),
    "queretaro": ("Estadio Corregidora", "Querétaro"),
    "puebla": ("Estadio Cuauhtémoc", "Puebla"),
    "necaxa": ("Estadio Victoria", "Aguascalientes"),
    "mazatlan": ("Estadio El Encanto", "Mazatlán"),
    "juarez": ("Estadio Olímpico Benito Juárez", "Ciudad Juárez"),
    "fc juarez": ("Estadio Olímpico Benito Juárez", "Ciudad Juárez"),
    "san luis": ("Estadio Alfonso Lastras", "San Luis Potosí"),
    "atletico san luis": ("Estadio Alfonso Lastras", "San Luis Potosí"),
}


def limpiar(texto: str) -> str:
    return texto.strip()


def normalizar(texto: str) -> str:
    return texto.lower().strip()


def pedir(texto: str, default: str = "") -> str:
    if default:
        value = input(f"{texto} [{default}]: ").strip()
        return value or default

    return input(f"{texto}: ").strip()


def cargar_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def guardar_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def obtener_bloqueados() -> List[str]:
    config = cargar_json(CONFIG_SURVIVOR_PATH, {})

    if isinstance(config, dict) and isinstance(config.get("equipos_bloqueados"), list):
        return [str(x) for x in config["equipos_bloqueados"]]

    return []


def sugerir_estadio_ciudad(local: str) -> tuple[str, str]:
    key = normalizar(local)

    if key in ESTADIOS_LIGA_MX:
        return ESTADIOS_LIGA_MX[key]

    for nombre, datos in ESTADIOS_LIGA_MX.items():
        if nombre in key or key in nombre:
            return datos

    return "PENDIENTE_CONFIRMAR", "PENDIENTE_CONFIRMAR"


def crear_partido(numero: int) -> Dict[str, Any]:
    print("")
    print(f"PARTIDO #{numero}")
    print("-" * 60)

    local = limpiar(pedir("Equipo local"))
    visitante = limpiar(pedir("Equipo visitante"))

    estadio_default, ciudad_default = sugerir_estadio_ciudad(local)

    fecha = limpiar(pedir("Fecha", "PENDIENTE_CONFIRMAR"))
    hora = limpiar(pedir("Hora", "PENDIENTE_CONFIRMAR"))
    estadio = limpiar(pedir("Estadio", estadio_default))
    ciudad = limpiar(pedir("Ciudad", ciudad_default))

    return {
        "local": local,
        "visitante": visitante,
        "fecha": fecha,
        "hora": hora,
        "estadio": estadio,
        "ciudad": ciudad,
        "clima": {
            "estado": "pendiente",
            "temperatura": 20.0,
            "descripcion": "Fallback local hasta actualizar clima real",
            "fuente": "fallback",
        },
        "momios": {
            "estado": "mercado_no_publicado",
            "fuente": "The Odds API",
            "actualizado_en": None,
        },
        "bookmakers": [
            {
                "key": "fallback_local",
                "title": "Fallback técnico - mercado no publicado",
                "markets": [
                    {
                        "key": "h2h",
                        "last_update": None,
                        "outcomes": [
                            {"name": local, "price": 1.80},
                            {"name": "Draw", "price": 3.40},
                            {"name": visitante, "price": 4.50},
                        ],
                    }
                ],
            }
        ],
        "lesiones": [],
        "suspendidos": [],
        "bajas_revisadas": False,
    }


def confirmar(texto: str) -> bool:
    value = input(f"{texto} [s/N]: ").strip().lower()
    return value in {"s", "si", "sí", "y", "yes"}


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("🧾 CREADOR DE JORNADA REAL — SURVIVOR LIGA MX")
    print("=" * 60)
    print("Esto reemplaza data/jornadas.json con los partidos que captures.")
    print("data/ no se sube a GitHub; es información local.\n")

    jornada = pedir("Nombre de jornada", "Jornada real Liga MX")
    torneo = pedir("Torneo", "Liga MX")
    temporada = pedir("Temporada", "PENDIENTE_CONFIRMAR")

    partidos: List[Dict[str, Any]] = []
    numero = 1

    while True:
        partidos.append(crear_partido(numero))
        numero += 1

        if not confirmar("¿Agregar otro partido?"):
            break

    bloqueados = obtener_bloqueados()

    data = {
        "torneo": torneo,
        "temporada": temporada,
        "jornada": jornada,
        "partidos": partidos,
        "equipos_bloqueados": bloqueados,
        "_metadata": {
            "actualizado_por": "src/crear_jornada_manual.py",
            "actualizado_en": datetime.now().isoformat(timespec="seconds"),
            "nota": "Jornada capturada manualmente para análisis Survivor Liga MX.",
        },
    }

    if JORNADAS_PATH.exists():
        backup = JORNADAS_PATH.with_suffix(
            f".backup-manual-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        )
        backup.write_text(JORNADAS_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"\n✅ Backup creado: {backup}")

    guardar_json(JORNADAS_PATH, data)

    print("")
    print("✅ Jornada real guardada correctamente.")
    print(f"✅ Archivo: {JORNADAS_PATH}")
    print(f"✅ Partidos capturados: {len(partidos)}")
    print(f"✅ Equipos bloqueados Survivor: {', '.join(bloqueados) if bloqueados else 'Ninguno'}")
    print("")
    print("Siguiente comando recomendado:")
    print("./run_bot.sh")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
