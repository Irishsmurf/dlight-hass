# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Redact `macAddress` in diagnostics download by adding it to `TO_REDACT` and passing `coordinator.info` through `async_redact_data` (closes #59).
- Log all exceptions from a failed `_send()` batch before re-raising the first, so compound device failures (e.g. simultaneous `turn_on` + `set_brightness` errors) are fully visible in the HA log (closes #60).
- Suppress spurious `dlight_physical_control` event after a failed emulated transition by stamping `_last_command_time` at fade start and short-circuiting `_handle_coordinator_update` via a `_fade_failed` guard (closes #61).

## [2.3.2] - 2026-06-14

### Fixed
- Refine `discovery_none` translation wording in `de`, `fr`, `ga`, and `ja` locale files for clarity and grammatical accuracy; restore the `en` locale file to match the canonical `strings.json` content.

## [2.3.1] - 2026-06-14

### Fixed
- Add missing `discovery_none` translation strings to `strings.json` and all five locale files (`en`, `de`, `fr`, `ga`, `ja`), fixing blank UI when UDP discovery returns zero results (closes #45).
- Restore separate `FADE_TO_OFF_TARGET_PCT = 1` constant so `_async_start_turn_off_fade` fades to 1% (not 5%), giving full-range step count and proper pacing at low brightness (closes #46).
- Replace misleading `rediscovery_triggered` binary sensor attribute with `rediscovery_in_progress` backed by a real task-liveness check on the coordinator (closes #47).
- Add `identify_in_progress` flag to coordinator; set in `button.py` `async_press` via try/finally and checked in `light.py` `_handle_coordinator_update` to suppress spurious `dlight_physical_control` events when a coordinator poll lands mid-flash (closes #51).
- Replace `math.floor` with `_to_ha_brightness` when clamping `_optimistic_brightness` in `async_turn_on`, and use `clamped_pct` directly in device commands to avoid a lossy HA→device→HA round-trip; fix the rapid-fire guard comparison to compare in HA scale so clamped-floor polls are correctly accepted (closes #48).
- Clamp `start_pct` to `MIN_BRIGHTNESS_PCT` before computing the interpolation plan in `_async_start_turn_on_fade`, eliminating the visual stutter when fading up from a sub-floor brightness set by an external client (closes #49).
- Extract `_filter_new_devices` and `_heal_known_lamps` helpers in `config_flow.py`; `async_step_retry` now calls only `_filter_new_devices`, preventing a silent coordinator reload when a known lamp reappears on a new IP during a user-initiated retry scan (closes #50).

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
