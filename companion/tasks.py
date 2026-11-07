"""Task vocabulary that needs no database: the `[task:]` marker, due times, and the fixed lines of Notices."""

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

TASK_MARKER = re.compile(r"\[task:([^\]]*)\]", re.IGNORECASE)
DUE_FIELD = re.compile(r"^\s*due\s*=\s*(.*?)\s*$", re.IGNORECASE)
DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")

DEFAULT_LINES: dict[str, list[str]] = {
    "checkin": ["hết giờ r, {title} xong chưa", "ê hết giờ r. {title} sao r a"],
    "reminder": ["tới giờ r: {title}", "ê, {title} tới hạn r đó"],
    "reminder_snoozed": ["đã bảo tới giờ r mà: {title}", "lại {title} nè, đừng lơ nữa"],
    "reminder_group": ["{count} việc tới hạn r: {titles}", "dồn {count} việc r a: {titles}"],
}


@dataclass(frozen=True)
class TaskProposal:
    """What Mochi suggested adding. Nothing is saved until the user accepts it."""

    title: str
    why: str | None
    due: datetime | None  # a date with no clock time is stored at midnight, see `has_time`
    has_time: bool
    due_unreadable: bool = False  # Mochi gave a time Python could not read; the Task is kept without one
    conversation_id: int | None = None  # the Conversation that produced it, even if accepted later


def parse_due(raw: str) -> tuple[datetime, bool] | None:
    """A due value as (moment, has_clock_time), or None. Python never guesses a date."""
    raw = raw.strip()
    try:
        if DATE_ONLY.match(raw):
            return datetime.fromisoformat(raw), False
        moment = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if moment.tzinfo is not None:
        moment = moment.astimezone().replace(tzinfo=None)
    return moment.replace(second=0, microsecond=0), True


def _proposal(body: str) -> TaskProposal | None:
    parts = [p.strip() for p in body.split("|")]
    raw_due = None
    if parts and (field := DUE_FIELD.match(parts[0])):
        raw_due = field.group(1)
        parts = parts[1:]
    if not parts or not parts[0]:
        return None
    title = parts[0]
    why = " | ".join(p for p in parts[1:] if p) or None
    due, has_time, unreadable = None, False, False
    if raw_due:
        parsed = parse_due(raw_due)
        if parsed:
            due, has_time = parsed
        else:
            unreadable = True
    return TaskProposal(title, why, due, has_time, unreadable)


def split_task(reply: str) -> tuple[str, TaskProposal | None]:
    """Strip every `[task: ...]` marker from a reply; return the first well-formed one."""
    proposal = None
    for body in TASK_MARKER.findall(reply):
        found = _proposal(body)
        if found and proposal is None:
            proposal = found
    return TASK_MARKER.sub("", reply), proposal


def stamp_due(due: datetime | None, has_time: bool) -> str | None:
    if due is None:
        return None
    return due.isoformat(timespec="minutes") if has_time else due.date().isoformat()


def format_due(due: datetime | None, has_time: bool) -> str:
    if due is None:
        return "no time set"
    return f"{due:%a %d %b %Y, %H:%M}" if has_time else f"{due:%a %d %b %Y}"


def load_lines(path: Path | None) -> dict[str, list[str]]:
    """The pools of fixed lines; the editable data file wins, the built-in pool fills any gap."""
    lines = {key: list(pool) for key, pool in DEFAULT_LINES.items()}
    try:
        data = json.loads(path.read_text()) if path else {}
    except (OSError, ValueError):
        return lines
    if isinstance(data, dict):
        for key, pool in data.items():
            if key in lines and isinstance(pool, list) and pool and all(isinstance(p, str) for p in pool):
                lines[key] = pool
    return lines


def pick_line(pool: list[str], seed: int, **fields: str) -> str:
    """A stable choice per seed, so a Notice does not change wording every time it is redrawn."""
    template = pool[seed % len(pool)]
    try:
        return template.format(**fields)
    except (KeyError, IndexError, ValueError):
        return template
