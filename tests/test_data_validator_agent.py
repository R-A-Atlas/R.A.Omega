"""E8 — Data Validator — existence and structure tests."""
import os

import pytest

AGENT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "atlas_agents", "engineering", "data_validator"
)
SKILL_FILE = os.path.join(
    os.path.dirname(__file__),
    "..",
    "atlas_vault",
    "02-Wiki",
    "Skills",
    "data-validator",
    "SKILL.md",
)


def test_agent_directory_exists():
    assert os.path.isdir(AGENT_DIR), f"Missing: {AGENT_DIR}"


def test_agent_prompt_exists():
    path = os.path.join(AGENT_DIR, "AGENT_PROMPT.md")
    assert os.path.exists(path), f"Missing AGENT_PROMPT.md in {AGENT_DIR}"


def test_skill_file_exists():
    assert os.path.exists(SKILL_FILE), f"Missing: {SKILL_FILE}"


def test_init_file_exists():
    path = os.path.join(AGENT_DIR, "__init__.py")
    assert os.path.exists(path), f"Missing __init__.py in {AGENT_DIR}"
