# IQS Improvements Plan
## Objective
Bring the dLight Home Assistant integration up to Core-grade standards by addressing IQS violations: removing user-configurable polling, using translatable exceptions, and surfacing the device MAC address if
    available.
5
## Key Files & Context
- `custom_components/dlight/config_flow.py`: Contains the `DLightOptionsFlow` to be removed.
- `custom_components/dlight/__init__.py`: Contains options update listener.
- `custom_components/dlight/coordinator.py`: Needs to hardcode the polling interval.
- `custom_components/dlight/const.py`: Polling constants to be updated.
- `custom_components/dlight/light.py`: Exception handling and `DeviceInfo` to be updated.
- `custom_components/dlight/strings.json`: Options strings to be removed, exceptions strings to be added.
- `tests/`: Various test files will need updating to reflect removed options flow and new exception structures.
   14
## Implementation Steps
   16
1. **Remove Options Flow:**
   - Remove `DLightOptionsFlow` and `async_get_options_flow` from `config_flow.py`.
   - Remove `_async_options_updated` and its listener registration from `__init__.py`.
   - Update `const.py` to define a single `POLL_INTERVAL = 30`, removing min/max and default constants.
   - Update `DLightCoordinator` in `coordinator.py` to use the hardcoded `POLL_INTERVAL`.
   - Remove `options` section from `strings.json` and all translation files.
   - Fix any tests relying on the options flow.
   24
2. **Implement Translatable Exceptions:**
   - In `light.py`, import `ServiceValidationError` from `homeassistant.exceptions`.
   - Update `async_turn_on` and `async_turn_off` to raise `ServiceValidationError` with `translation_domain=DOMAIN`, `translation_key="turn_on_failed"` (or `turn_off_failed`), and `translation_placeholders`.
   - Add the corresponding `exceptions` block to `strings.json`.
   - Update `test_light_service_error` in `tests/test_light.py` to assert `ServiceValidationError`.
   30
3. **Surface MAC Address:**
   - Investigate the payload returned by `get_info` and `discover_devices` for a MAC address (e.g., `macAddress` or `mac`).
   - If found, extract it in `coordinator.py`'s `_async_setup` and save it to `self.info`.
   - In `light.py`, import `CONNECTION_NETWORK_MAC` from `homeassistant.helpers.device_registry`.
   - Conditionally add `connections={(CONNECTION_NETWORK_MAC, mac)}` to `DeviceInfo` if the MAC is present in `coordinator.info`.
   36
## Verification & Testing
- Run `pytest` to ensure all tests pass.
- Verify tests reflect the removal of the options flow.
- Ensure the `ServiceValidationError` is correctly raised and formatted in `test_light_service_error`.