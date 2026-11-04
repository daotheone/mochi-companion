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


def test_memory_commands_end_to_end_across_restart(tmp_path):
    db = tmp_path / "m.db"
    out = drive(db, FakeProvider(), [
        "/remember #food #diet likes less sugar",
        "/remember hates mornings",
        "/memories",
        "/edit 2 hates early mornings",
        "/tag 2 #sleep",
        "/forget 1",
        "/quit",
    ])
    assert "[1] stated #food #diet: likes less sugar" in out
    assert "[2] stated: hates mornings" in out

    out = drive(db, FakeProvider(), ["/memories", "/quit"])
    assert "[2] stated #sleep: hates early mornings" in out
    assert "likes less sugar" not in out


def test_memory_command_mistakes_are_readable(tmp_path):
    out = drive(tmp_path / "m.db", FakeProvider(), [
        "/remember", "/remember #only #tags", "/forget 7", "/forget x", "/edit 1", "/confirm 3", "/quit",
    ])
    assert out.count("Usage:") == 4
    assert out.count("No Memory with id") == 2
    assert "Traceback" not in out


def test_observed_memory_is_announced_and_confirmable(tmp_path):
    db = tmp_path / "m.db"
    reply = "ô tốt\nthấy a làm từng bước ok hơn thì phải?\n[observe: tags=study | works better in small steps]"
    out = drive(db, FakeProvider([reply]), ["xong 2 câu r", "/memories", "/confirm 1", "/memories", "/quit"])

    assert "mochi: ô tốt\nmochi: thấy a làm từng bước ok hơn thì phải?" in out
    assert "[observe" not in out
    assert "noticed" in out and "/confirm 1" in out and "/forget 1" in out
    assert "[1] observed #study: works better in small steps" in out
    assert "[1] stated #study: works better in small steps" in out
