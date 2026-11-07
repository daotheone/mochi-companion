# mochi-companion
Get me out of the loneliness. A desktop companion that help me do task management, check on me and give some other interactions. Personal project.

## Install (quick start)

Mochi needs Linux, Python 3.14 or newer (3.15 works) and a [DeepSeek](https://platform.deepseek.com/) API key.

```bash
# 1. Get the code
git clone https://github.com/daotheone/mochi-companion.git
cd mochi-companion

# 2. Create a virtual environment and install, including the desktop Character
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[desktop]'      # or: uv sync --extra desktop

# 3. Add your API key (the .env file is not committed)
echo 'DEEPSEEK_API_KEY=your-key-here' > .env

# 4. Launch
mochi-desktop                    # the desktop Character
mochi                            # or chat in the terminal
```

Notes:
- Run `source .venv/bin/activate` in each new shell, or call `.venv/bin/mochi-desktop` directly.
- Python upgrades break a virtual environment (`ModuleNotFoundError: No module named 'companion'`). Delete `.venv` and repeat step 2.
- Running `mochi-desktop` again toggles Mochi's visibility, so you can bind it to a GNOME shortcut.
- Details for each interface are below.

## Phase 1: terminal chat

Chat with Mochi in the terminal; the Conversation survives restarts.

### Setup
- Linux, Python 3.14 (developed on GNOME/Wayland).
- With [uv](https://docs.astral.sh/uv/): `uv sync`. Without: `python3 -m venv .venv && .venv/bin/pip install -e . pytest`.
- Get a DeepSeek API key and put it in the environment or an uncommitted `.env` in the repo root:
  `DEEPSEEK_API_KEY=...`
- Optional settings: `MOCHI_MODEL` (default `deepseek-flash`), `MOCHI_HISTORY_LIMIT` (default `20`), `MOCHI_DATA_DIR`, `MOCHI_PERSONA`, `MOCHI_RECAP_MAX_DAYS` (default `3`: older Recaps are not sent to Mochi), `MOCHI_RECAP_FRESH_HOURS` (default `24`).

### Launch
`uv run mochi` (or `.venv/bin/mochi`, or `python -m companion.cli`)

Commands: `/new` starts a new Conversation (and writes a Recap of the old one), `/recaps` lists Recaps, `/retry` resends the unanswered Message, `/quit` exits.
History lives in SQLite at `~/.local/share/mochi-companion/mochi.db`. Edit Mochi's Persona in `persona/mochi.md`.

### Tests
`uv run pytest` (uses a fake provider; no API requests).

### Privacy
The most recent Messages (default 20) and the Persona are sent to DeepSeek, a hosted provider, on every request.

## Phase 3: desktop Character

Mochi as a floating, transparent figure on the desktop (PySide6). It shares Memories with the terminal but keeps its own Conversations; each launch starts a new one.

- Install: `uv sync --extra desktop` (or `.venv/bin/pip install -e '.[desktop]'`). Launch: `mochi-desktop`.
- Runs through XWayland (`QT_QPA_PLATFORM=xcb`, see ADR 0001). Typing Vietnamese needs your IBus input method to reach XWayland apps (`QT_IM_MODULE=ibus` if it does not).
- Click Mochi for the Chat Box (Esc or click again to close); double-click for the Main Window (Conversation, Memories), where Mochi moves into a Portrait until it closes or is minimised. Right-click: Hide, Quit.
- Running `mochi-desktop` again toggles visibility, so bind it to a GNOME shortcut or a `.desktop` launcher.
- Position and size live in `~/.config/mochi-companion/desktop.json` (`size`, default 128).
- Local art: put a sheet and a `frames.json` in `~/.config/mochi-companion/sprites/` and it replaces the bundled art (cells are `[column, row]` on the sheet). The map must define all 8 Expressions, or it is ignored with a warning.
- Speech Balloon skin: `balloon.json` in the same folder points at a nine-slice frame image (`{"image", "slice", "scale", "text_color"}`; outside-the-border pixels become transparent). Without it the balloon is plain. The GB Studio UI pack (`frames/LIGHT BG/light frame 02.png`, slice 8, scale 2) is used locally and not committed, since it ships without a licence.
- Art: `companion/desktop/sprites/frames.json` maps each Expression to cells of the bundled Rosa sheet. The sheet has its own licence, not this repo's: see `companion/desktop/sprites/ART-LICENSE.md`.
