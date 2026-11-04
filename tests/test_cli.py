from companion.cli import run
from companion.companion import Companion
from companion.fake_provider import FakeProvider
from companion.store import Store


def drive(db, provider, lines):
    c = Companion(Store(db), provider, "P")
    out: list[str] = []
    it = iter(lines)
    run(c, input_fn=lambda _: next(it), print_fn=out.append)
    c.store.close()
    return "\n".join(out)


def test_relaunch_prints_recent_messages(tmp_path):
    db = tmp_path / "m.db"
    drive(db, FakeProvider(["hello there"]), ["hi", "/quit"])
    out = drive(db, FakeProvider(), ["/quit"])
    assert "you: hi" in out and "mochi: hello there" in out


def test_error_is_readable_and_retry_works(tmp_path):
    db = tmp_path / "m.db"
    p = FakeProvider(["recovered"])
    p.fail_with = "network down"

    lines = iter(["hello", "/retry", "/quit"])
    c = Companion(Store(db), p, "P")
    out: list[str] = []

    def next_line(_):
        line = next(lines)
        if line == "/retry":
            p.fail_with = None
        return line

    run(c, input_fn=next_line, print_fn=out.append)
    text = "\n".join(out)
    assert "[error] network down" in text
    assert "mochi: recovered" in text
