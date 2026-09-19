"""The three agents: briefing → critique → synthesis.

Each agent loads its system prompt and dispatches via `llm.call`. The full
research pack is passed as `cached_prefix` so it's shared across all three
calls within a run via Anthropic prompt caching (cache key = prefix, which is
the pack — identical across agents). Per-agent `system` and `user` come after
the cached prefix and don't break the cache.
"""

from __future__ import annotations

from pathlib import Path

from src.reporting import llm
from src.reporting.pack import render_pack_markdown

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text()


def _pack_preface(pack: dict) -> str:
    """The cached prefix sent ahead of every agent's system prompt."""
    return (
        "# Research pack (source of truth for this run)\n\n"
        "The following JSON contains the full research pack for this report run, "
        "including the source paper text under `source_paper_full_text`. Treat "
        "everything below as authoritative; do not invent facts beyond it.\n\n"
        + render_pack_markdown(pack)
    )


def briefing(pack: dict, model: str, max_tokens: int = 10000) -> tuple[str, dict]:
    """Agent 1: generate the initial draft from the research pack."""
    system = _load_prompt("briefing")
    user = (
        "Write the research note per the system instructions. The research pack "
        "at the top of the system context is the source of truth."
    )
    return llm.call(model, system, user, max_tokens=max_tokens, cached_prefix=_pack_preface(pack))


def critique(
    pack: dict, draft: str, model: str, max_tokens: int = 4000
) -> tuple[str, dict]:
    """Agent 2: critique the draft against the research pack."""
    system = _load_prompt("critique")
    user = (
        "Here is the analyst's draft. Run the checks per the system instructions "
        "and return your findings.\n\n"
        "## Draft\n\n"
        f"{draft}"
    )
    return llm.call(model, system, user, max_tokens=max_tokens, cached_prefix=_pack_preface(pack))


def synthesize(
    pack: dict,
    draft: str,
    critique_text: str,
    model: str,
    max_tokens: int = 12000,
) -> tuple[str, dict]:
    """Agent 3: produce the final report incorporating critique."""
    system = _load_prompt("synthesize")
    user = (
        "Here is the analyst's draft and the PM's critique. Produce the final "
        "report per the system instructions.\n\n"
        "## Draft\n\n"
        f"{draft}\n\n"
        "## Critique\n\n"
        f"{critique_text}"
    )
    return llm.call(model, system, user, max_tokens=max_tokens, cached_prefix=_pack_preface(pack))
