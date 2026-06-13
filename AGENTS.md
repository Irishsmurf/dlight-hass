# AGENTS.md — dLight Home Assistant Integration

> Canonical agent instructions. `CLAUDE.md` and `GEMINI.md` are symlinks to this file — edit here only.

## Project Overview

`dlight` is a Home Assistant custom integration providing **local control** for dLight smart lamps via the `dlight-client` Python library (UDP discovery + TCP commands). No cloud dependency.

- **Domain:** `dlight` — one config entry per physical lamp, unique ID `dlight_{device_id}`.
- **Requires:** Python 3.12+, Home Assistant 2024.1+ (developed against 2025.1 APIs), `dlight-client==2.0.0`.

## Architecture

| Module (`custom_components/dlight/`) | Responsibility |
|---|---|
| `__init__.py` | Composition root: builds `DLightDevice` with a **persistent** `AsyncDLightClient`. Registers `client.close` on entry unload. Primes the first refresh and publishes the coordinator via `entry.runtime_data`. |
| `coordinator.py` | `DLightCoordinator`: fetches static device info **once**; polls `get_state(force_update=True)` on interval. Failure ⇒ entity unavailable. After repeated consecutive failures, fires a one-shot UDP rediscovery sweep and self-heals the entry's IP if the lamp answers from a new address. Owns `command_lock`. |
| `light.py` | `DLightEntity`: optimistic state view. Service calls (`turn_on`/`turn_off`) raise `HomeAssistantError` on failure for UI feedback. `transition:` is **emulated** by a cancellable background fade task (no native fade in the protocol). `PARALLEL_UPDATES = 1` serializes service calls; cross-platform command serialization uses `coordinator.command_lock`. |
| `button.py` | Identify button (`ButtonDeviceClass.IDENTIFY`, diagnostic category) — runs `device.flash()` under `coordinator.command_lock`. |
| `binary_sensor.py` | Connectivity diagnostic sensor mirroring `coordinator.last_update_success` (always `available`, so it reports *offline* instead of going unavailable). |
| `config_flow.py` | UDP discovery → pick list, manual entry, reconfigure step, and a `dhcp` step (manifest matches `registered_devices`) that self-heals a known lamp's IP when DHCP hands it a new one. There is **no options flow** (removed per ADR-0010; poll interval is fixed). Known lamps rediscovered on a new IP during a user-initiated scan are also self-healed; manual re-add of a known lamp refreshes its IP too. |
| `diagnostics.py` | Redacted snapshot (IP and device ID scrubbed) of entry data, options, device info, and last state. |
| `const.py` | Domain, config keys, Kelvin range (2600–6000K), poll interval/timeout, rediscovery backoff. |
| `translations/` | `en`, `de`, `fr`, `ja`, `ga` — keep key parity with `strings.json` when adding UI text. |

## Commands

- **Install dev dependencies:** `pip install -r requirements.txt`
- **Run tests:** `pytest`
- **Chaos Testing:** Run `python3 tests/fake_lamp.py` to simulate a lamp with injectable delays, resets, and hangs.
- **CI:** GitHub Actions run Hassfest, HACS validation, and pytest on push.

## Conventions

- **Config flow only** — no YAML configuration.
- Tests patch `DLightDevice` / `AsyncDLightClient` at the package root (`custom_components.dlight.*`), where they are instantiated; the coordinator is read from `entry.runtime_data`.
- **Localization Parity**: New UI strings, config flow steps, or exception keys MUST be added to `strings.json` and mirrored in every file within `translations/` (`en`, `de`, `fr`, `ja`, `ga`) to maintain Gold-tier localization standards.
- High test coverage expected for PRs; verify with `pytest` before committing.
- **Releases are automated**: bump `manifest.json`, commit, push a `vX.Y.Z` tag. The Release workflow verifies the tag matches the manifest version, runs pytest, builds `dlight.zip` (including `brand/`, which HA 2026.3+ serves locally for the integration icon), and publishes the GitHub release with generated notes. Tags with a suffix (`v1.4.0-rc1`) publish as prereleases. HACS installs the zip asset (`zip_release` in `hacs.json`), so every release MUST carry one.
- `custom_components/dlight/brand/` holds logo/icon assets. **Do not move them**: HA 2026.3+ serves them from exactly this path via the local brands proxy (so the icon displays without a `home-assistant/brands` submission), and the HACS Action's brands check also expects them here. They MUST be included in the release zip.
