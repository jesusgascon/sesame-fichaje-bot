import os
import tempfile
import unittest
from pathlib import Path

import telegram_bot as tb
import state_machine as sm


class FlowTestCase(unittest.TestCase):
    """Prueba el flujo del bot en dry-run con `send` inyectado (sin red)."""

    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        tb.AUDIT_LOG = tmp / "audit.jsonl"
        tb.DRY_STATE_FILE = tmp / "dry.json"
        tb.DRY_STATE.clear()
        tb.PENDING.clear()
        tb.RATE.clear()
        tb.LOCKS.clear()
        tb.CONFIG["authorized_chat_ids"] = [1]
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
