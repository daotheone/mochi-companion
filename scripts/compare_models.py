"""Run the same prompts and Memories through several models and write a side-by-side Markdown report.

    python scripts/compare_models.py [--models a,b] [--out docs/model-comparison.md]

Judge the output by hand: EN/VI switching, consistency, venting, and accurate recall.
"""
import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from companion.companion import Companion
from companion.config import PROJECT_ROOT, load_dotenv
from companion.deepseek_provider import DeepSeekProvider
from companion.provider import ProviderError
from companion.store import Store

DEFAULT_MODELS = "deepseek-flash"


NOW = datetime(2026, 11, 6, 21, 0)  # fixed, so a case's Recap ages are exactly as written


def add_recaps(companion: Companion, recaps: list[dict]) -> None:
    """Seed earlier, already-recapped Conversations that ended `age_hours` before NOW."""
    for recap in recaps:
        ended = NOW - timedelta(hours=recap["age_hours"])
        conversation = companion.store.new_conversation("character", ended)
        companion.store.add_message(conversation, "user", "(earlier)", ended)
        companion.store.add_message(conversation, "assistant", "(earlier)", ended)
        companion.store.add_recap(conversation, recap["text"], recap.get("sensitive", False), ended)


def run_case(case: dict, persona: str, api_key: str | None, model: str) -> str:
    clock = (lambda: NOW) if "recaps" in case else None
    companion = Companion(Store(":memory:"), DeepSeekProvider(api_key, model), persona, clock=clock)
    try:
        add_recaps(companion, case.get("recaps", []))
        for memory in case.get("memories", []):
            companion.store.add_memory(memory["text"], memory.get("tags", []), memory.get("kind", "stated"))
        *earlier, last = [m if isinstance(m, dict) else {"role": "user", "content": m} for m in case["messages"]]
        for turn in earlier:
            companion.store.add_message(companion.ensure_conversation(), turn["role"], turn["content"])
        reply = companion.send(last["content"])
        proposal = f"\n[saved Observed: {companion.last_proposal.text}]" if companion.last_proposal else ""
        return reply + proposal
    except ProviderError as e:
        return f"[error] {e}"
    finally:
        companion.store.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default=DEFAULT_MODELS)
    parser.add_argument("--prompts", default=str(ROOT / "scripts/compare_prompts.json"))
    parser.add_argument("--persona", default=str(ROOT / "persona/mochi.md"))
    parser.add_argument("--out", default=str(ROOT / "docs/model-comparison.md"))
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env", os.environ)
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    models = args.models.split(",")
    persona = Path(args.persona).read_text()
    cases = json.loads(Path(args.prompts).read_text())

    lines = [f"# Model comparison ({date.today()})", "", "Models: " + ", ".join(f"`{m}`" for m in models), ""]
    for case in cases:
        print(f"{case['id']} ...", file=sys.stderr)
        lines += [f"## {case['id']}", f"_{case['note']}_", ""]
        for memory in case.get("memories", []):
            lines.append(f"- Memory ({memory.get('kind', 'stated')}): {memory['text']}")
        for recap in case.get("recaps", []):
            lines.append(f"- Recap ({recap['age_hours']}h old{', sensitive' if recap.get('sensitive') else ''}): {recap['text']}")
        lines += ["", "User:", "```text", *(m if isinstance(m, str) else f"{m['role']}: {m['content']}" for m in case["messages"]), "```", ""]
        for model in models:
            reply = run_case(case, persona, api_key, model)
            lines += [f"**{model}**", "```text", reply, "```", ""]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines))
    print(f"Wrote {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
