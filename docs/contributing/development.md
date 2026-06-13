# Development Setup

Contributions are welcome — bug fixes, new translations, docs, and features. This page gets you a working local environment.

## Prerequisites

- **Python 3.12+** (the integration targets 3.12).
- **Git**, and a GitHub account for pull requests.
- A code editor; the repo includes no IDE config, so anything works.

## Get the code

```bash
git clone https://github.com/Irishsmurf/dlight-hass.git
cd dlight-hass
```

## Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

## Install dependencies

```bash
pip install -r requirements.txt
```

The test suite additionally needs the Home Assistant test harness:

```bash
pip install pytest pytest-asyncio pytest-homeassistant-custom-component pytest-sugar
```

!!! tip "Match CI"
    These are exactly the packages the Release/Test workflows install, so a green local run mirrors CI.

## Repository layout

```
custom_components/dlight/   # the integration
├── __init__.py             # composition root
├── coordinator.py          # polling + command lock + rediscovery
├── light.py                # light entity, optimistic state, transitions
├── button.py               # identify button
├── binary_sensor.py        # connectivity sensor
├── config_flow.py          # discovery / manual / reconfigure / dhcp
├── diagnostics.py          # redacted snapshot
├── const.py                # constants
├── strings.json            # source UI strings
├── translations/           # en, de, fr, ja, ga
└── brand/                  # logo + icon assets (do not move)
tests/                      # pytest suite + fake_lamp.py
docs/                       # this documentation site
AGENTS.md                   # canonical contributor/architecture notes
```

`AGENTS.md` (symlinked as `CLAUDE.md` / `GEMINI.md`) is the canonical short-form contributor guide — read it before larger changes.

## Conventions

- **Config-flow only.** No YAML configuration paths.
- **Patch at the package root in tests.** `DLightDevice` / `AsyncDLightClient` are patched at `custom_components.dlight.*`, where they're instantiated; the coordinator is read from `entry.runtime_data`.
- **Localization parity is mandatory.** Any new UI string, config-flow step, or exception key must be added to `strings.json` and mirrored in **all** of `translations/{en,de,fr,ja,ga}.json`. See [Localization](localization.md).
- **High test coverage** is expected for PRs — run `pytest` before committing. See [Testing](testing.md).
- **Don't move `brand/`.** Home Assistant 2026.3+ serves the integration icon from exactly that path, and the HACS brands check expects it there.

## Running against a real (or fake) lamp

You don't need hardware. `tests/fake_lamp.py` simulates a dLight with injectable delays, resets, and hangs for chaos testing:

```bash
python3 tests/fake_lamp.py
```

To test against a real Home Assistant instance, symlink or copy `custom_components/dlight/` into a dev HA config's `custom_components/` directory and restart.

## Submitting changes

1. Branch off `main`.
2. Make the change with tests and (if user-facing) translations.
3. Run `pytest` locally — keep it green.
4. Open a pull request. CI runs **Hassfest**, **HACS validation**, and **pytest** automatically.

When a change alters a documented architectural decision, update or add an ADR (see [Architecture Overview](../architecture/overview.md#design-decisions)).
