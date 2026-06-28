#!/usr/bin/env python3
"""
ai_provider.py — Proveedor Multi-IA para Survivor Liga MX Bot.

v1.31.0
- Groq sigue como proveedor principal.
- Gemini REST puede funcionar como respaldo sin instalar google-genai.
- No imprime API keys.
- No rota por auth/cuota/rate limit/plan:
  - 401
  - 403
  - 429
- Solo permite failover por falla técnica real:
  - Timeout
  - ConnectionError
  - HTTP 500/502/503/504
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests


def cargar_env_local() -> None:
    """
    Carga .env local sin imprimir secrets.
    No sobrescribe variables ya exportadas en el entorno.
    """
    root = Path(__file__).resolve().parents[1]
    env_path = root / ".env"

    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


cargar_env_local()


FAILOVER_STATUS_CODES = {500, 502, 503, 504}
NO_ROTATE_STATUS_CODES = {401, 403, 429}

GROQ_MODEL = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

GEMINI_ENDPOINT_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


class TechnicalAIError(RuntimeError):
    """Error técnico: permite failover a proveedor/llave de respaldo."""


class NonRotatableAIError(RuntimeError):
    """Error de auth/cuota/rate-limit/plan: NO permite rotación."""


def key_valida(value: str) -> bool:
    if not value:
        return False

    value = value.strip()
    placeholders = [
        "tu_api_key",
        "your_api_key",
        "changeme",
        "replace_me",
        "none",
        "null",
    ]
    return bool(value) and not any(p in value.lower() for p in placeholders)


def status_code_from_exception(exc: Exception) -> Optional[int]:
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status

    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)

    if isinstance(response_status, int):
        return response_status

    return None


def es_falla_tecnica(exc: Exception) -> bool:
    status = status_code_from_exception(exc)
    if status in FAILOVER_STATUS_CODES:
        return True

    nombre = type(exc).__name__.lower()
    texto = str(exc).lower()

    patrones = [
        "timeout",
        "connection",
        "connect",
        "temporarily unavailable",
        "server error",
        "service unavailable",
        "bad gateway",
        "gateway timeout",
        "remote end closed connection",
    ]

    return any(p in nombre or p in texto for p in patrones)


def groq_key_candidates() -> List[Tuple[str, str]]:
    primary = os.getenv("GROQ_API_KEY_PRIMARY", "").strip() or os.getenv("GROQ_API_KEY", "").strip()
    backup = os.getenv("GROQ_API_KEY_BACKUP", "").strip()

    keys: List[Tuple[str, str]] = []
    seen = set()

    for label, value in [("groq_primary", primary), ("groq_backup", backup)]:
        if not key_valida(value):
            continue

        if value in seen:
            continue

        keys.append((label, value))
        seen.add(value)

    return keys


def gemini_key_candidates() -> List[Tuple[str, str]]:
    primary = os.getenv("GEMINI_API_KEY", "").strip()
    backup = os.getenv("GEMINI_API_KEY_BACKUP", "").strip()

    keys: List[Tuple[str, str]] = []
    seen = set()

    for label, value in [("gemini_primary", primary), ("gemini_backup", backup)]:
        if not key_valida(value):
            continue

        if value in seen:
            continue

        keys.append((label, value))
        seen.add(value)

    return keys


def cargar_json_seguro(contenido: str) -> Dict[str, Any]:
    contenido = (contenido or "").strip()

    if not contenido:
        return {}

    try:
        return json.loads(contenido)
    except json.JSONDecodeError:
        pass

    inicio = contenido.find("{")
    fin = contenido.rfind("}")

    if inicio >= 0 and fin > inicio:
        posible_json = contenido[inicio : fin + 1]
        return json.loads(posible_json)

    raise ValueError("La IA no devolvió JSON válido.")


def prompt_usuario(texto_noticias: str) -> str:
    return (
        "Analiza este texto de noticias de Liga MX y devuelve JSON limpio "
        "con los jugadores confirmados como baja:\n\n"
        f"{texto_noticias}"
    )


def llamar_groq_con_key(
    label: str,
    api_key: str,
    texto_noticias: str,
    system_prompt: str,
) -> Dict[str, Any]:
    try:
        from groq import Groq
    except Exception as exc:
        raise RuntimeError("No está instalada la librería 'groq'. Instálala con: pip3 install groq") from exc

    client = Groq(api_key=api_key)

    respuesta = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0,
        max_tokens=2500,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": prompt_usuario(texto_noticias),
            },
        ],
    )

    contenido = respuesta.choices[0].message.content or "{}"
    data = cargar_json_seguro(contenido)
    data.setdefault("proveedor_ia", "groq")
    data.setdefault("modelo", GROQ_MODEL)
    data.setdefault("llave_usada", label)
    return data


def llamar_groq(
    texto_noticias: str,
    system_prompt: str,
) -> Dict[str, Any]:
    keys = groq_key_candidates()

    if not keys:
        raise RuntimeError("Falta GROQ_API_KEY_PRIMARY o GROQ_API_KEY.")

    last_error: Optional[Exception] = None

    for idx, (label, api_key) in enumerate(keys):
        try:
            print(f"IA Groq: intentando {label}...")
            resultado = llamar_groq_con_key(label, api_key, texto_noticias, system_prompt)
            print(f"IA Groq: OK con {label}.")
            return resultado

        except Exception as exc:
            last_error = exc
            status = status_code_from_exception(exc)

            if status in NO_ROTATE_STATUS_CODES:
                raise NonRotatableAIError(
                    f"Groq respondió {status}. No se rota por auth/cuota/rate limit."
                ) from exc

            if es_falla_tecnica(exc):
                print(f"IA Groq: falla técnica con {label}: {type(exc).__name__}")

                if idx < len(keys) - 1:
                    print("IA Groq: probando llave de respaldo técnico.")
                    continue

                raise TechnicalAIError("Groq falló técnicamente sin más llaves Groq.") from exc

            raise

    raise RuntimeError("No se pudo consultar Groq.") from last_error


def extraer_texto_gemini(payload: Dict[str, Any]) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        return "{}"

    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []

    textos = []
    for part in parts:
        if isinstance(part, dict) and part.get("text"):
            textos.append(str(part["text"]))

    return "\n".join(textos).strip() or "{}"


def llamar_gemini_con_key(
    label: str,
    api_key: str,
    texto_noticias: str,
    system_prompt: str,
) -> Dict[str, Any]:
    endpoint = GEMINI_ENDPOINT_TEMPLATE.format(model=GEMINI_MODEL)

    body = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            f"{system_prompt}\n\n"
                            f"{prompt_usuario(texto_noticias)}"
                        )
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 2500,
            "responseMimeType": "application/json",
        },
    }

    try:
        response = requests.post(
            endpoint,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            json=body,
            timeout=45,
        )
    except requests.Timeout as exc:
        raise TechnicalAIError("Gemini timeout.") from exc
    except requests.ConnectionError as exc:
        raise TechnicalAIError("Gemini connection error.") from exc

    status = response.status_code

    if status in NO_ROTATE_STATUS_CODES:
        raise NonRotatableAIError(
            f"Gemini respondió {status}. No se rota por auth/cuota/rate limit."
        )

    if status in FAILOVER_STATUS_CODES:
        raise TechnicalAIError(f"Gemini falla técnica HTTP {status}.")

    if status >= 400:
        raise RuntimeError(f"Gemini respondió HTTP {status}. No se usa como fallback técnico.")

    payload = response.json()
    contenido = extraer_texto_gemini(payload)
    data = cargar_json_seguro(contenido)
    data.setdefault("proveedor_ia", "gemini")
    data.setdefault("modelo", GEMINI_MODEL)
    data.setdefault("llave_usada", label)
    return data


def llamar_gemini(
    texto_noticias: str,
    system_prompt: str,
) -> Dict[str, Any]:
    keys = gemini_key_candidates()

    if not keys:
        raise RuntimeError("Falta GEMINI_API_KEY.")

    last_error: Optional[Exception] = None

    for idx, (label, api_key) in enumerate(keys):
        try:
            print(f"IA Gemini: intentando {label}...")
            resultado = llamar_gemini_con_key(label, api_key, texto_noticias, system_prompt)
            print(f"IA Gemini: OK con {label}.")
            return resultado

        except NonRotatableAIError:
            raise

        except TechnicalAIError as exc:
            last_error = exc
            print(f"IA Gemini: falla técnica con {label}: {type(exc).__name__}")

            if idx < len(keys) - 1:
                print("IA Gemini: probando llave de respaldo técnico.")
                continue

            raise TechnicalAIError("Gemini falló técnicamente sin más llaves Gemini.") from exc

        except Exception as exc:
            last_error = exc
            raise

    raise RuntimeError("No se pudo consultar Gemini.") from last_error


def llamar_ia(
    texto_noticias: str,
    system_prompt: str,
) -> Dict[str, Any]:
    """
    Proveedor principal: Groq.
    Proveedor respaldo: Gemini.

    Gemini solo entra si Groq falla técnicamente.
    No entra por auth/cuota/rate-limit/plan.
    """
    try:
        return llamar_groq(texto_noticias, system_prompt)

    except NonRotatableAIError:
        raise

    except TechnicalAIError:
        print("IA: Groq tuvo falla técnica. Intentando Gemini como respaldo.")

        try:
            return llamar_gemini(texto_noticias, system_prompt)
        except RuntimeError as gemini_exc:
            raise RuntimeError(
                "IA: Groq falló técnicamente y Gemini no pudo completar el análisis."
            ) from gemini_exc

    except Exception:
        raise
