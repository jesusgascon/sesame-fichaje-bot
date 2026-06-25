"""Tests del scheduler de recordatorios (probe de token + aviso de salida).

Todo en dry-run / con dependencias inyectadas (sin red). El recordatorio de salida
NUNCA ficha solo: deja un PENDING y reutiliza el flujo de confirmación SI/NO.
"""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import sesame_client as sc
import state_machine as sm
import telegram_bot as tb

from tests.test_telegram_flow import FlowTestCase


class TestParseAndDue(unittest.TestCase):
    def test_parse_hhmm(self):
        self.assertEqual(tb._parse_hhmm("16:45"), (16, 45))
        self.assertIsNone(tb._parse_hhmm("99:99"))
        self.assertIsNone(tb._parse_hhmm("nope"))
        self.assertIsNone(tb._parse_hhmm(None))

    def test_reminder_due(self):
        d = "2026-06-25"
        self.assertTrue(tb._reminder_due(datetime(2026, 6, 25, 16, 46), (16, 45), None, window_min=120))
        self.assertFalse(tb._reminder_due(datetime(2026, 6, 25, 16, 46), (16, 45), d))      # ya hoy
        self.assertFalse(tb._reminder_due(datetime(2026, 6, 25, 16, 44), (16, 45), None))   # aún no
        self.assertFalse(tb._reminder_due(datetime(2026, 6, 25, 19, 0), (16, 45), None, window_min=120))  # fuera de ventana
        self.assertFalse(tb._reminder_due(datetime(2026, 6, 25, 16, 46), None, None))       # sin hora


class ReminderBase(FlowTestCase):
    def setUp(self):
        super().setUp()
        tb.REMINDERS_STATE_FILE = Path(tempfile.mkdtemp()) / "rem.json"
        tb._REMINDERS.clear()
        tb.LINKS.set(1, "demo")

    def tearDown(self):
        tb._REMINDERS.clear()
        tb.CONFIG.pop("reminders", None)
        super().tearDown()


class TestClockOutReminder(ReminderBase):
    def test_reminds_when_still_clocked_in(self):
        tb.DRY_STATE["demo"] = sm.WORKING
        tb._run_clock_out_reminder({"clock_out_time": "16:45"})
        self.assertIn(1, tb.PENDING)                      # deja confirmación pendiente
        self.assertEqual(tb.PENDING[1]["command"], sm.FICHAR)
        self.assertIn("salida", self.last.lower())

    def test_silent_when_already_out(self):
        tb.DRY_STATE["demo"] = sm.OUT
        before = len(self.sent)
        tb._run_clock_out_reminder({"clock_out_time": "16:45"})
        self.assertNotIn(1, tb.PENDING)                   # nada que recordar
        self.assertEqual(len(self.sent), before)


class TestTokenProbe(ReminderBase):
    def setUp(self):
        super().setUp()
        self._dry = sc.DRY_RUN
        self._gcs = sc.get_current_state
        self._erf = sc.ENABLE_REAL_FILE
        sc.DRY_RUN = False
        # Aísla ENABLE_REAL (puede existir uno local de pruebas) para que el probe no
        # mezcle el aviso de "ENABLE_REAL caduca" con el de sesión caída.
        sc.ENABLE_REAL_FILE = Path(tempfile.mkdtemp()) / "ENABLE_REAL"

    def tearDown(self):
        sc.DRY_RUN = self._dry
        sc.get_current_state = self._gcs
        sc.ENABLE_REAL_FILE = self._erf
        super().tearDown()

    def test_warns_on_dead_session(self):
        def boom(emp, *a, **k):
            raise RuntimeError("Sesame GET falló: HTTP 401")
        sc.get_current_state = boom
        tb._run_token_probe({"enable_real_warn_days": 0})
        self.assertIn("caducar", self.last.lower())


class TestRunScheduled(ReminderBase):
    def test_fires_once_per_day(self):
        tb.DRY_STATE["demo"] = sm.WORKING
        tb.CONFIG["reminders"] = {
            "enabled": True, "clock_out_time": "16:45",
            "token_probe_time": "08:00", "clock_out_window_min": 120,
        }
        now = datetime.now().replace(hour=16, minute=46, second=0, microsecond=0)
        tb.run_scheduled(now)
        self.assertIn(1, tb.PENDING)
        sent_after_first = len(self.sent)

        tb.PENDING.clear()
        tb.run_scheduled(now)                  # mismo día: no re-dispara
        self.assertNotIn(1, tb.PENDING)
        self.assertEqual(len(self.sent), sent_after_first)

    def test_disabled_does_nothing(self):
        tb.DRY_STATE["demo"] = sm.WORKING
        tb.CONFIG["reminders"] = {"enabled": False, "clock_out_time": "16:45"}
        now = datetime.now().replace(hour=16, minute=46, second=0, microsecond=0)
        tb.run_scheduled(now)
        self.assertNotIn(1, tb.PENDING)


if __name__ == "__main__":
    unittest.main()
