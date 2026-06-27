#!/usr/bin/env python3
"""
Tests para src/pronostico_avanzado.py (orquestador de pronósticos).

Verifican que cada fuente cumple su rol y la degradación segura:
- con histórico + mercado -> mezcla modelo+mercado
- solo mercado -> usa mercado
- solo histórico -> usa modelo
- sin nada -> sin_datos
Sin red ni I/O real.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = str(Path(__file__).resolve().parents[1] / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import pronostico_avanzado as pa  # noqa: E402


def _bookmaker(key, cl, ce, cv, local="America", visita="Toluca"):
    return {
        "key": key, "title": key,
        "markets": [{"key": "h2h", "outcomes": [
            {"name": local, "price": cl},
            {"name": "Draw", "price": ce},
            {"name": visita, "price": cv},
        ]}],
    }


def _partido_con_mercado(local="America", visita="Toluca"):
    return {
        "home_team": local, "away_team": visita,
        "bookmakers": [_bookmaker("bet365", 1.8, 3.5, 4.5, local, visita)],
    }


def _historico():
    return [
        {"home_team": "America", "away_team": "Toluca", "home_goals": 3, "away_goals": 0},
        {"home_team": "America", "away_team": "Atlas", "home_goals": 2, "away_goals": 1},
        {"home_team": "Toluca", "away_team": "Atlas", "home_goals": 1, "away_goals": 1},
        {"home_team": "Toluca", "away_team": "America", "home_goals": 0, "away_goals": 2},
        {"home_team": "Atlas", "away_team": "America", "home_goals": 0, "away_goals": 3},
        {"home_team": "Atlas", "away_team": "Toluca", "home_goals": 1, "away_goals": 1},
    ]


class TestCuotasYMercado(unittest.TestCase):
    def test_cuotas_promedio(self):
        partido = {
            "home_team": "America", "away_team": "Toluca",
            "bookmakers": [
                _bookmaker("bet365", 1.8, 3.5, 4.5),
                _bookmaker("pinnacle", 2.0, 3.3, 4.1),
            ],
        }
        cuotas = pa.cuotas_promedio_1x2(partido)
        self.assertAlmostEqual(cuotas[0], 1.9, places=3)

    def test_ignora_fallback(self):
        partido = {
            "home_team": "America", "away_team": "Toluca",
            "bookmakers": [_bookmaker("fallback_local", 1.8, 3.4, 4.5)],
        }
        self.assertIsNone(pa.cuotas_promedio_1x2(partido))

    def test_probabilidades_mercado_suman_uno(self):
        probs = pa.probabilidades_mercado(_partido_con_mercado())
        self.assertAlmostEqual(sum(probs), 1.0, places=6)


class TestDegradacionSegura(unittest.TestCase):
    def test_modelo_mas_mercado(self):
        fuerzas = pa.calcular_fuerzas(_historico())
        r = pa.pronostico_partido(_partido_con_mercado(), fuerzas, peso_modelo=0.5)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["fuente"], "modelo+mercado")
        # Trae Over/Under y BTTS del modelo.
        self.assertIn("pick_ou", r)
        self.assertIn("pick_btts", r)

    def test_solo_mercado_sin_historico(self):
        r = pa.pronostico_partido(_partido_con_mercado(), None)
        self.assertEqual(r["fuente"], "solo_mercado")
        self.assertEqual(r["status"], "ok")

    def test_solo_modelo_sin_mercado(self):
        fuerzas = pa.calcular_fuerzas(_historico())
        partido = {"home_team": "America", "away_team": "Toluca", "bookmakers": []}
        r = pa.pronostico_partido(partido, fuerzas)
        self.assertEqual(r["fuente"], "solo_modelo")

    def test_sin_datos(self):
        partido = {"home_team": "Equipo Raro", "away_team": "Otro Raro", "bookmakers": []}
        r = pa.pronostico_partido(partido, None)
        self.assertEqual(r["status"], "sin_datos")

    def test_probabilidades_suman_cien(self):
        fuerzas = pa.calcular_fuerzas(_historico())
        r = pa.pronostico_partido(_partido_con_mercado(), fuerzas)
        total = r["prob_local_pct"] + r["prob_empate_pct"] + r["prob_visitante_pct"]
        self.assertAlmostEqual(total, 100.0, places=1)


class TestGenerarYRender(unittest.TestCase):
    def test_genera_varios(self):
        partidos = [
            _partido_con_mercado("America", "Toluca"),
            _partido_con_mercado("Atlas", "Toluca"),
        ]
        filas = pa.generar_pronosticos(partidos, _historico(), 0.5)
        self.assertEqual(len(filas), 2)

    def test_render_mantiene_esperar(self):
        filas = pa.generar_pronosticos([_partido_con_mercado()], _historico(), 0.5)
        reporte = pa.render_reporte(filas)
        self.assertIn("ESPERAR / NO ENVIAR", reporte)
        self.assertNotIn("CERRAR", reporte)
        self.assertIn("SURVIVOR", reporte)

    def test_no_perder_es_suma_local_empate(self):
        fuerzas = pa.calcular_fuerzas(_historico())
        r = pa.pronostico_partido(_partido_con_mercado(), fuerzas)
        esperado = round(r["prob_local_pct"] + r["prob_empate_pct"], 2)
        self.assertAlmostEqual(r["no_perder_local_pct"], esperado, places=1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
