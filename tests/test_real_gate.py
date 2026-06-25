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


if __name__ == "__main__":
    unittest.main()
