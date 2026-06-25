"""Regresiones del fix-pack de correctitud (council 2026-06-25).

Cubre:
- #1 zona horaria: /hoy convierte timestamps UTC a la zona local (Europe/Madrid),
  con DST, sin desfasar 1-2h.
- #2/#5 atomicidad + éxito honesto: execute_plan no aborta con excepción y run_plan
  NO muestra "✅" cuando una acción falla; avisa del plan a medias.
- #6 doble lectura: en la ruta inmediata (recheck=False) no se re-lee el estado.
"""

import unittest

import sesame_client as sc
import state_machine as sm
import telegram_bot as tb

from tests.test_telegram_flow import FlowTestCase


class TestTimezoneFormatting(unittest.TestCase):
    """#1: las horas de /hoy se muestran en hora local, no en UTC."""

    def setUp(self):
        # Fuerza Europe/Madrid y limpia la caché de zona del módulo.
        sc._DISPLAY_TZ_CACHE = None

    def tearDown(self):
        sc._DISPLAY_TZ_CACHE = None

    def test_utc_z_converted_to_madrid_summer(self):
        # Verano (CEST, UTC+2): 07:00Z -> 09:00 Madrid.
        self.assertEqual(sc._format_time_value("2026-06-25T07:00:00Z"), "09:00:00")

    def test_utc_z_converted_to_madrid_winter(self):
        # Invierno (CET, UTC+1): 07:00Z -> 08:00 Madrid.
        self.assertEqual(sc._format_time_value("2026-01-15T07:00:00Z"), "08:00:00")

    def test_offset_aware_kept_as_wall_clock(self):
        # Ya viene con offset local: se respeta la hora de pared.
        self.assertEqual(sc._format_time_value("2026-06-25T09:00:00+02:00"), "09:00:00")

    def test_naive_timestamp_unchanged(self):
        # Sin zona no inventamos: se muestra tal cual.
        self.assertEqual(sc._format_time_value("2026-06-25T09:00:00"), "09:00:00")

    def test_summary_uses_local_time(self):
        payload = [{
            "checkIn": "2026-06-25T07:00:00Z",
            "checkOut": "2026-06-25T15:00:00Z",
            "workCheckType": {"name": "Oficina"},
        }]
        lines = sc.format_checks_summary(payload)
        self.assertEqual(lines, ["09:00:00 - 17:00:00 · Oficina"])


class TestExecutePlanPartial(unittest.TestCase):
    """#2/#5 a nivel de cliente: execute_plan no lanza; marca la acción fallida."""

    def setUp(self):
        self._orig = sc.execute_action

        def fake(action, emp, coords, auth):
            if action == "CLOCK_OUT":
                raise RuntimeError("Sesame POST falló: HTTP 500")
            return {"dry_run": False, "action": action, "status": 200, "ok": True}

        sc.execute_action = fake

    def tearDown(self):
        sc.execute_action = self._orig

    def test_partial_plan_returns_results_without_raising(self):
        results = sc.execute_plan(["PAUSE_END", "CLOCK_OUT"], "emp", coords=(1.0, 2.0), auth={"csid": "x"})
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0]["ok"])
        self.assertFalse(results[1]["ok"])
        self.assertIn("500", results[1]["error"])

    def test_stops_after_first_failure(self):
        def fail_first(action, emp, coords, auth):
            raise RuntimeError("boom")
        sc.execute_action = fail_first
        results = sc.execute_plan(["CLOCK_IN", "PAUSE_START"], "emp", coords=(1.0, 2.0), auth={"csid": "x"})
        self.assertEqual(len(results), 1)  # se detuvo en la primera
        self.assertFalse(results[0]["ok"])


class TestRunPlanRealMessaging(FlowTestCase):
    """#2/#5 a nivel de bot: en real, '✅' solo si todo fue 2xx."""

    def setUp(self):
        super().setUp()
        self._dry, self._real = sc.DRY_RUN, sc.ALLOW_REAL
        self._exec = sc.execute_plan
        self._get_state = tb.get_state
        sc.DRY_RUN, sc.ALLOW_REAL = False, True
        tb.get_state = lambda emp: sm.WORKING

    def tearDown(self):
        sc.DRY_RUN, sc.ALLOW_REAL = self._dry, self._real
        sc.execute_plan = self._exec
        tb.get_state = self._get_state
        super().tearDown()

    def test_partial_failure_warns_not_ok(self):
        sc.execute_plan = lambda actions, emp: [
            {"action": "PAUSE_END", "ok": True, "status": 200},
            {"action": "CLOCK_OUT", "ok": False, "error": "HTTP 500"},
        ]
        plan = sm.Plan(["PAUSE_END", "CLOCK_OUT"], True, "Cerrar la pausa y finalizar jornada")
        tb.run_plan(1, "demo", plan, command=sm.FICHAR, expected_state=sm.PAUSED, recheck=False)
        self.assertNotIn("✅", self.last)
        self.assertIn("medias", self.last.lower())

    def test_all_ok_shows_check(self):
        sc.execute_plan = lambda actions, emp: [{"action": "CLOCK_IN", "ok": True, "status": 200}]
        plan = sm.Plan(["CLOCK_IN"], False, "Iniciar jornada")
        tb.run_plan(1, "demo", plan, command=sm.FICHAR, expected_state=sm.OUT, recheck=False)
        self.assertIn("✅", self.last)


class TestRecheckSkipsReread(FlowTestCase):
    """#6: recheck=False evita la segunda lectura/replanificación de estado."""

    def setUp(self):
        super().setUp()
        self._exec = sc.execute_plan
        self._get_state = tb.get_state
        self._plan_actions = sm.plan_actions
        self.replans = []

        def counting(state, command):
            self.replans.append((state, command))
            return self._plan_actions(state, command)

        sm.plan_actions = counting
        sc.execute_plan = lambda actions, emp: [{"action": "CLOCK_IN", "ok": True, "status": 200}]
        tb.get_state = lambda emp: sm.OUT

    def tearDown(self):
        sm.plan_actions = self._plan_actions
        sc.execute_plan = self._exec
        tb.get_state = self._get_state
        super().tearDown()

    def test_recheck_false_skips_replan(self):
        plan = sm.Plan(["CLOCK_IN"], False, "Iniciar jornada")
        tb.run_plan(1, "demo", plan, command=sm.FICHAR, expected_state=sm.OUT, recheck=False)
        self.assertEqual(self.replans, [])  # no hubo re-lectura

    def test_recheck_true_replans_once(self):
        plan = sm.Plan(["CLOCK_IN"], False, "Iniciar jornada")
        tb.run_plan(1, "demo", plan, command=sm.FICHAR, expected_state=sm.OUT, recheck=True)
        self.assertEqual(len(self.replans), 1)  # re-leyó una vez


if __name__ == "__main__":
    unittest.main()
