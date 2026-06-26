"""Regresiones del pack de observabilidad/fiabilidad (council #2, 2026-06-25).

Cubre:
- #1 ventana de medianoche: el estado se lee de AYER a HOY (evita doble check-in).
- #2 recibo read-after-write: éxito releído + fallo de token EN VOZ ALTA.
- #3 send() reintenta una vez ante errores de red transitorios.
- #4 comandos /version y /salud (solo lectura).
- #5 etiqueta "Remoto" (= web de Sesame).
"""

import unittest
import urllib.error
from datetime import date, timedelta

import sesame_client as sc
import state_machine as sm
import telegram_bot as tb

from tests.test_telegram_flow import FlowTestCase


class TestMidnightWindow(unittest.TestCase):
    """#1: get_current_state lee de AYER a HOY. La ventana debe incluir HOY (regresión
    del bug v1.0.3-v1.0.4: se consultaba ayer→ayer y el fichaje de hoy era invisible)."""

    def test_state_read_window_is_yesterday_to_today(self):
        captured = {}

        def fake_get_checks(emp, from_day=None, to_day=None, auth=None):
            captured["from_day"] = from_day
            captured["to_day"] = to_day
            return []

        orig, dry = sc.get_checks, sc.DRY_RUN
        sc.get_checks, sc.DRY_RUN = fake_get_checks, False
        try:
            sc.get_current_state("emp", auth={"csid": "x"})
        finally:
            sc.get_checks, sc.DRY_RUN = orig, dry
        self.assertEqual(captured["from_day"], (date.today() - timedelta(days=1)).isoformat())
        self.assertEqual(captured["to_day"], date.today().isoformat())  # ← debe incluir HOY

    def test_open_check_today_reads_as_working(self):
        """End-to-end por el get_checks real (mockeando solo la red): un fichaje
        abierto HOY se ve como 'working', y la URL pide de ayer a hoy."""
        captured = {}

        def fake_real_get(url, auth):
            captured["url"] = url
            return [{"checkIn": "2026-06-26T08:00:00Z", "checkOut": None}]  # abierto hoy

        orig_get, orig_real, dry = sc.get_checks, sc._real_get_json, sc.DRY_RUN
        sc._real_get_json, sc.DRY_RUN = fake_real_get, False
        try:
            state = sc.get_current_state("emp", auth={"csid": "x"})
        finally:
            sc._real_get_json, sc.get_checks, sc.DRY_RUN = orig_real, orig_get, dry
        self.assertEqual(state, "working")
        self.assertIn(f"from={(date.today() - timedelta(days=1)).isoformat()}", captured["url"])
        self.assertIn(f"to={date.today().isoformat()}", captured["url"])


class TestRemotoLabel(unittest.TestCase):
    """#5: el trabajo remoto se etiqueta "Remoto" como en Sesame."""

    def test_remote_label_matches_sesame(self):
        self.assertEqual(sc._check_label({"isRemote": True}), "Remoto")


class TestReceiptAndAuth(FlowTestCase):
    """#2: en real, éxito = recibo releído; token caducado = aviso en voz alta."""

    def setUp(self):
        super().setUp()
        self._dry, self._real = sc.DRY_RUN, sc.ALLOW_REAL
        self._exec, self._get_state = sc.execute_plan, tb.get_state
        sc.DRY_RUN, sc.ALLOW_REAL = False, True

    def tearDown(self):
        sc.DRY_RUN, sc.ALLOW_REAL = self._dry, self._real
        sc.execute_plan, tb.get_state = self._exec, self._get_state
        super().tearDown()

    def test_success_shows_receipt_with_real_state(self):
        sc.execute_plan = lambda actions, emp: [{"action": "CLOCK_IN", "ok": True, "status": 200}]
        tb.get_state = lambda emp: sm.WORKING
        plan = sm.Plan(["CLOCK_IN"], False, "Iniciar jornada")
        tb.run_plan(1, "demo", plan, command=sm.FICHAR, expected_state=sm.OUT, recheck=False)
        self.assertIn("✅", self.last)
        self.assertIn("trabajando", self.last.lower())  # "Ahora: trabajando"

    def test_token_expired_is_loud(self):
        sc.execute_plan = lambda actions, emp: [
            {"action": "CLOCK_IN", "ok": False, "error": "Sesame POST falló: HTTP 401"}
        ]
        tb.get_state = lambda emp: sm.OUT
        plan = sm.Plan(["CLOCK_IN"], False, "Iniciar jornada")
        tb.run_plan(1, "demo", plan, command=sm.FICHAR, expected_state=sm.OUT, recheck=False)
        self.assertIn("caducad", self.last.lower())
        self.assertIn("NO se registró", self.last)
        self.assertNotIn("✅", self.last)


class TestSendRetry(unittest.TestCase):
    """#3: send() reintenta una vez ante un fallo de red transitorio."""

    def setUp(self):
        self._tg, self._sleep = tb._tg, tb.time.sleep
        tb.time.sleep = lambda s: None  # no esperar en el test

    def tearDown(self):
        tb._tg, tb.time.sleep = self._tg, self._sleep

    def test_retries_once_then_succeeds(self):
        calls = []

        def flaky(method, **params):
            calls.append(method)
            if len(calls) == 1:
                raise urllib.error.URLError("boom")
            return {"ok": True}

        tb._tg = flaky
        tb.send(1, "hola")
        self.assertEqual(len(calls), 2)

    def test_gives_up_after_two_attempts(self):
        calls = []

        def always_down(method, **params):
            calls.append(method)
            raise urllib.error.URLError("down")

        tb._tg = always_down
        tb.send(1, "hola")  # no debe lanzar
        self.assertEqual(len(calls), 2)


class TestDiagnosticCommands(FlowTestCase):
    """#4: /version y /salud (solo lectura)."""

    def test_version_command(self):
        tb.handle(1, "/version")
        self.assertIn(tb.BOT_VERSION, self.last)

    def test_salud_command_in_dry_run(self):
        tb.handle(1, "/salud")
        self.assertIn(tb.BOT_VERSION, self.last)
        self.assertIn("Modo", self.last)
        self.assertIn("simulación", self.last.lower())


if __name__ == "__main__":
    unittest.main()
