import unittest

from core.ereader_core.power import (
    ALLOWED_TRANSITIONS, BatteryLevel, DevelopmentPowerBackend, InvalidTransition,
    PowerController, PowerState, battery_level_for,
)


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

    def test_pinned_wifi_is_cleared_when_leaving_active(self):
        self.assertTrue(self.power.request_wifi(True, pin=True))
        self.assertTrue(self.power.wifi_pinned)
        for state in (PowerState.IDLE, PowerState.SUSPEND):
            self.power.transition(state)
            self.assertFalse(self.power.wifi_pinned, state)
            self.assertTrue(self.backend.radios_blocked, state)

    def test_wifi_only_granted_in_active(self):
        for state in (PowerState.READING, PowerState.IDLE):
            self.power.transition(state)
            self.assertFalse(self.power.request_wifi(True), state)
            self.power.transition(PowerState.ACTIVE)
        self.assertTrue(self.power.request_wifi(True))
        self.assertTrue(self.power.request_wifi(False))

    def test_resume_is_required_after_suspend_and_clears_suspended_flag(self):
        self.power.transition(PowerState.SUSPEND)
        for forbidden in (PowerState.ACTIVE, PowerState.READING, PowerState.IDLE):
            with self.assertRaises(InvalidTransition):
                self.power.transition(forbidden)
        self.power.transition(PowerState.RESUME)
        self.assertFalse(self.backend.suspended)
        self.assertTrue(self.backend.display_enabled)
        self.assertTrue(self.backend.radios_blocked)
        self.power.transition(PowerState.READING)
        self.assertEqual(self.power.state, PowerState.READING)

    def test_resume_only_reachable_from_suspend(self):
        with self.assertRaises(InvalidTransition):
            self.power.transition(PowerState.RESUME)

    def test_shutdown_is_terminal(self):
        self.power.transition(PowerState.SHUTDOWN)
        self.assertTrue(self.backend.shutdown_requested)
        self.assertEqual(ALLOWED_TRANSITIONS[PowerState.SHUTDOWN], frozenset())
        for state in PowerState:
            if state is not PowerState.SHUTDOWN:
                with self.assertRaises(InvalidTransition):
                    self.power.transition(state)
        self.assertFalse(self.power.request_wifi(True))

    def test_same_state_transition_is_a_noop(self):
        self.power.transition(PowerState.READING)
        self.backend.display_dimmed = True
        self.power.transition(PowerState.READING)
        self.assertTrue(self.backend.display_dimmed)

    def test_low_battery_is_a_modifier_that_dims_but_keeps_state(self):
        self.power.transition(PowerState.READING)
        self.power.set_battery_level(BatteryLevel.LOW)
        self.assertEqual(self.power.state, PowerState.READING)
        self.assertTrue(self.backend.display_dimmed)
        self.power.set_battery_level(BatteryLevel.NORMAL)
        self.assertFalse(self.backend.display_dimmed)

    def test_critical_battery_forces_radios_off_and_suspends(self):
        self.power.request_wifi(True, pin=True)
        self.power.set_battery_level(BatteryLevel.CRITICAL)
        self.assertEqual(self.power.state, PowerState.SUSPEND)
        self.assertTrue(self.backend.suspended)
        self.assertTrue(self.backend.radios_blocked)
        self.assertFalse(self.power.wifi_pinned)

    def test_critical_battery_refuses_reading_and_wifi_until_recovered(self):
        self.power.set_battery_level(BatteryLevel.CRITICAL)
        self.power.transition(PowerState.RESUME)
        self.assertFalse(self.power.request_wifi(True))
        for state in (PowerState.ACTIVE, PowerState.READING, PowerState.IDLE):
            with self.assertRaises(InvalidTransition):
                self.power.transition(state)
        self.power.set_battery_level(BatteryLevel.NORMAL)
        self.power.transition(PowerState.ACTIVE)
        self.assertTrue(self.power.request_wifi(True))

    def test_battery_level_mapping(self):
        self.assertEqual(battery_level_for(50, False), BatteryLevel.NORMAL)
        self.assertEqual(battery_level_for(15, False), BatteryLevel.LOW)
        self.assertEqual(battery_level_for(5, False), BatteryLevel.CRITICAL)
        self.assertEqual(battery_level_for(1, True), BatteryLevel.NORMAL)
        with self.assertRaises(ValueError):
            battery_level_for(101, False)


if __name__ == "__main__":
    unittest.main()
