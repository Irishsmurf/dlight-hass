# GEMINI.md - dLight Home Assistant Integration

## Project Overview
The `dlight` project is a Home Assistant custom integration designed to provide local control for dLight smart lamps. It leverages the `dlight-client` Python library to communicate with the devices over the local network, bypassing the need for cloud services.

### Core Technologies
- **Home Assistant:** The primary platform for the integration.
- **Python:** The programming language used for the integration logic.
- **dlight-client (v1.4.0):** A specialized library for interacting with dLight devices, supporting Python 3.12+.
- **asyncio:** Used for asynchronous communication and operations.

### Architecture
- **Config Flow:** Managed via `config_flow.py`, supporting automatic UDP discovery and manual entry.
- **Light Platform:** Implemented in `light.py`, it defines the `DLightEntity` using `CoordinatorEntity` for robust state management.
- **Data Update Coordinator:** Centralized polling and state management, stored in `hass.data[DOMAIN][entry_id]`.
- **Constants:** Centralized in `const.py`.

## Building and Running
As this is a Home Assistant custom component, it executes within the Home Assistant environment.

### Prerequisites
- Home Assistant (installed and running).
- Python 3.12+.

### Commands
- **Install Dependencies:** `pip install -r requirements.txt`
- **Testing:** `pytest` (Configured in `pytest.ini`).
- **CI/CD:** GitHub Actions for Hassfest, HACS validation, and Pytest.

### TODOs
- [x] Implement unit tests in `tests/test_light.py` and `tests/test_config_flow.py`.
- [x] Add a `const.py` file to centralize domain and other constants.
- [x] Implement device discovery in the config flow.
- [x] Setup GitHub Actions for validation and testing.
- [x] Add brand assets for HACS.

## Development Conventions
- **Domain:** `dlight` (Renamed from `dlight-hass`).
- **Logging:** Standard `logging` module.
- **Configuration:** Config Flow only.
- **Testing:** High coverage requirement for PRs.
