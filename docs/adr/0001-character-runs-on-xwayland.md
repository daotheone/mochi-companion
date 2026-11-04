# Character runs on XWayland, not native Wayland

The Character needs to place itself, stay on top, and remember its position, and native Wayland gives a client no way to do the first or last of these on GNOME. So the desktop app forces Qt's `xcb` platform and runs through XWayland, even though the rest of the desktop is Wayland. Do not "fix" this by removing the override.

## Considered Options

- **Native Wayland**: rejected, because the app cannot position itself or stay above other windows.
- **GNOME Shell extension**: rejected, because it adds a second JavaScript codebase that can break on each GNOME release.
- **Regular small window**: kept as the fallback if the overlay proves unusable.

## Consequences

The usual cost of XWayland is blur on scaled displays. Both current monitors run at scale 1, so this does not apply yet, but it would on a scaled display. The Character also depends on GNOME continuing to ship XWayland.
