# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Add an MIT `LICENSE` (matching `dlight-client`) and a license badge/section in the README; the HACS Action's license check requires one (`Validation license`).
- Support the standard `flash: short | long` option of `light.turn_on` (`LightEntityFeature.FLASH`): runs `device.flash()` with 2 or 5 blinks under `command_lock`, with `identify_in_progress` set so a mid-flash poll isn't reported as a physical change; the lamp returns to its previous state. A failure raises the new translated `flash_failed` error (closes #92).

### Fixed
- Snap `color_temp_kelvin` to the lamp's 100 K grid (round half up, then clamp) in `async_turn_on` and in every emulated-fade step. The lamp floors off-grid values on its own (5250 → 5200), so the next poll never matched the optimistic state: the UI snapped back after the hold window and a spurious `dlight_physical_control` `changed` event fired, which broke circadian/sun-following automations (closes #88).
- Restart the optimistic hold window when an emulated fade completes, not only when it starts. A fade longer than the poll interval used to end outside the window, so its closing reconcile compared against the pre-fade state and fired a spurious `dlight_physical_control` `changed` event for the whole fade (closes #89).
- Use the configured poll interval (`coordinator.poll_interval`) for the light's optimistic hold window and the connectivity sensor's `poll_interval_seconds` attribute; both still used the 30 s `POLL_INTERVAL` default after the options flow (#79) made the interval configurable, so with a 60 s interval a stale poll could snap the UI back (closes #90).
- Report the installed firmware as `latest_version` on the update entity until an OTA source exists; with `latest_version = None` Home Assistant showed the entity as `unknown` forever instead of *up to date* (closes #91).
- Retry the static device-info query after a successful poll (at most every `INFO_RETRY_INTERVAL`, 300 s) when it failed at setup, and update the device registry entry in place; a lamp offline at Home Assistant start used to keep a generic card (no model, firmware or MAC) and an unavailable firmware entity until the entry was reloaded. The manufacturer is now plain `dLight` instead of `dLight (via custom integration)` (closes #93).

## [2.5.0] - 2026-06-15

### Added
- Add `OptionsFlowHandler` to `config_flow.py` with three poll-interval presets (15 s / 30 s / 60 s); `DLightCoordinator` reads `entry.options.get("poll_interval", POLL_INTERVAL)` on init so a saved change triggers an entry reload and the new interval takes effect immediately (closes #79).
- Add `dlight.flash` service to `__init__.py`; accepts a `device_id` and calls `device.flash()` under `coordinator.command_lock` — enables automation-triggered lamp identification without targeting the button entity (closes #78).

### Changed
- Add Codecov flags and component definitions for `sensor`, `event`, and `update` platforms in `.codecov.yml` and `tests.yaml`; per-component coverage is now tracked and enforced for all six platforms (closes #74).
- Enrich diagnostics snapshot with a `coordinator_health` dict containing `consecutive_failures` (int), `last_success` (ISO timestamp or null), and `rediscovery_in_flight` (bool); no IP addresses are included in the new fields (closes #75).

### Fixed
- Clamp `color_temp_kelvin` to `[KELVIN_MIN, KELVIN_MAX]` in `async_turn_on` before issuing device commands; out-of-range values (e.g. 6500 K daylight preset) are silently bounded to the hardware range instead of triggering undefined device behaviour (closes #77).
- Override `available` on `DLightUpdateEntity` to return `True` whenever `coordinator.info` contains `swVersion`; the firmware version is static metadata fetched once at setup and should remain visible even while the lamp is unreachable (closes #76).

## [2.4.0] - 2026-06-14

### Added
- Add `sensor` platform with two diagnostic entities per lamp: **Brightness** (%, unique id `dlight_{id}_brightness`) and **Color Temperature** (K, unique id `dlight_{id}_color_temp`), both backed by the existing coordinator poll with no extra network traffic (closes #64).
- Migrate config flow `async_step_user` and `async_step_retry` from blocking `discover_devices()` to streaming `discover_devices_stream()`; a lamp that answers immediately now resolves the pick-list without waiting the full 2-second discovery window (closes #63).
- Add `update` platform with a `DLightUpdateEntity` that surfaces `coordinator.info["swVersion"]` as the installed firmware version (`latest_version = None` until an OTA source is known); entity is diagnostic and goes unavailable with the coordinator (closes #65).

### Changed
- Add `--cov-fail-under=80` coverage gate and `--cov-report=term-missing` summary to the CI pytest job; PRs that drop overall coverage below 80% now fail with a clear per-module report (closes #62).

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
