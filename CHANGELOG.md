# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Fire a `dlight_physical_control` HA event when a poll detects a state change that was not initiated by Home Assistant, enabling automations that respond to physical button presses or external control.

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
