# Alpine EReader OS — System Architecture Specification

**Document status:** Phase 0 — Architecture. No implementation code, build scripts, or shell commands are included, per project instructions. This document is written to be handed to an engineering team as a basis for Phase 1 (Proof of Concept).

**Notation used throughout this document:**

| Tag | Meaning |
|---|---|
| **[FACT]** | Externally verifiable, checked against current sources at time of writing (Aug 2026) |
| **[DECISION]** | An architectural choice this document is making, with reasoning |
| **[HYPOTHESIS]** | A claim believed true but not yet validated on real hardware |
| **[RECOMMENDATION]** | A suggested direction, open to revision by the team |
| **[REQUIREMENT]** | Something the system must satisfy |
| **[RISK]** | A known danger to the project, with mitigation |

---

## 1. Executive Summary

Alpine EReader OS is a Linux-based operating system designed to turn old mobile hardware into simple, private, energy-efficient, open-source reading devices.

The central engineering problem this document resolves is **not** "how do we build an e-reader application" — mature, best-in-class open-source reading software already exists. The central problem is: **how do we get a minimal, atomically-updatable, privacy-respecting Linux system to boot reliably on a fleet of Android phones and tablets that were never designed to run anything but Android**, and then get out of the way so the device behaves like an appliance rather than a computer.

**[DECISION]** This document recommends that Alpine EReader OS be understood as two separable things wearing one name:

1. A **composition and update methodology** inherited from Alpine — bootable OCI containers (`the image-update mechanism`), `the image-build pipeline`/Image Builder, and the the selected image-update mechanism read-only-`/usr` model — used to assemble, sign, ship, and atomically update device images.
2. A **device-porting strategy** borrowed from the existing Linux-on-phones ecosystem (postmarketOS's device-port model, and Halium/libhybris where a device has no mainline kernel path), because a conventional desktop/server distribution alone does not solve ARM phone SoC support and re-deriving that work from scratch would consume the entire project.

The reading application layer should not be built from scratch either. **[RECOMMENDATION]** KOReader — a mature, AGPLv3, actively maintained (2019–2026, still shipping monthly releases as of this writing) e-reader application that already implements a reader engine, library view, OPDS client, dictionary lookup, annotation system, and power-aware behavior for embedded ARM Linux devices — is the strongest starting point for the "EReader Shell + Reader Engine + Library + Catalog" layers of the stack, adopted as a process-isolated component rather than rebuilt in parallel. This is a significant deviation from treating each of those layers as bespoke subsystems to design from zero, and it is treated as such throughout this document.

The rest of this document works through the architecture layer by layer, device support strategy, installer design, power management, security, licensing, repository layout, and a phased roadmap starting from a single pilot device (Samsung Galaxy J2 Core, 2018/2020, Exynos 7570, 1 GB RAM).

---

## 2. Vision

Old Android phones and tablets accumulate in drawers because their manufacturers stop updating them long before the hardware is actually dead. A phone with a working screen, a working battery, and a working CPU is discarded not because it can't function, but because its software has become unsafe, unsupported, or simply unpleasant to use.

Alpine EReader OS reclaims that hardware for a single, narrow purpose: reading. Not browsing, not messaging, not running apps — reading. In exchange for that narrowness, the system can be dramatically simpler, safer, and more power-efficient than the general-purpose smartphone OS it replaces.

The target experience is an appliance, not a computer:

```
Power on → Library → Book → Read → Suspend → Resume → Power off
```

A user who has never heard the word "Linux" should be able to own and operate this device for years without ever needing to. The operating system's job is to disappear.

**[FACT]** This vision has real precedent: postmarketOS already runs mainline-oriented Linux distributions on several hundred discontinued Android devices, explicitly framing its mission around device longevity, user control, and rejecting vendor-mandated obsolescence. Alpine EReader OS narrows that same underlying idea (Linux on repurposed phones) to a single application domain, which is what makes the scope tractable for a small project.

---

## 3. Goals

**[REQUIREMENT]** The system must, at minimum:

- Boot into a reading-focused interface on supported ARM Android hardware, with the original Android system replaced (not dual-booted, not virtualized).
- Open and render EPUB, PDF, and plain text at MVP; expand format coverage afterward.
- Persist reading progress, bookmarks, and highlights across power cycles.
- Function completely offline, with networking as an explicit, user-initiated, time-boxed exception.
- Ship zero mandatory telemetry, zero mandatory accounts, and zero advertising.
- Update atomically, with rollback, without requiring a terminal.
- Be installable by a non-technical user through a guided graphical tool for every device where the manufacturer permits it.
- Run acceptably within 1 GB of RAM (the pilot device's ceiling) and comfortably above that on more capable hardware.
- Be built overwhelmingly from existing, actively-maintained open-source components, minimizing original code.
- Support the addition of new devices through a bounded, documented "device port" process rather than a rewrite.

---

## 4. Non-Goals

**[DECISION]** The following are explicitly out of scope, and treated as anti-goals if pursued:

- **Not a general-purpose Linux phone.** No app ecosystem, no launcher paradigm, no ambition to replace Android as a daily-driver smartphone OS. postmarketOS, Ubuntu Touch/UBports, and Mobian already occupy that space and are not being competed with.
- **Not a DRM-capable reading platform.** No Adobe ADEPT, no Amazon proprietary DRM, no circumvention of either. See §27.
- **Not a bookstore.** No payment processing, no first-party marketplace, no curated commercial catalog. Book acquisition is delegated to OPDS catalogs, user-supplied files, and optional third-party applications the user chooses to install.
- **Not a universal installer for every Android device on day one.** Bootloader unlock policy is fragmented across OEMs by design (see §24); the project will not claim a capability it cannot deliver.
- **Not an E-Ink product at MVP.** The pilot and near-term device set are LCD panels. E-Ink support is a later, hardware-dependent expansion (§20, §37).
- **Not a vehicle for reinventing solved problems.** No custom kernel, no custom EPUB/PDF rendering engine, no custom compositor unless a concrete gap is found in existing options.

---

## 5. Requirements

Organized by category; each is tagged for priority weight where the distinction matters for scoping the MVP (§43).

**Functional**
- **[REQUIREMENT]** Render EPUB (reflowable) and PDF (fixed-layout) correctly, including embedded fonts and basic CSS for EPUB.
- **[REQUIREMENT]** Track and restore reading position per book, addressable to sub-page granularity for reflowable formats.
- **[REQUIREMENT]** Import books by filesystem copy (USB-MTP or SD card) with automatic library detection — no companion desktop app required.
- **[RECOMMENDATION]** Support OPDS catalog browsing and download once Wi-Fi is explicitly enabled by the user.

**Non-functional**
- **[REQUIREMENT]** No process may make outbound network connections while the device is in the `READING` power state (§21).
- **[REQUIREMENT]** System partition is read-only in normal operation; only a defined user-data area is writable.
- **[REQUIREMENT]** A failed update must never leave the device unable to boot into *some* working state (either the previous deployment or a recovery image).
- **[REQUIREMENT]** All update and install artifacts are cryptographically signed and verified before being applied.

**Constraints**
- **[FACT]** The pilot device (Galaxy J2 Core) has 1 GB RAM, an Exynos 7570 Quad (4× Cortex-A53 @ 1.4 GHz), Mali-T720 MP1 GPU, 8–16 GB eMMC storage (roughly 4 GB free after the stock OS, though Alpine EReader OS will reclaim most of this by removing Android entirely), a 5″ 540×960 TFT/PLS LCD, and a *removable* 2600 mAh Li-ion battery — removable batteries are increasingly rare in this device class and matter for power-instrumentation work (§37) and for safe long-term storage of decommissioned units.
- **[REQUIREMENT]** Every architectural choice must be evaluated first against "does this fit in ~1 GB RAM," not against desktop-class assumptions.

---

## 6. Design Principles

1. **The OS should be invisible.** Every design decision is filtered through "does a non-technical user ever need to know this exists?"
2. **Reuse before rewrite.** Original code is a liability (maintenance burden, security surface, review burden). It is justified only where no adequate open-source component exists.
3. **Read-only by default.** The system tree is immutable in normal operation; only explicit, audited user data is writable. This is a security property and an update-safety property simultaneously.
4. **Radios are opt-in, not ambient.** Wi-Fi, Bluetooth, GPS, and cellular modems default to *off* and are enabled only for the specific task that needs them, for the shortest useful duration.
5. **One visible thing at a time.** The UI shows exactly one full-screen surface. There is no multitasking model to design, secure, or explain.
6. **Failure must be survivable without a PC.** Every failure mode (bad update, corrupted library DB, bricked-looking boot) must have an on-device recovery path.
7. **Devices are heterogeneous; the core is not.** A hard boundary separates code that is the same on every device from code that is device-specific (§13).
8. **Prefer physical buttons and gestures over always-on touch polling** where the hardware has them, both for battery and for accessibility.
9. **Every non-obvious technical decision in this document is labeled and justified**, per the project's own instruction, so a future contributor can see *why*, not just *what*.


---

## 7. High-Level Architecture

The layered diagram proposed in the brief is a reasonable starting sketch, but it conflates two different kinds of layering: a **boot/privilege layering** (what starts first, what runs as root) and a **build-time composition layering** (what's assembled into the image vs. what's device-specific). Separating these makes the device-port problem (§13) tractable. The revised model:

```
                    ┌─────────────────────────────────────┐
                    │           DEVICE PORT                │
                    │  (per-device: kernel/BSP, bootloader  │
                    │   glue, firmware blobs, calibration)  │
                    └───────────────┬───────────────────────┘
                                    │  device.info + kernel + DT/blobs
                                    ▼
Hardware → Bootloader → Linux Kernel → udev/OpenRC → CORE (device-agnostic)
                                                          │
                    ┌─────────────────────────────────────┼─────────────────────┐
                    ▼                                     ▼                     ▼
              powerd (state machine)              networkd (radio gate)   updated (the image-update mechanism client)
                    │                                     │                     │
                    └─────────────────┬───────────────────┴─────────────────────┘
                                      ▼
                          Display stack (DRM/KMS, no compositor
                          unless the reader backend requires one)
                                      │
                                      ▼
                        EReader Shell (thin, custom, first-boot +
                        settings + library launcher UI)
                                      │
                                      ▼
                   Reader / Library / OPDS engine (KOReader, process-isolated)
                                      │
                                      ▼
                          /var/lib/ereader (user data: books,
                          library DB, progress, settings)
```

**[DECISION]** The "CORE" band is identical across every certified device. Everything above the horizontal line that separates it from "DEVICE PORT" is compiled once and shipped as a base OCI image layer; everything below is per-device and layered on top at image-build time (§33). This is the single most important structural decision in this document, because it is what makes "support N devices" a linear cost instead of an N-way rewrite.

For each layer: responsibility, interfaces, and substitutability are detailed in §8–§32. At a glance:

| Layer | Responsibility | Can be swapped later? |
|---|---|---|
| Bootloader | Verify and load kernel | No — fixed by hardware vendor |
| Kernel + Device Port | Hardware enablement | Per-device, yes — new ports added without touching Core |
| Core userspace | OpenRC, powerd, networkd, updated, storage | No — this is the product |
| Display stack | Get pixels on screen | Yes — DRM/KMS direct render vs. Weston kiosk-shell (§14) |
| EReader Shell | First boot, settings, library launcher chrome | Yes — thin and disposable by design |
| Reader/Library/OPDS engine | Actual reading experience | In principle yes, in practice KOReader for the foreseeable roadmap |

---

## 8. Component Architecture

**[DECISION]** Minimizing the number of distinct long-running processes is a stated goal (§6, §38). The proposed component set:

| Component | Type | Privilege | Rationale |
|---|---|---|---|
| `powerd` | daemon | root (needs CPU governor, radio, display control) | Owns the power state machine (§21) |
| `networkd` | daemon (thin wrapper, not a reimplementation) | root (interface control) + unprivileged worker for downloads | Radio gating + OPDS/download client |
| `updated` | daemon (Alpine image-update mechanism under a thin policy wrapper) | root | Update orchestration, signature verification, rollback |
| `library-svc` | daemon or library, TBD in PoC (§35, §36) | unprivileged, user-data group only | Owns the SQLite library DB, exposes it over IPC (§31) so the shell and the reader agree on one source of truth |
| EReader Shell | application | unprivileged | First boot, settings, library browsing UI, launches the reader |
| KOReader (reader/library/OPDS engine) | application, launched per-book or persistent | unprivileged, sandboxed (§25) | Rendering, in-book navigation, dictionary, annotations |
| Recovery agent | runs only in recovery mode, separate image | root, recovery-image-only | Reflash, log collection, diagnostics (§23) |

**[OPEN QUESTION, resolved provisionally]** Should `library-svc` be a separate daemon, or should KOReader's own SQLite-backed history/statistics database simply *be* the library, with the EReader Shell reading it directly? KOReader already tracks per-book state. Introducing a second, competing database (Core's `library-svc`) risks divergence between "what the shell shows" and "what the reader has open." **[RECOMMENDATION]** Prototype without a separate `library-svc` in Phase 1–2: let the Shell read KOReader's own database read-only for the library grid, and revisit only if a concrete need appears (multi-format catalog metadata KOReader doesn't track, cross-device sync reconciliation, etc.). This removes an entire component and its associated IPC surface from the MVP.

