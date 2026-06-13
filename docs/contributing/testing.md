# Testing

The integration has a high-coverage `pytest` suite built on `pytest-homeassistant-custom-component`. PRs are expected to keep it green and to add tests for new behavior.

## Run the suite

```bash
pytest
```

Configuration lives in `pytest.ini`:

```ini
[pytest]
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
```

`asyncio_mode = auto` means async tests don't need an explicit marker.

### Useful invocations

```bash
pytest tests/test_light.py            # one module
pytest -k "rediscovery"               # match by name
pytest -x                             # stop on first failure
pytest -vv                            # verbose
```

## Test layout

| File | Covers |
|---|---|
| `tests/conftest.py` | Shared fixtures (mock client/device, config entries). |
| `tests/test_config_flow.py` | Discovery, manual entry, reconfigure, DHCP self-healing. |
| `tests/test_coordinator.py` | Polling, failure handling, rediscovery sweeps. |
| `tests/test_light.py` | Optimistic state, rapid-fire guard, transitions, scaling. |
| `tests/test_button.py` | Identify flash, command-lock behavior, error mapping. |
| `tests/test_binary_sensor.py` | Connectivity reporting and always-available semantics. |
| `tests/test_diagnostics.py` | Redaction of IP and device ID. |
| `tests/test_hacs.py` | HACS/manifest sanity. |
| `tests/fake_lamp.py` | A scriptable fake lamp for chaos testing. |

## Conventions

- **Patch where it's used.** `DLightDevice` and `AsyncDLightClient` are instantiated in `custom_components.dlight.*`, so patch them at the **package root**, not in the third-party library:
  ```python
  with patch("custom_components.dlight.AsyncDLightClient", ...):
      ...
  ```
- **Read the coordinator from `runtime_data`.** Entities are wired through `entry.runtime_data`; reach the coordinator there rather than reconstructing it.
- **No real network.** Tests never touch a real lamp — mock the client/device or use `fake_lamp.py`.

## Chaos testing with the fake lamp

`tests/fake_lamp.py` simulates a dLight you can misbehave on purpose — inject delays, force resets, or hang the socket — to exercise timeout, availability, and rediscovery paths:

```bash
python3 tests/fake_lamp.py
```

Use it to reproduce flaky-network conditions that are hard to script with plain mocks.

## What CI runs

On every push and PR, GitHub Actions run:

| Workflow | Checks |
|---|---|
| `tests.yaml` | The full `pytest` suite. |
| `hassfest.yaml` | Home Assistant's manifest/integration validation. |
| `hacs.yaml` | HACS repository validation (including the brand assets). |

The Release workflow re-runs `pytest` before publishing, so a failing test blocks a release. Match CI locally by installing the same test dependencies listed in [Development Setup](development.md#install-dependencies).

## Writing good tests

- Cover the **edge of the behavior**, not just the happy path — e.g. a stale poll arriving inside the rapid-fire window, a fade cancelled mid-step, a lamp that changes IP while offline.
- Assert on **observable state** (entity attributes, entry data, dispatched reloads), not internal call counts where you can avoid it.
- When you add a user-facing string, add a test only if there's logic around it — but **always** mirror the string across translations (see [Localization](localization.md)).
