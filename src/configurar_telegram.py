#!/usr/bin/env python3
from __future__ import annotations

import json
import time
import urllib.request
from getpass import getpass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"


def leer_env() -> dict:
    data = {}
    if not ENV_PATH.exists():
        return data

    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def escribir_env(data: dict) -> None:
    orden = [
        "ODDS_API_KEY",
        "GROQ_API_KEY",
        "GROQ_MODEL",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
    ]

    lines = []
    for key in orden:
        if key in data and data[key]:
            lines.append(f"{key}={data[key]}")

    for key, value in data.items():
        if key not in orden and value:
            lines.append(f"{key}={value}")

    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def telegram_get(token: str, method: str) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    with urllib.request.urlopen(url, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def get_me(token: str) -> dict:
    data = telegram_get(token, "getMe")
    if not data.get("ok"):
        raise RuntimeError(f"Token inválido o Telegram respondió error: {data}")
    return data["result"]


def buscar_chat_id(token: str) -> str | None:
    data = telegram_get(token, "getUpdates")

    if not data.get("ok"):
        raise RuntimeError(f"Telegram no respondió OK: {data}")

    updates = data.get("result", [])

    for update in reversed(updates):
        message = update.get("message") or update.get("channel_post")
        if not message:
            continue

        chat = message.get("chat", {})
        chat_id = chat.get("id")

        if chat_id:
            return str(chat_id)

    return None


def main() -> int:
    print("🤖 CONFIGURAR TELEGRAM — SURVIVOR LIGA MX")
    print("=" * 60)
    print("Pega el token solo aquí en Terminal. No lo pegues en ChatGPT.\n")

    env = leer_env()
    token = getpass("Pega tu TELEGRAM_BOT_TOKEN aquí: ").strip()

    if not token:
        raise SystemExit("ERROR: TELEGRAM_BOT_TOKEN vacío.")

    bot = get_me(token)
    username = bot.get("username")
    first_name = bot.get("first_name", "")

    print("\n✅ Token válido.")
    print(f"🤖 Bot detectado: {first_name}")
    print(f"👉 Username exacto: @{username}")
    print("")
    print("AHORA HAZ ESTO EN TELEGRAM:")
    print(f"1. Busca exactamente: @{username}")
    print("2. Abre ese chat.")
    print("3. Presiona el botón START o manda /start.")
    print("4. Luego manda también: hola")
    print("")
    print("Voy a esperar hasta 90 segundos para detectar tu chat_id...")
    print("No cierres esta Terminal.\n")

    chat_id = None

    for intento in range(1, 19):
        chat_id = buscar_chat_id(token)
        if chat_id:
            break

        print(f"⏳ Esperando mensaje del bot... intento {intento}/18")
        time.sleep(5)

    if not chat_id:
        raise SystemExit(
            "\n❌ No encontré chat_id.\n"
            "Casi seguro estás mandando /start al bot equivocado, o no abriste el username exacto mostrado arriba.\n"
            f"Busca en Telegram exactamente: @{username}\n"
        )

    env["TELEGRAM_BOT_TOKEN"] = token
    env["TELEGRAM_CHAT_ID"] = chat_id
    escribir_env(env)

    print("\n✅ Telegram configurado correctamente.")
    print(f"✅ TELEGRAM_CHAT_ID detectado: {chat_id}")
    print("✅ Guardado en .env sin tocar tus otras llaves.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
