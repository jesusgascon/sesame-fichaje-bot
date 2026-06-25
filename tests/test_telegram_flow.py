import os
import tempfile
import unittest
from pathlib import Path

import sesame_client
import telegram_bot as tb
import state_machine as sm


class FlowTestCase(unittest.TestCase):
    """Prueba el flujo del bot en dry-run con `send` inyectado (sin red)."""

    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        tb.AUDIT_LOG = tmp / "audit.jsonl"
        tb.DRY_STATE_FILE = tmp / "dry.json"
        tb.OFFSET_FILE = tmp / "tg_offset"
        tb.LOCK_DIR = tmp / ".locks"
        tb.LINKS = tb.link_store.LinkStore(tmp / "links.json")
        tb.DRY_STATE.clear()
        tb.PENDING.clear()
        tb.PENDING_OTP.clear()
        tb.RATE.clear()
        tb.LOCKS.clear()
        tb.CONFIG["authorized_chat_ids"] = [1]
        tb.CONFIG["employee_id"] = "demo"
        os.environ["BOT_TEST_EMPLOYEE_ID"] = "demo"
        os.environ["BOT_KILL_SWITCH"] = "0"
        self.sent = []
        self._orig_send = tb.send
        tb.send = lambda chat, text, markup=None: self.sent.append(text)

    def tearDown(self):
        tb.send = self._orig_send
        os.environ.pop("BOT_TEST_EMPLOYEE_ID", None)
        os.environ.pop("BOT_KILL_SWITCH", None)

    @property
    def last(self):
        return self.sent[-1]


class TestHappyPath(FlowTestCase):
    def test_full_cycle(self):
        tb.handle(1, "/estado")
        self.assertIn("fuera", self.last)

        tb.handle(1, "fichar")          # out -> CLOCK_IN, sin confirmar
        self.assertIn("trabajando", self.last)

        tb.handle(1, "pausar")          # working -> PAUSE_START
        self.assertIn("descansando", self.last)

        tb.handle(1, "fichar")          # paused -> pide confirmación
        self.assertIn("SI", self.last)

        tb.handle(1, "SI")             # confirma: PAUSE_END + CLOCK_OUT
        self.assertIn("fuera", self.last)

    def test_cancel_confirmation(self):
        tb.DRY_STATE["demo"] = sm.WORKING
        tb.handle(1, "fichar")          # working -> CLOCK_OUT, pide confirmación
        self.assertIn("SI", self.last)
        tb.handle(1, "NO")
        self.assertIn("Cancelado", self.last)
        # El estado no cambió tras cancelar.
        tb.handle(1, "/estado")
        self.assertIn("trabajando", self.last)


class TestGuards(FlowTestCase):
    def test_unauthorized_chat_blocked(self):
        tb.handle(999, "/estado")
        self.assertIn("no autorizado", self.last.lower())

    def test_public_command_allowed_without_auth(self):
        tb.handle(999, "/mi_chat_id")
        self.assertIn("999", self.last)

    def test_kill_switch_blocks(self):
        os.environ["BOT_KILL_SWITCH"] = "1"
        tb.DRY_STATE["demo"] = sm.OUT
        tb.handle(1, "fichar")
        self.assertIn("kill switch", self.last.lower())

    def test_expired_confirmation(self):
        tb.DRY_STATE["demo"] = sm.WORKING
        tb.handle(1, "fichar")          # crea PENDING
        tb.PENDING[1]["expires_at"] = 0  # fuerza caducidad
        tb.handle(1, "SI")
        self.assertIn("caducado", self.last.lower())


class TestOtpPairing(FlowTestCase):
    def test_vincular_issues_otp_and_binds(self):
        tb.handle(1, "/vincular")
        self.assertIn("consola", self.last.lower())
        self.assertIn(1, tb.PENDING_OTP)
        code = tb.PENDING_OTP[1]["code"]
        tb.handle(1, code)
        self.assertIn("vinculado", self.last.lower())
        self.assertEqual(tb.LINKS.get(1), "demo")

    def test_wrong_code_rejected(self):
        tb.handle(1, "/vincular")
        real_code = tb.PENDING_OTP[1]["code"]
        wrong = "000000" if real_code != "000000" else "111111"
        tb.handle(1, wrong)
        self.assertIn("incorrecto", self.last.lower())
        self.assertIsNone(tb.LINKS.get(1))

    def test_expired_code_rejected(self):
        tb.handle(1, "/vincular")
        code = tb.PENDING_OTP[1]["code"]
        tb.PENDING_OTP[1]["expires_at"] = 0
        tb.handle(1, code)
        self.assertIn("caducado", self.last.lower())
        self.assertIsNone(tb.LINKS.get(1))

    def test_vincular_requires_authorization(self):
        tb.handle(999, "/vincular")
        self.assertIn("no autorizado", self.last.lower())


class TestGateR1(FlowTestCase):
    def test_real_mode_requires_verified_binding(self):
        dry, real = sesame_client.DRY_RUN, sesame_client.ALLOW_REAL
        try:
            sesame_client.DRY_RUN = False
            sesame_client.ALLOW_REAL = True
            # Sin binding, en real NO se deriva el employeeId de config (gate R1).
            self.assertIsNone(tb.resolve_employee_id(1))
            tb.LINKS.set(1, "demo")
            self.assertEqual(tb.resolve_employee_id(1), "demo")
        finally:
            sesame_client.DRY_RUN = dry
            sesame_client.ALLOW_REAL = real

    def test_dry_run_allows_config_fallback(self):
        self.assertEqual(tb.resolve_employee_id(1), "demo")


class TestRateLimit(unittest.TestCase):
    def test_blocks_after_limit_without_renewing_window(self):
        tb.RATE.clear()
        tb.RATE_LIMIT_COUNT = 3
        results = [tb.rate_limited(7) for _ in range(6)]
        self.assertEqual(results, [False, False, False, True, True, True])
        # Los intentos bloqueados NO se acumulan: la ventana guarda solo 3.
        self.assertEqual(len(tb.RATE[7]), 3)


if __name__ == "__main__":
    unittest.main()
