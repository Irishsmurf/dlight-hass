# AGENTS.md — dLight Home Assistant Integration

> Canonical agent instructions. `CLAUDE.md` and `GEMINI.md` are symlinks to this file — edit here only.

## Project Overview

`dlight` is a Home Assistant custom integration providing **local control** for dLight smart lamps via the `dlight-client` Python library (UDP discovery + TCP commands). No cloud dependency.

- **Domain:** `dlight` — one config entry per physical lamp, unique ID `dlight_{device_id}`.
- **Requires:** Python 3.12+, Home Assistant 2024.1+ (developed against 2025.1 APIs), `dlight-client==1.4.0`.

## Architecture

| Module (`custom_components/dlight/`) | Responsibility |
|---|---|
| `__init__.py` | Composition root: builds `DLightDevice` + `DLightCoordinator`, primes the first refresh, publishes the coordinator via the typed `entry.runtime_data` (`DLightConfigEntry` alias), registers the options-reload listener. No `hass.data` usage. |
| `coordinator.py` | `DLightCoordinator`: fetches static device info (model/firmware) **once** in `_async_setup`; polls only `get_state()` on the configurable interval. State-poll failure ⇒ entity unavailable. |
| `light.py` | `DLightEntity` only — a thin view over the coordinator with *optimistic state*: commands update the UI immediately, the next confirmed poll replaces the guess. Brightness scaling uses ceiling division both ways (1% never becomes "off"). `PARALLEL_UPDATES = 1` serializes commands per lamp. |
| `config_flow.py` | UDP discovery → pick list, manual entry, reconfigure step, and options flow (poll interval 5–600s). Known lamps rediscovered on a new IP are **self-healed** (entry updated + reloaded); manual re-add of a known lamp also refreshes its IP. |
| `diagnostics.py` | Redacted snapshot (IP and device ID scrubbed) of entry data, options, device info, and last state. |
| `const.py` | Domain, config/option keys, poll-interval bounds, Kelvin range (2600–6000K), poll timeout. |
| `translations/` | `en`, `de`, `fr`, `ja`, `ga` — keep key parity with `strings.json` when adding UI text. |

## Commands

- **Install dev dependencies:** `pip install -r requirements.txt`
- **Run tests:** `pytest` (config in `pytest.ini`; uses `pytest-homeassistant-custom-component`)
- **CI:** GitHub Actions run Hassfest, HACS validation, and pytest on push.

## Conventions

- **Config flow only** — no YAML configuration.
- Tests patch `DLightDevice` / `AsyncDLightClient` at the package root (`custom_components.dlight.*`), where they are instantiated; the coordinator is read from `entry.runtime_data`.
- New UI strings go into `strings.json` **and** every file in `translations/`.
- High test coverage expected for PRs; verify with `pytest` before committing.
- Bump `manifest.json` version for every release; tag releases as `vX.Y.Z`.
- `brand/` (repo root) holds logo/icon assets staged for a future `home-assistant/brands` submission — they are not read by HA or HACS from this repo.
