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

HUMAN_WRITING_STYLE_RULES = (
    "MANDATORY HUMAN WRITING STYLE:\n"
    "- Write like a real human. Be professional, but natural, like you are "
    "explaining something to a smart friend. Avoid buzzwords, corporate "
    "jargon, and em dashes. Never sound like a press release. Be clear, "
    "direct, conversational, and real.\n"
    "- Use direct language and varied sentence structures. Avoid a formulaic "
    "rhythm or a repetitive template.\n"
    "- Use specific evidence from the candidate's actual resume. Connect that "
    "evidence to the job requirements naturally instead of copying the job "
    "description or stuffing keywords.\n"
    "- Preserve real qualifications, experience, dates, skill levels, and "
    "achievements. Never invent evidence, metrics, credentials, employers, or "
    "responsibilities.\n"
    "- Avoid generic openings and cliches, including: \"I am thrilled to "
    "apply\", \"aligns closely with my experience\", \"with a solid "
    "foundation in\", \"I am excited to apply\", \"I would be a great "
    "fit\", \"leverage my experience\", \"proven track record\", "
    "\"dynamic professional\", \"results-driven\", \"hit the ground "
    "running\", \"in today's fast-paced\", and \"valuable addition to "
    "your team\".\n"
    "- Never use em dashes. Use commas, full stops, colons, or parentheses "
    "instead.\n"
    "- Avoid corporate jargon, exaggerated claims, repetitive conclusions, "
    "and generic filler.\n"
    "- Keep the writing appropriate for the document: a resume must be "
    "concise and evidence-based; a cover letter must sound like a real person "
    "explaining why their experience fits the role.\n"
    "- Sound natural because the facts are specific, not because the tone is "
    "casual or padded."
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
