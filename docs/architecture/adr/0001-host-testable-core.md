# ADR 0001: Reference Core services use Python's standard library in Phase 1

Status: accepted for the proof-of-concept repository.

The first Core services are implemented in dependency-free Python so their
policy, configuration, and storage contracts run identically under Windows
development tooling and Alpine's `python3` package. This does not select the
final target implementation language or claim that Python services have been
measured on the J2 Core. Device-facing writes remain behind backends, so a
validated device port can supply Linux sysfs/rfkill/DRM integration without
changing Core policy semantics.
