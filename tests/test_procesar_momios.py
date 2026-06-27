#!/usr/bin/env python3
"""
Tests para scripts/procesar_momios.py.

Verifican: promedio entre casas reales, exclusión del fallback técnico,
cálculo de margen/probabilidades y exportación a CSV. No tocan red ni disco
real (salvo un CSV temporal).
"""
from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT / "scripts"), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

import procesar_momios as pm  # noqa: E402


def _bookmaker(key, local, empate, visita, local_name="America", visita_name="Toluca"):
    return {
        "key": key,
        "title": key,
        "markets": [
            {"key": "h2h", "outcomes": [
                {"name": local_name, "price": local},
                {"name": "Draw", "price": empate},
                {"name": visita_name, "price": visita},
            ]}
        ],
    }


class TestAnalizarPartido(unittest.TestCase):
    def test_promedia_casas_reales(self):
        partido = {
            "home_team": "America", "away_team": "Toluca",
            "fecha": "2026-07-16", "hora": "19:00",
            "bookmakers": [
                _bookmaker("bet365", 2.0, 3.0, 4.0),
                _bookmaker("pinnacle", 2.2, 3.0, 3.6),
            ],
        }
        r = pm.analizar_partido(partido)
        self.assertIsNotNone(r)
        self.assertEqual(r["casas_contadas"], 2)
        self.assertAlmostEqual(r["cuota_local"], 2.1, places=3)      # (2.0+2.2)/2
        self.assertAlmostEqual(r["cuota_visitante"], 3.8, places=3)  # (4.0+3.6)/2

    def test_ignora_fallback(self):
        partido = {
            "home_team": "America", "away_team": "Toluca",
            "bookmakers": [
                _bookmaker("bet365", 2.0, 3.0, 4.0),
                _bookmaker("fallback_local", 1.8, 3.4, 4.5),
            ],
        }
        r = pm.analizar_partido(partido)
        self.assertEqual(r["casas_contadas"], 1)  # solo bet365
        self.assertAlmostEqual(r["cuota_local"], 2.0, places=3)

    def test_solo_fallback_devuelve_none(self):
        partido = {
            "home_team": "America", "away_team": "Toluca",
            "bookmakers": [_bookmaker("fallback_local", 1.8, 3.4, 4.5)],
        }
        self.assertIsNone(pm.analizar_partido(partido))

    def test_sin_bookmakers_devuelve_none(self):
        self.assertIsNone(pm.analizar_partido({"home_team": "A", "away_team": "B"}))

    def test_margen_y_probabilidades(self):
        partido = {
            "home_team": "America", "away_team": "Toluca",
            "bookmakers": [_bookmaker("bet365", 2.0, 3.0, 4.0)],
        }
        r = pm.analizar_partido(partido)
        self.assertAlmostEqual(r["margen_casa_pct"], 8.33, places=2)
        total = r["prob_local_pct"] + r["prob_empate_pct"] + r["prob_visitante_pct"]
        self.assertAlmostEqual(total, 100.0, places=1)


class TestExportarCSV(unittest.TestCase):
    def test_csv_tiene_header_y_filas(self):
        partidos = [{
            "home_team": "America", "away_team": "Toluca",
            "fecha": "2026-07-16", "hora": "19:00",
            "bookmakers": [_bookmaker("bet365", 2.0, 3.0, 4.0)],
        }]
        filas = pm.analizar_jornada(partidos)
        with tempfile.TemporaryDirectory() as d:
            csv_path = Path(d) / "out.csv"
            pm.exportar_csv(filas, csv_path)
            with csv_path.open(encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["local"], "America")
        self.assertIn("margen_casa_pct", rows[0])


class TestResumenSeguro(unittest.TestCase):
    def test_resumen_mantiene_esperar(self):
        out = pm.render_resumen([], 9)
        self.assertIn("ESPERAR / NO ENVIAR", out)
        self.assertNotIn("CERRAR", out)

    def test_resumen_sin_mercado(self):
        out = pm.render_resumen([], 9)
        self.assertIn("Sin mercado real", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
