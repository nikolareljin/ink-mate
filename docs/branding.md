# Brand and application assets

InkMate's identity combines a compact e-paper device with a friendly ink-drop
speech glyph. It is intended to remain recognizable at favicon size.

## Assets

| File | Use |
| --- | --- |
| `assets/inkmate-logo.png` | Transparent master logo for documentation and presentations |
| `assets/inkmate-app-icon-512.png` | 512 px application/PWA icon |
| `assets/inkmate-app-icon-192.png` | 192 px application/PWA icon |
| `assets/favicon.ico` | Multi-resolution 16–256 px browser favicon |
| `assets/inkmate-hero.png` | Wide README, website, and presentation hero |

All logo-derived PNG files include transparency. Keep the master proportions
and do not recolor individual facial or sparkle elements independently.

## Visual language

- Charcoal represents the enclosure and ink.
- Warm cream represents the reflective, non-backlit e-paper surface.
- Muted teal is a restrained status accent, not a full-screen UI color.
- Rounded geometry keeps the hardware approachable without implying a toy.

The hero is an illustrative product concept, not a mechanical rendering of the
shipping enclosure. Hardware photographs should be labelled separately.

## Web use

```html
<link rel="icon" href="/assets/favicon.ico" sizes="any">
```

README and documentation references use repository-relative paths so they work
on GitHub and in static documentation generators.

## Generation provenance

The raster logo and hero were generated with the built-in OpenAI image tool.
The logo was generated on a chroma-key field and processed locally to produce
