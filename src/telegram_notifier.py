#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path


MAX_TELEGRAM_CHARS = 3500


def dividir_texto(texto: str, max_chars: int = MAX_TELEGRAM_CHARS) -> list[str]:
    partes = []

    while len(texto) > max_chars:
        corte = texto.rfind("\n", 0, max_chars)
        if corte == -1:
            corte = max_chars

        partes.append(texto[:corte].strip())
        texto = texto[corte:].strip()

    if texto:
        partes.append(texto)

    return partes


def enviar_mensaje(token: str, chat_id: str, texto: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": texto,
        "disable_web_page_preview": True,
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))

    if not data.get("ok"):
        raise RuntimeError(f"Telegram respondió error: {data}")


def construir_mensaje_desde_reporte(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"No existe el reporte: {path}")

    texto = path.read_text(encoding="utf-8", errors="ignore").strip()

    encabezado = (
        "🔥 BOT SURVIVOR LIGA MX — SATCHEL\n"
        f"Enviado: {datetime.now().isoformat(timespec='seconds')}\n"
        + "=" * 40
        + "\n\n"
    )

    return encabezado + texto


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report",
        default="reports/reporte_survivor_ultimo.txt",
        help="Ruta del reporte final a enviar.",
    )
    args = parser.parse_args()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        print("⚠️ Telegram no configurado. Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID.")
        return 2

    mensaje = construir_mensaje_desde_reporte(Path(args.report))
    partes = dividir_texto(mensaje)

    for idx, parte in enumerate(partes, start=1):
        if len(partes) > 1:
            parte = f"Parte {idx}/{len(partes)}\n\n{parte}"

        enviar_mensaje(token, chat_id, parte)

    print(f"✅ Telegram enviado correctamente. Mensajes enviados: {len(partes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
