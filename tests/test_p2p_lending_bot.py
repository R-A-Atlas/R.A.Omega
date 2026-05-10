# tests/test_p2p_lending_bot.py
# P2P Lending Bot — existence and structure tests
# Run: python -m pytest tests/test_p2p_lending_bot.py -v

import os
import pytest

AGENT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "atlas_agents", "alternative/p2p_lending"
)
SKILL_FILE = os.path.join(
    os.path.dirname(__file__), "..",
    "atlas_vault", "02-Wiki", "Skills", "p2p-lending-bot", "SKILL.md"
)


def test_agent_directory_exists():
    """Agent directory must exist."""
    assert os.path.isdir(AGENT_DIR), f"Missing: {AGENT_DIR}"


def test_agent_prompt_exists():
    """AGENT_PROMPT.md must exist."""
    path = os.path.join(AGENT_DIR, "AGENT_PROMPT.md")
    assert os.path.exists(path), f"Missing AGENT_PROMPT.md in {AGENT_DIR}"


def test_skill_file_exists():
    """SKILL.md must exist in vault."""
    assert os.path.exists(SKILL_FILE), f"Missing: {SKILL_FILE}"


def test_init_file_exists():
    """__init__.py must exist."""
    path = os.path.join(AGENT_DIR, "__init__.py")
    assert os.path.exists(path), f"Missing __init__.py in {AGENT_DIR}"
