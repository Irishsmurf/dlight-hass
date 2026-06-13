<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="custom_components/dlight/brand/dark_logo.png">
    <img src="custom_components/dlight/brand/logo.png" alt="dLight" width="360">
  </picture>
</p>

<p align="center">
  <strong>Local control for dLight smart lamps in Home Assistant — no cloud, low latency.</strong>
</p>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Default-orange.svg" alt="HACS Default"></a>
  <a href="https://github.com/Irishsmurf/dlight-hass/actions/workflows/tests.yaml"><img src="https://github.com/Irishsmurf/dlight-hass/actions/workflows/tests.yaml/badge.svg" alt="Tests"></a>
  <a href="https://github.com/Irishsmurf/dlight-hass/actions/workflows/hassfest.yaml"><img src="https://github.com/Irishsmurf/dlight-hass/actions/workflows/hassfest.yaml/badge.svg" alt="Hassfest"></a>
  <a href="https://github.com/Irishsmurf/dlight-hass/actions/workflows/hacs.yaml"><img src="https://github.com/Irishsmurf/dlight-hass/actions/workflows/hacs.yaml/badge.svg" alt="HACS Action"></a>
</p>

---

**dLight** is a custom [Home Assistant](https://www.home-assistant.io/) integration that controls dLight smart lamps **entirely on your local network**. It uses UDP discovery and persistent TCP connections via the [`dlight-client`](https://pypi.org/project/dlight-client/) library — no cloud account, no vendor API, no internet dependency once the lamp is on your Wi-Fi.

## 📖 Documentation

**Full docs live at → [irishsmurf.github.io/dlight-hass](https://irishsmurf.github.io/dlight-hass/)**

| | |
|---|---|
| 🚀 [Installation](https://irishsmurf.github.io/dlight-hass/getting-started/installation/) | Get it running via HACS or manually. |
| ⚙️ [Configuration](https://irishsmurf.github.io/dlight-hass/getting-started/configuration/) | Discover and add your lamps. |
| 💡 [Features](https://irishsmurf.github.io/dlight-hass/user-guide/features/) | Light, identify button, connectivity sensor. |
| 🔧 [Troubleshooting](https://irishsmurf.github.io/dlight-hass/user-guide/troubleshooting/) | Fix discovery and connectivity issues. |
| 🏗️ [Architecture](https://irishsmurf.github.io/dlight-hass/architecture/overview/) | How the coordinator, optimistic state, and self-healing work. |
| 🤝 [Contributing](https://irishsmurf.github.io/dlight-hass/contributing/development/) | Dev setup, testing, translations, releases. |

## ✨ Features

- **Purely local** — UDP discovery + persistent TCP commands; no cloud dependency.
- **Full control** — on/off, brightness (0–100 %), and tunable white from **2600 K to 6000 K**.
- **Feels instant** — optimistic state updates the UI immediately; a confirmed poll reconciles it.
- **Emulated transitions** — smooth fades despite the protocol having no native fade.
- **IP self-healing** — recovers from DHCP address changes via the DHCP watcher, a runtime discovery sweep, or re-running setup.
- **Diagnostics** — download a sanitized snapshot (IP and device ID redacted) for bug reports.
- **Reconfigure support** — update a lamp's connection details from the UI.
- **Localized** — English, German, French, Japanese, and Irish.

## 🚀 Quick start

1. **Install** via [HACS](https://irishsmurf.github.io/dlight-hass/getting-started/installation/#hacs-recommended) (add this repo as a custom integration repository) or [manually](https://irishsmurf.github.io/dlight-hass/getting-started/installation/#manual).
2. **Restart** Home Assistant.
3. **Add the integration:** Settings → Devices & Services → **+ Add Integration** → search *dLight*. Discovery runs automatically; if it finds nothing (common when HA runs in a container), you add the lamp manually by **IP address + Device ID**.

> [!NOTE]
> A dLight must already be on your Wi-Fi (provisioned via the Google Home app or similar) before Home Assistant can discover it.

## 🤝 Contributing

Bug fixes, features, docs, and translations are all welcome. See the [contributing guide](https://irishsmurf.github.io/dlight-hass/contributing/development/) and the canonical [`AGENTS.md`](AGENTS.md) for architecture notes.

```bash
git clone https://github.com/Irishsmurf/dlight-hass.git
cd dlight-hass
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-homeassistant-custom-component pytest-sugar
pytest
```

The docs site is built with MkDocs:

```bash
pip install -r docs/requirements.txt
mkdocs serve   # http://127.0.0.1:8000
```

## 📦 Releases

Releases are automated: bump the version in `manifest.json`, commit, and push a matching `vX.Y.Z` tag. The Release workflow runs the tests, builds `dlight.zip` (what HACS installs, including the `brand/` assets), and publishes the GitHub release. See [Releasing](https://irishsmurf.github.io/dlight-hass/contributing/releasing/).

## ⚠️ Disclaimer

This is an unofficial community project with no official vendor support. Use at your own risk. The dLight name and branding identify this integration and the hardware it controls; the project is not affiliated with or endorsed by the hardware vendor.
