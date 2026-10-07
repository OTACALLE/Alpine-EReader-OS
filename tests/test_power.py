import unittest

from core.ereader_core.power import DevelopmentPowerBackend, PowerController, PowerState


class PowerTests(unittest.TestCase):
    def setUp(self):
        self.backend = DevelopmentPowerBackend()
        self.power = PowerController(self.backend)

    def test_reading_forces_radios_off(self):
        self.assertTrue(self.power.request_wifi(True))
        self.power.transition(PowerState.READING)
        self.assertTrue(self.backend.radios_blocked)
        self.assertFalse(self.power.request_wifi(True))

    def test_suspend_turns_off_display_and_radios(self):
        self.power.transition(PowerState.SUSPEND)
        self.assertTrue(self.backend.radios_blocked)
        self.assertFalse(self.backend.display_enabled)
        self.assertTrue(self.backend.suspended)
