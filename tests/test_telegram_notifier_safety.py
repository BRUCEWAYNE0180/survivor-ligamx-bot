from pathlib import Path
from unittest import mock
import importlib.util
import os
import sys
import tempfile
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "telegram_notifier.py"
SPEC = importlib.util.spec_from_file_location("telegram_notifier", MODULE_PATH)
telegram_notifier = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = telegram_notifier
assert SPEC.loader is not None
SPEC.loader.exec_module(telegram_notifier)


class TelegramNotifierSafetyTests(unittest.TestCase):
    def _write_report(self, text: str) -> Path:
        handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
        with handle:
            handle.write(text)
        return Path(handle.name)

    def _run_main(self, report_path: Path):
        env = {
            "TELEGRAM_BOT_TOKEN": "dummy-token",
            "TELEGRAM_CHAT_ID": "dummy-chat",
        }

        with mock.patch.dict(os.environ, env, clear=False):
            with mock.patch.object(sys, "argv", ["telegram_notifier.py", "--report", str(report_path)]):
                with mock.patch.object(telegram_notifier, "enviar_mensaje") as enviar_mock:
                    code = telegram_notifier.main()

        return code, enviar_mock

    def test_secure_report_sends_full_report_once(self):
        report = self._write_report(
            "Reporte final\nDecisión operativa: ESPERAR / NO ENVIAR\n"
        )

        code, enviar_mock = self._run_main(report)

        self.assertEqual(code, 0)
        self.assertEqual(enviar_mock.call_count, 1)
        sent_text = enviar_mock.call_args.args[2]
        self.assertIn("BOT SURVIVOR LIGA MX", sent_text)
        self.assertIn("ESPERAR / NO ENVIAR", sent_text)

    def test_dangerous_report_sends_only_warning(self):
        report = self._write_report(
            "Reporte final\nDecisión operativa: ESPERAR / NO ENVIAR\nCERRAR pick\n"
        )

        code, enviar_mock = self._run_main(report)

        self.assertEqual(code, 3)
        self.assertEqual(enviar_mock.call_count, 1)
        sent_text = enviar_mock.call_args.args[2]
        self.assertIn("NO ENVIAR: reporte bloqueado", sent_text)
        self.assertNotIn("CERRAR pick", sent_text)

    def test_no_cerrar_false_positive_is_allowed(self):
        report = self._write_report(
            "Reporte final\nDecisión operativa: ESPERAR / NO ENVIAR\nNO CERRAR pick.\n"
        )

        code, enviar_mock = self._run_main(report)

        self.assertEqual(code, 0)
        self.assertEqual(enviar_mock.call_count, 1)
        sent_text = enviar_mock.call_args.args[2]
        self.assertIn("NO CERRAR", sent_text)

    def test_missing_safe_marker_sends_warning(self):
        report = self._write_report("Solo logs sin etiqueta segura.\n")

        code, enviar_mock = self._run_main(report)

        self.assertEqual(code, 2)
        self.assertEqual(enviar_mock.call_count, 1)
        sent_text = enviar_mock.call_args.args[2]
        self.assertIn("NO ENVIAR: reporte bloqueado", sent_text)
        self.assertIn("etiqueta segura", sent_text)

    def test_long_dangerous_report_is_validated_before_split(self):
        report = self._write_report(
            "Reporte final\nDecisión operativa: ESPERAR / NO ENVIAR\n"
            + ("línea segura\n" * 500)
            + "CERRAR pick\n"
        )

        code, enviar_mock = self._run_main(report)

        self.assertEqual(code, 3)
        self.assertEqual(enviar_mock.call_count, 1)
        sent_text = enviar_mock.call_args.args[2]
        self.assertNotIn("Parte 1/", sent_text)
        self.assertIn("NO ENVIAR: reporte bloqueado", sent_text)

    def test_missing_credentials_returns_2_without_sending(self):
        report = self._write_report(
            "Reporte final\nDecisión operativa: ESPERAR / NO ENVIAR\n"
        )

        with mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}, clear=False):
            with mock.patch.object(sys, "argv", ["telegram_notifier.py", "--report", str(report)]):
                with mock.patch.object(telegram_notifier, "enviar_mensaje") as enviar_mock:
                    code = telegram_notifier.main()

        self.assertEqual(code, 2)
        enviar_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
