import unittest

import sesame_client as sc


class TestClassifyFromChecks(unittest.TestCase):
    def test_out_without_checks(self):
        self.assertEqual(sc.classify_state_from_checks([]), "out")

    def test_out_when_all_closed(self):
        payload = [{"checkIn": "2026-06-25T08:00:00", "checkOut": "2026-06-25T16:00:00"}]
        self.assertEqual(sc.classify_state_from_checks(payload), "out")

    def test_working_when_open(self):
        payload = [{"checkIn": "2026-06-25T08:00:00", "checkOut": None}]
        self.assertEqual(sc.classify_state_from_checks(payload), "working")

    def test_paused_when_open_break(self):
        payload = [{"checkIn": "2026-06-25T08:00:00", "checkOut": None, "workBreakId": "abc"}]
        self.assertEqual(sc.classify_state_from_checks(payload), "paused")

    def test_remote_when_open_remote(self):
        payload = [{"checkIn": "2026-06-25T08:00:00", "checkOut": None, "isRemote": True}]
        self.assertEqual(sc.classify_state_from_checks(payload), "remote")

    def test_uses_last_open_check(self):
        payload = [
            {"checkIn": "08:00", "checkOut": "12:00"},
            {"checkIn": "13:00", "checkOut": None, "workBreakId": "x"},
        ]
        self.assertEqual(sc.classify_state_from_checks(payload), "paused")

    def test_unwraps_data_key(self):
        payload = {"data": [{"checkIn": "08:00", "checkOut": None}]}
        self.assertEqual(sc.classify_state_from_checks(payload), "working")


class TestClassifyState(unittest.TestCase):
    def test_status_strings(self):
        self.assertEqual(sc.classify_state({"status": "working"}), "working")
        self.assertEqual(sc.classify_state({"status": "paused"}), "paused")
        self.assertEqual(sc.classify_state({"status": "finished"}), "out")
        self.assertEqual(sc.classify_state({"state": "remote work"}), "remote")

    def test_boolean_flags(self):
        self.assertEqual(sc.classify_state({"isPaused": True}), "paused")
        self.assertEqual(sc.classify_state({"isRemote": True}), "remote")
        self.assertEqual(sc.classify_state({"isWorking": True}), "working")

    def test_empty_is_out(self):
        self.assertEqual(sc.classify_state({}), "out")


class TestFormatSummary(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(sc.format_checks_summary([]), ["Sin fichajes hoy."])

    def test_open_entry(self):
        payload = [{"checkIn": "2026-06-25T08:00:00", "checkOut": None}]
        lines = sc.format_checks_summary(payload)
        self.assertEqual(len(lines), 1)
        self.assertIn("abierto", lines[0])
        self.assertIn("08:00:00", lines[0])

    def test_closed_entry_has_both_times(self):
        payload = [{"checkIn": "2026-06-25T08:00:00", "checkOut": "2026-06-25T16:30:00"}]
        line = sc.format_checks_summary(payload)[0]
        self.assertIn("08:00:00", line)
        self.assertIn("16:30:00", line)


class TestConfigHelpers(unittest.TestCase):
    def test_is_configured(self):
        self.assertFalse(sc.is_configured(""))
        self.assertFalse(sc.is_configured(None))
        self.assertFalse(sc.is_configured("   "))
        self.assertFalse(sc.is_configured("PEGA_AQUI_EL_TOKEN"))
        self.assertFalse(sc.is_configured("TU_EMPLOYEE_ID"))
        self.assertTrue(sc.is_configured("abc123"))


if __name__ == "__main__":
    unittest.main()
