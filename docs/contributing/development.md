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

You don't need hardware. `tests/fake_lamp.py` simulates a dLight lamp with configurable network faults for end-to-end chaos testing:

```bash
python3 tests/fake_lamp.py
```

To test against a real Home Assistant instance, symlink or copy `custom_components/dlight/` into a dev HA config's `custom_components/` directory and restart.

## Chaos Testing

`fake_lamp.py` supports injectable failure modes to exercise the coordinator's resilience without real hardware or a bad network.

### Command-line flags

| Flag | Description | Exercises |
|------|-------------|-----------|
| `--drop-rate 0.3` | Silently drop 30% of incoming TCP connections | Coordinator reconnect logic |
| `--error-rate 0.2` | Return invalid (non-JSON) responses for 20% of commands | `UpdateFailed` error path, failure counter |
| `--latency 500` | Add 500 ms to every response | Timeout threshold (`POLL_TIMEOUT`) |
| `--latency-spike 5000 0.1` | 5 000 ms spike on 10% of responses | Race between optimistic hold window and slow confirmation |
| `--disconnect-after 3` | Close TCP after every 3 commands, forcing a reconnect | Persistent-connection re-establishment |
| `--offline-for 60` | Start silent for 60 s then come back | Rediscovery sweep and self-heal path |

**Example — rediscovery scenario:**

```bash
python3 tests/fake_lamp.py --offline-for 120 --drop-rate 0.5
```

Wait for the coordinator to reach `REDISCOVERY_FAILURE_THRESHOLD` failures, then watch the UDP sweep fire in the HA logs.

**Example — rapid-fire guard stress test:**

```bash
python3 tests/fake_lamp.py --latency 800 --error-rate 0.1
```

Send brightness slider commands quickly; confirm the UI doesn't snap back to stale poll values within the hold window.

### Runtime commands

Once running, type commands at the prompt:

| Command | Effect |
|---------|--------|
| `on` / `off` | Toggle lamp power state |
| `bright N` | Set brightness (0–100) |
| `temp N` | Set color temperature (Kelvin) |
| `chaos on` | Enable all chaos modes at once (drop=30%, error=20%, latency=200ms, spikes, disconnect-after=5) |
| `chaos off` | Disable all chaos modes |
| `drop N` | Set drop rate (e.g. `drop 0.4`) |
| `error N` | Set error rate (e.g. `error 0.15`) |
| `latency N` | Set base latency in ms (e.g. `latency 300`) |
| `spike` | Arm a one-shot 10 s latency spike on the next command |
| `offline N` | Go dark for N seconds (simulates DHCP renewal / power cycle) |
| `disconnect N` | Close TCP after every N commands (0 to disable) |
| `status` | Print current lamp and chaos state |
| `quit` | Shut down |

### What each scenario exercises

- **`--drop-rate`** — The coordinator's persistent `AsyncDLightClient` must reconnect. Tests that `UpdateFailed` is raised and the failure counter increments correctly.
- **`--error-rate`** — Protocol-level errors (non-JSON) hit the `except DLightError` path in `_async_update_data`. At `REDISCOVERY_FAILURE_THRESHOLD` consecutive failures the UDP sweep fires.
- **`--latency` / `--latency-spike`** — Responses that arrive after `POLL_TIMEOUT` raise `TimeoutError`. Spikes timed to arrive *within* the optimistic hold window test that the rapid-fire guard correctly suppresses the stale poll.
- **`--disconnect-after`** — Exercises the persistent-connection re-establishment in `dlight-client`. From the coordinator's perspective the next command should transparently succeed after one failure.
- **`--offline-for` / `offline N`** — Simulates a lamp losing power or changing IP. After `REDISCOVERY_FAILURE_THRESHOLD` failures the coordinator launches a UDP sweep (`_async_attempt_rediscovery`). Combine with restarting the fake lamp on a different port (and updating `CONF_IP_ADDRESS` in HA) to test the full self-heal path.

## Submitting changes

1. Branch off `main`.
2. Make the change with tests and (if user-facing) translations.
3. Run `pytest` locally — keep it green.
4. Open a pull request. CI runs **Hassfest**, **HACS validation**, and **pytest** automatically.

When a change alters a documented architectural decision, update or add an ADR (see [Architecture Overview](../architecture/overview.md#design-decisions)).
