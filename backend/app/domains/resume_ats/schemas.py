"""Pydantic schemas for the Resume ATS domain.

Result models for the deterministic engine. The API request/response
schemas are added when the ATS endpoints land in a later slice.
"""

from pydantic import BaseModel


class KeywordMatchResult(BaseModel):
    """Outcome of keyword matching between a resume and a job description."""

    score: int
    matched: list[str]
    missing: list[str]


class AtsAnalysis(BaseModel):
    """Deterministic analysis fields of the six-section ATS baseline."""

    original_ats_score: str
    optimized_ats_score: str
    matching_keywords: list[str]
    missing_keywords: list[str]
