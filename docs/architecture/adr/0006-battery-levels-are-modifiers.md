# ADR 0006: LOW and CRITICAL battery are modifiers, RESUME is a state

Status: accepted.

ARCHITECTURE.md §21.2 calls LOW BATTERY "a modifier state, not exclusive with
READING/IDLE" and says CRITICAL BATTERY forces radios off and moves the device
to SUSPEND/SHUTDOWN. They are therefore modelled as `BatteryLevel`
(NORMAL/LOW/CRITICAL) on the controller, not as additional `PowerState`
members. `RESUME` is a real transient state: SUSPEND may only be left through
RESUME (or SHUTDOWN), and RESUME is reachable only from SUSPEND. SHUTDOWN is
terminal. The 15% / 5% thresholds are provisional and unmeasured.
