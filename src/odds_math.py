#!/usr/bin/env python3
"""
odds_math.py — Matemática pura de momios (Survivor Liga MX).

Funciones sin estado, sin red, sin I/O: conversión de formatos, probabilidad
implícita, margen de la casa (overround/vig) y probabilidades sin vig.

NO toma decisiones de apuesta, NO cierra ni envía picks. Solo cálculo.
"""
from __future__ import annotations

from typing import List, Sequence


def americano_a_decimal(momio: float) -> float:
    """Convierte un momio americano (+150, -125) a cuota decimal."""
    m = float(momio)
    if m == 0:
        raise ValueError("Momio americano no puede ser 0.")
    if m > 0:
        return 1.0 + m / 100.0
    return 1.0 + 100.0 / abs(m)


def decimal_a_probabilidad(cuota: float) -> float:
    """Probabilidad implícita (con vig) de una cuota decimal: 1/cuota."""
    c = float(cuota)
    if c <= 1.0:
        raise ValueError(f"Cuota decimal inválida: {cuota} (debe ser > 1.0).")
    return 1.0 / c


def probabilidades_implicitas(cuotas: Sequence[float]) -> List[float]:
    """Lista de probabilidades implícitas (con vig) para varias cuotas."""
    return [decimal_a_probabilidad(c) for c in cuotas]


def margen_casa(cuotas: Sequence[float]) -> float:
    """
    Margen de la casa (overround / vig) como fracción.

    overround = sum(1/cuota) - 1. Ej. [2.0, 3.0, 4.0] -> 0.0833 (8.33%).
    Un mercado "justo" (sin margen) daría 0.0.
    """
    if not cuotas:
        raise ValueError("Se requiere al menos una cuota.")
    return sum(probabilidades_implicitas(cuotas)) - 1.0


def margen_casa_pct(cuotas: Sequence[float]) -> float:
    """Margen de la casa expresado en porcentaje (redondeado a 2 decimales)."""
    return round(margen_casa(cuotas) * 100.0, 2)


def probabilidades_sin_vig(cuotas: Sequence[float]) -> List[float]:
    """
    Probabilidades normalizadas (sin vig): la implícita de cada resultado
    dividida entre la suma total. Suman 1.0.
    """
    implicitas = probabilidades_implicitas(cuotas)
    total = sum(implicitas)
    if total <= 0:
        raise ValueError("Suma de probabilidades implícitas inválida.")
    return [p / total for p in implicitas]
