# AGENTS.md

## Project

Alpine EReader OS is a minimal, private, open-source Linux operating system
for repurposing old Android phones and tablets as dedicated e-readers.

The architectural specification in `ARCHITECTURE.md` is the primary source
of truth.

## Current Phase

The project is currently in Phase 1 — Proof of Concept.

Phase 1 must produce a minimal executable development system and establish
the first implementation of the EReader Shell architecture.

## Development Principles

1. Follow `ARCHITECTURE.md`.
2. Do not silently change architectural decisions.
3. Do not introduce dependencies without justification.
4. Prefer existing mature open-source components over reimplementations.
5. Keep device-specific code inside `devices/`.
6. Keep the Core device-independent.
7. Keep the EReader Shell thin.
8. Treat KOReader as an external reader engine.
9. Do not create a new EPUB/PDF rendering engine.
10. Do not create a general desktop environment.
11. Do not add telemetry, accounts, advertising, or cloud requirements.
12. Networking must remain optional and explicit.
13. Do not implement cellular, GPS, camera, Bluetooth, or other unnecessary
    smartphone functionality for the MVP.
14. Do not perform hardware experiments or invent measurements unless the
    task explicitly requires them.
15. Never fabricate hardware capabilities or kernel support.

## Device Policy

The initial target device is the Samsung Galaxy J2 Core.

Device-specific assumptions must be documented in:

`devices/samsung-j2core/`

Do not assume that the Galaxy J2 Core can boot Alpine Linux directly.

Bootloader, kernel, device tree, firmware, display, touchscreen and storage
support must be established from evidence before implementation depends on them.

## Shell

The EReader Shell is a thin system UI.

The Shell is responsible for:

- boot/initial state
- library navigation
- launching KOReader
- settings
- network controls
- update controls
- device information
- recovery entry points

The Shell is NOT responsible for:

- EPUB rendering
- PDF rendering
- implementing a document engine
- maintaining a second independent book database
- general application management

## KOReader

KOReader is the primary reading engine.

Do not fork or rewrite KOReader unless explicitly required.

Prefer integration and upstream-compatible changes.

## Testing

Every implementation task should add or update tests where practical.

Before declaring a task complete:

- run the project's available tests
- run static analysis where configured
- verify that documentation matches implementation
- report failures explicitly

Never claim a test passed if it was not actually executed.

## Git

Prefer small, focused commits.

Do not rewrite unrelated files.

Do not modify architectural decisions without creating or updating an ADR.

## Agent Behavior

Before making a substantial architectural change:

1. inspect the existing repository;
2. inspect `ARCHITECTURE.md`;
3. identify affected components;
4. explain the proposed approach;
5. implement the smallest viable change;
6. test it;
7. summarize changed files and remaining risks.

Do not ask the user to perform work that the agent can safely perform itself.
