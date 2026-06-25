import unittest

import state_machine as sm


class TestPlanActions(unittest.TestCase):
    def test_transition_table(self):
        cases = {
            (sm.OUT, sm.FICHAR): ([sm.CLOCK_IN], False),
            (sm.WORKING, sm.FICHAR): ([sm.CLOCK_OUT], True),
            (sm.REMOTE, sm.FICHAR): ([sm.CLOCK_OUT], True),
            (sm.PAUSED, sm.FICHAR): ([sm.PAUSE_END, sm.CLOCK_OUT], True),
            (sm.OUT, sm.PAUSAR): ([sm.CLOCK_IN, sm.PAUSE_START], True),
            (sm.WORKING, sm.PAUSAR): ([sm.PAUSE_START], False),
            (sm.REMOTE, sm.PAUSAR): ([sm.PAUSE_START], False),
            (sm.PAUSED, sm.PAUSAR): ([sm.PAUSE_END], False),
        }
        for (state, command), (actions, confirm) in cases.items():
            plan = sm.plan_actions(state, command)
            self.assertEqual(plan.actions, actions, f"acciones {state}+{command}")
            self.assertEqual(plan.needs_confirmation, confirm, f"confirm {state}+{command}")

    def test_unknown_state_returns_empty(self):
        plan = sm.plan_actions("desconocido", sm.FICHAR)
        self.assertEqual(plan.actions, [])

    def test_state_is_case_insensitive(self):
        self.assertEqual(sm.plan_actions("WORKING", sm.FICHAR).actions, [sm.CLOCK_OUT])

    def test_transition_table_matches_doc(self):
        # La tabla documentada debe cubrir las 8 combinaciones.
        self.assertEqual(len(sm.TRANSITION_TABLE), 8)


if __name__ == "__main__":
    unittest.main()
