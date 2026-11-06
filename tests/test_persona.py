import re

from companion.companion import EXPRESSIONS
from companion.config import PROJECT_ROOT
from companion.persona import PERSONA_TOKEN_CAP, persona_warning


def test_shipped_persona_fits_its_token_cap():
    text = (PROJECT_ROOT / "persona/mochi.md").read_text()
    assert persona_warning(text) is None


def test_oversized_persona_gets_a_readable_warning():
    warning = persona_warning("x " * 20000)
    assert warning and str(PERSONA_TOKEN_CAP) in warning


def test_persona_offers_exactly_the_expressions_the_core_knows():
    text = (PROJECT_ROOT / "persona/mochi.md").read_text()
    listed = next(line for line in text.splitlines() if line.startswith("Chỉ chọn một trong:"))
    assert tuple(listed.split(":")[1].split(".")[0].replace(",", " ").split()) == EXPRESSIONS
    assert set(re.findall(r"\[feel: (\w+)\]", text)) <= set(EXPRESSIONS)
