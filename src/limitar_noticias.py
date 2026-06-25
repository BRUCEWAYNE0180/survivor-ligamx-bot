#!/usr/bin/env python3
from pathlib import Path
import re
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parents[1]
NOTICIAS_PATH = BASE_DIR / "data" / "noticias_ligamx.txt"

MAX_NOTICIAS = 15
MAX_RESUMEN_CHARS = 280
MARCADOR_FILTRADO = "NOTA: Archivo filtrado automáticamente para Groq."

PALABRAS_CLAVE = [
    "lesión", "lesion", "lesionado", "lesionados",
    "suspendido", "suspensión", "suspension", "sancionado",
    "baja", "bajas", "descartado", "no jugará", "no jugara",
    "duda", "molestia", "entrenó separado", "entreno separado",
    "convocatoria", "rueda de prensa", "alineación", "alineacion",
    "titular", "regresa", "alta médica", "alta medica"
]

def score_bloque(bloque: str) -> int:
    texto = bloque.lower()
    return sum(1 for palabra in PALABRAS_CLAVE if palabra in texto)

def archivo_ya_filtrado(texto: str, bloques: list[str]) -> bool:
    return MARCADOR_FILTRADO in texto and len(bloques) <= MAX_NOTICIAS


def limpiar_encabezado(encabezado: str) -> str:
    lineas = []

    for linea in encabezado.splitlines():
        if linea.startswith("NOTA: Archivo filtrado automáticamente para Groq."):
            continue
        if linea.startswith("Prioridad: lesiones, suspensiones, bajas, dudas, convocatorias"):
            continue
        lineas.append(linea)

    return "\n".join(lineas).strip()


def recortar_resumen(bloque: str) -> str:
    lineas = []
    for linea in bloque.splitlines():
        if linea.startswith("Link:"):
            continue

        if linea.startswith("Resumen:"):
            resumen = linea.replace("Resumen:", "", 1).strip()
            if len(resumen) > MAX_RESUMEN_CHARS:
                resumen = resumen[:MAX_RESUMEN_CHARS].rstrip() + "..."
            lineas.append(f"Resumen: {resumen}")
        else:
            lineas.append(linea)

    return "\n".join(lineas).strip()

def main():
    if not NOTICIAS_PATH.exists():
        raise SystemExit(f"ERROR: No existe {NOTICIAS_PATH}")

    texto = NOTICIAS_PATH.read_text(encoding="utf-8")

    partes = re.split(r"\n(?=NOTICIA #\d+)", texto)
    encabezado = partes[0].strip()
    bloques = [p.strip() for p in partes[1:] if p.strip().startswith("NOTICIA #")]

    if archivo_ya_filtrado(texto, bloques):
        print("♻️ Archivo de noticias ya está filtrado para Groq.")
        print(f"✅ Noticias ya filtradas: {len(bloques)}")
        print("➡️ No se reescribe data/noticias_ligamx.txt; se conserva hash para cache IA.")
        return

    backup = NOTICIAS_PATH.with_suffix(
        f".backup-sin-filtrar-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
    )
    backup.write_text(texto, encoding="utf-8")

    puntuados = sorted(
        bloques,
        key=lambda b: score_bloque(b),
        reverse=True
    )

    seleccionados = puntuados[:MAX_NOTICIAS]
    seleccionados = [recortar_resumen(b) for b in seleccionados]

    salida = [
        limpiar_encabezado(encabezado),
        "",
        f"NOTA: Archivo filtrado automáticamente para Groq. Máximo {MAX_NOTICIAS} noticias.",
        "Prioridad: lesiones, suspensiones, bajas, dudas, convocatorias y ruedas de prensa.",
        "",
    ]

    salida.extend(seleccionados)

    NOTICIAS_PATH.write_text("\n\n".join(salida).strip() + "\n", encoding="utf-8")

    print(f"✅ Backup creado: {backup}")
    print(f"✅ Noticias originales: {len(bloques)}")
    print(f"✅ Noticias filtradas para IA: {len(seleccionados)}")
    print(f"✅ Archivo reducido: {NOTICIAS_PATH}")

if __name__ == "__main__":
    main()
