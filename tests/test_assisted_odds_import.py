#!/usr/bin/env python3
"""
Tests para src/assisted_odds_import.py y el CLI scripts/assisted_caliente_odds.py.

Lógica pura: NO abre navegador, NO usa red, NO requiere Playwright.

Ejecutar:
    python3 -m unittest tests.test_assisted_odds_import
o:
    python3 tests/test_assisted_odds_import.py
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

import assisted_odds_import as aoi  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures de texto visible (estilo Caliente Liga MX)
# ---------------------------------------------------------------------------
# 9 partidos Liga MX con momios americanos 1X2, con ruido de menú alrededor
# (encabezados que NO deben producir falsos positivos).
TEXTO_CALIENTE_9 = """\
Apuestas Fútbol México  Liga MX  Hoy  Mañana  Más ligas
Local   Empate   Visitante
21:05 16 Jul América -160 Empate +320 Atlas +420
19:00 16 Jul Necaxa -125 Empate +260 Atlante +275
17:00 17 Jul Cruz Azul -140 Empate +280 Pumas UNAM +360
19:00 17 Jul Chivas +110 Empate +240 Tigres UANL +210
21:00 17 Jul Monterrey -170 Empate +330 Mazatlán +440
12:00 18 Jul Toluca -150 Empate +290 Querétaro +390
17:00 18 Jul León -115 Empate +250 Juárez +300
19:00 18 Jul Pachuca -130 Empate +270 Santos +330
21:00 18 Jul Tijuana +105 Empate +245 Puebla +215
Ver más mercados  Reglas de la casa
"""

# Mismo contenido pero TODO en una sola línea gigante (simula un DOM que se
# aplana en un solo bloque de texto). El parser NO debe mezclar partidos.
TEXTO_BLOQUE_GIGANTE = (
    "Liga MX Apuestas "
    "19:00 16 Jul Necaxa -125 Empate +260 Atlante +275 "
    "21:05 16 Jul América -160 Empate +320 Atlas +420 "
    "fin de la lista"
)


class TestMomioAmericano(unittest.TestCase):
    def test_validos(self):
        for m in ("+120", "-125", "+260", "-160", "+100", "-100", "+275"):
            self.assertTrue(aoi.es_momio_americano_valido(m), m)

    def test_invalidos(self):
        # Sin signo, magnitud < 100, un dígito, texto, vacío, None.
        for m in ("125", "+99", "-50", "+5", "abc", "", None, "+", "1.5"):
            self.assertFalse(aoi.es_momio_americano_valido(m), repr(m))


class TestParser9Partidos(unittest.TestCase):
    def test_detecta_nueve(self):
        res = aoi.analizar_texto(TEXTO_CALIENTE_9, esperados=9)
        self.assertEqual(res["status"], aoi.STATUS_OK)
        self.assertEqual(res["total_validos"], 9)
        self.assertTrue(res["coincide_esperados"])
        self.assertEqual(res["duplicados_removidos"], 0)
        self.assertEqual(len(res["invalidos"]), 0)

    def test_campos_extraidos(self):
        res = aoi.analizar_texto(TEXTO_CALIENTE_9, esperados=9)
        # El evento del ejemplo del usuario debe quedar perfectamente parseado.
        necaxa = next(
            e for e in res["eventos"] if e["equipo_local"] == "Necaxa"
        )
        self.assertEqual(necaxa["hora"], "19:00")
        self.assertEqual(necaxa["fecha"], "16 Jul")
        self.assertEqual(necaxa["equipo_visitante"], "Atlante")
        self.assertEqual(necaxa["momio_local"], "-125")
        self.assertEqual(necaxa["momio_empate"], "+260")
        self.assertEqual(necaxa["momio_visitante"], "+275")

    def test_equipos_multipalabra(self):
        res = aoi.analizar_texto(TEXTO_CALIENTE_9, esperados=9)
        cruz = next(e for e in res["eventos"] if e["equipo_local"] == "Cruz Azul")
        self.assertEqual(cruz["equipo_visitante"], "Pumas UNAM")


class TestNoMezclaBloqueGigante(unittest.TestCase):
    def test_no_mezcla_pares(self):
        res = aoi.analizar_texto(TEXTO_BLOQUE_GIGANTE, esperados=2)
        self.assertEqual(res["total_validos"], 2)

        pares = {
            (e["equipo_local"], e["equipo_visitante"]) for e in res["eventos"]
        }
        # Los pares correctos deben mantenerse intactos.
        self.assertIn(("Necaxa", "Atlante"), pares)
        self.assertIn(("América", "Atlas"), pares)
        # Y NO debe existir ninguna combinación cruzada.
        self.assertNotIn(("Necaxa", "Atlas"), pares)
        self.assertNotIn(("América", "Atlante"), pares)

    def test_no_se_traga_otro_partido_en_visitante(self):
        res = aoi.analizar_texto(TEXTO_BLOQUE_GIGANTE, esperados=2)
        for e in res["eventos"]:
            # Ningún nombre de equipo debe contener un token de hora de otro
            # partido ni un signo de momio.
            self.assertNotRegex(e["equipo_local"], r"\d{1,2}:\d{2}")
            self.assertNotRegex(e["equipo_visitante"], r"\d{1,2}:\d{2}")
            self.assertNotIn("+", e["equipo_visitante"])
            self.assertNotIn("-", e["equipo_visitante"])


class TestMomioInvalido(unittest.TestCase):
    def test_evento_con_momio_invalido_se_descarta(self):
        # +50 tiene magnitud < 100 => momio inválido => evento descartado.
        texto = "19:00 16 Jul Necaxa +50 Empate +260 Atlante +275"
        res = aoi.analizar_texto(texto, esperados=1)
        self.assertEqual(res["total_validos"], 0)
        self.assertEqual(len(res["invalidos"]), 1)
        self.assertEqual(res["status"], aoi.STATUS_NO_MATCHES)

    def test_evento_valido_convive_con_invalido(self):
        texto = (
            "19:00 16 Jul Necaxa +50 Empate +260 Atlante +275\n"
            "21:05 16 Jul América -160 Empate +320 Atlas +420\n"
        )
        res = aoi.analizar_texto(texto, esperados=1)
        self.assertEqual(res["total_validos"], 1)
        self.assertEqual(len(res["invalidos"]), 1)
        self.assertEqual(res["eventos"][0]["equipo_local"], "América")


class TestDuplicados(unittest.TestCase):
    def test_partido_duplicado_se_deduplica(self):
        texto = (
            "19:00 16 Jul Necaxa -125 Empate +260 Atlante +275\n"
            "19:00 16 Jul Necaxa -125 Empate +260 Atlante +275\n"
        )
        res = aoi.analizar_texto(texto, esperados=1)
        self.assertEqual(res["total_validos"], 1)
        self.assertEqual(res["duplicados_removidos"], 1)

    def test_dedup_ignora_acentos_y_mayusculas(self):
        # "América" y "America" deben tratarse como el mismo equipo.
        texto = (
            "21:05 16 Jul América -160 Empate +320 Atlas +420\n"
            "21:05 16 Jul America -160 Empate +320 ATLAS +420\n"
        )
        res = aoi.analizar_texto(texto, esperados=1)
        self.assertEqual(res["total_validos"], 1)
        self.assertEqual(res["duplicados_removidos"], 1)


class TestNoMatchesFound(unittest.TestCase):
    def test_texto_sin_eventos(self):
        res = aoi.analizar_texto("Bienvenido a la página. No hay momios visibles.")
        self.assertEqual(res["status"], aoi.STATUS_NO_MATCHES)
        self.assertEqual(res["total_validos"], 0)

    def test_texto_vacio(self):
        res = aoi.analizar_texto("")
        self.assertEqual(res["status"], aoi.STATUS_NO_MATCHES)


class TestReporte(unittest.TestCase):
    def test_reporte_mantiene_esperar_no_enviar(self):
        res = aoi.analizar_texto(TEXTO_CALIENTE_9, esperados=9)
        reporte = aoi.render_report(res, url=aoi.FUENTE)
        self.assertIn("ESPERAR / NO ENVIAR", reporte)
        self.assertIn("No marcar pick listo", reporte)
        # Nunca debe autorizar cierre operativo.
        self.assertNotIn("CERRAR", reporte)

    def test_reporte_sin_secretos(self):
        res = aoi.analizar_texto(TEXTO_CALIENTE_9, esperados=9)
        url_con_secreto = (
            "https://sports.caliente.mx/es_MX/Apuestas-Futbol-Mexico"
            "?apikey=SUPERSECRETO123&token=BEARER_XYZ"
        )
        reporte = aoi.render_report(res, url=url_con_secreto)
        # Solo el host debe aparecer; nunca la query con la llave/token.
        self.assertIn("sports.caliente.mx", reporte)
        self.assertNotIn("SUPERSECRETO123", reporte)
        self.assertNotIn("BEARER_XYZ", reporte)
        self.assertNotIn("apikey", reporte)
        for marcador in ("API_KEY", "password", "Bearer ", "Authorization"):
            self.assertNotIn(marcador, reporte)

    def test_reporte_no_matches(self):
        res = aoi.analizar_texto("sin nada util")
        reporte = aoi.render_report(res)
        self.assertIn("NO_MATCHES_FOUND", reporte)
        self.assertIn("ESPERAR / NO ENVIAR", reporte)


class TestExportJSON(unittest.TestCase):
    def test_payload_no_marca_pick_listo(self):
        res = aoi.analizar_texto(TEXTO_CALIENTE_9, esperados=9)
        payload = aoi.construir_payload_json(res)
        self.assertEqual(payload["decision"], "ESPERAR / NO ENVIAR")
        self.assertFalse(payload["pick_listo"])
        self.assertEqual(payload["total"], 9)
        self.assertEqual(payload["liga"], "Liga MX")
        # Cada evento expone exactamente los campos pedidos.
        for ev in payload["eventos"]:
            self.assertEqual(
                set(ev.keys()),
                {
                    "fecha", "hora", "equipo_local", "equipo_visitante",
                    "momio_local", "momio_empate", "momio_visitante",
                },
            )

    def test_json_serializable(self):
        import json

        res = aoi.analizar_texto(TEXTO_CALIENTE_9, esperados=9)
        data = json.loads(aoi.exportar_json(res))
        self.assertEqual(len(data["eventos"]), 9)


# ---------------------------------------------------------------------------
# Garantías de seguridad/cumplimiento sobre el código fuente
# ---------------------------------------------------------------------------
class TestRestriccionesCodigoFuente(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src_modulo = (SRC_DIR / "assisted_odds_import.py").read_text(encoding="utf-8")
        cls.src_script = (
            BASE_DIR / "scripts" / "assisted_caliente_odds.py"
        ).read_text(encoding="utf-8")
        cls.fuentes = (cls.src_modulo, cls.src_script)

    def test_no_usa_stealth(self):
        # No se importa ni se invoca playwright-stealth (uso real, no comentarios).
        for fuente in self.fuentes:
            self.assertNotIn("playwright_stealth", fuente)
            self.assertNotIn("stealth(", fuente)
            self.assertNotIn("stealth_async", fuente)
            self.assertNotIn("stealth_sync", fuente)

    def test_no_usa_proxy(self):
        # launch/launch_persistent_context nunca recibe un proxy.
        for fuente in self.fuentes:
            self.assertNotIn("proxy=", fuente)

    def test_no_automatiza_login(self):
        # No rellena formularios ni maneja credenciales.
        for fuente in self.fuentes:
            self.assertNotIn(".fill(", fuente)
            self.assertNotIn("password", fuente)
            self.assertNotIn("credentials", fuente)
            self.assertNotIn(".set_credentials", fuente)

    def test_no_manda_telegram(self):
        # No importa ni usa el notificador de Telegram.
        for fuente in self.fuentes:
            self.assertNotIn("telegram_notifier", fuente)
            self.assertNotIn("import telegram", fuente)
            self.assertNotIn("sendMessage", fuente)
            self.assertNotIn("bot.send", fuente)

    def test_no_cambia_picks(self):
        # No importa módulos que modifican picks ni usa cierre operativo.
        for fuente in self.fuentes:
            self.assertNotIn("ajustar_pick_survivor", fuente)
            self.assertNotIn("registrar_voto", fuente)
            self.assertNotIn("CERRAR", fuente)

    def test_browser_visible(self):
        # El navegador se abre VISIBLE (headless=False), nunca headless=True.
        self.assertIn("headless=False", self.src_script)
        self.assertNotIn("headless=True", self.src_script)

    def test_decision_fija_en_modulo(self):
        self.assertEqual(aoi.DEC_ESPERAR, "ESPERAR / NO ENVIAR")


if __name__ == "__main__":
    unittest.main(verbosity=2)
