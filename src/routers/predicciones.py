#!/usr/bin/env python3
"""
routers/predicciones.py — Endpoints de predicciones REALES (ESPN + Poisson).

Expone en la web las predicciones legítimas basadas en datos reales de ESPN
(vía el motor), en lugar de los momios inventados. Read-only, con caché en
memoria (TTL) para no golpear ESPN en cada request.

- GET /predicciones  -> 1X2 / Over-Under / BTTS / marcador por partido próximo.
- GET /survivor      -> mejor equipo "no perder" de la jornada (excluye usados).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi import APIRouter

try:
    import motor_pronosticos as motor
except ImportError:  # pragma: no cover - contexto de paquete (web)
    from src import motor_pronosticos as motor  # type: ignore

try:
    import tabla_posiciones as tabla_mod
except ImportError:  # pragma: no cover
    from src import tabla_posiciones as tabla_mod  # type: ignore

try:
    import comparador_mercado as mercado_mod
except ImportError:  # pragma: no cover
    from src import comparador_mercado as mercado_mod  # type: ignore

try:
    import fuentes_datos as fuentes_mod
except ImportError:  # pragma: no cover
    from src import fuentes_datos as fuentes_mod  # type: ignore

try:
    import analisis_riesgo as riesgo_mod
except ImportError:  # pragma: no cover
    from src import analisis_riesgo as riesgo_mod  # type: ignore

router = APIRouter(tags=["Predicciones"])

_CACHE: Dict[str, Any] = {"data": None, "ts": None}
_CACHE_TABLA: Dict[str, Any] = {"data": None, "ts": None}
_CACHE_RIESGO: Dict[str, Any] = {"data": None, "ts": None}
_TTL_MIN = 30
_TTL_RIESGO_MIN = 360  # el histórico cambia lento; análisis pesado => caché larga


def _fresco() -> bool:
    return bool(_CACHE["data"]) and bool(_CACHE["ts"]) and (
        datetime.utcnow() - _CACHE["ts"] < timedelta(minutes=_TTL_MIN)
    )


def _obtener() -> Dict[str, Any]:
    if not _fresco():
        _CACHE["data"] = motor.generar_pronosticos()
        _CACHE["ts"] = datetime.utcnow()
    return _CACHE["data"]


def _obtener_tabla() -> Dict[str, Any]:
    fresco = bool(_CACHE_TABLA["data"]) and bool(_CACHE_TABLA["ts"]) and (
        datetime.utcnow() - _CACHE_TABLA["ts"] < timedelta(minutes=_TTL_MIN)
    )
    if not fresco:
        _CACHE_TABLA["data"] = tabla_mod.obtener_tabla()
        _CACHE_TABLA["ts"] = datetime.utcnow()
    return _CACHE_TABLA["data"]


@router.get("/predicciones", summary="Predicciones reales (ESPN + Poisson)")
def predicciones() -> Dict[str, Any]:
    """1X2 / Over-Under / BTTS / marcador por cada partido próximo."""
    return _obtener()


@router.get("/survivor", summary="Mejor pick de Survivor (no perder)")
def survivor(excluir: str = "") -> Dict[str, Any]:
    """
    Mejor equipo para Survivor (mayor prob. de no perder). `excluir`: equipos
    ya usados, separados por coma (ej. ?excluir=America,Toluca).
    """
    data = _obtener()
    usados = [e.strip() for e in excluir.split(",") if e.strip()]
    pick = motor.mejor_pick_survivor(data.get("pronosticos", []), usados)
    return {
        "generado_utc": data.get("generado_utc"),
        "fuente_datos": data.get("fuente_datos"),
        "equipos_excluidos": usados,
        "pick_survivor": pick,
        "decision": data.get("decision"),
    }


@router.get("/jornada", summary="Vista de jornada: predicciones + pick + top-3 + motivación + momios")
def jornada(excluir: str = "") -> Dict[str, Any]:
    """
    Todo-en-uno para decidir la semana: predicciones, mejor pick de Survivor +
    top-3, motivación de la tabla y comparación vs mercado (si hay momios).
    """
    data = _obtener()
    pronos = data.get("pronosticos", [])
    comp = mercado_mod.comparar_pronosticos(pronos)  # momios gated (no-op sin key)
    pronos = comp.get("pronosticos", pronos)
    try:
        motivacion = motor.motivacion_por_equipo()
    except Exception:  # pragma: no cover - fallback defensivo de red
        motivacion = {}
    usados = [e.strip() for e in excluir.split(",") if e.strip()]
    top = motor.mejores_picks_survivor(pronos, usados, motivacion, n=3)
    return {
        "generado_utc": data.get("generado_utc"),
        "fuente_datos": data.get("fuente_datos"),
        "equipos_excluidos": usados,
        "pick_survivor": top[0] if top else None,
        "top_picks": top,
        "mercado_habilitado": comp.get("mercado_habilitado", False),
        "partidos_con_momios": comp.get("partidos_con_momios", 0),
        "pronosticos": pronos,
        "decision": data.get("decision"),
    }


@router.get("/tabla", summary="Tabla Liga MX (ESPN) + motivación por equipo")
def tabla() -> Dict[str, Any]:
    """Tabla general con zona de clasificación y motivación por equipo."""
    try:
        data = _obtener_tabla()
    except Exception as exc:  # pragma: no cover - fallback defensivo de red
        return {"torneo": "", "tabla": [], "error": str(exc),
                "decision": "INFORMATIVO / REVISIÓN HUMANA"}
    return {**data, "decision": "INFORMATIVO / REVISIÓN HUMANA"}


@router.get("/valor", summary="Predicciones + comparación vs mercado (opcional)")
def valor() -> Dict[str, Any]:
    """
    Predicciones del modelo anotadas con comparación vs mercado (dónde el modelo
    ve 'valor'). SOLO activa si hay key de momios configurada (ODDS_API_IO_KEY);
    si no, devuelve las predicciones sin comparación (mercado_habilitado=False).
    Informativo: el modelo es la fuente de verdad; no es consejo de apuesta.
    """
    data = _obtener()
    comp = mercado_mod.comparar_pronosticos(data.get("pronosticos", []))
    return {
        "generado_utc": data.get("generado_utc"),
        "fuente_datos": data.get("fuente_datos"),
        **comp,
    }


@router.get("/valor/diagnostico", summary="Diagnóstico de la conexión a momios (debug)")
def valor_diagnostico() -> Dict[str, Any]:
    """Muestra qué devuelve odds-api.io (eventos/casas/mercados) sin exponer la key."""
    return mercado_mod.diagnostico_mercado()


@router.get("/health/fuentes", summary="Salud de las fuentes de datos (ESPN/TheSportsDB/odds)")
def health_fuentes() -> Dict[str, Any]:
    """Ping a cada fuente para detectar caídas antes de la jornada."""
    return fuentes_mod.estado_fuentes()


@router.get("/analisis/riesgo", summary="¿Cuándo falla el favorito? (análisis de upsets, datos reales)")
def analisis_riesgo() -> Dict[str, Any]:
    """
    Mide, sobre el histórico real (walk-forward), cuándo y por qué falla el
    favorito del modelo: por condición (local vs visitante), nivel de confianza
    y partidos cerrados ('under'). Útil para no quemar el Survivor con un
    favorito engañoso. Análisis pesado => caché de 6 horas.
    """
    fresco = bool(_CACHE_RIESGO["data"]) and bool(_CACHE_RIESGO["ts"]) and (
        datetime.utcnow() - _CACHE_RIESGO["ts"] < timedelta(minutes=_TTL_RIESGO_MIN)
    )
    if not fresco:
        try:
            datos = fuentes_mod.obtener_resultados(meses=18)
            _CACHE_RIESGO["data"] = riesgo_mod.analizar_riesgo_favoritos(datos["resultados"])
            _CACHE_RIESGO["data"]["fuente_datos"] = datos.get("fuente")
        except Exception as exc:  # pragma: no cover - fallback defensivo de red
            return {"partidos_evaluados": 0, "error": str(exc),
                    "decision": "INFORMATIVO / REVISIÓN HUMANA"}
        _CACHE_RIESGO["ts"] = datetime.utcnow()
    return _CACHE_RIESGO["data"]
