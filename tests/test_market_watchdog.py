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


# ---------------------------------------------------------------------------
# v1.33.0 — Movimiento de momios
# ---------------------------------------------------------------------------
def snap(home, draw, away, partido="A vs B"):
    """Construye un snapshot de partido a partir de momios decimales."""
    prob = wd.odds_a_prob_implicita(home, draw, away)
    return {
        "partido": partido,
        "odds": {"home": home, "draw": draw, "away": away},
        "prob": prob,
        "favorito": wd.favorito_de_prob(prob),
    }


class TestProbabilidadImplicita(unittest.TestCase):
    def test_conversion_y_normalizacion(self):
        prob = wd.odds_a_prob_implicita(2.0, 4.0, 4.0)
        self.assertIsNotNone(prob)
        # 1/2 : 1/4 : 1/4 -> 50/25/25 tras normalizar (sin vig).
        self.assertAlmostEqual(prob["home"], 50.0, places=4)
        self.assertAlmostEqual(prob["draw"], 25.0, places=4)
        self.assertAlmostEqual(prob["away"], 25.0, places=4)

    def test_suma_100(self):
        prob = wd.odds_a_prob_implicita(1.91, 3.5, 4.2)
        self.assertAlmostEqual(sum(prob.values()), 100.0, places=4)

    def test_favorito_local(self):
        prob = wd.odds_a_prob_implicita(1.5, 4.0, 6.0)
        self.assertEqual(wd.favorito_de_prob(prob), "home")

    def test_momios_invalidos(self):
        self.assertIsNone(wd.odds_a_prob_implicita(0, 3.0, 3.0))
        self.assertIsNone(wd.odds_a_prob_implicita("x", 3.0, 3.0))


