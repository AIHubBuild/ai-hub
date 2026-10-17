"""Shared writing-style contract for AI-generated content.

Both assistant domains import this module so the same baseline rules
apply to resumes, cover letters, troubleshooting replies, and incident
summaries. Task-specific prompts add their own constraints without
repeating the shared guidance.

The module also provides a deterministic safety net for the hard rule
"never use em dashes". It only normalises punctuation. It never adds,
removes, or changes claims.
"""

import re

SHARED_STYLE_GUIDE = (
    "SHARED WRITING STYLE:\n"
    "- Write as a thoughtful professional explaining something clearly "
    "to an intelligent reader.\n"
    "- Be direct, specific, and useful. Prefer familiar words, active "
    "voice, and varied sentence lengths.\n"
    "- Avoid buzzwords, clichés, generic enthusiasm, corporate filler, "
    "and robotic transitions such as \"Furthermore\", \"Moreover\", or "
    "\"Additionally\".\n"
    "- Never use em dashes. Use commas, full stops, colons, or "
    "parentheses instead.\n"
    "- Do not repeat the same sentence pattern or force content into a "
    "formulaic three-part list.\n"
    "- State facts plainly. Distinguish what is known from what is "
    "inferred. Never invent facts, results, actions, sources, or "
    "credentials.\n"
    "- Do not claim an action was completed unless the input confirms "
    "it.\n"
    "- Natural does not mean casual, chatty, or padded. Match the tone "
    "to the task."
)

EM_DASH = "\u2014"
_EM_DASH_PATTERN = re.compile(r"\s*\u2014\s*")
_SPACE_RUN = re.compile(r"[ \t]{2,}")
_SPACE_BEFORE_PUNCTUATION = re.compile(r"[ \t]+([,.;:!?])")
_COMMA_RUN = re.compile(r",\s*,")


def contains_em_dash(text: str) -> bool:
    return EM_DASH in text


def normalize_writing(text: str) -> str:
    """Apply deterministic punctuation cleanup to generated prose.

    Em dashes become commas because that is the least intrusive change
    for a clause break. The function does not rewrite sentences or alter
    factual content.
    """
    if not text:
        return text

    cleaned = _EM_DASH_PATTERN.sub(", ", text)
    cleaned = _COMMA_RUN.sub(",", cleaned)
    cleaned = _SPACE_BEFORE_PUNCTUATION.sub(r"\1", cleaned)
    cleaned = _SPACE_RUN.sub(" ", cleaned)
    return cleaned.strip()
