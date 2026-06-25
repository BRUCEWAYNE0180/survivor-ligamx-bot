#!/usr/bin/env python3
"""
Tests para src/market_watchdog.py (lógica pura, sin red ni API).

Ejecutar:
    python3 -m unittest tests.test_market_watchdog
o:
    python3 tests/test_market_watchdog.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Hacemos importable src/ (mismo patrón de imports planos del proyecto).
BASE_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import market_watchdog as wd  # noqa: E402


def partido_mercado_real() -> dict:
    return {
        "home_team": "America",
        "away_team": "Juarez",
        "momios": {"estado": "mercado_real_api"},
        "bookmakers": [
            {"key": "pinnacle", "title": "Pinnacle", "markets": [{"key": "h2h"}]}
        ],
    }


def partido_fallback() -> dict:
    return {
        "home_team": "Chivas",
        "away_team": "Pumas",
        "momios": {"estado": "mercado_no_publicado_api"},
        "bookmakers": [
            {"key": "fallback_local", "title": "Fallback técnico", "markets": []}
        ],
    }


class TestClasificacion(unittest.TestCase):
    def test_sin_partidos(self):
        self.assertEqual(wd.clasificar_disponibilidad(0, 0), wd.ST_SIN_PARTIDOS)

    def test_ninguno(self):
        self.assertEqual(wd.clasificar_disponibilidad(0, 9), wd.ST_NINGUNO)

    def test_parcial(self):
        self.assertEqual(wd.clasificar_disponibilidad(3, 9), wd.ST_PARCIAL)

    def test_completo(self):
        self.assertEqual(wd.clasificar_disponibilidad(9, 9), wd.ST_COMPLETO)

    def test_status_completo_es_ready_no_cerrar(self):
        self.assertEqual(wd.status_watchdog(wd.ST_COMPLETO), wd.WD_READY)
        # El watchdog jamás autoriza CERRAR.
        self.assertEqual(wd.etiqueta_operativa(wd.ST_COMPLETO), wd.OP_NO_ENVIAR)
        self.assertNotIn("CERRAR", wd.etiqueta_operativa(wd.ST_COMPLETO))


class TestConteoLocal(unittest.TestCase):
    def test_cuenta_solo_mercado_real(self):
        partidos = [partido_mercado_real(), partido_fallback(), partido_fallback()]
        disponibles, total = wd.contar_mercado_local(partidos)
        self.assertEqual((disponibles, total), (1, 3))

    def test_cero_de_nueve(self):
        partidos = [partido_fallback() for _ in range(9)]
        disponibles, total = wd.contar_mercado_local(partidos)
        self.assertEqual((disponibles, total), (0, 9))


class TestDecidirAlerta(unittest.TestCase):
    def test_sin_cambio_0_9_no_envia(self):
        # 0/9 -> 0/9: no debe enviar (evita spam).
        tipo = wd.decidir_alerta(0, wd.ST_NINGUNO, 0, wd.ST_NINGUNO)
        self.assertIsNone(tipo)

    def test_sin_partidos_no_envia(self):
        tipo = wd.decidir_alerta(0, wd.ST_NINGUNO, 0, wd.ST_SIN_PARTIDOS)
        self.assertIsNone(tipo)

    def test_aparece_mercado(self):
        # 0/9 -> 3/9
        tipo = wd.decidir_alerta(0, wd.ST_NINGUNO, 3, wd.ST_PARCIAL)
        self.assertEqual(tipo, "MERCADO_APARECIO")

    def test_aumenta_mercado(self):
        # 3/9 -> 6/9
        tipo = wd.decidir_alerta(3, wd.ST_PARCIAL, 6, wd.ST_PARCIAL)
        self.assertEqual(tipo, "MERCADO_AUMENTO")

    def test_parcial_a_completo_es_alerta_fuerte(self):
        # 6/9 -> 9/9
        tipo = wd.decidir_alerta(6, wd.ST_PARCIAL, 9, wd.ST_COMPLETO)
        self.assertEqual(tipo, "MERCADO_COMPLETO")

    def test_cero_a_completo_directo(self):
        tipo = wd.decidir_alerta(0, wd.ST_NINGUNO, 9, wd.ST_COMPLETO)
        self.assertEqual(tipo, "MERCADO_COMPLETO")

    def test_disminuye_mercado(self):
        tipo = wd.decidir_alerta(9, wd.ST_COMPLETO, 4, wd.ST_PARCIAL)
        self.assertEqual(tipo, "MERCADO_DISMINUYO")

    def test_completo_estable_no_reenvia(self):
        tipo = wd.decidir_alerta(9, wd.ST_COMPLETO, 9, wd.ST_COMPLETO)
        self.assertIsNone(tipo)


class TestMensajeTelegram(unittest.TestCase):
    def test_mensaje_completo_menciona_ready_y_no_cierra(self):
        msg = wd.construir_mensaje_telegram("MERCADO_COMPLETO", 9, 9, wd.ST_COMPLETO, "live")
        self.assertIn(wd.WD_READY, msg)
        self.assertIn("auditor_pre_cierre", msg)
        self.assertNotIn("CERRAR automá", msg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
