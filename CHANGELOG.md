# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Add missing `discovery_none` translation strings to `strings.json` and all five locale files (`en`, `de`, `fr`, `ga`, `ja`), fixing blank UI when UDP discovery returns zero results (closes #45).

### Added
- Add structured debug logging across `coordinator.py` (poll start/success/failure, rediscovery), `light.py` (turn-on/off/toggle params, optimistic state, fade step-by-step, poll-guard decisions), and `config_flow.py` (discovery result count, known-lamp self-heal, DHCP step trigger).
- Expand `tests/fake_lamp.py` with injectable chaos: `--drop-rate`, `--error-rate`, `--latency`, `--latency-spike`, `--disconnect-after`, and `--offline-for` CLI flags; runtime `chaos`, `spike`, `offline`, and `disconnect` interactive commands. Add Chaos Testing guide to `docs/contributing/development.md`.

### Fixed
- Register `client.close` before `async_config_entry_first_refresh()` so the persistent TCP connection is always cleaned up, even when setup fails with `ConfigEntryNotReady`.

### Added
- Add `tests/test_init.py` with 8 lifecycle tests covering setup, unload, client cleanup on success and failure, listener registration/removal, and missing-config error paths.
- Add `EventEntity` (`event.py`) for physical control: physical button presses and external state changes now appear as a proper device entity in the HA UI (device class `button`, diagnostic category), in addition to the existing `dlight_physical_control` bus event. Supports event types `turned_on`, `turned_off`, and `changed`.
- Add `docs/user-guide/physical-control-event.md` documenting the `dlight_physical_control` event: payload reference, automation examples, Physical Control entity usage, and limitations. Linked from `features.md`, `mkdocs.yml` nav, and `README.md`.

## [2.1.0] - 2026-06-14

### Added
- Use `DLightDevice.apply_scene()` to atomically apply brightness and color temperature in a single TCP command when both are set together, reducing connection overhead and enabling atomic rollback on failure.
- Fire a `dlight_physical_control` HA event when a poll detects a state change that was not initiated by Home Assistant, enabling automations that respond to physical button presses or external control.
- Integrate Codecov Flags (`coordinator`, `config_flow`, `light`, `button`, `binary_sensor`) for per-component coverage segmentation in CI.
- Add Codecov component definitions (`coordinator`, `config_flow`, `light_entity`, `diagnostics`, `integration_init`) for per-feature coverage thresholds and targeted PR feedback.

## [2.0.0] - 2026-06-14

### Added
- Optimize toggling via native `DLightDevice.toggle()` convenience method.
- Use lightweight `DLightDevice.ping()` connectivity check for faster setup verification and cheap rediscovery pre-checks.
- Switch offline rediscovery from `discover_devices()` to `discover_devices_stream()` for early-exit on first match, reducing unnecessary UDP scan time.

### Changed
- Simplify state updates and transitions by synchronizing entity and coordinator states via local `dlight-client` state change listener push events rather than calling manual `async_request_refresh` poll requests.

### Fixed
- Prevent UI inconsistencies during toggling by properly setting or clearing optimistic brightness and color temperature values in `async_toggle`.
- Defensively handle potential exceptions from lightweight ping checks in setup and rediscovery.

## [1.6.6] - 2026-06-13

### Fixed
- Prevent stale polls from reverting rapid-fire brightness changes.

## [1.6.5] - 2026-06-13

### Changed
- Comfortaa Bold wordmark in logos.

## [1.6.4] - 2026-06-13

### Changed
- Spec-compliant brand icons/logos.

## [1.6.3] - 2026-06-12

### Changed
- Added dLight lockup logos.

## [1.6.2] - 2026-06-12

### Changed
- Added dark-theme icon and bumped GitHub Actions to Node 24.

## [1.6.1] - 2026-06-12

### Changed
- Included `brand/` in the release zip.

## [1.6.0] - 2026-06-12

### Added
- Added transitions, DHCP self-healing, and diagnostic entities.

## [1.5.3] - 2026-06-12

### Changed
- Redesigned brand logo.

## [1.5.2] - 2026-06-10

### Changed
- Release version bump.

## [1.5.1] - 2026-06-10

### Changed
- Release version bump.

## [1.5.0] - 2026-06-10

### Added
- Persistent connections and improved error handling.
