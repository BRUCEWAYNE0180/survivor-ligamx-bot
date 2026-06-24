#!/usr/bin/env python3
"""
actualizador_noticias_web.py

Busca noticias recientes de Liga MX usando Google News RSS y genera:
data/noticias_ligamx.txt

Después puedes correr:
set -a && source .env && set +a && python3 -u src/aplicar_noticias_ia.py
"""

from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


BASE_DIR = Path(__file__).resolve().parents[1]
JORNADAS_PATH = BASE_DIR / "data" / "jornadas.json"
SALIDA_NOTICIAS = BASE_DIR / "data" / "noticias_ligamx.txt"


LOCAL_KEYS = ["local", "equipo_local", "home", "home_team", "casa"]
VISITANTE_KEYS = ["visitante", "equipo_visitante", "away", "away_team", "visita"]


def buscar_valor(obj: Dict[str, Any], keys: List[str]) -> str:
    for key in keys:
        value = obj.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def extraer_partidos(data: Any) -> List[Dict[str, Any]]:
    partidos: List[Dict[str, Any]] = []

    if isinstance(data, list):
        return [p for p in data if isinstance(p, dict)]

    if not isinstance(data, dict):
        return partidos

    if isinstance(data.get("partidos"), list):
        partidos.extend([p for p in data["partidos"] if isinstance(p, dict)])

    if isinstance(data.get("jornadas"), list):
        for jornada in data["jornadas"]:
            if isinstance(jornada, dict) and isinstance(jornada.get("partidos"), list):
                partidos.extend([p for p in jornada["partidos"] if isinstance(p, dict)])

    for key, value in data.items():
        if key.startswith("jornada") and isinstance(value, list):
            partidos.extend([p for p in value if isinstance(p, dict)])

    return partidos


def limpiar_html(texto: str) -> str:
    texto = html.unescape(texto or "")
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def google_news_rss_url(query: str) -> str:
    q = urllib.parse.quote_plus(query)
    return f"https://news.google.com/rss/search?q={q}&hl=es-419&gl=MX&ceid=MX:es-419"


def consultar_google_news(query: str, max_items: int = 5) -> List[Dict[str, str]]:
    url = google_news_rss_url(query)

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 LigaMXSurvivorBot/1.0"
        },
    )

    with urllib.request.urlopen(req, timeout=20) as response:
        xml_data = response.read()

    root = ET.fromstring(xml_data)
    items = []

    for item in root.findall(".//item")[:max_items]:
        title = limpiar_html(item.findtext("title", ""))
        description = limpiar_html(item.findtext("description", ""))
        pub_date = limpiar_html(item.findtext("pubDate", ""))
        link = limpiar_html(item.findtext("link", ""))
        source = item.find("source")
        source_name = limpiar_html(source.text) if source is not None and source.text else ""

        if title:
            items.append(
                {
                    "query": query,
                    "titulo": title,
                    "descripcion": description,
                    "fecha": pub_date,
                    "fuente": source_name,
                    "link": link,
                }
            )

    return items


def construir_queries(local: str, visitante: str) -> List[str]:
    base = [
        f'Liga MX {local} {visitante} lesionados suspendidos',
        f'{local} Liga MX lesionados suspendidos bajas',
        f'{visitante} Liga MX lesionados suspendidos bajas',
        f'{local} rueda de prensa Liga MX bajas',
        f'{visitante} rueda de prensa Liga MX bajas',
    ]

    # Más agresivo para detectar frases clave.
    extra = [
        f'{local} no juega lesión suspensión Liga MX',
        f'{visitante} no juega lesión suspensión Liga MX',
    ]

    return base + extra


def main() -> int:
    if not JORNADAS_PATH.exists():
        raise SystemExit(f"ERROR: No existe {JORNADAS_PATH}")

    data = json.loads(JORNADAS_PATH.read_text(encoding="utf-8"))
    partidos = extraer_partidos(data)

    if not partidos:
        raise SystemExit("ERROR: No encontré partidos en data/jornadas.json")

    todas_noticias: List[Dict[str, str]] = []
    vistos = set()

    print("📰 Buscando noticias importantes de Liga MX...")

    for partido in partidos:
        local = buscar_valor(partido, LOCAL_KEYS)
        visitante = buscar_valor(partido, VISITANTE_KEYS)

        if not local or not visitante:
            continue

        print(f"🔎 {local} vs {visitante}")

        for query in construir_queries(local, visitante):
            try:
                noticias = consultar_google_news(query, max_items=4)
            except Exception as exc:
                print(f"   ⚠️ Falló query: {query} | {exc}")
                continue

            for noticia in noticias:
                firma = noticia["titulo"].lower().strip()
                if firma in vistos:
                    continue
                vistos.add(firma)
                todas_noticias.append(noticia)

    ahora = datetime.now().isoformat(timespec="seconds")

    lineas = [
        "REPORTE AUTOMÁTICO DE NOTICIAS LIGA MX",
        f"Generado en: {ahora}",
        "",
        "Objetivo: detectar bajas confirmadas, lesiones, suspensiones, dudas importantes, ruedas de prensa y cambios relevantes.",
        "",
    ]

    if not todas_noticias:
        lineas.append("No se encontraron noticias recientes.")
    else:
        for idx, noticia in enumerate(todas_noticias, start=1):
            lineas.extend(
                [
                    f"NOTICIA #{idx}",
                    f"Consulta: {noticia['query']}",
                    f"Título: {noticia['titulo']}",
                    f"Fuente: {noticia['fuente']}",
                    f"Fecha: {noticia['fecha']}",
                    f"Resumen: {noticia['descripcion']}",
                    f"Link: {noticia['link']}",
                    "",
                ]
            )

    SALIDA_NOTICIAS.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    print(f"✅ Noticias encontradas: {len(todas_noticias)}")
    print(f"✅ Archivo creado: {SALIDA_NOTICIAS}")
    print("➡️ Siguiente paso: correr src/aplicar_noticias_ia.py")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
