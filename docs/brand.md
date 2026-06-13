# Brand

The dLight visual identity is small and deliberate: one mark, one wordmark, a single accent blue, and a tunable-white gradient that nods to the product itself. This page documents the canonical tokens so the integration, this site, and any future artwork stay consistent.

!!! info "Canonical source"
    The brand files live in `custom_components/dlight/brand/` (SVG + PNG, light and dark variants). **Don't move them** — Home Assistant 2026.3+ serves the integration icon from exactly that path, and HACS validation expects it there. This page mirrors the values defined in those SVGs.

## The mark

The icon is a stylized desk lamp: a rounded head (the bezel) containing a warm-to-cool light panel, on a stem and base.

![dLight icon](assets/icon.svg#only-light){ width="96" }
![dLight icon](assets/dark_icon.svg#only-dark){ width="96" }

The light panel uses the **tunable-white gradient**; everything else (bezel, stem, base) is the brand blue — or its lightened variant on dark backgrounds.

## The wordmark

“dLight” is set in **Comfortaa Bold**, outlined to paths in the SVG so it renders identically everywhere without a web-font dependency.

![dLight logo](assets/logo.svg#only-light){ width="280" }
![dLight logo](assets/dark_logo.svg#only-dark){ width="280" }

## Color palette

<div class="dlight-swatches" markdown>
<div class="dlight-swatch" style="background:#4285F4">Primary blue<br>#4285F4</div>
<div class="dlight-swatch" style="background:#8AB4F8">Blue (dark bg)<br>#8AB4F8</div>
<div class="dlight-swatch" style="background:#3C4043">Wordmark grey<br>#3C4043</div>
<div class="dlight-swatch" style="background:#E8EAED;color:#3C4043">Grey (dark bg)<br>#E8EAED</div>
</div>

<div class="dlight-swatches" markdown>
<div class="dlight-swatch" style="background:#FFB54D;color:#3C4043">Warm<br>#FFB54D</div>
<div class="dlight-swatch" style="background:#FFF1DC;color:#3C4043">Neutral<br>#FFF1DC</div>
<div class="dlight-swatch" style="background:#7CACF8">Cool<br>#7CACF8</div>
</div>

| Token | Light | Dark | Used for |
|---|---|---|---|
| **Primary blue** | `#4285F4` | `#8AB4F8` | Bezel, stem, base; UI accents and links. |
| **Wordmark grey** | `#3C4043` | `#E8EAED` | The “dLight” wordmark. |
| **Tunable-white ramp** | `#FFB54D` → `#FFF1DC` → `#7CACF8` | same | The light panel; decorative gradient rules. |

The ramp is literal: it spans the lamp's real **2600 K (warm) → 6000 K (cool)** range — the same span the light entity exposes in Home Assistant.

## Asset variants

| File (in `brand/`) | Purpose |
|---|---|
| `icon.svg` / `icon.png` / `icon@2x.png` | Square mark, light backgrounds. |
| `dark_icon.svg` / `dark_icon.png` / `dark_icon@2x.png` | Square mark, dark backgrounds. |
| `logo.svg` / `logo.png` / `logo@2x.png` | Mark + wordmark, light backgrounds. |
| `dark_logo.svg` / `dark_logo.png` / `dark_logo@2x.png` | Mark + wordmark, dark backgrounds. |

This documentation site reuses copies of these assets under `docs/assets/` and wires the palette into the Material theme via `docs/stylesheets/brand.css`, so the docs match the integration's identity.

## Documentation illustrations

A few additional on-brand illustrations are generated for the docs (all under `docs/assets/`), built from the same tokens above:

| Asset | Purpose |
|---|---|
| `hero.svg` | Glowing-lamp hero illustration on the landing page. |
| `color-temperature.svg` | The 2600 K → 6000 K tunable-white scale, reused in [Features](user-guide/features.md) and [Transitions](user-guide/transitions.md). |
| `entities.svg` | The device card with its Light, Identify, and Connectivity entities. |
| `social-card.svg` / `social-card.png` | Open Graph / link-preview card (1200 × 630). The PNG is the rasterized output wired into every page's `og:image`. |

These are project illustrations, not part of the integration package — they live only in the docs tree and don't ship in `dlight.zip`.

## Usage guidelines

- **Pick the right variant for the background** — light assets on light, dark assets on dark. Don't recolor the mark by hand; use the provided dark variants.
- **Keep the gradient direction warm → cool** (left to right). It mirrors the product's color-temperature axis.
- **Don't stretch or recolor the wordmark.** It's outlined Comfortaa Bold; substituting a different weight or font breaks the identity.
- **Give the mark clear space** roughly equal to the height of its base.
- This is an **unofficial** community integration. The branding identifies *this project*; it isn't an endorsement by, or affiliation with, the dLight hardware vendor.
