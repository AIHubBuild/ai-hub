"""Test-suite environment defaults.

Tests run with an explicit local/test environment and explicit DeepSeek
provider configuration, matching the minimum configuration required for
local DeepSeek use. Tests that need deployment-like behavior or a
missing provider configuration override these values with monkeypatch.
"""

import os

import pytest

os.environ["ENVIRONMENT"] = "test"
os.environ["AI_DEPLOYMENT"] = "false"
os.environ["AI_PROVIDER"] = "deepseek"
os.environ["AI_BASE_URL"] = "https://api.deepseek.com"
os.environ["AI_MODEL"] = "deepseek-flash"


@pytest.fixture(autouse=True)
def _explicit_test_environment(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("AI_DEPLOYMENT", "false")
    monkeypatch.setenv("AI_PROVIDER", "deepseek")
    monkeypatch.setenv("AI_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("AI_MODEL", "deepseek-flash")
