#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


BASE_DIR = Path(__file__).resolve().parents[1]
JORNADAS_PATH = BASE_DIR / "data" / "jornadas.json"
PICK_AJUSTADO_PATH = BASE_DIR / "data" / "pick_ajustado_survivor.json"
OUTPUT_JSON = BASE_DIR / "data" / "pre_cierre_survivor.json"
OUTPUT_TXT = BASE_DIR / "reports" / "pre_cierre_survivor_ultimo.txt"


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


def fecha_hora_confirmada(partido: Dict[str, Any]) -> bool:
    fecha = str(partido.get("fecha", "")).upper()
    hora = str(partido.get("hora", "")).upper()

    if not fecha or not hora:
        return False

    if "PENDIENTE" in fecha or "PENDIENTE" in hora:
        return False

    return True


def mercado_real_disponible(partido: Dict[str, Any]) -> bool:
    momios = partido.get("momios", {})

    if isinstance(momios, dict):
        estado = str(momios.get("estado", "")).lower()
        if any(x in estado for x in ["mercado_no_publicado", "cerrado", "pendiente", "no_publicado"]):
            return False

    bookmakers = partido.get("bookmakers", [])

    if not isinstance(bookmakers, list) or not bookmakers:
        return False

    for bookmaker in bookmakers:
        if not isinstance(bookmaker, dict):
            continue

        key = str(bookmaker.get("key", "")).lower()
        title = str(bookmaker.get("title", "")).lower()

        if "fallback" in key or "fallback" in title:
            return False

    return True


def evaluar_pre_cierre() -> Dict[str, Any]:
    data = cargar_json(JORNADAS_PATH, [])
    pick_data = cargar_json(PICK_AJUSTADO_PATH, {})

    partidos = extraer_partidos(data)
    problemas: List[str] = []
    avisos: List[str] = []

    if not partidos:
        problemas.append("No hay partidos cargados en data/jornadas.json.")

    for partido in partidos:
        local = partido.get("home_team") or partido.get("local") or "LOCAL?"
        visitante = partido.get("away_team") or partido.get("visitante") or "VISITANTE?"
        nombre = f"{local} vs {visitante}"

        if not fecha_hora_confirmada(partido):
            problemas.append(f"{nombre}: falta fecha/hora confirmada.")

        if not mercado_real_disponible(partido):
            problemas.append(f"{nombre}: falta mercado real / momios reales.")

        if not partido.get("bajas_revisadas"):
            problemas.append(f"{nombre}: bajas no revisadas por IA.")

        riesgo = partido.get("riesgo_sorpresa", {})
        if isinstance(riesgo, dict):
            nivel = str(riesgo.get("nivel", "")).upper()
            etiqueta = str(riesgo.get("etiqueta", ""))

            if nivel == "ROJO":
                problemas.append(f"{nombre}: marcado como {etiqueta}.")
            elif nivel == "AMARILLO":
                avisos.append(f"{nombre}: riesgo medio; solo cerrar si el pick ajustado también permite cerrar.")

    decision_pick = (
        pick_data.get("decision", {}).get("decision")
        if isinstance(pick_data.get("decision"), dict)
        else None
    )

    if decision_pick and decision_pick != "CERRAR":
        problemas.append(f"Pick ajustado no está en CERRAR; estado actual: {decision_pick}.")

    if problemas:
        decision_final = "ESPERAR / NO ENVIAR"
        mensaje = "No cerrar todavía. Faltan condiciones reales para usar el pick en Survivor."
    else:
        decision_final = "CERRAR"
        mensaje = "Condiciones mínimas completas: mercado real, fecha/hora, bajas revisadas y pick ajustado en CERRAR."

    return {
        "generado_en": datetime.now().isoformat(timespec="seconds"),
        "decision_final": decision_final,
        "mensaje": mensaje,
        "problemas": problemas,
        "avisos": avisos,
        "decision_pick_ajustado": decision_pick or "NO DETECTADA",
    }


def escribir_txt(resultado: Dict[str, Any]) -> None:
    OUTPUT_TXT.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("AUDITOR PRE-CIERRE SURVIVOR")
    lines.append("-" * 60)
    lines.append(f"Decisión final: {resultado['decision_final']}")
    lines.append(f"Mensaje: {resultado['mensaje']}")
    lines.append(f"Pick ajustado: {resultado['decision_pick_ajustado']}")
    lines.append("")

    lines.append("Problemas bloqueantes:")
    if resultado["problemas"]:
        for problema in resultado["problemas"]:
            lines.append(f"- {problema}")
    else:
        lines.append("- Ninguno")

    lines.append("")
    lines.append("Avisos:")
    if resultado["avisos"]:
        for aviso in resultado["avisos"]:
            lines.append(f"- {aviso}")
    else:
        lines.append("- Ninguno")

    OUTPUT_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    resultado = evaluar_pre_cierre()

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    escribir_txt(resultado)

    print("🧾 AUDITOR PRE-CIERRE SURVIVOR")
    print("=" * 60)
    print(f"Decisión final: {resultado['decision_final']}")
    print(resultado["mensaje"])
    print(f"✅ JSON guardado: {OUTPUT_JSON}")
    print(f"✅ Texto guardado: {OUTPUT_TXT}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
