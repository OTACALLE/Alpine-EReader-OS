import unittest

from core.ereader_core import powerd
from core.ereader_core.power import DevelopmentPowerBackend, PowerController, PowerState


class PowerdTests(unittest.TestCase):
    def test_run_loops_until_stop_then_shuts_down_backend(self):
        backend = DevelopmentPowerBackend()
        controller = PowerController(backend)
        ticks = []
        powerd.run(controller, lambda: len(ticks) >= 3, lambda s: ticks.append(s), 0.5)
        self.assertEqual(ticks, [0.5, 0.5, 0.5])
        self.assertEqual(controller.state, PowerState.SHUTDOWN)
        self.assertTrue(backend.shutdown_requested)

    def test_main_exits_cleanly_after_run_for(self):
        self.assertEqual(powerd.main(["--run-for", "0.05", "--interval", "0.01"]), 0)

    def test_main_rejects_non_positive_interval(self):
        with self.assertRaises(SystemExit):
            powerd.main(["--interval", "0"])


if __name__ == "__main__":
    unittest.main()
