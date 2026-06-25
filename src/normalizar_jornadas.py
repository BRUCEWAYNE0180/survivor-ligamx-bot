#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


BASE_DIR = Path(__file__).resolve().parents[1]
JORNADAS_PATH = BASE_DIR / "data" / "jornadas.json"


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

    if isinstance(data, dict):
        if isinstance(data.get("partidos"), list):
            return [p for p in data["partidos"] if isinstance(p, dict)]

    return []


def normalizar_partido(partido: Dict[str, Any]) -> Dict[str, Any]:
    local = (
        partido.get("home_team")
        or partido.get("local")
        or partido.get("equipo_local")
        or partido.get("casa")
        or ""
    )

    visitante = (
        partido.get("away_team")
        or partido.get("visitante")
        or partido.get("equipo_visitante")
        or partido.get("visita")
        or ""
    )

    partido["home_team"] = local
    partido["away_team"] = visitante
    partido["local"] = local
    partido["visitante"] = visitante

    partido.setdefault("fecha", "PENDIENTE_CONFIRMAR")
    partido.setdefault("hora", "PENDIENTE_CONFIRMAR")
    partido.setdefault("estadio", "PENDIENTE_CONFIRMAR")
    partido.setdefault("ciudad", "PENDIENTE_CONFIRMAR")

    partido.setdefault("lesiones", [])
    partido.setdefault("suspendidos", [])
    partido.setdefault("bajas_revisadas", False)

    partido.setdefault(
        "clima",
        {
            "estado": "pendiente",
            "temperatura": 20.0,
            "descripcion": "Fallback local",
            "fuente": "fallback",
        },
    )

    partido.setdefault(
        "momios",
        {
            "estado": "mercado_no_publicado",
            "fuente": "The Odds API",
            "actualizado_en": None,
        },
    )

    # Fallback técnico para que predictor.py no falle cuando The Odds API
    # todavía no publica mercado. NO son momios reales.
    if not isinstance(partido.get("bookmakers"), list) or not partido.get("bookmakers"):
        partido["bookmakers"] = [
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
        ]

    partido["_normalizado_por"] = "src/normalizar_jornadas.py"
    partido["_normalizado_en"] = datetime.now().isoformat(timespec="seconds")

    return partido


def main() -> int:
    if not JORNADAS_PATH.exists():
        raise SystemExit(f"ERROR: No existe {JORNADAS_PATH}")

    data = cargar_json(JORNADAS_PATH, {})
    partidos = extraer_partidos(data)

    if not partidos:
        raise SystemExit("ERROR: No encontré partidos para normalizar.")

    backup = JORNADAS_PATH.with_suffix(
        f".backup-normalizar-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    backup.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    partidos_normalizados = [normalizar_partido(p) for p in partidos]

    JORNADAS_PATH.write_text(
        json.dumps(partidos_normalizados, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"✅ Jornadas normalizadas: {len(partidos_normalizados)} partido(s)")
    print(f"✅ Backup creado: {backup}")
    print("✅ data/jornadas.json quedó compatible con main.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
