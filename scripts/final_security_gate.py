#!/usr/bin/env python3
"""
final_security_gate.py

Guardia final de seguridad operativa para Survivor Liga MX.

Objetivo:
- Validar que el reporte final mantenga una decisión segura.
- Bloquear cualquier reporte que no incluya una etiqueta permitida.
- Bloquear señales peligrosas como CERRAR, PICK LISTO, ENVIAR PICK o APUESTA.

Este script NO cierra picks.
Este script NO envía Telegram.
Este script solo permite continuar si el reporte conserva:
- ESPERAR / NO ENVIAR
- READY_FOR_FULL_AUDIT / NO ENVIAR AUTOMÁTICO
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path


ALLOWED_MARKERS = [
    "ESPERAR / NO ENVIAR",
    "READY_FOR_FULL_AUDIT / NO ENVIAR AUTOMÁTICO",
    "READY_FOR_FULL_AUDIT / NO ENVIAR AUTOMATICO",
]

FORBIDDEN_PATTERNS = [
    r"\bCERRAR\b",
    r"\bPICK\s+LISTO\b",
    r"\bENVIAR\s+PICK\b",
    r"\bENVIAR\s+FINAL\b",
    r"\bMANDAR\s+PICK\b",
    r"\bAPOSTAR\b",
    r"\bAPUESTA\b",
    r"\bAUTO\s*PICK\b",
    r"\bAUTO\s*SEND\b",
    r"\bAUTO\s*ENVIAR\b",
    r"\bBET\b",
]


@dataclass(frozen=True)
class SafetyGateResult:
    ok: bool
    exit_code: int
    message: str
    allowed_marker: str | None = None
    forbidden_matches: tuple[str, ...] = ()


def normalize_text(text: str) -> str:
    text = text or ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.upper()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def find_allowed_marker(text: str) -> str | None:
    normalized_text = normalize_text(text)

    for marker in ALLOWED_MARKERS:
        if normalize_text(marker) in normalized_text:
            return marker

    return None


def find_forbidden_matches(text: str) -> tuple[str, ...]:
    normalized_text = normalize_text(text)
    matches: list[str] = []

    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, normalized_text):
            matches.append(pattern)

    return tuple(matches)


def validate_report_text(text: str) -> SafetyGateResult:
    allowed_marker = find_allowed_marker(text)

    if not allowed_marker:
        return SafetyGateResult(
            ok=False,
            exit_code=2,
            message="NO ENVIAR: el reporte no contiene etiqueta segura permitida.",
        )

    forbidden_matches = find_forbidden_matches(text)

    if forbidden_matches:
        return SafetyGateResult(
            ok=False,
            exit_code=3,
            message="NO ENVIAR: el reporte contiene señales operativas prohibidas.",
            allowed_marker=allowed_marker,
            forbidden_matches=forbidden_matches,
        )

    return SafetyGateResult(
        ok=True,
        exit_code=0,
        message="OK: reporte validado por safety gate. Decisión segura conservada.",
        allowed_marker=allowed_marker,
    )


def validate_report_file(report_path: Path) -> SafetyGateResult:
    if not report_path.exists():
        return SafetyGateResult(
            ok=False,
            exit_code=1,
            message=f"NO ENVIAR: no existe el reporte final: {report_path}",
        )

    text = report_path.read_text(encoding="utf-8", errors="replace")
    return validate_report_text(text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Valida que el reporte final mantenga ESPERAR / NO ENVIAR."
    )
    parser.add_argument(
        "--report",
        required=True,
        help="Ruta del reporte final a validar.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = validate_report_file(Path(args.report))

    print(result.message)

    if result.allowed_marker:
        print(f"Etiqueta segura detectada: {result.allowed_marker}")

    if result.forbidden_matches:
        print("Patrones prohibidos detectados:")
        for match in result.forbidden_matches:
            print(f"- {match}")

    if result.ok:
        print("Decisión: ESPERAR / NO ENVIAR")
    else:
        print("Decisión: NO ENVIAR")

    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
