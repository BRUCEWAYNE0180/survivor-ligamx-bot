#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
from getpass import getpass
import re

ENV_PATH = Path(".env")

def es_linea_env_valida(linea: str) -> bool:
    """
    Acepta líneas tipo:
    KEY=value
    export KEY=value

    Ignora comentarios y líneas vacías.
    """
    limpia = linea.strip()

    if not limpia:
        return True

    if limpia.startswith("#"):
        return True

    if limpia.startswith("export "):
        limpia = limpia[len("export "):].strip()

    return re.match(r"^[A-Za-z_][A-Za-z0-9_]*=.*$", limpia) is not None


def normalizar_linea(linea: str) -> str:
    limpia = linea.strip()

    if limpia.startswith("export "):
        limpia = limpia[len("export "):].strip()

    return limpia


def clave_de_linea(linea: str) -> str:
    limpia = normalizar_linea(linea)
    if "=" not in limpia:
        return ""
    return limpia.split("=", 1)[0].strip()


def main():
    print("🔐 Reparador de .env para Survivor Liga MX")
    print("No se mostrará tu clave en pantalla.\n")

    nueva_groq = getpass("Pega tu NUEVA GROQ_API_KEY que empieza con gsk_: ").strip()

    if not nueva_groq.startswith("gsk_"):
        raise SystemExit("ERROR: La clave de Groq debe empezar con gsk_")

    if "\n" in nueva_groq or "\r" in nueva_groq or " " in nueva_groq:
        raise SystemExit("ERROR: La clave no debe tener espacios ni saltos de línea.")

    lineas_originales = []

    if ENV_PATH.exists():
        lineas_originales = ENV_PATH.read_text(encoding="utf-8").splitlines()

        backup = ENV_PATH.with_name(
            f".env.backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )
        backup.write_text("\n".join(lineas_originales) + "\n", encoding="utf-8")
        print(f"✅ Backup creado: {backup}")
    else:
        print("⚠️ No existía .env. Se creará uno nuevo.")

    nuevas_lineas = []
    keys_vistas = set()

    for linea in lineas_originales:
        limpia = linea.strip()

        # Elimina líneas vacías duplicadas después; por ahora permite una.
        if not limpia:
            continue

        # Mantiene comentarios.
        if limpia.startswith("#"):
            nuevas_lineas.append(limpia)
            continue

        # Elimina líneas rotas donde la clave gsk_ quedó sola.
        if limpia.startswith("gsk_") or "command not found" in limpia:
            continue

        # Elimina cualquier línea previa de Groq, correcta o rota.
        linea_normalizada = normalizar_linea(limpia)
        key = clave_de_linea(linea_normalizada)

        if key == "GROQ_API_KEY":
            continue

        # Mantiene solamente líneas .env válidas.
        if not es_linea_env_valida(linea_normalizada):
            continue

        # Evita duplicados de la misma variable. Conserva la primera válida.
        if key in keys_vistas:
            continue

        keys_vistas.add(key)
        nuevas_lineas.append(linea_normalizada)

    # Agrega GROQ_API_KEY limpia al final.
    if nuevas_lineas:
        nuevas_lineas.append("")

    nuevas_lineas.append(f"GROQ_API_KEY={nueva_groq}")

    ENV_PATH.write_text("\n".join(nuevas_lineas) + "\n", encoding="utf-8")

    print("\n✅ .env reparado correctamente.")
    print("✅ ODDS_API_KEY se mantuvo intacta si existía y estaba bien escrita.")
    print("✅ GROQ_API_KEY quedó guardada con formato correcto.")
    print("✅ Se eliminaron líneas sueltas tipo gsk_ que causaban 'command not found'.")


if __name__ == "__main__":
    main()