class TestClasificarMovimiento(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(wd.clasificar_movimiento(0.0), wd.MOV_NORMAL)
        self.assertEqual(wd.clasificar_movimiento(4.9), wd.MOV_NORMAL)

    def test_importante(self):
        self.assertEqual(wd.clasificar_movimiento(5.0), wd.MOV_IMPORTANTE)
        self.assertEqual(wd.clasificar_movimiento(7.99), wd.MOV_IMPORTANTE)

    def test_drastico(self):
        self.assertEqual(wd.clasificar_movimiento(8.0), wd.MOV_DRASTICO)
        self.assertEqual(wd.clasificar_movimiento(15.0), wd.MOV_DRASTICO)


class TestExtraer1x2(unittest.TestCase):
    def test_extrae_y_promedia(self):
        bookmakers = [
            {"key": "a", "markets": [{"key": "h2h", "outcomes": [
                {"name": "America", "price": 2.0},
                {"name": "Draw", "price": 3.0},
                {"name": "Juarez", "price": 4.0},
            ]}]},
            {"key": "b", "markets": [{"key": "h2h", "outcomes": [
                {"name": "America", "price": 2.2},
                {"name": "Draw", "price": 3.2},
                {"name": "Juarez", "price": 4.4},
            ]}]},
        ]
        odds = wd.extraer_1x2_de_bookmakers(bookmakers, "America", "Juarez")
        self.assertIsNotNone(odds)
        self.assertAlmostEqual(odds["home"], 2.1, places=4)
        self.assertAlmostEqual(odds["draw"], 3.1, places=4)
        self.assertAlmostEqual(odds["away"], 4.2, places=4)

    def test_sin_mercado_completo(self):
        bookmakers = [{"key": "a", "markets": [{"key": "h2h", "outcomes": [
            {"name": "America", "price": 2.0},
            {"name": "Draw", "price": 3.0},
        ]}]}]
        self.assertIsNone(wd.extraer_1x2_de_bookmakers(bookmakers, "America", "Juarez"))


class TestFavoritoFlip(unittest.TestCase):
    def test_flip_local_a_visitante(self):
        base = snap(1.6, 4.0, 5.5)   # favorito home
        cur = snap(5.5, 4.0, 1.6)    # favorito away
        mov = wd.evaluar_movimiento_partido(base, cur)
        self.assertTrue(mov["favorito_flip"])
        self.assertEqual(mov["favorito_prev"], "home")
        self.assertEqual(mov["favorito_cur"], "away")

    def test_sin_flip(self):
        base = snap(1.8, 3.5, 4.5)
        cur = snap(1.85, 3.5, 4.3)
        mov = wd.evaluar_movimiento_partido(base, cur)
        self.assertFalse(mov["favorito_flip"])


class TestDecidirAlertaMovimiento(unittest.TestCase):
    def test_menos_de_5_no_telegram(self):
        base = snap(2.0, 3.4, 3.8)
        cur = snap(2.05, 3.4, 3.7)  # movimiento pequeño
        mov = wd.evaluar_movimiento_partido(base, cur)
        self.assertEqual(mov["clasificacion"], wd.MOV_NORMAL)
        enviar, tipo = wd.decidir_alerta_movimiento(mov, None)
        self.assertFalse(enviar)
        self.assertIsNone(tipo)

    def test_8_o_mas_dispara_telegram(self):
        base = snap(2.5, 3.3, 2.8)
        cur = snap(1.6, 3.6, 6.0)  # gran salto de probabilidad
        mov = wd.evaluar_movimiento_partido(base, cur)
        self.assertGreaterEqual(mov["max_delta_pts"], 8.0)
        enviar, tipo = wd.decidir_alerta_movimiento(mov, None)
        self.assertTrue(enviar)

    def test_flip_es_alerta_fuerte(self):
        base = snap(1.6, 4.0, 5.5)
        cur = snap(5.5, 4.0, 1.6)
        mov = wd.evaluar_movimiento_partido(base, cur)
        enviar, tipo = wd.decidir_alerta_movimiento(mov, None)
        self.assertTrue(enviar)
        self.assertEqual(tipo, "FLIP")

    def test_duplicado_no_reenvia(self):
        mov = {
            "clasificacion": wd.MOV_DRASTICO,
            "max_delta_pts": 10.0,
            "favorito_prev": "home",
            "favorito_cur": "home",
            "favorito_flip": False,
        }
        prev_alerta = {"clasificacion": wd.MOV_DRASTICO, "max_delta_pts": 10.0, "favorito_cur": "home"}
        enviar, tipo = wd.decidir_alerta_movimiento(mov, prev_alerta)
        self.assertFalse(enviar)  # mismo movimiento -> sin duplicado

    def test_duplicado_reenvia_si_empeora(self):
        mov = {
            "clasificacion": wd.MOV_DRASTICO,
            "max_delta_pts": 14.0,  # empeoró >= 3 pts
            "favorito_prev": "home",
            "favorito_cur": "home",
            "favorito_flip": False,
        }
        prev_alerta = {"clasificacion": wd.MOV_DRASTICO, "max_delta_pts": 10.0, "favorito_cur": "home"}
        enviar, tipo = wd.decidir_alerta_movimiento(mov, prev_alerta)
        self.assertTrue(enviar)

    def test_importante_opcional(self):
        base = snap(2.0, 3.4, 3.8)
        cur = snap(1.75, 3.5, 4.4)  # ~5-8 pts
        mov = wd.evaluar_movimiento_partido(base, cur)
        self.assertEqual(mov["clasificacion"], wd.MOV_IMPORTANTE)
        # Por defecto, IMPORTANTE no envía Telegram.
        enviar_def, _ = wd.decidir_alerta_movimiento(mov, None, incluir_importante=False)
        self.assertFalse(enviar_def)
        # Con opt-in, sí.
        enviar_opt, _ = wd.decidir_alerta_movimiento(mov, None, incluir_importante=True)
        self.assertTrue(enviar_opt)


class TestEvaluarMovimientos(unittest.TestCase):
    def test_primer_snapshot_sin_movimiento(self):
        cur = {"a|b": snap(2.0, 3.3, 3.6, "A vs B")}
        baseline, alertas, movimientos = wd.evaluar_movimientos({}, {}, cur)
        self.assertEqual(movimientos, [])
        self.assertIn("a|b", baseline)

    def test_segunda_corrida_drastica_alerta(self):
        base = {"a|b": snap(2.5, 3.3, 2.8, "A vs B")}
        cur = {"a|b": snap(1.6, 3.6, 6.0, "A vs B")}
        baseline, alertas, movimientos = wd.evaluar_movimientos(base, {}, cur)
        self.assertEqual(len(movimientos), 1)
        self.assertTrue(movimientos[0]["telegram"])
        self.assertIn("a|b", alertas)


class TestMensajeMovimiento(unittest.TestCase):
    def test_mensaje_usa_auditar_no_cerrar(self):
        movs = [{
            "partido": "America vs Juarez",
            "clasificacion": wd.MOV_DRASTICO,
            "max_delta_pts": 12.0,
            "favorito_prev": "home",
            "favorito_cur": "away",
            "favorito_flip": True,
        }]
        msg = wd.construir_mensaje_movimiento(movs, hay_flip=True)
        self.assertIn(wd.OP_AUDITAR, msg)
        self.assertIn("AUDITAR", msg)
        self.assertNotIn("CERRAR\n", msg)
        self.assertNotIn("Etiqueta operativa: CERRAR", msg)


# ---------------------------------------------------------------------------
# v1.34.0 — Multi-mercado (totals, BTTS, hándicap, Draw No Bet)
# ---------------------------------------------------------------------------
def book_h2h(home="America", away="Juarez", h=2.0, d=3.2, a=3.8):
    return {"key": "book", "markets": [{"key": "h2h", "outcomes": [
        {"name": home, "price": h}, {"name": "Draw", "price": d}, {"name": away, "price": a},
    ]}]}


def market_totals(point=2.5, over=1.9, under=1.95):
    return {"key": "totals", "outcomes": [
        {"name": "Over", "price": over, "point": point},
        {"name": "Under", "price": under, "point": point},
    ]}


def market_btts(yes=1.8, no=2.0):
    return {"key": "btts", "outcomes": [
        {"name": "Yes", "price": yes}, {"name": "No", "price": no},
    ]}


def market_spreads(home="America", away="Juarez", hp=-0.5, h=1.9, a=1.95):
    return {"key": "spreads", "outcomes": [
        {"name": home, "price": h, "point": hp},
        {"name": away, "price": a, "point": -hp},
    ]}


def market_dnb(home="America", away="Juarez", h=1.5, a=2.5):
    return {"key": "draw_no_bet", "outcomes": [
        {"name": home, "price": h}, {"name": away, "price": a},
    ]}


def book_full():
    return {"key": "book", "markets": [
        book_h2h()["markets"][0],
        market_totals(),
        market_btts(),
        market_spreads(),
        market_dnb(),
    ]}


def snap_two(mercado, side_key1, side_key2, o1, o2, **extra):
    """Construye un snapshot de un mercado de 2 vías para tests de movimiento."""
    pr = wd.prob_dos_vias(o1, o2)
    prob = {side_key1: round(pr[0], 2), side_key2: round(pr[1], 2)}
    campo = wd.CAMPO_LADO.get(mercado, "favorito")
    snap = {"odds": {side_key1: o1, side_key2: o2}, "prob": prob, campo: wd.favorito_de_prob(prob)}
    snap.update(extra)
    return snap


class TestExtraccionOpcionales(unittest.TestCase):
    def test_totals_presente(self):
        t = wd.extraer_totals_de_bookmakers([book_full()], linea=2.5)
        self.assertIsNotNone(t)
        self.assertEqual(t["point"], 2.5)
        self.assertIn("over", t["odds"])
        self.assertIn("under", t["odds"])

    def test_totals_ausente(self):
        self.assertIsNone(wd.extraer_totals_de_bookmakers([book_h2h()]))

    def test_btts_presente_y_ausente(self):
        self.assertIsNotNone(wd.extraer_btts_de_bookmakers([book_full()]))
        self.assertIsNone(wd.extraer_btts_de_bookmakers([book_h2h()]))

    def test_spread_presente_y_ausente(self):
        sp = wd.extraer_spread_de_bookmakers([book_full()], "America", "Juarez")
        self.assertIsNotNone(sp)
        self.assertAlmostEqual(sp["point"], -0.5, places=4)
        self.assertIsNone(wd.extraer_spread_de_bookmakers([book_h2h()], "America", "Juarez"))

    def test_dnb_presente_y_ausente(self):
        dnb = wd.extraer_dnb_de_bookmakers([book_full()], "America", "Juarez")
        self.assertIsNotNone(dnb)
        self.assertIn("home", dnb["odds"])
        self.assertIsNone(wd.extraer_dnb_de_bookmakers([book_h2h()], "America", "Juarez"))


class TestSnapshotMulti(unittest.TestCase):
    def test_todos_los_mercados(self):
        sp = wd.snapshot_partido_multi("America", "Juarez", [book_full()])
        self.assertIsNotNone(sp)
        for mk in ("1x2", "totals", "btts", "spreads", "dnb"):
            self.assertIn(mk, sp["mercados"])

    def test_solo_1x2_resto_no_disponible(self):
        sp = wd.snapshot_partido_multi("America", "Juarez", [book_h2h()])
        self.assertIn("1x2", sp["mercados"])
        for mk in wd.MERCADOS_OPCIONALES:
            self.assertNotIn(mk, sp["mercados"])
        # Resumen marca opcionales en 0 (mercado no disponible).
        snap = {"america|juarez": sp}
        resumen = wd.resumen_disponibilidad_mercados(snap)
        self.assertEqual(resumen["totals"], 0)
        self.assertEqual(resumen["btts"], 0)
        self.assertEqual(resumen["dnb"], 0)


class TestMovimientoTotals(unittest.TestCase):
    def test_menos_de_5_no_telegram(self):
        base = snap_two("totals", "over", "under", 1.90, 1.95, point=2.5)
        cur = snap_two("totals", "over", "under", 1.92, 1.93, point=2.5)
        mov = wd.evaluar_movimiento_mercado("totals", base, cur)
        self.assertEqual(mov["clasificacion"], wd.MOV_NORMAL)
        enviar, _ = wd.decidir_alerta_mercado(mov, None)
        self.assertFalse(enviar)

    def test_8_o_mas_dispara_telegram(self):
        base = snap_two("totals", "over", "under", 2.40, 1.60, point=2.5)
        cur = snap_two("totals", "over", "under", 1.60, 2.40, point=2.5)
        mov = wd.evaluar_movimiento_mercado("totals", base, cur)
        self.assertGreaterEqual(mov["max_delta_pts"], 8.0)
        # Side flip over<->under => CRITICO.
        self.assertTrue(mov["flip"])
        self.assertEqual(mov["clasificacion"], wd.MOV_CRITICO)
        enviar, tipo = wd.decidir_alerta_mercado(mov, None)
        self.assertTrue(enviar)

    def test_flip_lado_es_critico(self):
        base = snap_two("totals", "over", "under", 1.70, 2.20, point=2.5)  # lado over
        cur = snap_two("totals", "over", "under", 2.20, 1.70, point=2.5)   # lado under
        mov = wd.evaluar_movimiento_mercado("totals", base, cur)
        self.assertTrue(mov["flip"])
        self.assertEqual(mov["clasificacion"], wd.MOV_CRITICO)


class TestMovimientoBTTS(unittest.TestCase):
    def test_side_flip_critico(self):
        base = snap_two("btts", "yes", "no", 1.70, 2.20)  # lado yes
        cur = snap_two("btts", "yes", "no", 2.20, 1.70)   # lado no
        mov = wd.evaluar_movimiento_mercado("btts", base, cur)
        self.assertTrue(mov["flip"])
        self.assertEqual(mov["clasificacion"], wd.MOV_CRITICO)
        enviar, tipo = wd.decidir_alerta_mercado(mov, None)
        self.assertTrue(enviar)
        self.assertEqual(tipo, wd.MOV_CRITICO)

    def test_movimiento_pequeno_normal(self):
        base = snap_two("btts", "yes", "no", 1.90, 1.95)
        cur = snap_two("btts", "yes", "no", 1.92, 1.93)
        mov = wd.evaluar_movimiento_mercado("btts", base, cur)
        self.assertEqual(mov["clasificacion"], wd.MOV_NORMAL)


class TestMovimientoHandicap(unittest.TestCase):
    def test_movimiento_mayor_de_linea_critico(self):
        base = snap_two("spreads", "home", "away", 1.90, 1.95, point=-0.5)
        cur = snap_two("spreads", "home", "away", 1.90, 1.95, point=-1.0)
        mov = wd.evaluar_movimiento_mercado("spreads", base, cur)
        self.assertEqual(mov["clasificacion"], wd.MOV_CRITICO)
        self.assertAlmostEqual(mov["linea_move"], 0.5, places=4)
        enviar, _ = wd.decidir_alerta_mercado(mov, None)
        self.assertTrue(enviar)

    def test_linea_estable_precio_pequeno_normal(self):
        base = snap_two("spreads", "home", "away", 1.90, 1.95, point=-0.5)
        cur = snap_two("spreads", "home", "away", 1.92, 1.93, point=-0.5)
        mov = wd.evaluar_movimiento_mercado("spreads", base, cur)
        self.assertEqual(mov["clasificacion"], wd.MOV_NORMAL)
        enviar, _ = wd.decidir_alerta_mercado(mov, None)
        self.assertFalse(enviar)


class TestMovimientoDNB(unittest.TestCase):
    def test_dnb_side_flip_critico(self):
        base = snap_two("dnb", "home", "away", 1.50, 2.50)  # favorito home
        cur = snap_two("dnb", "home", "away", 2.50, 1.50)   # favorito away
        mov = wd.evaluar_movimiento_mercado("dnb", base, cur)
        self.assertTrue(mov["flip"])
        self.assertEqual(mov["clasificacion"], wd.MOV_CRITICO)
        enviar, tipo = wd.decidir_alerta_mercado(mov, None)
        self.assertTrue(enviar)
        self.assertEqual(tipo, wd.MOV_CRITICO)

    def test_dnb_drastico_por_precio(self):
        base = snap_two("dnb", "home", "away", 2.10, 1.75)
        cur = snap_two("dnb", "home", "away", 1.55, 2.55)
        mov = wd.evaluar_movimiento_mercado("dnb", base, cur)
        # Hay flip de favorito -> CRITICO (y delta grande).
        self.assertGreaterEqual(mov["max_delta_pts"], 8.0)

    def test_dnb_pequeno_normal(self):
        base = snap_two("dnb", "home", "away", 1.80, 2.00)
        cur = snap_two("dnb", "home", "away", 1.82, 1.98)
        mov = wd.evaluar_movimiento_mercado("dnb", base, cur)
        self.assertEqual(mov["clasificacion"], wd.MOV_NORMAL)


class TestDecidirAlertaMercadoDuplicado(unittest.TestCase):
    def test_critico_primero_envia(self):
        mov = {"clasificacion": wd.MOV_CRITICO, "max_delta_pts": 12.0, "flip": True,
               "lado_cur": "away", "linea_cur": None}
        enviar, tipo = wd.decidir_alerta_mercado(mov, None)
        self.assertTrue(enviar)
        self.assertEqual(tipo, wd.MOV_CRITICO)

    def test_duplicado_no_reenvia(self):
        mov = {"clasificacion": wd.MOV_DRASTICO, "max_delta_pts": 10.0, "flip": False,
               "lado_cur": "over", "linea_cur": None}
        prev = {"clasificacion": wd.MOV_DRASTICO, "max_delta_pts": 10.0, "lado_cur": "over", "linea_cur": None}
        enviar, _ = wd.decidir_alerta_mercado(mov, prev)
        self.assertFalse(enviar)

    def test_reenvia_si_empeora(self):
        mov = {"clasificacion": wd.MOV_DRASTICO, "max_delta_pts": 14.0, "flip": False,
               "lado_cur": "over", "linea_cur": None}
        prev = {"clasificacion": wd.MOV_DRASTICO, "max_delta_pts": 10.0, "lado_cur": "over", "linea_cur": None}
        enviar, _ = wd.decidir_alerta_mercado(mov, prev)
        self.assertTrue(enviar)

    def test_reenvia_si_escala_severidad(self):
        mov = {"clasificacion": wd.MOV_CRITICO, "max_delta_pts": 9.0, "flip": False,
               "lado_cur": "home", "linea_cur": -1.0}
        prev = {"clasificacion": wd.MOV_DRASTICO, "max_delta_pts": 9.0, "lado_cur": "home", "linea_cur": -0.5}
        enviar, _ = wd.decidir_alerta_mercado(mov, prev)
        self.assertTrue(enviar)

    def test_importante_opcional(self):
        mov = {"clasificacion": wd.MOV_IMPORTANTE, "max_delta_pts": 6.0, "flip": False,
               "lado_cur": "over", "linea_cur": None}
        self.assertFalse(wd.decidir_alerta_mercado(mov, None, incluir_importante=False)[0])
        self.assertTrue(wd.decidir_alerta_mercado(mov, None, incluir_importante=True)[0])


class TestEvaluarMovimientosMulti(unittest.TestCase):
    def _snap_partido(self, totals_over, totals_under):
        return {"partido": "America vs Juarez", "mercados": {
            "1x2": {"odds": {"home": 2.0, "draw": 3.2, "away": 3.8},
                    "prob": wd.odds_a_prob_implicita(2.0, 3.2, 3.8),
                    "favorito": wd.favorito_de_prob(wd.odds_a_prob_implicita(2.0, 3.2, 3.8))},
            "totals": snap_two("totals", "over", "under", totals_over, totals_under, point=2.5),
        }}

    def test_primer_snapshot_sin_movimiento(self):
        cur = {"k": self._snap_partido(1.9, 1.95)}
        baseline, alertas, movs = wd.evaluar_movimientos_multi({}, {}, cur)
        self.assertEqual(movs, [])
        self.assertIn("k", baseline)

    def test_segunda_corrida_flip_totals_alerta(self):
        base = {"k": self._snap_partido(1.70, 2.30)}  # lado over
        cur = {"k": self._snap_partido(2.30, 1.70)}   # lado under -> flip CRITICO
        baseline, alertas, movs = wd.evaluar_movimientos_multi(base, {}, cur)
        totals_mov = [m for m in movs if m["mercado"] == "totals"]
        self.assertEqual(len(totals_mov), 1)
        self.assertTrue(totals_mov[0]["telegram"])
        self.assertEqual(totals_mov[0]["clasificacion"], wd.MOV_CRITICO)
        self.assertIn("totals", alertas["k"])


class TestMensajeMulti(unittest.TestCase):
    def test_usa_auditar_no_cerrar(self):
        movs = [
            {"partido": "America vs Juarez", "mercado": "totals", "clasificacion": wd.MOV_CRITICO,
             "max_delta_pts": 15.0, "flip": True, "lado_prev": "over", "lado_cur": "under",
             "linea_prev": 2.5, "linea_cur": 2.5, "linea_move": 0.0},
            {"partido": "America vs Juarez", "mercado": "spreads", "clasificacion": wd.MOV_CRITICO,
             "max_delta_pts": 2.0, "flip": False, "lado_prev": "home", "lado_cur": "home",
             "linea_prev": -0.5, "linea_cur": -1.0, "linea_move": 0.5},
        ]
        msg = wd.construir_mensaje_multi(movs)
        self.assertIn(wd.OP_AUDITAR, msg)
        self.assertIn("AUDITAR", msg)
        self.assertNotIn("Etiqueta operativa: CERRAR", msg)
        # Menciona el rol de cada mercado.
        self.assertIn("primario", msg)


class TestCeroNueveSinCambios(unittest.TestCase):
    def test_0_9_no_evalua_ni_alerta(self):
        partidos = [partido_fallback() for _ in range(9)]
        disponibles, total = wd.contar_mercado_local(partidos)
        self.assertEqual((disponibles, total), (0, 9))
        self.assertEqual(wd.clasificar_disponibilidad(disponibles, total), wd.ST_NINGUNO)
        self.assertEqual(wd.etiqueta_operativa(wd.ST_NINGUNO), wd.OP_NO_ENVIAR)
        # Sin cambio de disponibilidad -> sin alerta.
        self.assertIsNone(wd.decidir_alerta(0, wd.ST_NINGUNO, 0, wd.ST_NINGUNO))


if __name__ == "__main__":
    unittest.main(verbosity=2)
