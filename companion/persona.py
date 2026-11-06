PERSONA_TOKEN_CAP = 3500
CHARS_PER_TOKEN = 3  # conservative: Vietnamese tokenizes worse than English


def persona_warning(text: str) -> str | None:
    """A readable warning if the Persona is likely over its token cap, else None."""
    estimate = len(text) // CHARS_PER_TOKEN
    if estimate <= PERSONA_TOKEN_CAP:
        return None
    return (
        f"Persona is about {estimate} tokens, over the {PERSONA_TOKEN_CAP} cap. "
        "Trim it so Mochi stays cheap and sharp."
    )