---

## 9. Linux/Alpine Base

**[DECISION]** Alpine Linux is the selected base distribution. Its small footprint, `apk` package manager, musl-based userspace, and BusyBox-oriented minimal system are aligned with a single-purpose e-reader. This choice does **not** itself solve device support, reliable updates, or power management.

**[DECISION]** Use Alpine packages and repositories for the base userspace wherever compatible. Validate every required dependency against musl; where software assumes glibc, prefer an upstream-compatible build or a narrowly scoped compatibility solution rather than introducing a broad second userspace without a demonstrated need. KOReader, graphics libraries, input/display stack, and hardware utilities must be tested on the target architecture and device.

**[DECISION]** Use OpenRC for service supervision and boot-time service orchestration. Replace systemd-specific units, `sd_notify`, socket activation, and systemd sandbox directives with OpenRC-compatible service definitions and independently validated Linux security mechanisms. D-Bus remains an option for IPC, but its policy and privilege boundaries must be verified on the chosen Alpine packages.

**[REQUIREMENT]** Alpine EReader OS must implement a signed update design with integrity verification, staged installation, interrupted-update recovery, boot-health checks, and rollback. `apk upgrade` alone is not an atomic system-image update strategy. The implementation choice—read-only root with an A/B or recovery layout, snapshot-capable storage, or another tested design—must be made per device and documented. Do not describe updates as atomic until the end-to-end behavior has been demonstrated on hardware.

**[RISK]** Alpine's musl/BusyBox/OpenRC environment can expose assumptions in software and scripts written for glibc, GNU userland, or systemd. **Mitigation:** add compatibility checks to the Phase 1 proof of concept, keep the runtime dependency set small, and record any exceptions in the build manifest and Device Profile.

**[DECISION]** Device kernels, firmware, bootloader interaction, and device trees continue to come from the existing Linux-on-phones ecosystem where licensing and technical compatibility permit. Alpine is the userspace base, not a substitute for device-specific kernel bring-up.
---

## 10. Boot Architecture

**[REQUIREMENT]** Boot must reach the library screen with no user interaction beyond pressing power, in bounded time (target in §36).

Sequence: vendor first-stage bootloader (unmodified — this is not something the project can or should touch) → **[DECISION]** a signed second-stage boot artifact appropriate to the device's verification chain (this varies by SoC/OEM; see §13, §24 — there is no universal answer) → Linux kernel (device-port-specific, §13) → `OpenRC` as PID 1 → early services (`powerd` at minimum, before any radio is touched) → display stack up → EReader Shell starts full-screen → Shell checks for a "resume" state (was the device merely suspended, not powered off?) and if so hands off directly to the last-open book.

**[DECISION]** Boot splash: a static image, not an animation. Animated boot splashes cost CPU/GPU cycles and battery for zero functional value on a device whose entire purpose is minimizing motion on screen (§20, §41).

**[RISK]** Devices with a vendor "recovery partition expectation" baked into the bootloader (i.e., the bootloader will refuse to continue, or will show a scary vendor warning screen, if it detects a non-stock boot image) — this is common and is a per-device documentation matter (part of the Device Profile, §13), not something the Core can paper over.

---

## 11. Kernel Architecture

