# mochi-companion
Get me out of the loneliness. A desktop companion that help me do task management, check on me and give some other interactions. Personal project.

## Phase 1: terminal chat

Chat with Mochi in the terminal; the Conversation survives restarts.

### Setup
- Linux, Python 3.14 (developed on GNOME/Wayland).
- With [uv](https://docs.astral.sh/uv/): `uv sync`. Without: `python3.14 -m venv .venv && .venv/bin/pip install -e . pytest`.
- Get a Groq API key and put it in the environment or an uncommitted `.env` in the repo root:
  `GROQ_API_KEY=...`
- Optional settings: `MOCHI_MODEL` (default `qwen/qwen3.8-27b`), `MOCHI_HISTORY_LIMIT` (default `20`), `MOCHI_DATA_DIR`, `MOCHI_PERSONA`.

### Launch
`uv run mochi` (or `.venv/bin/mochi`, or `python -m companion.cli`)

Commands: `/new` starts a new Conversation, `/retry` resends the unanswered Message, `/quit` exits.
History lives in SQLite at `~/.local/share/mochi-companion/mochi.db`. Edit Mochi's Persona in `persona/mochi.md`.

### Tests
`uv run pytest` (uses a fake provider; no API requests).

### Privacy
The most recent Messages (default 20) and the Persona are sent to Groq, a hosted provider, on every request.
