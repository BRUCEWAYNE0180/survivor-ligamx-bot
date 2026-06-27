#!/usr/bin/env python3
"""Tests unitarios para src/odds_math.py (matemática pura de momios)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = str(Path(__file__).resolve().parents[1] / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import odds_math as om  # noqa: E402


class TestAmericanoADecimal(unittest.TestCase):
    def test_positivo(self):
        self.assertAlmostEqual(om.americano_a_decimal(150), 2.5)

    def test_negativo(self):
        self.assertAlmostEqual(om.americano_a_decimal(-200), 1.5)

    def test_cero_invalido(self):
        with self.assertRaises(ValueError):
            om.americano_a_decimal(0)


class TestDecimalAProbabilidad(unittest.TestCase):
    def test_basico(self):
        self.assertAlmostEqual(om.decimal_a_probabilidad(2.0), 0.5)
        self.assertAlmostEqual(om.decimal_a_probabilidad(4.0), 0.25)

    def test_cuota_invalida(self):
        with self.assertRaises(ValueError):
            om.decimal_a_probabilidad(1.0)
        with self.assertRaises(ValueError):
            om.decimal_a_probabilidad(0.5)


class TestMargenCasa(unittest.TestCase):
    def test_overround_conocido(self):
        # [2.0, 3.0, 4.0] -> 0.5+0.3333+0.25 = 1.0833 -> margen 0.0833.
        self.assertAlmostEqual(om.margen_casa([2.0, 3.0, 4.0]), 0.083333, places=4)

    def test_margen_pct(self):
        self.assertAlmostEqual(om.margen_casa_pct([2.0, 3.0, 4.0]), 8.33)

    def test_mercado_justo_margen_cero(self):
        # Cuotas justas para 50/50: 2.0 y 2.0 -> margen 0.
        self.assertAlmostEqual(om.margen_casa([2.0, 2.0]), 0.0, places=6)

    def test_vacio_invalido(self):
        with self.assertRaises(ValueError):
            om.margen_casa([])

    def test_margen_positivo_con_vig(self):
        # Un mercado real siempre tiene margen > 0.
        self.assertGreater(om.margen_casa([1.8, 3.4, 4.5]), 0.0)


class TestProbabilidadesSinVig(unittest.TestCase):
    def test_suman_uno(self):
        probs = om.probabilidades_sin_vig([2.0, 3.0, 4.0])
        self.assertAlmostEqual(sum(probs), 1.0, places=9)

    def test_valores_normalizados(self):
        probs = om.probabilidades_sin_vig([2.0, 3.0, 4.0])
        self.assertAlmostEqual(probs[0], 0.4615, places=3)
        self.assertAlmostEqual(probs[1], 0.3077, places=3)
        self.assertAlmostEqual(probs[2], 0.2308, places=3)

    def test_favorito_mayor_probabilidad(self):
        # Cuota más baja => mayor probabilidad sin vig.
        probs = om.probabilidades_sin_vig([1.5, 4.0, 6.0])
        self.assertEqual(max(range(len(probs)), key=lambda i: probs[i]), 0)

    def test_implicitas_mayores_que_sin_vig(self):
        # Con vig, las implícitas suman > 1; sin vig suman 1.
        cuotas = [2.0, 3.0, 4.0]
        impl = om.probabilidades_implicitas(cuotas)
        self.assertGreater(sum(impl), 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
