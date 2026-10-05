# Alpine-EReader-OS

> A minimal, private, open-source Linux operating system for turning old Android phones and tablets into dedicated e-readers.

Alpine EReader OS repurposes aging mobile hardware into simple reading appliances.

The goal is deliberately narrow:

```text

Power on → Library → Book → Read → Suspend → Resume → Power off

No app ecosystem.
No advertising.
No mandatory accounts.
No telemetry.
No unnecessary background services.

The operating system should disappear and let the device become an e-reader.

Project Status

Current phase: Phase 0 — Architecture

The architecture has been defined, but implementation has not yet begun.

The next development stage is Phase 1 — Proof of Concept, focused on bringing the system up on the initial pilot device and validating the architecture on real hardware.

The current architecture specification intentionally contains no implementation code, build scripts, or installation commands. See:

docs/architecture/ — system architecture
docs/development/ — development documentation
docs/devices/ — device-specific documentation
What Is Alpine EReader OS?

Alpine EReader OS is a Linux-based operating system designed specifically for repurposing obsolete or unsupported Android hardware as dedicated reading devices.

Instead of attempting to create another general-purpose Linux phone operating system, the project deliberately reduces the problem to one primary task:

reading books.

This narrow scope allows the system to eliminate large parts of the complexity normally associated with smartphones:

no mobile application ecosystem
no cellular functionality
no GPS
no camera stack
no notification system
no background application model
no mandatory cloud services
no mandatory network connectivity

The result should behave more like an appliance than a conventional computer.

Why?

Many old phones remain perfectly usable as computing hardware long after their manufacturers stop providing meaningful software support.

A working screen, CPU, storage and battery do not suddenly become useless because Android has become obsolete.

Alpine EReader OS attempts to give that hardware a second life.

The project combines:

Alpine Linux as the minimal userspace foundation
Existing Linux-on-mobile ecosystems for device enablement
KOReader as the reading and library engine
A small custom EReader Shell
A device-independent Core
Per-device Device Ports
A deliberately constrained power and networking model
Signed, rollback-capable system updates

The project therefore focuses original engineering effort where it provides the most value instead of reinventing mature software.

Core Principles
1. The OS should be invisible

A non-technical user should not need to understand Linux, kernels, package managers or bootloaders to use the finished device.

2. Reuse before rewrite

Existing, mature open-source components should be used whenever they adequately solve the problem.

The project should not build a new EPUB engine, PDF engine, Wi-Fi stack or general-purpose compositor merely for the privilege of maintaining one more implementation.

3. Read-only by default

The operating system is immutable during normal operation.

System files are replaced through controlled image updates, while user data remains persistent.

4. Radios are opt-in

Wi-Fi and other radios are disabled by default.

Network access exists for explicit operations such as:

downloading books
browsing OPDS catalogs
checking for updates
optional synchronization

Reading itself does not require networking.

5. One visible thing at a time

There is no desktop environment.

The UI is designed around a single full-screen surface and a simple navigation stack.

6. Failures must be recoverable

Updates, storage corruption and other failures should not permanently strand the device.

Recovery and rollback are architectural requirements, not afterthoughts.

7. Devices are heterogeneous; the Core is not

Hardware-specific code belongs in a Device Port.

The operating-system Core should remain shared across supported devices.

Architecture
                         ┌──────────────────────────┐
                         │       DEVICE PORT         │
                         │                          │
                         │ Kernel                   │
                         │ Device Tree              │
                         │ Firmware                 │
                         │ Hardware configuration   │
                         └────────────┬─────────────┘
                                      │
                                      ▼
Hardware
   │
   ▼
Bootloader
   │
   ▼
Linux Kernel
   │
   ▼
OpenRC
   │
   ▼
┌──────────────────────────────────────────────────────┐
│                       CORE                           │
│                                                      │
│  powerd       network policy       update system     │
│                                                      │
│  storage       security           system services    │
└─────────────────────────┬────────────────────────────┘
                          │
                          ▼
                 Display / Input
                          │
                          ▼
                 EReader Shell
                          │
                          ▼
                    KOReader
                          │
                          ▼
                    User Data

The architecture separates the system into two major domains:

Core

Shared, device-independent functionality:

Alpine userspace
OpenRC
power management
network policy
update management
storage model
security controls
EReader Shell
Device Port

Hardware-specific functionality:

kernel
device tree
firmware
boot configuration
hardware quirks
recovery mechanism
device-specific documentation

Adding a new device should therefore mean creating a new Device Port rather than rewriting the operating system.

Reader Engine

Alpine EReader OS does not intend to develop a new reading engine.

The current architecture adopts KOReader as the primary reading, library and OPDS component.

KOReader already provides mature support for:

EPUB
PDF
plain text
multiple additional document formats
annotations
bookmarks
dictionary lookup
reading statistics
library functionality
OPDS catalogs
embedded-device reading workflows

The Alpine EReader OS project provides the operating-system environment and a thin UI layer around it.

This keeps the project focused on the parts that are actually unique.

Process isolation

KOReader is treated as a separate process rather than being directly linked into the EReader Shell.

This provides:

a cleaner security boundary
a cleaner licensing boundary
reduced coupling
easier upstream tracking
less incentive to maintain a permanent KOReader fork

Where possible, improvements should be contributed upstream rather than maintained as private modifications.

Pilot Device

The initial hardware target is:

Samsung Galaxy J2 Core

Target characteristics include:

Component	Pilot hardware
SoC	Samsung Exynos 7570
CPU	4× ARM Cortex-A53
RAM	1 GB
Display	5", 540×960 LCD
Storage	8–16 GB eMMC
Battery	2600 mAh removable
GPU	Mali-T720 MP1

The J2 Core is not intended to be the only supported device.

It is the first engineering target because it provides a constrained, realistic environment in which the architecture can be validated.

The 1 GB RAM constraint is particularly important: architectural decisions must be evaluated against low-memory hardware rather than desktop assumptions.

Device Support

Every supported device receives a Device Profile.

A Device Profile records information such as:

manufacturer and model
device codename
regional variants
SoC
RAM and storage
display characteristics
battery characteristics
kernel strategy
bootloader requirements
firmware requirements
partition layout
recovery procedure
known hardware limitations
support tier
maintainer
Support Tiers
🟢 Certified

The device has passed the project's full hardware test matrix and has an active maintainer.

🟡 Experimental

The device boots and provides core reading functionality, but one or more areas remain unreliable or insufficiently validated.

🔴 Unsupported

The device has no viable known path forward, has failed previous investigation, or does not meet the project's hardware requirements.

Unsupported is an intentional status.

The project would rather say "this device cannot currently be supported" than encourage users to brick hardware based on wishful thinking.

Power Management

Power management is a first-class subsystem.

The system defines explicit states:

ACTIVE
   ↓
READING
   ↓
IDLE
   ↓
SUSPEND
   ↓
RESUME

Additional battery states include:

LOW BATTERY
CRITICAL BATTERY
SHUTDOWN

During normal reading:

Wi-Fi is disabled
Bluetooth is disabled
GPS is disabled
cellular modem is disabled
unnecessary background processes are absent
rendering occurs only when required

A dedicated powerd component owns this policy.

LCD reality

The project does not claim that an LCD phone can achieve Kindle-like reading battery life.

E-Ink is bistable; LCD is not.

An LCD requires continuous power while displaying a readable image, especially because of its backlight.

Therefore the realistic optimization target is:

dramatically better standby behavior and lower system overhead, not magical LCD physics.

No battery-life number will be published until it has been measured using the project's defined methodology.

Privacy

Privacy is an architectural property.

The default system provides:

zero mandatory telemetry
zero advertising
zero mandatory accounts
zero cloud dependency
offline-first operation
network access only when explicitly requested

Reading statistics may exist locally, but the default system has no telemetry pipeline for sending reading behavior, book titles, location or personal identifiers elsewhere.

Security

The system is designed around several security boundaries.

Immutable system

The normal system environment is read-only.

Signed images

Installation and update artifacts must be cryptographically verified.

Rollback

A failed update must leave the device with a known-good boot path whenever the device's boot architecture permits it.

Sandboxed reader

KOReader processes untrusted document files and therefore receives restricted privileges and filesystem/network access.

Radio isolation

Applications cannot arbitrarily enable radios while the device is in the READING state.

Anti-downgrade

The update system should prevent unauthorized installation of older vulnerable system images.

Encryption

Full-disk encryption is not required for MVP.

This is a deliberate trade-off: mandatory authentication would conflict with the project's frictionless suspend/resume model.

Optional encryption remains a future possibility.

Networking

Networking is intentionally boring.

That is a feature.

The system does not run an always-connected desktop networking stack.

Wi-Fi is activated only when required.

Potential network functionality includes:

OPDS catalogs
book downloads
system updates
optional synchronization

Reading itself remains completely functional with Wi-Fi permanently disabled.

OPDS

OPDS is the primary catalog protocol.

The intended flow is:

Open Catalogs
      ↓
Enable Wi-Fi
      ↓
Browse OPDS catalog
      ↓
Select book
      ↓
Download
      ↓
Verify
      ↓
Add to library
      ↓
Disable Wi-Fi

The project intends to reuse KOReader's existing OPDS implementation rather than develop a new protocol client unless a concrete gap appears.

Storage Model

The system separates immutable system state from persistent user state.

System
├── Kernel
├── Core userspace
├── EReader Shell
├── KOReader
└── System configuration

User Data
├── Books/
├── Documents/
├── Notes/
├── Dictionary/
└── Config/

A book copied into:

Books/

should automatically appear in the library.

The user should not need an explicit import operation.

User Experience

The interface is deliberately minimal.

Primary screens include:

Library
Reader
Catalogs
Search
Settings
Dictionary
Annotations
Device Info
Update

There is no:

notification center
conventional launcher
desktop
app drawer
persistent multitasking UI
decorative animation

The visual language is intended to be:

calm
high contrast
textual
minimal
readable
responsive
low-power

Physical buttons are preferred for navigation where available.

Accessibility

Initial accessibility priorities include:

adjustable font size
high-contrast themes
physical-button navigation
dyslexia-friendly typography
text-to-speech

A full desktop-style screen-reader stack is a later-phase goal rather than an MVP requirement.

Updates

System updates are image-based rather than ordinary package upgrades.

The intended update model provides:

Download
   ↓
Verify signature
   ↓
Stage new image
   ↓
Preserve user data
   ↓
Boot new system
   ↓
Health check
   ↓
Success → keep
   │
   └── Failure → rollback

The exact storage/update implementation is device-dependent and must be validated on real hardware.

apk upgrade alone is not considered sufficient for the project's atomic-update requirement.

Recovery

A supported device should eventually have an independent recovery environment capable of:

reinstalling the system
rolling back to a previous deployment
running basic hardware diagnostics
collecting logs
restoring supported configuration data

Recovery should remain accessible even when the main system cannot boot, subject to the capabilities of the device boot chain.

Installation

The long-term goal is a cross-platform graphical installer for:

Windows
Linux
macOS

The installer should:

Detect the device.
Identify its exact model/codename.
Check its support tier.
Explain any bootloader requirements.
Back up accessible user data where possible.
Require explicit confirmation before destructive operations.
Flash the appropriate signed image.
Verify the installation.
Start the device into first boot.

The installer will not pretend that every Android device has the same bootloader process.

OEM unlocking procedures vary substantially between manufacturers and device generations.

DRM

Alpine EReader OS does not implement DRM circumvention.

The MVP supports non-DRM content.

Readium LCP is identified in the architecture as a possible future protected-content technology because it is an open, standardized system, but it is not part of the MVP.

Development Roadmap
Phase	Objective
0	Architecture
1	Proof of Concept
2	Minimal EReader
3	Library
4	Reader UX
5	Power validation
6	Graphical installer
7	Additional devices
8	Certified devices
Phase 0 — Architecture

Current phase.

Deliverable:

reviewed system architecture
defined Core/Device-Port boundary
defined MVP
defined development roadmap
Phase 1 — Proof of Concept

First implementation phase.

The immediate objective is to establish that the fundamental stack can work on the pilot hardware:

Boot
 ↓
Linux
 ↓
Minimal userspace
 ↓
Display
 ↓
KOReader
 ↓
Open a book

This phase resolves the architecture's hardware-dependent hypotheses on real hardware.

Phase 2 — Minimal EReader

Build the first actual system components:

powerd
system/user-data separation
basic Shell
reliable reading
progress persistence
suspend/resume
Phase 3 — Library

Build the dedicated library experience:

book discovery
automatic indexing
covers
metadata
navigation
Phase 4 — Reader UX

Integrate KOReader into the final appliance experience:

first-run flow
simplified settings
dictionary
annotations
reader navigation
visual polish
Phase 5 — Power

Validate the power architecture on physical hardware and publish reproducible measurements.

Phase 6 — Installer

Create the user-facing graphical installation workflow.

Phase 7 — Additional Devices

Port the system to additional hardware without modifying the Core architecture.

This is the first real test of whether the Core/Device-Port separation was designed correctly.

Phase 8 — Certification

Establish the first fully certified devices with:

complete test coverage
update/rollback validation
recovery validation
power validation
security validation
named maintainers
Repository Structure

The intended repository structure is:

alpine-ereader-os/
│
├── core/
│   ├── powerd/
│   ├── network/
│   ├── update/
│   └── ...
│
├── shell/
│
├── devices/
│   ├── <device-codename>/
│   └── ...
│
├── build/
│
├── tests/
│
├── docs/
│   ├── architecture/
│   ├── installation/
│   ├── devices/
│   ├── development/
│   ├── security/
│   ├── power/
│   ├── reader/
│   ├── contributing/
│   ├── recovery/
│   └── licensing/
│
├── LICENSE
├── README.md
└── ...

The architecture specification remains the authoritative source for detailed system decisions.

Design Philosophy

The project intentionally avoids building large amounts of original software.

The expected strategy is:

Problem	Approach
Linux userspace	Alpine Linux
Service supervision	OpenRC
Device enablement	Existing Linux-on-phone ecosystem
Reader engine	KOReader
Wi-Fi association	iwd / wpa_supplicant
IPC	D-Bus
Display	DRM/KMS by default
UI	Thin custom EReader Shell
Power policy	Custom powerd
Device abstraction	Device Profiles / Device Ports
Updates	Signed image-based system
Recovery	Device-specific recovery environment

The philosophy is simple:

Build only what the project uniquely needs. Reuse everything else.

What Alpine EReader OS Is Not

Alpine EReader OS is not intended to become:

a general-purpose smartphone OS
an Android replacement
a desktop Linux distribution
an app platform
an e-book marketplace
a DRM circumvention platform
an E-Ink-only operating system
a custom Linux kernel project
a custom PDF/EPUB engine

There are already projects better suited to those goals.

This project exists specifically because a single-purpose Linux reading appliance is a much smaller and more tractable problem.

Contributing

The project uses the architecture specification's decision format as the basis for future architectural discussions:

Decision
Options
Trade-offs
Recommendation
Reasoning

Major architectural changes should be documented rather than silently introduced.

Device-specific responsibility should remain separated from Core responsibility.

A device maintainer should be able to maintain:

devices/<codename>/

without requiring unrestricted control over the entire operating system.

License

The final repository licensing structure follows the architecture specification and the licenses of its dependencies.

In particular:

KOReader remains AGPL-3.0
modifications to KOReader must comply with its license
project documentation uses CC-BY-SA-4.0
third-party components retain their respective licenses

See docs/licensing/ for the current dependency and licensing inventory.

Current Priorities

The project is currently not trying to build the entire operating system.

The immediate priority is much narrower:

Phase 0
   ↓
Phase 1
   ↓
Boot the pilot hardware
   ↓
Bring up Linux
   ↓
Run KOReader
   ↓
Open a book

Everything else comes afterward.

The architecture deliberately postpones:

graphical installation
synchronization
OPDS
polished recovery
multi-device support
certification
power-life claims

until the fundamental hardware/software path has been demonstrated.

Documentation

The main architecture specification is:

docs/architecture/system-architecture.md

It contains the detailed decisions behind:

system architecture
device ports
boot
kernel strategy
graphics
reader integration
storage
networking
power management
updates
recovery
installation
security
privacy
accessibility
testing
CI/CD
governance
licensing
roadmap

This README is intentionally a project-level overview rather than a replacement for that specification.

Vision

Alpine EReader OS is ultimately trying to turn this:

Old Android phone
       +
obsolete software
       +
unused hardware

into this:

┌───────────────────────────────┐
│                               │
│          MY LIBRARY            │
│                               │
│   1984                        │
│   The Republic                │
│   Foundation                  │
│   ...                         │
│                               │
└───────────────────────────────┘

             ↓

          READ

             ↓

          SLEEP

             ↓

          RESUME

A computer that does almost nothing.

And therefore does the one thing it was built to do extremely well.

Alpine EReader OS — Phase 0 Architecture

The operating system should disappear.
