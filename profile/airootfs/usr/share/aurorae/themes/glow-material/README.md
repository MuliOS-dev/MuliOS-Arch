# Glow Material — Aurorae window decoration

## Appearance

Version 0.1.0 introduces the first window-frame prototype:

- Dark charcoal titlebar (`#171C19`).
- Thin emerald active-window outline (`#48C780`).
- Neutral inactive-window outline (`#35433A`).
- Muted title text for inactive windows.
- Restrained button hover feedback; close uses a muted red hover state.
- No SVG blur filter, compositor dependency, or custom KWin effect.

## Package contents

- `metadata.desktop`: Aurorae theme metadata.
- `GlowMaterialrc`: titlebar, border, and button layout.
- `decoration.svg`: active and inactive frame assets.
- `close.svg`, `minimize.svg`, `maximize.svg`, `restore.svg`: button states.

## Install for the current user

From the repository root:

```sh
mkdir -p ~/.local/share/aurorae/themes
cp -a aurorae/glow-material ~/.local/share/aurorae/themes/
```

Then open **System Settings → Colors & Themes → Window Decorations**, select **Glow Material**, and apply it. The exact category label can vary slightly by Plasma release.

To remove it:

```sh
rm -rf ~/.local/share/aurorae/themes/glow-material
```

Do not use `sudo` for a per-user installation.

## Test checklist

- [ ] Theme appears in the Window Decorations selector.
- [ ] Active window has the emerald border.
- [ ] Inactive window uses the neutral border.
- [ ] Close, minimize, maximize, and restore buttons work.
- [ ] Hover and pressed button states render.
- [ ] Window title remains legible with long titles.
- [ ] Border and titlebar scale correctly at 100%, 125%, 150%, and 200%.
- [ ] Maximized and tiled windows do not show unwanted gaps.
- [ ] Wayland and X11 behavior checked where supported.
- [ ] No SVG parsing or KWin decoration errors in the journal.

## Current limitations

This is an early Aurorae prototype, not a complete desktop theme. The titlebar and frame geometry need visual validation on the actual target KWin release. Aurorae cannot guarantee a custom outer glow beyond the SVG decoration frame; the current border uses layered, translucent vector strokes rather than a blur filter. Maximized-window border behavior must be verified on the target version.

## License

MIT. See the repository root [LICENSE](../../LICENSE).
