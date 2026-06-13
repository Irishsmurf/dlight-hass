# Localization

The integration aims for **Gold-tier** localization. Every user-facing string is translated, and **parity across languages is mandatory** — a string added in one language must exist in all of them.

## Supported languages

| Code | Language |
|---|---|
| `en` | English |
| `de` | German |
| `fr` | French |
| `ja` | Japanese |
| `ga` | Irish |

## How strings are organized

- **`strings.json`** — the canonical English source. New strings start here.
- **`translations/<code>.json`** — one file per language, mirroring the structure of `strings.json`.

Strings cover three areas:

| Section | What it holds |
|---|---|
| `config.step` | Config-flow steps — titles, descriptions, field labels, field hints. |
| `config.error` / `config.abort` | Form errors and abort reasons. |
| `exceptions` | Translatable runtime errors (e.g. `turn_on_failed`, `identify_failed`). |

## The parity rule

> Any new UI string, config-flow step, or exception key **MUST** be added to `strings.json` and mirrored in **every** file under `translations/`.

A new key in `strings.json` that's missing from `de.json` (or any other) breaks parity and will be caught in review (and by Hassfest/HACS validation around translation structure).

## Adding or changing a string

1. Add or edit the key in **`custom_components/dlight/strings.json`**.
2. Apply the **same change to every** `translations/*.json` file, with the translated value:
   - `en.json` — mirror the English source.
   - `de.json`, `fr.json`, `ja.json`, `ga.json` — provide the localized text.
3. Keep the **key structure identical** across all files — only the values differ.
4. Run `pytest` and let Hassfest validate locally/in CI.

```json title="Example: same key, every file"
// strings.json  +  en.json
"turn_on_failed": { "message": "Failed to turn on {device_name}. Device reported: {error}" }

// de.json
"turn_on_failed": { "message": "{device_name} konnte nicht eingeschaltet werden. Gerät meldete: {error}" }
```

!!! warning "Placeholders are literal"
    Tokens like `{device_name}` and `{error}` are substituted at runtime — **do not translate or rename them**. Keep them exactly as in the source.

## Adding a new language

1. Create `translations/<code>.json` as a full copy of `en.json`.
2. Translate every value (not the keys, not the placeholders).
3. Update any contributor docs that enumerate supported languages (this page, the README, and `AGENTS.md`).
4. Add tests/validation expectations if the suite enumerates languages.

## Translation tips

- Match Home Assistant's own tone — concise, imperative, sentence case.
- Keep field hints short; they render under inputs.
- When unsure about a term, check how Home Assistant core translates the equivalent concept in the same language.