**[DECISION]** No custom kernel is written. Three sourcing strategies, chosen per device (recorded in that device's Device Profile, §13):

1. **Mainline or near-mainline kernel**, when the SoC has upstream support. **[FACT]** postmarketOS has been actively moving toward a *generic* mainline kernel image (one kernel binary + per-device Device Tree Blobs) rather than fully bespoke per-device kernels, specifically to reduce the device-support maintenance burden — this is the same trade Alpine EReader OS should make, and the same real-world precedent justifies it.
2. **Vendor downstream kernel, used as-is**, when no mainline path exists but the vendor source is available (common for MediaTek/Exynos/older Snapdragon phones sold in markets where GPL kernel-source disclosure is enforced). Loses long-term upstream security fixes; gains "it boots at all."
3. **Vendor kernel + libhybris/Halium HAL bridge**, when hardware needs Android's own binary-blob drivers (GPU, in particular) to function and cannot reasonably be replaced. **[FACT]** Halium/libhybris is an actively maintained (commits as recent as July 2026) open-source bridge that lets a glibc-based userspace call into an unmodified Android vendor kernel's bionic-based HAL drivers; it is the same mechanism UBports/Ubuntu Touch relies on for its widest device coverage.

**[RECOMMENDATION]** Because Alpine EReader OS deliberately does **not** need camera, cellular modem, or GPS (§5, §17) — which are, by a wide margin, the hardest subsystems to get working on any Linux-on-phone project, mainline or Halium alike, because ISP and modem firmware are the least likely to ever be documented or upstreamed — this project's kernel-porting problem is structurally easier than a general-purpose Linux phone project. It only needs: display, touch, storage, Wi-Fi (togglable, not always-on), battery/PMIC reporting, and basic input (buttons). This should be stated plainly to contributors: **the hardest 20% of phone porting is exactly the 20% this project doesn't need.**

**[DECISION]** Kernel version policy: track whatever the chosen sourcing strategy provides; do not attempt to forward-port or backport security patches onto a frozen vendor kernel as a general practice — that is a maintenance trap for a small project. Document known-CVE exposure per device in its Device Profile instead (§25, §34).

---

## 12. Hardware Abstraction

**[DECISION]** No general-purpose HAL abstraction library is built. This is deliberately narrower than a phone OS's HAL: Core code talks to the kernel through standard Linux subsystems that are themselves already the abstraction — `evdev` for input, DRM/KMS for display, `power_supply` class (sysfs) for battery/PMIC, `rfkill` for radio enable/disable, ALSA for the (optional, low-priority) audio path for TTS/accessibility. Device-specific quirks are handled by udev rules and kernel config shipped in the Device Port, not by a new abstraction layer.

**[REQUIREMENT]** Every subsystem the device physically has but the product does not use — camera, cellular modem, GPS, Bluetooth, NFC, fingerprint sensor — must be reachable but **disabled by default** at the kernel/udev level (module blacklist or `rfkill block`), not merely unused by userspace. This is a security and power property, not just a tidiness one (§19, §25).

**[FACT]** The pilot device's radio inventory: Wi-Fi 802.11 b/g/n, Bluetooth 4.2, GPS/A-GPS/GLONASS/BeiDou, and 4G LTE Cat4 modem. Of these, only Wi-Fi is a product requirement; the rest should be `rfkill`-blocked at boot and never surfaced in the UI.

---

## 13. Device Port Architecture

This is the section the brief correctly flags as critical, and it is where most of this project's real engineering risk lives.

### 13.1 The Device Profile

**[DECISION]** Every supported device is described by a structured **Device Profile**, versioned alongside its port in `devices/<codename>/` (§39). Conceptually (no schema/code at this stage), it records:

- Identity: manufacturer, model, market codenames/SKUs (a single retail model can have several — the J2 Core alone has at least four regional SM-J260x variants), SoC.
- Capabilities: RAM, storage, display resolution/panel type, battery capacity and whether it's removable, physical buttons available, radios present.
- Kernel strategy used (§11: mainline / vendor-downstream / Halium-bridged) and the kernel version/source pointer.
- Bootloader unlock method, or explicit "no known method" (§24).
- Boot chain specifics: what the bootloader expects, signature requirements, partition layout quirks.
- Firmware blob requirements (Wi-Fi, GPU) and their redistribution licensing status (§40).
- Known limitations (e.g., "touch has a dead zone in the bottom 4mm," "suspend/resume unreliable below 5% battery").
- Recovery method available for this specific device (§23).
- Support tier (§13.2) and named maintainer, if any.

### 13.2 Support Tier Classification

**[DECISION]** Three tiers, with concrete, checkable criteria — deliberately modeled on the precedent set by postmarketOS's own tiering, which as of its 2026 releases explicitly requires mainline-or-near-mainline kernel status as a documented condition for its top device tier:

| Tier | Criteria (all must hold) |
|---|---|
| 🟢 **GREEN / Certified** | Boots reliably across the full test matrix (§35: boot, suspend/resume, battery reporting accuracy, touch, storage integrity, recovery, update+rollback) for N consecutive nightly/beta builds without regression; has a named, responsive device maintainer; has a documented, non-destructive recovery path that doesn't require re-deriving unlock steps from scratch; ships on the stable update channel. |
| 🟡 **YELLOW / Experimental** | Boots and core reading functionality (library, open book, render, turn pages, save progress, suspend) works, but at least one subsystem is unreliable or unverified (commonly: battery percentage accuracy, suspend/resume edge cases, touch calibration); no maintainer commitment; beta/nightly channel only; users are told explicitly "usable, but don't rely on it as your only copy of anything." |
| 🔴 **RED / Unsupported** | Known-incompatible (no unlock path found after genuine investigation, SoC family lacks any viable kernel strategy, insufficient RAM/storage) **or** previously attempted and abandoned. Documented specifically so the next contributor doesn't repeat a known-dead-end investigation. This tier is a feature, not an omission — it protects users from bricking a device based on false hope. |

### 13.3 Adding a New Device

**[RECOMMENDATION]** The process a new device port should follow, at a conceptual level: (1) identify SoC family and check whether it already has an existing mainline or postmarketOS downstream kernel port to start from — reuse, don't re-derive; (2) determine bootloader unlock feasibility and document it honestly, including "unknown" or "no" (§24); (3) fill in a Device Profile from the template; (4) get the kernel booting to a serial/UART console before attempting display; (5) bring up display (DRM/KMS) and touch; (6) bring up battery/PMIC reporting and Wi-Fi `rfkill` control; (7) run the certification test suite (§35) to determine the honest tier; (8) submit as a device port PR with an assigned or volunteer maintainer.

**[RISK]** Step (2) is where most device attempts will die, and that is expected and fine — see §24 for why this cannot be smoothed over with better tooling.


---

## 14. Graphics Architecture

**[DECISION]** Question the premise before answering it. A Wayland compositor's entire job is compositing — arbitrating and blending *multiple* client surfaces. Alpine EReader OS, by design principle #5 (§6), only ever shows one full-screen surface. That means a general compositor may be solving a problem this system doesn't have.

| Option | Description | Trade-off |
|---|---|---|
| A. Direct DRM/KMS rendering, no compositor | The reader application owns the display directly (DRM master), similar to how embedded/kiosk applications commonly run via an `eglfs`/framebuffer-style backend | Fewest processes, smallest attack surface, lowest RAM/CPU — but the app is responsible for its own DRM handling, and multi-app scenarios (e.g., a system dialog over the reader) require in-app UI rather than window-manager compositing |
| B. Weston `kiosk-shell` | Weston's reference compositor ships a purpose-built shell (~2,000 LOC) explicitly designed for "one application/surface running full-screen" embedded use cases | Gets Wayland-protocol compatibility and DRM backend handling for free from a well-tested reference implementation, at the cost of one more long-running process and the general Wayland stack's dependency weight |
| C. Cage / Mir-kiosk | Other minimal kiosk-mode Wayland compositors with the same single-app philosophy | Similar trade-off to B, smaller communities |

**[DECISION]** Recommendation is **A for the reader/shell surface**, with **B (Weston kiosk-shell) held in reserve** as the fallback if KOReader's Linux backend (which historically uses SDL2/SDL3 on desktop builds and direct framebuffer on embedded e-readers, per its own build configuration) turns out to need a compositor's cooperation to run acceptably on the target kernel/GPU driver stack — this is a **[HYPOTHESIS]** to be resolved empirically in Phase 1 (PoC), not asserted here. Either way: no full desktop compositor (GNOME Shell, KDE Plasma, Sway) is ever in scope.

**[RECOMMENDATION]** Rendering policy regardless of backend chosen: full-screen redraws only on page turn or explicit UI action; no continuous frame pushing, no cursor blink, no idle animation loop. This is as much a power decision (§21) as a graphics one.

---

## 15. Reader Architecture

**Decision: reader engine strategy.**

| Option | Description | Trade-off |
|---|---|---|
| A. Compose from parts | Alpine EReader OS's own shell directly links/orchestrates separate libraries: MuPDF for PDF, a separate EPUB engine, a custom library manager, a custom OPDS client | Maximum design control; also maximum original-code surface, maximum integration risk, and re-derives things (annotation UX, dictionary lookup, statistics, gesture handling) that already exist and are mature elsewhere |
| B. Adopt KOReader wholesale, process-isolated, as the reading/library/OPDS engine; Alpine EReader OS provides the OS shell around it (boot, power, update, first-run, settings surface) | Inherits a decade of format-handling, typesetting, and embedded-device power-awareness work in one step | Less "designed by this project," some UI reskinning work needed to hit the calm/minimal aesthetic (§28) — KOReader's default UI is dense and power-user-oriented, though it is highly configurable and can hide most chrome during reading |
| C. Fork KOReader deeply | Same base as B, but maintain a divergent fork rather than configuring/patching upstream | More UI control; loses easy upstream tracking and puts the project on the hook for security patching a fork of a document-parsing codebase — a bad trade for a small team (§25 threat model) |

**[DECISION]** **Option B**, with the explicit understanding that KOReader's process boundary is also this project's primary security boundary (§25) and, not incidentally, its cleanest licensing boundary (§40). **[FACT]** KOReader is AGPL-3.0-only, portable across Cervantes, Kindle, Kobo, PocketBook, reMarkable, Android, and desktop Linux, natively multi-format (EPUB, PDF, DjVu, FB2, MOBI, CBZ/CBT, TXT, CHM, DOC via bundled `k2pdfopt` reflow for scanned documents), with a built-in OPDS client, dictionary lookup, gesture-based navigation, per-book statistics, and e-ink-aware rendering behavior it can also apply usefully on LCD (partial-region redraw minimization).

**[RECOMMENDATION]** Engineering work in this layer is therefore mostly: (1) packaging KOReader's Linux/framebuffer build inside the Core image; (2) building a thin, custom first-run and settings surface around it (§28) rather than exposing KOReader's full settings menu tree to a non-technical user; (3) upstreaming small patches where the project's needs diverge (e.g., a "launch directly into last book on resume" behavior) rather than forking.

**On MuPDF, Poppler, and Readium (the alternatives the brief asked to be evaluated):**

| Engine | License **[FACT]** | Role here |
|---|---|---|
| **MuPDF** | Dual: AGPL-3.0 or commercial (Artifex) | Already used *inside* KOReader for PDF; not something Alpine EReader OS needs to integrate separately |
| **Poppler** | GPL-2.0-or-later (a fork of Xpdf, which was GPL, not LGPL — anything linking it must itself be GPL) | Not selected; KOReader's MuPDF path covers PDF, and Poppler's GPL (rather than LGPL) linking requirement is more restrictive for no functional gain here |
| **Readium** (current generation — Readium Mobile/Desktop/Web) | BSD-3-Clause (all current Readium Foundation projects, since a full relicense from AGPL to BSD in Jan 2018) | Excellent, permissively-licensed toolkit — but it is a *toolkit for building* a reader, not a finished embedded-Linux reading application. Adopting it would mean building the library/OPDS/UI layers from scratch on top of it, which is exactly the "Option A" work this document recommends against. Worth revisiting only if the project later needs a from-scratch reader for a reason KOReader can't accommodate. |

**[HYPOTHESIS]** KOReader's memory footprint fits comfortably inside a 1 GB device once Android and its services are removed; this must be measured in Phase 1, not assumed — KOReader ships on Kindle/Kobo hardware with far less RAM than 1 GB, which is a strong signal but not a substitute for measuring it on this specific kernel/rootfs.

---

## 16. Library Architecture

**[DECISION]** Conceptual data model (no SQL yet, per instruction). Entities:

- **Book**: id, title, author(s), cover image reference, language, description/genre tags, series name + index, file path, file format, file hash (integrity + dedup), date added, file size.
- **ReadingState**: book_id (FK), progress position (format-specific — e.g. an EPUB CFI-like locator or a page number for fixed-layout), last-read timestamp, total time read (optional, local-only statistic, never transmitted anywhere by default).
- **Bookmark**: book_id (FK), position, optional user note, created timestamp.
- **Highlight**: book_id (FK), position range, highlighted text (stored locally), optional note, color/style.
- **Catalog**: user-added OPDS or other source endpoints (§18), display name, last-browsed state.
- **DeviceSettings**: font, theme, margins, and the handful of user-facing preferences (§28).

**[DECISION]** Per §8's resolution, this model is realized as KOReader's own on-device database/sidecar-file conventions rather than a second, competing schema, unless Phase 2 measurement shows a real gap (e.g., needing catalog metadata richer than KOReader tracks). If a gap does appear, the extension is additive — a companion table the Shell reads, not a replacement of KOReader's own state.

---

## 17. Storage Architecture

**[REQUIREMENT]** Clean separation between **read-only system** and **read-write user data** — and this maps directly onto the Alpine image-update tooling model already adopted in §9, rather than being a separate invention:

| Area | Contents | Mutability |
|---|---|---|
| System (the selected image-update mechanism-managed deployment) | Kernel, Core userspace, KOReader binary + assets, Shell binary | Read-only at runtime; changes only via an atomic, signed deployment (§22) |
| `/var` (persistent, the selected image-update mechanism convention) | Library database, book files, cover cache, user settings, logs, OPDS catalog cache, download staging | Read-write, survives updates, is exactly what gets backed up (§23) |

**[RECOMMENDATION]** User-visible directory structure, kept close to the brief's own sketch since a non-technical user benefits from `Books`/`Documents` being self-explanatory if they ever plug the device into a PC over MTP:

```
/var/lib/ereader/
├── Books/          # any file dropped here is auto-detected and indexed
├── Documents/       # non-book text/PDF the user wants readable but unlibraried
├── Notes/           # exported highlights/annotations, human-readable format
├── Dictionary/      # user-installed dictionary files
└── Config/          # settings, not meant for casual user editing
```

**[REQUIREMENT]** Dropping `1984.epub` into `Books/` must make it appear in the library without any explicit "import" step — a filesystem watch (`inotify`) triggers re-scan, consistent with a Kindle/Kobo-like experience.

**[DECISION]** No client-side full-disk encryption at MVP — see the explicit trade-off called out in §25's threat model; this is a deliberate, revisitable choice, not an oversight.

---

## 18. Network Architecture

**[REQUIREMENT]** Radios off by default; Wi-Fi enabled only for an explicit user action (opening Catalogs, checking for updates, configuring sync) and disabled again afterward automatically unless the user pins it on.

**[DECISION]** No general NetworkManager-style always-on daemon with auto-reconnect-everywhere behavior. `networkd` here is deliberately narrow: expose "turn Wi-Fi on for task X," "list known networks," "connect," "turn off" — not a full desktop network stack. Reuse `iwd` or `wpa_supplicant` underneath (do not reimplement Wi-Fi association) behind this narrow policy layer.

**[DECISION]** Downloads (OPDS book fetches, catalog metadata, update payloads) run through a single download manager that: resumes interrupted transfers, verifies file integrity post-download (hash check for updates; for books, at minimum confirming the file isn't truncated/corrupt before adding to the library), and surfaces failures in plain language ("Couldn't finish downloading — try again when you have Wi-Fi").

---

## 19. OPDS Architecture

**[DECISION]** OPDS (Open Publication Distribution System — an Atom/RSS-derived, open, widely-implemented catalog standard) is the primary catalog protocol, consistent with the "providers/plugin architecture" the brief requests (§17 below covers *sources*; this section covers the *protocol client*).

Flow: user opens **Catalogs** → selects or adds an OPDS endpoint URL → Wi-Fi is enabled for this task → client fetches and renders the Atom feed as a navigable list/search UI → user selects a book → download manager (§18) fetches it → Wi-Fi is disabled again (unless pinned) → book is added to the library automatically.

**[RECOMMENDATION]** Since KOReader (§15) already ships a built-in OPDS client, this is very likely another case where the engineering task is *configuration and default-catalog curation*, not new protocol-client code — to be confirmed in Phase 1.

---

## 20. Synchronization Architecture

**[REQUIREMENT]** The system must work completely and permanently without ever configuring sync. Sync is an optional layer, never a dependency.

| Option | Description |
|---|---|
| Syncthing | Peer-to-peer, no central server, open-source, good fit philosophically (no account, no cloud) |
| WebDAV / Nextcloud | Server-based, works with infrastructure many privacy-conscious users already self-host |
| SFTP | Simple, universal, no special server software needed |

**[DECISION]** What syncs: books (optional — many users will prefer USB/SD transfer instead, §17), reading progress, bookmarks, highlights, and settings. **Not** a first-class OS service — implemented as an optional, disableable component the user opts into during or after first boot (§9 in the flow), never presented during the mandatory parts of setup.


---

## 21. Power Management Architecture

This is, per the brief's own framing, the most important subsystem, and it is where the project must be most honest about physics before it is clever about engineering.

### 21.1 LCD vs. E-Ink — the physical reality

**[FACT]** E-Ink (electrophoretic) displays are *bistable*: once pixels are set, holding a static image costs approximately zero power — the display only draws meaningful energy during a refresh event (a page turn). This is the entire reason Kindle-class devices measure battery life in weeks: for the overwhelming majority of "reading time," the screen is drawing nothing.

**[FACT]** LCD panels are not bistable. Any legible, static image requires a continuously-powered backlight, and the panel itself typically refreshes at a fixed rate (commonly 60 Hz) regardless of whether the content changed. There is no equivalent "free to hold" state.

**[DECISION]** Consequence, stated plainly so it is never later promised away: **Alpine EReader OS on LCD hardware cannot and will not match E-Ink battery life while the screen is on.** "Reading time" battery life will structurally resemble smartphone screen-on-time endurance, not Kindle endurance. What the project *can* legitimately compete on — and should — is **standby/idle** time, by being far leaner than stock Android once the screen is off: no background app churn, no push-notification services, no telemetry check-ins, no always-on radio scanning. **[HYPOTHESIS]**, pending measurement (§37): idle standby time should meaningfully exceed the original Android install on the same hardware; active screen-on reading time will not exceed what the LCD panel's backlight power draw physically allows, regardless of software optimization.

### 21.2 Power States

| State | Display | CPU | Wi-Fi/BT/GPS/Modem | Notes |
|---|---|---|---|---|
| **ACTIVE** | On, full brightness (user-set) | Normal governor | Off unless a network task is in progress | Transient — user is actively navigating menus |
| **READING** | On, user-set brightness (typically dimmer than ACTIVE) | Lowest governor that keeps page-turn latency acceptable (§36) | Hard off — enforced, not just idle (§5, §18) | The steady state during actual reading |
| **IDLE** | Dimmed or off after a configurable no-touch timeout | Deep idle | Off | Transitional state before SUSPEND |
| **SUSPEND** | Off | Suspended (`s2idle`/`deep`, device-dependent — recorded per Device Profile) | Off | Instant-on resume is a UX requirement (§36); this is the state the device spends most of its life in |
| **SHUTDOWN** | Off | Off | Off | Full power-off; slower resume (full boot), used for long-term storage or user-initiated power-off |
| **LOW BATTERY** | Warning shown once, brightness auto-reduced | Unchanged | Unchanged (still off unless user overrides) | A modifier state, not exclusive with READING/IDLE |
| **CRITICAL BATTERY** | Forced dim/off, warning modal | Minimum | Forced off, no override | Device auto-transitions to SUSPEND/SHUTDOWN to protect the battery and the library database from an unclean power loss mid-write |

**[DECISION]** Radios are gated at the `powerd` level, not left to application-layer discipline — an application (including a future third-party OPDS catalog plugin) cannot simply decide to enable Wi-Fi; it requests it from `powerd`, which enforces the state-machine rule that Wi-Fi is refused while in `READING`. This is a deliberate architectural chokepoint, not a convention.

### 21.3 What is *not* promised

**[DECISION]** No specific battery-life number appears anywhere in this document, per instruction. Any number quoted publicly before real measurement (§37) exists would be fabrication.

---

## 22. Update Architecture

**[DECISION]** Alpine EReader OS will use a project-defined signed image-update mechanism. Alpine's `apk` package manager is appropriate for building and maintaining the userspace, but package-level upgrades do not by themselves guarantee an atomic, rollback-capable operating-system update.

**[REQUIREMENT]** The update design must fetch signed metadata, verify image integrity and authenticity, stage updates without destroying the currently bootable system, preserve user data, and retain a known-good boot path. A boot-health check must confirm that the new deployment reaches the library screen; otherwise the device must return to the last-known-good system without user intervention, where the bootloader and partition layout make this possible.

**[DECISION]** The exact implementation—A/B system slots, a dedicated recovery image, or another mechanism—must be selected and measured per device. Account for flash capacity, wear, bootloader capabilities, and the ability to recover from power loss during writing. Do not assume the selected image-update mechanism-style content deduplication or storage efficiency.

**[DECISION]** Channels: `stable`, `beta`, `nightly`, provided by signed manifests or repositories. `stable` is the default and the only channel offered during first boot. Rollback and anti-downgrade policy must be reconciled explicitly: ordinary failure rollback may return to a previously trusted image, while externally initiated downgrade attempts must require an authenticated recovery path.
---

## 23. Recovery Architecture

**[REQUIREMENT]** A device must never require a PC to recover from a bad state, wherever the hardware makes that possible.

**[DECISION]** A minimal, separate recovery deployment/partition (the specific mechanism — dedicated recovery partition vs. a special the selected image-update mechanism deployment slot — is decided per-device in the Device Profile, since it depends on how much spare storage and how flexible the bootloader's boot-entry selection is) provides: reinstall-from-scratch, roll back to the previous working deployment, restore user settings from the last known-good backup if one exists, basic hardware diagnostics (display test pattern, touch test, battery reading, storage health), and log collection to an SD card or USB drive for bug reports.

**[REQUIREMENT]** Recovery mode must be reachable via a physical-button combination at boot (device-specific, documented per Device Profile) that works even if the main system is completely unbootable.

---

## 24. Installer Architecture

This is, alongside device porting, where the brief is most insistent that no false universal solution be proposed — correctly so, because none exists. The installer's honest job is to **automate what is mechanically automatable and clearly hand off, with documentation, whatever legally or technically requires the OEM's own process.**

### 24.1 What can be automated

**[RECOMMENDATION]** A cross-platform (Windows/Linux/macOS) graphical installer that: detects a connected device over USB (via ADB and/or fastboot enumeration), identifies manufacturer/model/codename against the Device Profile database, reports the resulting support tier (§13.2) *before* touching anything, checks current bootloader/firmware state via read-only queries, guides the user through whatever manual unlock step their specific device requires (see 24.2 — this step differs by OEM and cannot be skipped by the tool), offers a best-effort backup of user-accessible data via MTP file copy where the device is still running Android, verifies available storage, requires an explicit, unambiguous confirmation before any destructive action, flashes the signed image via `fastboot` for devices with a standard AOSP-style unlock flow, verifies the flashed image's integrity, and hands off to first boot.

### 24.2 What categorically cannot be automated — and why

**[FACT, current as of 2026]** Bootloader unlock policy is fragmented by design across manufacturers, and has been getting *more* restrictive, not less, in several important cases:

- **Samsung**: unlock (where available at all) requires enabling "OEM unlocking" in Developer Options, then confirming in Download Mode — a manual, on-device, physical-button step that cannot be scripted remotely. Whether the toggle is even present depends on region/SKU (carrier-locked US/Canada models have not offered it since roughly the Galaxy S7 generation) and, critically, **Samsung has removed the bootloader-unlock capability entirely starting with One UI 8** for devices that have received that update. Unlocking permanently trips a hardware Knox e-fuse (0x0→0x1) and disables Knox-dependent features irreversibly — acceptable for a device being repurposed, but irreversible and worth stating plainly to the user. **Note for the pilot device specifically:** the J2 Core is old, low-end, and was abandoned by Samsung's own update cycle early (Android Go edition devices historically receive minimal OTA support) — which means it is very unlikely to have ever received a firmware build new enough to have the unlock capability revoked. Older, long-abandoned devices are, somewhat counterintuitively, *more* likely to retain unlock capability than a newer Samsung device still receiving updates. This must still be verified per physical unit and regional SKU, not assumed.
- **Xiaomi**: requires binding a Mi Account to the device and waiting a mandatory, server-enforced cooldown period before the official Mi Unlock tool will proceed — a wait that cannot be bypassed by any third-party installer, by design.
- **Motorola**: requires the user to manually request a unique unlock code from Motorola's own website using the device's IMEI, then apply it — again, something only Motorola's servers can issue.
- **Google/Pixel and many smaller AOSP-based OEMs**: standard `fastboot flashing unlock`, fully automatable — the easy case, and not representative of the field as a whole.
- **Unknown/regional/obscure models**: no community unlock research may exist at all. This is a legitimate 🔴 RED classification (§13.2), not a gap in the installer.

**[DECISION]** The installer's UI must therefore branch per detected device into one of: "fully automated," "guided manual steps with links to this device's documentation," or "not supported — here is why," and must never claim the third case is the second.

### 24.3 Non-destructive sequencing

**[REQUIREMENT]** Order of operations: detect → **identify and confirm compatibility tier before any other step** → back up if possible → require explicit destructive-action confirmation → unlock (manual step, if required) → flash → verify → reboot → hand off to first boot (§9's original numbered flow is preserved; this restates it with the automation boundary made explicit).


---

## 25. Security Architecture

**[DECISION]** Threat model is developed fully in §34; this section covers the standing architectural controls.

- **Image signing**: every image (install, update, recovery) is signed; the device's boot chain verifies the signature before executing it, to whatever depth the specific device's hardware root of trust allows (this varies — a locked-down AVB chain and a device with no verified boot support at all require different honest statements in the Device Profile, not a single claim).
- **Reader process isolation**: the reader/library/OPDS engine (KOReader, §15) — which is, by nature, a parser of untrusted, user-supplied files (EPUB/PDF parsing has a real history of memory-safety CVEs across the ecosystem, MuPDF included) — runs sandboxed via available sandboxing primitives (to be validated on Alpine) (`ProtectSystem=strict`, a private, restricted view of the filesystem outside its own data directory, `PrivateNetwork=yes` since it never legitimately needs raw network access — OPDS downloads flow through the download manager, not the parser process, `NoNewPrivileges=yes`, a dedicated low-privilege user) rather than running as a general desktop application with the user's full filesystem/network access.
- **Update integrity**: covered in §22 — signature verification is mandatory, not optional, and a failed verification blocks the update rather than warning-and-proceeding.
- **Anti-downgrade**: the update mechanism should refuse to install an image with a lower monotonic version/rollback-index than the currently-installed one, except through an explicit, separately-authenticated "factory reset to an older recovery image" path — this prevents an attacker from downgrading a device to a version with known vulnerabilities.
- **Physical access / lost device**: addressed honestly as a trade-off, not solved — see below.

**[DECISION, with explicit trade-off]** Full-disk encryption (LUKS) is **not** adopted at MVP. Reasoning: this product's central UX promise (§9, §33) is zero mandatory login and instant resume from suspend; requiring a passphrase on every resume directly contradicts that, and a passphrase the device auto-unlocks defeats the point of encrypting in the first place. **[RISK]** A lost or stolen device exposes its local library and reading history to whoever has it physically. **Mitigation, partial**: this is disclosed to the user during first boot as a plain statement of fact (not buried in a EULA), and encryption is left available as an **opt-in, advanced setting** for users who prefer the trade-off in the other direction. This is flagged again as an explicit open question in §47.

---

## 26. Privacy Architecture

**[REQUIREMENT]** Zero mandatory telemetry. Not "opt-out telemetry," not "anonymized telemetry" — no data collection pipeline exists in the default build for reading habits, book titles, location, or any personal identifier. **[DECISION]** This is enforced architecturally, not just as a policy: there is simply no telemetry-transmission code path compiled into the default image, so there is nothing to disable-and-forget. A local-only, on-device reading-statistics feature (KOReader already has one) is fine and stays fine precisely because it never leaves the device.

**[REQUIREMENT]** No account creation anywhere in the core flow (§9, §26). Sync (§20) and OPDS catalogs (§19) may involve credentials for services the *user* chooses to configure, but those are the user's own accounts with third parties of their choosing, never a Alpine EReader OS account.

---

## 27. DRM Considerations

**[DECISION]** No DRM circumvention is designed, described, or facilitated anywhere in this project, full stop — consistent with the brief's own instruction and with what is legally sound: implementing interoperability with proprietary schemes like Adobe ADEPT or Amazon's formats would require either a license this project will not have, or circumvention that is illegal in many jurisdictions regardless of interoperability intent.

**[DECISION]** Practical consequence: Alpine EReader OS supports **non-DRM content only**. Books protected by proprietary DRM are out of scope; a user who owns such books is responsible for their own tools and their own compliance with the terms they agreed to, entirely outside this project.

**[FACT]** One DRM-adjacent scheme is worth naming precisely because it is *not* the same category of problem: **Readium LCP** (Licensed Content Protection), maintained by the nonprofit EDRLab, is an open, standardized, library/indie-publishing-oriented protection scheme with openly published specifications and open-source reference components (its license server is BSD-3-Clause; reference reader support exists in the Readium ecosystem). Because it is open and interoperable by design rather than proprietary and closed, it is architecturally the *only* protected-content scheme this document would consider supporting in a future phase — and even that is explicitly deferred, not part of the MVP or near-term roadmap.

**[REQUIREMENT]** The UI must communicate DRM status honestly: if a book fails to open because it's DRM-protected, the error says so plainly rather than presenting a generic "unsupported format" message that would send a user on a wild goose chase.

---

## 28. UI/UX Architecture

**[DECISION]** Consistent with §6 and §15, the EReader Shell is deliberately thin — it is not a full desktop-style UI toolkit exercise, it is a small set of full-screen views wrapping a mostly-KOReader-driven reading experience.

**Screens**: Library (grid/list of books, cover-forward), Reader (full-screen, chrome hidden by default, revealed by a tap-zone or gesture), Catalogs (OPDS browser, only reachable when the user explicitly opens it), Search (local library + open catalog, contextual), Settings (font, theme, margins, Wi-Fi, updates, device info — deliberately a short list, not KOReader's full power-user settings tree), Dictionary (lookup UI, triggered from in-book word selection), Annotations (a plain list view of highlights/notes, exportable), Device Info (storage, battery, version — useful for support requests), Update, Recovery (only ever seen via the dedicated recovery boot path, §23).

**[DECISION]** Navigation model: single-surface, stack-based (Library → Book → back to Library), no persistent chrome, no notification tray — there is nothing to notify about, by design (§6). Physical volume buttons are mapped to page-turn where the device has them, both for one-handed ergonomics and because it avoids waking the touch digitizer (§29, §21).

**Visual principles**: calm, textual, high-contrast, minimal color, no gradients, no drop shadows, no decorative motion. Explicit light and dark themes (not just an "auto" toggle with no manual override — battery and ambient-light preference are both legitimate reasons to choose manually). Typography, margins, and line spacing are user-adjustable within KOReader's existing, mature typesetting controls rather than reimplemented.

**[REQUIREMENT]** The UI must render correctly in both portrait and landscape and on both phone-sized and tablet-sized panels — this is a layout-flexibility requirement on the thin Shell layer (KOReader itself already handles this across its existing device matrix).

---

## 29. Accessibility

**[RECOMMENDATION]** Prioritized by tractability and impact, not by the brief's original ordering:

- **Font size and high-contrast themes**: low effort, high impact, already native to KOReader's typesetting engine — ship on day one.
- **Dyslexia-friendly typography**: bundle at least one purpose-built open-license font (e.g., a Braille-Institute-style humanist sans designed for legibility, or an open dyslexia-oriented face) as a selectable option, not the default — this is a low-cost, high-value inclusion.
- **Physical-button navigation**: already recommended in §28 for power/ergonomic reasons; it is also a meaningful accessibility win for users with limited fine-motor precision on a touchscreen.
- **Text-to-speech (read-aloud)**: **[DECISION]** prioritized *above* full screen-reader support, because it serves a much larger population (low vision, reading fatigue, dyslexia, situational "eyes-busy" use) at a fraction of the engineering cost of a full accessibility stack.
- **Full screen-reader support** (an Orca/AT-SPI-equivalent stack): **[DECISION]** marked 🟡 YELLOW / later-phase aspiration, not an MVP requirement — a general accessibility-tree stack is a genuinely heavy dependency for a minimal custom Shell with no desktop toolkit underneath it, and promising it prematurely would either bloat the Core or ship a broken half-implementation. This is a real limitation, stated honestly rather than glossed over.


---

## 30. Process Model

Restating and finalizing the component set from §8 as the canonical process list, with lifecycle notes:

| Process | Starts | Restart policy | Typical resource footprint concern |
|---|---|---|---|
| `OpenRC` (PID 1) | Kernel handoff | N/A | Baseline |
| `powerd` | Early boot, before any radio init | Always-restart (critical path — the whole power model depends on it) | Must be lightweight; it runs for the device's entire powered-on life |
| `networkd` (thin `iwd`/`wpa_supplicant` policy wrapper) | On-demand, activated by radio requests (§18) | Restart on failure, but not always-running | Should be able to fully exit when radios are off, not idle-poll |
| `updated` (Alpine image-update mechanism) | On-demand (user check) or scheduled opportunistically (§22) | Not always-running | Zero footprint when not actively checking/applying |
| EReader Shell | After display stack is up | Restart on crash, but a crash here is a launch-to-recovery-hint event, not silent | Owns the visible UI life of the device |
| KOReader | Launched by the Shell when a book is opened; may stay resident between books or be re-launched, TBD in Phase 1 measurement | Restart on crash, returning to Library with the last saved position intact | The single largest memory consumer — sized first in RAM budgeting |
| Recovery agent | Only in the separate recovery boot mode | N/A (not part of normal runtime) | Isolated from normal-mode resource budget entirely |

**[DECISION]** No general-purpose "app framework" process (no init system beyond `OpenRC` itself, no session manager, no D-Bus session bus separate from the system bus) — for a single-user, single-app-at-a-time appliance, a session bus is one more moving part with no session to manage.

---

## 31. IPC

**[DECISION]** D-Bus (system bus) for the handful of cross-process calls that exist: `powerd` exposing state and radio-request methods, `updated` exposing check/apply/status, the Shell querying both. This is chosen over the alternatives for unglamorous but correct reasons: it is available as a package in Alpine, with dependency and policy costs to be measured, it has mature policy/access-control via `polkit` (relevant since `powerd`/`updated` are privileged and the Shell is not), and it avoids inventing and securing a bespoke protocol.

**[DECISION, explicitly rejecting alternatives]** gRPC and REST-over-localhost are **not** used — they solve problems (schema evolution across independently-versioned services, network-transparent RPC) this single-device, single-vendor, co-versioned system does not have, and both add a dependency and serialization-overhead cost with no corresponding benefit here.

**[DECISION]** Where the Shell and KOReader need to hand off state (e.g., "open this book at last position," "return to library after closing a book"), a lightweight mechanism — a Unix domain socket or even a well-defined file-based handoff, resolved in Phase 1 based on what KOReader's own architecture makes natural — is preferred over routing this through D-Bus, since it is a tight, frequent, two-party interaction rather than a system-wide service call. Early-boot coordination (before D-Bus itself is up) relies on OpenRC service dependencies and explicit readiness checks rather than a custom mechanism.

---

## 32. Data Model

Already specified conceptually in §16 (Library entities). This section restates the **placement** rule, since it is the single most load-bearing data-architecture decision in the document:

**[REQUIREMENT]** Every piece of state in the system is classifiable as exactly one of:
- **Read-only system state** (ships in the image, replaced only by an atomic update) — kernel, binaries, default assets, default configuration.
- **Read-write user state** (lives in `/var`, survives updates, is what a backup/restore operation actually needs to preserve) — library DB, book files, settings, logs, catalog cache.

Nothing should exist ambiguously between these two categories; if a piece of data doesn't clearly belong to one, that's a design smell to resolve before implementation, not something to leave fuzzy.

---

## 33. Build System

**[DECISION]** Use Alpine's `apk` packages as the base for a reproducible image-build pipeline. The pipeline assembles a device-agnostic Core and a per-device layer containing the kernel, firmware, device tree, and configuration. The exact image-generation and flashing tools are implementation choices to validate in Phase 1; Fedora-specific `bootc`/`osbuild` assumptions do not apply.

**[DECISION]** Two-stage composition per §7: a **Core** image (device-agnostic userspace, built once) is the base; each **Device Port** adds its kernel, firmware blobs, and device-specific configuration, producing one final image per certified/experimental device. Adding a device must not alter existing device build definitions.

**[REQUIREMENT]** Builds must be reproducible: the same source commit and package versions must produce a bit-identical—or at minimum functionally identical and independently verifiable—image. Pin repository snapshots/package versions and preserve build manifests so released images can be audited.

**[RECOMMENDATION]** Cross-compilation: build ARM64 images on ARM64 CI runners where available, with x86_64-hosted cross-compilation/emulation as a fallback.
---

## 34. CI/CD

**[RECOMMENDATION]** Pipeline shape:

```
commit → lint → unit tests → build (per Core + per Device Port)
      → image assembly (Alpine image pipeline) → boot test (QEMU, where the
        target SoC is QEMU-emulatable — Core-only logic can be tested
        this way even when the real device SoC can't be)
      → integration tests (§35) → security checks (dependency/CVE
        scan, security-policy and sandbox audit, signature/provenance check)
      → sign → publish to update channel
```

**[RECOMMENDATION]** QEMU is used for everything that doesn't depend on real device-specific hardware (Core logic, powerd state-machine unit behavior, library/database logic, D-Bus contract tests) — this is the majority of the system by line count, per the Core/Device-Port split in §7. Real hardware-in-the-loop testing (§35) is reserved for what QEMU genuinely cannot substitute for: actual display/touch/battery/radio behavior on actual silicon.

---

## 35. Testing

**[REQUIREMENT]** Coverage, mapped to what's actually being risk-managed:

| Category | What it catches | Environment |
|---|---|---|
| Unit | Logic errors in Core daemons (powerd state transitions, library data-model operations) | Host CI, no hardware |
| Integration | Cross-component contracts (D-Bus interfaces, Shell↔KOReader handoff) | QEMU or host |
| Boot | Does the image reach the library screen | QEMU (Core-only claims) + real hardware (device-specific claims) |
| UI | Does the Shell render and navigate correctly at target resolutions | Host + real hardware for touch-specific behavior |
| Power | Do state transitions actually gate radios/CPU/display as specified | **Requires real hardware** — this cannot be meaningfully faked in QEMU |
| Network | OPDS fetch, download resume/retry, radio on/off timing | Real hardware for radio timing; host-simulated network conditions for protocol logic |
| Storage | Filesystem integrity across power loss (simulated), library DB corruption recovery | Real hardware for power-loss simulation, host for logic |
| Recovery | Reflash, rollback, log collection all actually work from a broken state | Real hardware, deliberately induced failure states |
| Update/Rollback | A bad update is detected and rolled back automatically (§22) | Real hardware, deliberately shipped "broken" test image |
| Security | Signature verification actually rejects tampered images; sandboxing actually restricts KOReader's filesystem/network access | Real hardware + host-based static analysis |

**[DECISION]** Minimum bar for a device to claim 🟢 Certified (§13.2): every row above passes on real hardware, across N consecutive nightly/beta builds with no regression, with a named maintainer who has committed to responding to breakage.


---

## 36. Performance

**[DECISION]** Every metric below is explicitly labeled by category, per instruction — none of these are measured numbers yet, they are the categories of number this project must eventually produce and defend:

| Metric | Category | Rationale |
|---|---|---|
| Boot time (power-on to library screen) | **TARGET** | Not safety-critical, but central to the "appliance" feel; a reasonable target is competitive with the device's original Android boot time, not an arbitrary absolute number invented here |
| Resume time (suspend to usable screen) | **REQUIREMENT** | This is the state the device lives in most of the time (§21); it must feel instant or the whole "appliance" premise fails |
| Page-turn latency | **REQUIREMENT** | Directly perceptible by the user on every interaction; inherited largely from KOReader's own established performance envelope on comparable embedded hardware, not something this project needs to re-engineer |
| RAM headroom under the 1 GB ceiling | **REQUIREMENT** | Falling short here isn't a degraded experience, it's an OOM-killer crash |
| Book open time (cold) | **TARGET** | Varies legitimately by format/file size/whether reflow is needed; a target range, not a single number |
| Search latency (local library) | **ASPIRATION** | Nice to have snappy; not load-bearing for the core experience given realistic library sizes on this hardware class |

**[RECOMMENDATION]** All of these should be defined as concrete numbers only after Phase 1 (PoC) measurement on the actual pilot device — publishing invented targets before that would violate the same "don't invent numbers" principle as §21.3 and §37.

---

## 37. Power Benchmarking

**[REQUIREMENT]** A defined, repeatable methodology — not invented numbers, an invented **method**:

- **Controlled conditions**: identical physical unit for stock-Android and Alpine-EReader-OS runs (avoids battery-health/cycle-count as a confound), fixed and lux-meter-calibrated screen brightness rather than an OS-reported "brightness level" (which isn't comparable across OSes), stable ambient temperature range, identical test content and identical page-turn cadence (scripted, not manual, for repeatability).
- **Independent ground truth**: **[DECISION]** rely on an external USB in-line power meter (hardware current/voltage logging, independent of the device's own — possibly inaccurate, especially on a decommissioned battery — fuel-gauge reporting) as the primary measurement, with the PMIC's own `power_supply` sysfs reporting recorded *alongside* for cross-checking, not as the sole source of truth.
- **Scenarios measured separately** (a single "battery life" number hides more than it reveals): active reading (screen on, continuous), idle/standby (screen off, suspended), and a mixed realistic-use profile (e.g., 2 hours reading + 22 hours standby) — each reported separately, per §21.1's explicit distinction between what LCD hardware can and cannot deliver.
- **A/B methodology**: same physical device, same battery, stock Android vs. Alpine EReader OS, run back-to-back to control for battery aging between measurements as tightly as possible.

**[DECISION]** No public claim ("gets N hours of reading" / "Nx the standby time of stock Android") is made until this methodology has actually been run and the result is reproducible by a third party from the published method.

---

## 38. Device Certification

Formalizes §13.2's tier system as a process, and connects it to §35's test suite:

**[REQUIREMENT]** To move from 🟡 Experimental to 🟢 Certified, a device must: pass every row of the §35 test matrix on real hardware, across a minimum number of consecutive nightly/beta builds without regression (the exact N is a Phase 8 policy decision, not fixed here), have a Device Profile that is complete and accurate (not aspirational), have a named maintainer who has responded to at least one real community-reported issue, and have a working, tested, non-destructive recovery path.

**[DECISION]** Certification is per-device, not per-SoC-family — two phones sharing a chipset do not automatically share a tier, because bootloader policy, RAM, and panel differences can diverge their real-world reliability even with an identical kernel port.

---

## 39. Repository Structure

**[DECISION]** A monorepo, restructured from the brief's sketch to reflect the Core/Device-Port split established in §7 and the "adopt, don't rebuild, the reader" decision in §15:

```
alpine-ereader-os/
├── core/                 # Device-agnostic base image definition (Containerfile-
│                         #   equivalent for the Core OCI layer): OpenRC service definitions,
│                         #   powerd, networkd, updated, D-Bus policy
├── shell/                # EReader Shell: library UI, settings, first-boot flow
├── reader-integration/    # KOReader packaging, sandboxing config, patches carried
│                         #   upstream-first (not a fork — see §15, §40)
├── devices/              # One directory per device port
│   ├── _template/         # Device Profile template + porting checklist
│   └── samsung-j2core/    # Kernel/BSP references, device tree, Device Profile,
│                         #   device-specific image layer definition
├── images/                # the image-build pipeline/the image-update mechanism manifests tying core + a device port
│                         #   together into a shippable image, per device
├── installer/             # Cross-platform (Win/Linux/macOS) graphical installer
├── recovery/               # Recovery image composition + on-device diagnostics
├── docs/                  # See §42
├── tests/                 # Unit, integration, boot (QEMU), hardware-in-the-loop
│                         #   test definitions and fixtures
├── tooling/                # Dev scripts, CI helpers, Device Profile schema
│                         #   validation, release tooling
└── governance/             # MAINTAINERS, CONTRIBUTING, security disclosure policy,
                          #   RFC template (§41)
```

**[DECISION]** Notably absent from this structure, relative to the brief's original sketch: separate top-level `library/`, `power/`, `network/`, `update/` directories. Per §8/§30, these are Core daemons living together inside `core/`, not independent subprojects — splitting them into separate top-level directories would overstate their independence and complicate the "one image = core + one device port" build model in §33.

---

## 40. Licensing

**[DECISION]** Original Alpine EReader OS code (installer, Shell, device-profile tooling, build/CI tooling, documentation) is licensed **Apache-2.0** — permissive enough to encourage adoption and OEM/community experimentation, while its explicit patent grant is meaningfully more protective than a bare MIT/BSD license, consistent with the brief's own stated preference for protective licenses.

**[FACT]** Third-party component licenses, and what each implies:

| Component | License **[FACT]** | Implication |
|---|---|---|
| Linux kernel | GPL-2.0 | Inherited regardless of sourcing strategy (§11); non-negotiable, universally understood in this ecosystem |
| KOReader | AGPL-3.0-only | See below — this is the one with a real architectural implication |
| MuPDF (used inside KOReader) | AGPL-3.0 / commercial dual license (Artifex) | Already resolved by KOReader's own AGPL choice; not a separate concern for this project since it isn't integrated independently (§15) |
| Readium (not adopted, §15, but noted for completeness) | BSD-3-Clause | Would have been the most permissive option, but was not the right *technical* fit regardless of license |
| Firmware blobs (Wi-Fi, GPU, per device) | Typically proprietary-but-redistributable | An unavoidable practical compromise on this hardware class — the same compromise Alpine, Debian, and postmarketOS all make via a `linux-firmware`-style package; the honest move is to isolate and clearly label these blobs per Device Profile (§13.1) rather than pretend a 100% blob-free image is achievable on repurposed phone SoCs |

**[DECISION, load-bearing]** Because KOReader is AGPL-3.0, the **process boundary** between it and the rest of the system (§8, §15, §25) is not only a security boundary, it is the licensing boundary too. As long as Alpine EReader OS's own Shell/Core code communicates with KOReader as a separate process over IPC (§31) rather than being linked into or being a modified derivative of KOReader itself, the Shell and Core can remain Apache-2.0 without AGPL's copyleft extending to them. **Any patches made to KOReader itself must be released under AGPL-3.0** (and should be upstreamed, per §15, rather than held as a private fork). **[RISK]** If a future engineering shortcut merges KOReader's Lua runtime directly into the Shell process for convenience, that decision would drag the combined work under AGPL — this is flagged explicitly so it isn't discovered by accident later.

**[DECISION]** Documentation: Creative Commons **CC-BY-SA-4.0**, matching the copyleft spirit of the code license choices without forcing a software license onto prose.


---

## 41. Governance

**[RECOMMENDATION]**

- **MAINTAINERS** file listing Core maintainers and, separately, per-device maintainers (§13, §38) — a device maintainer's scope is explicitly bounded to their `devices/<codename>/` directory, so device-specific responsibility doesn't require Core-level trust.
- **RFC process for architectural decisions**: this document's own `[DECISION] / Options / Trade-offs / Recommendation / Reasoning` format (used throughout, per the brief's own instruction) is adopted as the literal RFC template for future major changes — it already worked for producing this document, and reusing it means new contributors learn one format, not two.
- **Release channels**: `stable` / `beta` / `nightly` (§22), with `stable` releases following a predictable cadence once the project is past Phase 8 (§44); pre-1.0, release discipline is looser by necessity.
- **Security disclosure**: a private reporting channel (email or a security-advisory feature on the chosen forge) with a committed initial-response window, disclosed publicly only after a fix is available — standard practice, not a novel design point.
- **Public roadmap**: tracked via the forge's native project/milestone tooling, mirroring the phase structure in §44, kept honest about what's actually in progress vs. aspirational.

---

## 42. Documentation

**[RECOMMENDATION]** Structure, with content scope per directory:

```
docs/
├── architecture/     # This document and its living updates; ADRs (Architectural
│                     #   Decision Records) for changes made after Phase 0
├── installation/      # Per-audience: end-user installer walkthrough, and a
│                     #   separate "how installation actually works" for porters
├── devices/           # One page per device, generated from/linking to its
│                     #   Device Profile — the single source of truth for
│                     #   "will this work on my phone"
├── development/       # Build-from-source, contribution workflow, coding
│                     #   conventions
├── security/          # Threat model (§34 as a living document), disclosure
│                     #   policy, sandboxing rationale
├── power/             # The methodology from §37, plus published results once
│                     #   they exist — methodology and results, kept separate,
│                     #   so results can be updated without re-litigating method
├── reader/            # How KOReader is integrated, patch policy, upstream
│                     #   relationship
├── contributing/       # Governance (§41), RFC template, code of conduct
├── recovery/           # End-user recovery walkthrough per device
└── licensing/          # The table in §40, kept current as dependencies change
```

**[REQUIREMENT]** The first page a new user or contributor reaches must state, in plain language, both what the project is and — per §9's branding risk — that Alpine Linux is the base distribution and that system updates are managed by the project.

---

## 43. MVP

**[DECISION]** The smallest system that validates the core premise, deliberately excluding everything not load-bearing to that validation:

**In scope:**
- Boots on the pilot device (Galaxy J2 Core) to a library screen.
- Opens and renders EPUB, PDF, and plain text (KOReader's existing coverage, not new work).
- Saves and restores reading position, bookmarks, highlights.
- Books added via USB/MTP file copy are auto-detected (§17).
- Suspend/resume and full shutdown both work reliably.
- Functions with Wi-Fi permanently off — no feature in the MVP requires networking.
- One device, 🟡 Experimental tier is an acceptable MVP outcome; 🟢 Certified is a later-phase target (§38).

**Deliberately excluded, and why:**
- **OPDS/catalog browsing** — real, but not needed to validate "can this hardware be a usable e-reader"; adds a network stack and radio-gating complexity to the critical path of proving the core premise.
- **Sync** — explicitly optional even in the full product vision (§20); zero reason to pull it into MVP.
- **Graphical installer** — the PoC/MVP device can be flashed by the engineering team directly; the polished installer (§24) is Phase 6 work, needed for *users*, not for validating the architecture.
- **Recovery partition polish** — a manual re-flash by the same process used for install is an acceptable MVP-phase "recovery" story; the dedicated on-device recovery UI (§23) comes later.
- **Every format beyond EPUB/PDF/TXT** — FB2, MOBI, CBZ, etc. are already "free" via KOReader (§15) but are not what needs to be *proven* at MVP stage.
- **A second device** — proving the Core/Device-Port split (§7) generalizes is explicitly Phase 7 work, not MVP work; one device proves the reading experience, not the porting methodology.

---

## 44. Development Roadmap

| Phase | Objective | Key deliverables | Primary risk | Success criteria |
|---|---|---|---|---|
| **0 — Architecture** | This document and its review | Reviewed, revised architecture spec; Phase 1 plan | Scope creep before any code exists | Team consensus that §48's recommended architecture is buildable |
| **1 — Proof of Concept** | Resolve the open [HYPOTHESIS] items empirically | Kernel boots to a shell prompt on the pilot device; KOReader runs (even ungracefully) on that kernel; RAM footprint measured | Kernel bring-up on the J2 Core's Exynos 7570 turns out harder than the postmarketOS precedent suggests | A book opens and renders on real hardware, however roughly |
| **2 — Minimal EReader** | Core daemons exist in skeletal form | `powerd` state machine (§21) implemented and unit-tested; read-only/read-write split (§17, §32) enforced | Underestimating how much of "minimal" still needs building | Device boots, reads a book, saves progress, suspends/resumes reliably |
| **3 — Library** | Library/browsing experience solid | Shell's library grid, auto-detect-on-copy (§17) working end-to-end | Scope creep into a full file manager | Dropping a file in `Books/` reliably makes it appear and open correctly |
| **4 — Reader** | Reading experience polish | Shell chrome around KOReader finalized (§15, §28); dictionary, annotations exposed cleanly | KOReader reskinning takes longer than "configuration," edges toward "fork" (§15's Option C, to be avoided) | A non-technical tester can read a book start-to-finish with no explanation |
| **5 — Power** | Power model validated on real hardware | §37 methodology executed; standby/idle numbers published (reading numbers published honestly per §21.1's ceiling) | LCD reality undercutting user/stakeholder expectations (§21.1) | Reproducible, published measurement — not necessarily a flattering one |
| **6 — Installer** | Non-technical install path | Graphical installer (§24) for the pilot device at minimum | Manual-unlock-step UX being confusing despite best documentation efforts | A non-technical volunteer successfully installs without engineering-team hand-holding |
| **7 — First Additional Device(s)** | Validate the Core/Device-Port split generalizes | 1–2 more devices ported using the process in §13.3 | The split turns out leakier than designed — Core assumptions that were secretly J2-Core-specific | Second device reaches at least 🟡 Experimental without modifying `core/` |
| **8 — Certified Devices** | First 🟢 Certified device(s) | Full §35 test matrix passing across N builds; named maintainers in place | Maintainer bus-factor (one person per device is fragile) | At least one device meets every §38 criterion |
| **9 — Public Release** | 1.0, public-facing | Public docs (§42), stable channel, public roadmap (§41) | Support load exceeding a volunteer project's capacity | Installable end-to-end by a stranger, from public documentation alone |


---

## 45. Risk Register

Consolidating risks flagged throughout the document, plus the explicit threat model requested in the brief.

### 45.1 Project risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Bootloader unlock proves infeasible on the pilot device or its regional SKU | Low–Medium (§24.2's reasoning favors feasibility, but is unverified per-unit) | High — blocks Phase 1 entirely | Verify on the actual physical unit before any other engineering investment; have a documented fallback second candidate device from postmarketOS's existing supported list |
| KOReader integration needs more than "configuration" (§15's Option C creeping in) | Medium | Medium — schedule and licensing-boundary risk (§40) | Timebox the Phase 4 reskinning effort; treat any deep-fork temptation as a stop-and-reassess signal, not a schedule adjustment |
| Kernel bring-up (§11) takes materially longer than the postmarketOS precedent suggests | Medium | High — is the critical path for everything downstream | Phase 1 exists specifically to surface this early, before Core/Shell work is invested |
| Maintainer bus-factor on device ports (§38, §41) | Medium–High over time | Medium — degrades to 🟡/🔴 for unmaintained devices, doesn't corrupt the Core | Tier system (§13.2) is designed to degrade gracefully and honestly rather than silently rot |
| LCD power reality (§21.1) disappoints stakeholders expecting Kindle-like numbers | High if not managed proactively | Reputational, not technical | This document states the physics plainly, repeatedly, precisely to prevent this surprise later |

### 45.2 Threat model

| Threat | Mitigation |
|---|---|
| Tampered/malicious install or update image | Signature verification at flash and at update-apply time (§22, §25); anti-downgrade check |
| Compromised update server | Signature is verified client-side against a pinned key, independent of server compromise; server compromise alone cannot produce a validly-signed malicious image |
| Malicious or malformed book file (EPUB/PDF parser exploitation) | Reader process sandboxing (§25) — `PrivateNetwork`, restricted filesystem view, unprivileged user; a compromised parser process cannot reach the network or the rest of the filesystem |
| Malicious USB device presenting as storage | Standard USB-mass-storage/MTP handling; no auto-execution of any content from removable storage, ever |
| Bootloader-level attack | Bounded by whatever hardware root-of-trust the specific device actually has (§25) — documented honestly per Device Profile, not oversold |
| Physical access / device theft | Explicitly acknowledged, partially mitigated only (§25's opt-in-encryption trade-off) |
| Filesystem corruption (e.g., power loss mid-write) | Read-only system tree (§9, §32) means corruption can only affect user data, never the bootable system; CRITICAL BATTERY auto-suspend (§21.2) reduces the window for a mid-write power loss |
| Downgrade attack | Anti-downgrade / monotonic version check (§25) |
| Supply chain (compromised build pipeline, dependency, or contributor commit) | Reproducible builds (§33), signed artifacts, CI security scanning (§34); no silver bullet, but standard layered practice |

---

## 46. Architectural Decisions

The load-bearing decisions from this document, consolidated for quick reference (each is argued in full at its home section):

1. **"Alpine" means the image-update mechanism/the image-build pipeline/the selected image-update mechanism tooling + Alpine Linux userspace, not literal Alpine package compatibility on a phone.** (§9)
2. **Device kernels are sourced from the existing phone-Linux ecosystem (postmarketOS-style mainline where possible, Halium/libhybris where not), never derived from scratch.** (§11)
3. **A hard Core/Device-Port split makes device count a linear, not combinatorial, cost.** (§7, §13, §33)
4. **KOReader is adopted wholesale as the reader/library/OPDS engine, process-isolated, rather than rebuilt from MuPDF/Poppler/Readium parts.** (§15)
5. **No Wayland compositor unless Phase 1 proves one is actually needed; direct DRM/KMS is the default assumption.** (§14)
6. **Radios are gated at a system chokepoint (`powerd`), not left to application-level discipline.** (§21.2)
7. **project-defined signed image updates with rollback, not naive A/B partitioning — materially better fit for constrained flash storage.** (§22)
8. **No full-disk encryption at MVP, traded explicitly against the zero-friction-resume UX promise.** (§25)
9. **No DRM support of any kind, with Readium LCP named as the sole architecturally-plausible future exception because it is open rather than proprietary.** (§27)
10. **KOReader's AGPL-3.0 boundary is kept clean via process isolation (IPC, not linking), so it doesn't drag the rest of the codebase under AGPL.** (§40)
11. **D-Bus for system IPC; explicitly not gRPC/REST — solving problems this system doesn't have.** (§31)
12. **No public power-life numbers until the §37 methodology has actually been run.** (§21.3, §36, §37)

---

## 47. Open Questions

Genuinely unresolved, and flagged as such rather than papered over:

1. **Encryption vs. frictionless resume (§25)** — is opt-in-only the right final answer, or should the project revisit a lower-friction encryption scheme (e.g., hardware-backed key storage that doesn't require passphrase entry on every resume) once a specific device's hardware capabilities are known?
2. **`library-svc` as a separate component (§8)** — will KOReader's own database prove sufficient indefinitely, or will a real need for independent catalog metadata force a second data store into existence, and if so, how is consistency between the two guaranteed?
3. **Compositor necessity (§14)** — resolved empirically in Phase 1, not here; this document's "no compositor by default" stance is a hypothesis, not a settled fact.
4. **KOReader upstream relationship (§15, §40)** — will the project's specific needs (a much simpler default settings surface, an OS-driven first-boot flow) be achievable through KOReader's existing configuration/patch system, or will they require upstream feature requests with uncertain timelines? This materially affects the Phase 4 schedule.
5. **E-Ink roadmap (§20's non-goal, §37)** — is there a realistic future device class (e.g., a decommissioned E-Ink device with an unlockable bootloader) worth designing display-abstraction headroom for now, even though no such target device is identified yet?
6. **Certification "N consecutive builds" threshold (§38)** — deliberately left as a Phase 8 policy decision; too early to fix a number with zero devices yet certified.
7. **Branding (§9, §42)** — does "Alpine EReader OS" invite enough confusion with desktop Alpine to justify a distinct name before public release, given this document's own finding that the relationship is "tooling philosophy," not "spin"?

---

## 48. Final Recommended Architecture

Synthesizing §1–§47 into the single recommended shape of the system:

**Composition and update layer**: Alpine's `the image-update mechanism` + `the image-build pipeline` toolchain, producing signed, atomically-updatable OCI-based system images with the selected image-update mechanism's read-only-`/usr` model underneath — chosen for its storage-efficient rollback (no full A/B duplication needed) on flash-constrained repurposed hardware, and because it lets device support be assembled as **Core layer + Device Port layer**, keeping the cost of supporting device N+1 independent of devices 1 through N.

**Device enablement layer**: kernels and hardware bring-up sourced from the existing Linux-on-phones ecosystem — mainline where a device already has it, vendor-downstream where it doesn't, and Halium/libhybris where only Android's own binary blobs make a subsystem work at all — never re-derived from scratch. This project's scope is structurally easier than a general-purpose Linux phone because it explicitly doesn't need the hardest subsystems (camera, modem, GPS) that consume most porting effort elsewhere.

**Application layer**: KOReader, adopted as a process-isolated engine rather than reimplemented, wrapped in a deliberately thin, custom EReader Shell that owns first-boot, the library grid, and a short settings surface — keeping the AGPL boundary clean via IPC rather than linking, and keeping the reskinning effort bounded to configuration rather than a fork.

**Display**: direct DRM/KMS rendering by default, Weston kiosk-shell held in reserve, no general compositor, no desktop environment — because the system only ever shows one surface.

**Power**: a `powerd`-enforced state machine (ACTIVE / READING / IDLE / SUSPEND / SHUTDOWN / LOW BATTERY / CRITICAL BATTERY) that gates radios at a single chokepoint, with an explicit, public acknowledgment that LCD hardware cannot match E-Ink reading-time battery life, and a real, published measurement methodology instead of promised numbers.

**Security posture**: signed images end to end, sandboxed reader process (the system's only real untrusted-input surface), read-only system partition, anti-downgrade protection, and one explicitly disclosed, deliberate gap — no full-disk encryption at MVP — rather than an unstated one.

**Governance**: this document's own Decision/Options/Trade-offs/Recommendation/Reasoning format becomes the project's RFC template; per-device maintainership keeps device-specific trust bounded; a three-tier certification system (🟢/🟡/🔴) tells users the truth about what will and won't work before they wipe their hardware.

**What makes this buildable by a small team**: nearly every hard subsystem in this architecture is a *reuse* decision, not a *build* decision — Alpine `apk` plus project-maintained image/update tooling, device kernels (postmarketOS/Halium ecosystem), the reader/library/OPDS engine (KOReader), Wi-Fi association (`iwd`/`wpa_supplicant`), IPC (`D-Bus`). What remains to actually build is comparatively small and well-bounded: `powerd`'s state machine, the thin EReader Shell, the Device Profile/Device Port packaging convention, and the installer — which is exactly the size of project a small, focused team can realistically ship, iterate on, and maintain.

---

*End of Phase 0 architecture specification. Per project instruction, no implementation code, build scripts, or installation commands are included above. The recommended next step is Phase 1 (Proof of Concept), whose first and most schedule-critical action is verifying bootloader-unlock feasibility on the physical Galaxy J2 Core unit intended for testing, before any other engineering time is invested.*
