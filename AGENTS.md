# AGENTS.md — dLight Home Assistant Integration

> Canonical agent instructions. `CLAUDE.md` and `GEMINI.md` are symlinks to this file — edit here only.

## Project Overview

`dlight` is a Home Assistant custom integration providing **local control** for dLight smart lamps via the `dlight-client` Python library (UDP discovery + TCP commands). No cloud dependency.

- **Domain:** `dlight` — one config entry per physical lamp, unique ID `dlight_{device_id}`.
- **Requires:** Python 3.12+, Home Assistant 2024.1+ (developed against 2025.1 APIs), `dlight-client==1.6.1`.

## Architecture

| Module (`custom_components/dlight/`) | Responsibility |
|---|---|
| `__init__.py` | Composition root: builds `DLightDevice` with a **persistent** `AsyncDLightClient`. Registers `client.close` on entry unload. Primes the first refresh and publishes the coordinator via `entry.runtime_data`. |
| `coordinator.py` | `DLightCoordinator`: fetches static device info **once**; polls `get_state(force_update=True)` on interval. Failure ⇒ entity unavailable. |
| `light.py` | `DLightEntity`: optimistic state view. Service calls (`turn_on`/`turn_off`) raise `HomeAssistantError` on failure for UI feedback. `PARALLEL_UPDATES = 1` serializes commands per lamp. |
| `config_flow.py` | UDP discovery → pick list, manual entry, reconfigure step, and options flow (poll interval 5–600s). Known lamps rediscovered on a new IP are **self-healed** (entry updated + reloaded); manual re-add of a known lamp also refreshes its IP. |
| `diagnostics.py` | Redacted snapshot (IP and device ID scrubbed) of entry data, options, device info, and last state. |
| `const.py` | Domain, config/option keys, poll-interval bounds, Kelvin range (2600–6000K), poll timeout. |
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
- **Releases are automated**: bump `manifest.json`, commit, push a `vX.Y.Z` tag. The Release workflow verifies the tag matches the manifest version, runs pytest, builds a slim `dlight.zip` (excludes `brand/`), and publishes the GitHub release with generated notes. Tags with a suffix (`v1.4.0-rc1`) publish as prereleases. HACS installs the zip asset (`zip_release` in `hacs.json`), so every release MUST carry one.
- `custom_components/dlight/brand/` holds logo/icon assets. **Do not move them**: the HACS Action's brands check requires them at exactly this path (until the domain is submitted to `home-assistant/brands`).
