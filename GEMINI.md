# GEMINI.md - dLight Home Assistant Integration

## Project Overview
The `dlight-hass` project is a Home Assistant custom integration designed to provide local control for dLight smart lamps. It leverages the `dlight-client` Python library to communicate with the devices over the local network, bypassing the need for cloud services.

### Core Technologies
- **Home Assistant:** The primary platform for the integration.
- **Python:** The programming language used for the integration logic.
- **dlight-client (v1.4.0):** A specialized library for interacting with dLight devices, supporting Python 3.11+.
- **asyncio:** Used for asynchronous communication and operations.

### Architecture
- **Config Flow:** Managed via `config_flow.py`, allowing users to add devices through the Home Assistant UI by providing an IP address and Device ID.
- **Light Platform:** Implemented in `light.py`, it defines the `DLightEntity` which inherits from `CoordinatorEntity` and `LightEntity`.
- **Data Update Coordinator:** Uses `DataUpdateCoordinator` to poll the device state every 30 seconds, ensuring Home Assistant stays in sync with the physical hardware.
- **Optimistic Updates:** The integration employs an optimistic state model, updating the UI immediately upon a service call before waiting for a confirmed poll result.

## Building and Running
As this is a Home Assistant custom component, it does not require a traditional build process. It is executed within the Home Assistant environment.

### Prerequisites
- Home Assistant (installed and running).
- Python 3.12+ (as per Home Assistant requirements).

### Commands
- **Install Dependencies:** `pip install -r requirements.txt`
- **Testing:** `pytest`
- **Linting/Style:** Follow standard Home Assistant development guidelines (e.g., using `ruff` or `flake8`).

### TODOs
- [x] Implement unit tests in `tests/test_light.py` and `tests/test_config_flow.py`.
- [x] Add a `const.py` file to centralize domain and other constants.
- [x] Implement device discovery in the config flow.

## Development Conventions
- **Domain:** The integration domain is `dlight`.
- **Logging:** Use the standard `logging` module with a logger named after the module (e.g., `_LOGGER = logging.getLogger(__name__)`).
- **Configuration:** Always use Config Flow for device configuration; avoid `configuration.yaml` if possible.
- **Type Hinting:** Use Python type hints consistently across the codebase.
- **Error Handling:** Use specific exceptions from the `dlightclient` library (`DLightError`, `DLightTimeoutError`, etc.) to handle communication issues gracefully.
- **Entity Naming:** Use `_attr_has_entity_name = True` and follow Home Assistant's naming conventions for devices and entities.
