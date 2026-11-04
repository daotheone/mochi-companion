# mochi-companion
Get me out of the loneliness. A desktop companion that help me do task management, check on me and give some other interactions. Personal project.

## Phase 1: terminal chat

Chat with Mochi in the terminal; the Conversation survives restarts.

### Setup
- Linux, Python 3.14 (developed on GNOME/Wayland).
- With [uv](https://docs.astral.sh/uv/): `uv sync`. Without: `python3.14 -m venv .venv && .venv/bin/pip install -e . pytest`.
- Get a DeepSeek API key and put it in the environment or an uncommitted `.env` in the repo root:
  `DEEPSEEK_API_KEY=...`
- Optional settings: `MOCHI_MODEL` (default `deepseek-flash`), `MOCHI_HISTORY_LIMIT` (default `20`), `MOCHI_DATA_DIR`, `MOCHI_PERSONA`.

### Launch
`uv run mochi` (or `.venv/bin/mochi`, or `python -m companion.cli`)

Commands: `/new` starts a new Conversation, `/retry` resends the unanswered Message, `/quit` exits.
History lives in SQLite at `~/.local/share/mochi-companion/mochi.db`. Edit Mochi's Persona in `persona/mochi.md`.

### Tests
`uv run pytest` (uses a fake provider; no API requests).

### Privacy
The most recent Messages (default 20) and the Persona are sent to DeepSeek, a hosted provider, on every request.

## Phase 3: desktop Character

Mochi as a floating, transparent figure on the desktop (PySide6). It shares Memories with the terminal but keeps its own Conversations; each launch starts a new one.

- Install: `uv sync --extra desktop` (or `.venv/bin/pip install -e '.[desktop]'`). Launch: `mochi-desktop`.
- Runs through XWayland (`QT_QPA_PLATFORM=xcb`, see ADR 0001). Typing Vietnamese needs your IBus input method to reach XWayland apps (`QT_IM_MODULE=ibus` if it does not).
- Click Mochi for the Chat Box (Esc or click again to close); double-click for the Main Window (Conversation, Memories). Right-click: Hide, Quit.
- Running `mochi-desktop` again toggles visibility, so bind it to a GNOME shortcut or a `.desktop` launcher.
- Position and size live in `~/.config/mochi-companion/desktop.json` (`size`, default 128).
- Art: `companion/desktop/sprites/frames.json` maps each state to a row of the spritesheet. Swap in final art by editing the map; `scripts/make_placeholder_sprites.py` regenerates the placeholder.
