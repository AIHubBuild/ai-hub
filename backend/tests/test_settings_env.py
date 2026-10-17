"""Regression tests for environment-variable loading.

Production incident: the backend's ``.env`` (containing the AI API
key) was not loaded because the configured ``env_file`` paths were
relative to the process working directory. These tests pin the fix: the
paths must be anchored to the backend directory (derived independently
from the real file locations, so an off-by-one path bug fails loudly),
and a key in such a file must load regardless of the current working
directory.
"""

from pathlib import Path

import app.core.config as config_module
from app.core.config import Settings

TEST_KEY = "test-deepseek-key-for-regression"

CONFIG_FILE = Path(config_module.__file__).resolve()
EXPECTED_BACKEND_DIR = CONFIG_FILE.parents[2]
EXPECTED_REPO_ROOT = CONFIG_FILE.parents[3]


def test_env_file_paths_are_anchored_to_backend_directory():
    paths = Settings.model_config["env_file"]
    assert len(paths) == 2
    assert all(Path(p).is_absolute() for p in paths)
    assert paths == (
        str(EXPECTED_BACKEND_DIR / ".env"),
        str(EXPECTED_REPO_ROOT / ".env"),
    )


def test_key_loads_from_env_file_regardless_of_cwd(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(f"DEEPSEEK_API_KEY={TEST_KEY}\n", encoding="utf-8")

    for name in ("AI_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    settings = Settings(_env_file=str(env_file))

    assert settings.ai_api_key == TEST_KEY
    assert settings.openai_api_key == TEST_KEY
