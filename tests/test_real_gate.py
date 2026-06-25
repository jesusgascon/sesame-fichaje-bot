import os
import tempfile
import time
import unittest
from pathlib import Path

import sesame_client as sc


class TestEnableRealToken(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._orig_file = sc.ENABLE_REAL_FILE
        self._orig_ttl = sc.ENABLE_REAL_TTL
        sc.ENABLE_REAL_FILE = self.tmp / "ENABLE_REAL"
        sc.ENABLE_REAL_TTL = 3600

    def tearDown(self):
        sc.ENABLE_REAL_FILE = self._orig_file
        sc.ENABLE_REAL_TTL = self._orig_ttl

    def test_missing_file_not_valid(self):
        ok, reason = sc.enable_real_token_valid()
        self.assertFalse(ok)
        self.assertIn("falta", reason)

    def test_fresh_file_valid(self):
        sc.ENABLE_REAL_FILE.touch()
        ok, _ = sc.enable_real_token_valid()
        self.assertTrue(ok)

    def test_expired_file_not_valid(self):
        sc.ENABLE_REAL_FILE.touch()
        old = time.time() - 10_000
        os.utime(sc.ENABLE_REAL_FILE, (old, old))
        ok, reason = sc.enable_real_token_valid()
        self.assertFalse(ok)
        self.assertIn("caducado", reason)


class TestRealPathArmed(unittest.TestCase):
    def test_dry_run_is_not_armed(self):
        # Por defecto sesame_client arranca en dry-run.
        ok, reason = sc.real_path_armed()
        self.assertFalse(ok)
        self.assertEqual(reason, "dry-run")


class TestExecuteActionDryRun(unittest.TestCase):
    def test_dry_run_simulates_without_network(self):
        res = sc.execute_action("CLOCK_IN", "emp-1", coords=(1.0, 2.0))
        self.assertTrue(res["dry_run"])
        self.assertTrue(res["ok"])


class TestEndpointContract(unittest.TestCase):
    """Fija el contrato capturado del navegador: trabajo via check-in/out con
    workCheckTypeId=null; pausa via endpoint toggle /pause con workBreakId."""

    def setUp(self):
        os.environ["BOT_PAUSE_CHECK_TYPE_ID"] = "break-id-123"

    def tearDown(self):
        os.environ.pop("BOT_PAUSE_CHECK_TYPE_ID", None)

    def _action(self, action):
        return sc.execute_action(action, "EMP", coords=(41.63, -0.91))

    def test_clock_in_uses_check_in(self):
        res = self._action("CLOCK_IN")
        self.assertTrue(res["url"].endswith("/EMP/check-in"))
        self.assertIsNone(res["body"]["workCheckTypeId"])
        self.assertNotIn("workBreakId", res["body"])

    def test_clock_out_uses_check_out(self):
        res = self._action("CLOCK_OUT")
        self.assertTrue(res["url"].endswith("/EMP/check-out"))

    def test_pause_start_uses_pause_endpoint_with_break_id(self):
        res = self._action("PAUSE_START")
        self.assertTrue(res["url"].endswith("/EMP/pause"))
        self.assertIsNone(res["body"]["workCheckTypeId"])
        self.assertEqual(res["body"]["workBreakId"], "break-id-123")

    def test_pause_end_resumes_work_via_check_in(self):
        # Terminar la pausa = reanudar trabajo = check-in normal (sin workBreakId).
        res = self._action("PAUSE_END")
        self.assertTrue(res["url"].endswith("/EMP/check-in"))
        self.assertIsNone(res["body"]["workCheckTypeId"])
        self.assertNotIn("workBreakId", res["body"])


if __name__ == "__main__":
    unittest.main()
