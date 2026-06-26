#!/usr/bin/env python3
"""
assisted_odds_import.py — Assisted Sportsbook Odds Import (Survivor Liga MX).

v1.39.0.

Lógica PURA de parseo/validación/reporte para una importación ASISTIDA POR
USUARIO de momios 1X2 desde un sportsbook (ej. Caliente Liga MX).

Modelo asistido (NO automatizado):
- El navegador se abre VISIBLE (lo hace el script CLI, no este módulo).
- El usuario completa manualmente cualquier verificación/login si aparece.
- Después el bot solo lee el TEXTO VISIBLE de la página y lo parsea aquí.

Reglas duras (este módulo no rompe ninguna):
- NO stealth. NO playwright-stealth. NO proxy. NO bypass de
  firewall/captcha/login/verificación. NO automatiza login. NO guarda
  credenciales. NO manda Telegram. NO cambia picks. NO imprime secretos.
- Decisión operativa SIEMPRE: ESPERAR / NO ENVIAR. Nunca marca un pick listo.

Este módulo no hace red, no abre navegador y no toca .env: solo recibe texto
ya capturado y devuelve estructuras + reportes en texto.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
VERSION = "v1.39.0"

# Decisión operativa: este flujo asistido NUNCA cierra ni envía un pick.
DEC_ESPERAR = "ESPERAR / NO ENVIAR"

# Estados de resultado del parseo.
STATUS_OK = "OK"
STATUS_NO_MATCHES = "NO_MATCHES_FOUND"

LIGA = "Liga MX"
FUENTE = "assisted_manual_sportsbook"

# Etiquetas posibles para el empate (columna central del 1X2).
_DRAW_LABELS = ("empate", "draw", "x")

# Meses ES/EN (abreviados o completos) -> número de mes.
_MESES: Dict[str, int] = {
    "ene": 1, "enero": 1, "jan": 1, "january": 1,
    "feb": 2, "febrero": 2, "february": 2,
    "mar": 3, "marzo": 3, "march": 3,
    "abr": 4, "abril": 4, "apr": 4, "april": 4,
    "may": 5, "mayo": 5,
    "jun": 6, "junio": 6, "june": 6,
    "jul": 7, "julio": 7, "july": 7,
    "ago": 8, "agosto": 8, "aug": 8, "august": 8,
    "sep": 9, "set": 9, "sept": 9, "septiembre": 9, "september": 9,
    "oct": 10, "octubre": 10, "october": 10,
    "nov": 11, "noviembre": 11, "november": 11,
    "dic": 12, "diciembre": 12, "dec": 12, "december": 12,
}

# Un momio americano: signo obligatorio + 2 a 4 dígitos (ej. +120, -125, +275).
_RE_MOMIO = re.compile(r"^[+-]\d{2,4}$")

# Magnitud mínima válida de un momio americano (even money = ±100).
_MOMIO_MIN_ABS = 100

# Patrón de un evento 1X2 dentro del texto visible.
#
#   HH:MM  DD  Mon  EquipoLocal  MOMIO  Empate  MOMIO  EquipoVisitante  MOMIO
#   19:00  16  Jul  Necaxa       -125   Empate  +260   Atlante          +275
#
# Notas de diseño anti-mezcla (bloque gigante de DOM):
# - Los nombres de equipo se capturan con una clase que EXCLUYE dígitos y los
#   signos +/-; así un nombre nunca puede "tragarse" un momio ni cruzar al
#   siguiente evento. Cada coincidencia arranca en un token de hora HH:MM.
# - La clase de equipo NO incluye saltos de línea; usamos finditer, por lo que
#   los eventos se extraen de forma independiente y no se combinan partidos.
_EQUIPO = r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ.'’/ ]+?"
_MOMIO_G = r"[+-]\d{2,4}"

_RE_EVENTO = re.compile(
    r"(?P<hora>\d{1,2}:\d{2})[ \t]+"
    r"(?P<dia>\d{1,2})[ \t]+"
    r"(?P<mes>[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{3,12})\.?[ \t]+"
    r"(?P<local>" + _EQUIPO + r")[ \t]+"
    r"(?P<momio_local>" + _MOMIO_G + r")[ \t]+"
    r"(?:Empate|Draw|X)[ \t]+"
    r"(?P<momio_empate>" + _MOMIO_G + r")[ \t]+"
    r"(?P<visitante>" + _EQUIPO + r")[ \t]+"
    r"(?P<momio_visitante>" + _MOMIO_G + r")",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers de normalización / validación
# ---------------------------------------------------------------------------
def _quitar_acentos(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _norm_equipo(nombre: str) -> str:
    """Normaliza nombre de equipo SOLO para comparar/deduplicar (no para mostrar)."""
    base = _quitar_acentos(str(nombre or "")).lower()
    base = re.sub(r"[^a-z0-9 ]+", " ", base)
    return re.sub(r"\s+", " ", base).strip()


def es_momio_americano_valido(momio: Any) -> bool:
    """True si `momio` es un momio americano válido (±NN..±NNNN, |valor| >= 100)."""
    s = str(momio or "").strip()
    if not _RE_MOMIO.fullmatch(s):
        return False
    try:
        return abs(int(s)) >= _MOMIO_MIN_ABS
    except (TypeError, ValueError):
        return False


def _mes_a_numero(mes: str) -> int:
    """Devuelve el número de mes (1-12) o 0 si no se reconoce."""
    clave = _quitar_acentos(str(mes or "")).lower().strip(".")
    if clave in _MESES:
        return _MESES[clave]
    # Tolera abreviaturas de 3 letras de meses largos no listados.
    return _MESES.get(clave[:3], 0)


def evento_momios_validos(evento: Dict[str, Any]) -> bool:
    """True si los tres momios del evento son americanos válidos."""
    return all(
        es_momio_americano_valido(evento.get(campo))
        for campo in ("momio_local", "momio_empate", "momio_visitante")
    )


# ---------------------------------------------------------------------------
# Parseo de eventos desde texto visible
# ---------------------------------------------------------------------------
def _construir_evento(m: "re.Match[str]") -> Dict[str, Any]:
    dia = m.group("dia").strip()
    mes_raw = m.group("mes").strip()
    mes_num = _mes_a_numero(mes_raw)
    return {
        "hora": m.group("hora").strip(),
        "dia": int(dia),
        "mes_texto": mes_raw,
        "mes": mes_num,
        "fecha": f"{int(dia):02d} {mes_raw}",
        "equipo_local": m.group("local").strip(),
        "equipo_visitante": m.group("visitante").strip(),
        "momio_local": m.group("momio_local").strip(),
        "momio_empate": m.group("momio_empate").strip(),
        "momio_visitante": m.group("momio_visitante").strip(),
    }


def extraer_eventos_crudos(texto: str) -> List[Dict[str, Any]]:
    """
    Extrae todos los eventos candidatos del texto visible.

    Filtra coincidencias con mes no reconocido o día fuera de rango (1-31),
    lo que evita falsos positivos cuando el DOM trae un bloque gigante.
    """
    eventos: List[Dict[str, Any]] = []
    for m in _RE_EVENTO.finditer(str(texto or "")):
        ev = _construir_evento(m)
        if ev["mes"] == 0:
            continue
        if not (1 <= ev["dia"] <= 31):
            continue
        if not ev["equipo_local"] or not ev["equipo_visitante"]:
            continue
        eventos.append(ev)
    return eventos


def deduplicar(eventos: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """
    Deduplica por (local, visitante, fecha, hora) usando nombres normalizados.
    Conserva la primera aparición. Devuelve (eventos_unicos, num_duplicados).
    """
    vistos = set()
    unicos: List[Dict[str, Any]] = []
    duplicados = 0
    for ev in eventos:
        clave = (
            _norm_equipo(ev.get("equipo_local")),
            _norm_equipo(ev.get("equipo_visitante")),
            str(ev.get("fecha", "")).strip().lower(),
            str(ev.get("hora", "")).strip(),
        )
        if clave in vistos:
            duplicados += 1
            continue
        vistos.add(clave)
        unicos.append(ev)
    return unicos, duplicados


def analizar_texto(texto: str, esperados: int = 9) -> Dict[str, Any]:
    """
    Pipeline completo de parseo sobre el texto visible.

    Devuelve un dict con eventos válidos/deduplicados, conteos, eventos
    inválidos, estado (OK / NO_MATCHES_FOUND) y la decisión operativa fija.
    """
    crudos = extraer_eventos_crudos(texto)

    validos_pre: List[Dict[str, Any]] = []
    invalidos: List[Dict[str, Any]] = []
    for ev in crudos:
        if evento_momios_validos(ev):
            validos_pre.append(ev)
        else:
            invalidos.append(ev)

    eventos, duplicados = deduplicar(validos_pre)
    status = STATUS_OK if eventos else STATUS_NO_MATCHES

    return {
        "liga": LIGA,
        "fuente": FUENTE,
        "esperados": esperados,
        "total_detectados": len(crudos),
        "total_validos": len(eventos),
        "duplicados_removidos": duplicados,
        "invalidos": invalidos,
        "eventos": eventos,
        "status": status,
        "coincide_esperados": len(eventos) == esperados,
        "decision": DEC_ESPERAR,
    }


# ---------------------------------------------------------------------------
# Exportación a JSON (sin secretos)
# ---------------------------------------------------------------------------
def construir_payload_json(resultado: Dict[str, Any]) -> Dict[str, Any]:
    """Construye el payload JSON exportable (solo datos de momios, sin secretos)."""
    eventos_export = [
        {
            "fecha": ev["fecha"],
            "hora": ev["hora"],
            "equipo_local": ev["equipo_local"],
            "equipo_visitante": ev["equipo_visitante"],
            "momio_local": ev["momio_local"],
            "momio_empate": ev["momio_empate"],
            "momio_visitante": ev["momio_visitante"],
        }
        for ev in resultado.get("eventos", [])
    ]
    return {
        "version": VERSION,
        "liga": resultado.get("liga", LIGA),
        "fuente": resultado.get("fuente", FUENTE),
        "generado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": resultado.get("status", STATUS_NO_MATCHES),
        "total": len(eventos_export),
        "decision": DEC_ESPERAR,
        "pick_listo": False,
        "eventos": eventos_export,
    }


def exportar_json(resultado: Dict[str, Any]) -> str:
    """Serializa el payload JSON con indentación estable."""
    return json.dumps(construir_payload_json(resultado), ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Render del reporte TXT (sin secretos, sin cierre operativo, mantiene ESPERAR)
# ---------------------------------------------------------------------------
def render_report(resultado: Dict[str, Any], *, url: str = "") -> str:
    """
    Genera el reporte en texto plano. No incluye secretos ni credenciales:
    solo el host de la URL (si se pasa), conteos y la decisión operativa.
    """
    eventos = resultado.get("eventos", [])
    lineas: List[str] = [
        f"# ASSISTED SPORTSBOOK ODDS IMPORT — SURVIVOR LIGA MX ({VERSION})",
        "",
        "Modo: importación ASISTIDA POR USUARIO (no stealth, no bypass, no proxy).",
        "Login/verificación: manual, en navegador visible. No se guardan credenciales.",
        f"Liga: {resultado.get('liga', LIGA)}",
        f"Fuente: {resultado.get('fuente', FUENTE)}",
    ]
    if url:
        lineas.append(f"Host: {_host_de_url(url)}")
    lineas += [
        "",
        f"Status: {resultado.get('status', STATUS_NO_MATCHES)}",
        f"Eventos esperados: {resultado.get('esperados', '?')}",
        f"Eventos detectados (crudos): {resultado.get('total_detectados', 0)}",
        f"Eventos válidos (deduplicados): {resultado.get('total_validos', 0)}",
        f"Duplicados removidos: {resultado.get('duplicados_removidos', 0)}",
        f"Eventos inválidos (momios no americanos): {len(resultado.get('invalidos', []))}",
        f"Coincide con esperados: {'SÍ' if resultado.get('coincide_esperados') else 'NO'}",
        "",
    ]

    if resultado.get("status") == STATUS_NO_MATCHES:
        lineas += [
            "AVISO: NO_MATCHES_FOUND — no se detectaron eventos 1X2 válidos en el",
            "texto visible. Revisar manualmente la página y volver a capturar.",
            "",
        ]

    if eventos:
        lineas.append("Eventos Liga MX (1X2):")
        for ev in eventos:
            lineas.append(
                f"- {ev['fecha']} {ev['hora']} | "
                f"{ev['equipo_local']} ({ev['momio_local']}) | "
                f"Empate ({ev['momio_empate']}) | "
                f"{ev['equipo_visitante']} ({ev['momio_visitante']})"
            )
        lineas.append("")

    invalidos = resultado.get("invalidos", [])
    if invalidos:
        lineas.append("Eventos descartados por momios inválidos:")
        for ev in invalidos:
            lineas.append(
                f"- {ev.get('fecha', '?')} {ev.get('hora', '?')} | "
                f"{ev.get('equipo_local', '?')} vs {ev.get('equipo_visitante', '?')} "
                f"(momios: {ev.get('momio_local')}, {ev.get('momio_empate')}, "
                f"{ev.get('momio_visitante')})"
            )
        lineas.append("")

    lineas += [
        "DECISIÓN GENERAL:",
        f"- {DEC_ESPERAR}.",
        "- No cambiar pick.",
        "- No enviar Telegram.",
        "- No marcar pick listo (este flujo nunca cierra un pick).",
        "- Importación solo informativa para auditoría manual de mercado.",
    ]
    return "\n".join(lineas) + "\n"


def _host_de_url(url: str) -> str:
    """Devuelve solo el host de una URL (sin querystring) para el reporte."""
    try:
        from urllib.parse import urlparse

        return urlparse(str(url)).netloc or str(url)
    except Exception:
        return str(url)
