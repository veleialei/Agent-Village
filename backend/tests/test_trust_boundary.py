"""
Trust boundary tests — the core invariant of Agent Village.

Three layers tested:
  1. _resolve_context   — server-side trust resolution (pure function, no DB)
  2. _build_system_prompt — owner prompt exposes memories; stranger prompt never does
  3. _fetch_agent_data  — living_memory is physically never queried in the stranger path
"""

import pytest
from unittest.mock import MagicMock, patch, call

from app.services.chat_service import (
    _resolve_context,
    _build_system_prompt,
    _fetch_agent_data,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

AGENT = {
    "id": "a1a1a1a1-0000-0000-0000-000000000001",
    "api_key": "sq_sample_agent_1",
    "name": "Luna",
    "bio": "A dreamy stargazer who collects moonlight in jars.",
    "visitor_bio": "Welcome to my lunar observatory! Touch nothing shiny.",
    "status": "Gazing at constellations",
}

PRIVATE_MEMORY = "Owner's wife's birthday is March 15, she loves orchids"
SKILLS = [{"category": "observation", "description": "Identifies 47 constellations"}]


# ── Layer 1: trust resolution ─────────────────────────────────────────────────

class TestResolveContext:
    def test_correct_key_grants_owner(self):
        assert _resolve_context(AGENT, "sq_sample_agent_1") == "owner"

    def test_wrong_key_downgrades_to_stranger(self):
        assert _resolve_context(AGENT, "wrong_key") == "stranger"

    def test_missing_key_is_stranger(self):
        assert _resolve_context(AGENT, None) == "stranger"

    def test_empty_string_key_is_stranger(self):
        assert _resolve_context(AGENT, "") == "stranger"

    def test_trust_is_case_sensitive(self):
        assert _resolve_context(AGENT, "SQ_SAMPLE_AGENT_1") == "stranger"


# ── Layer 2: system prompt content ───────────────────────────────────────────

class TestBuildSystemPrompt:
    def test_owner_prompt_includes_memories(self):
        prompt = _build_system_prompt(AGENT, SKILLS, "owner", [PRIVATE_MEMORY])
        assert "March 15" in prompt
        assert "orchids" in prompt

    def test_owner_prompt_uses_full_bio(self):
        prompt = _build_system_prompt(AGENT, SKILLS, "owner", [])
        assert AGENT["bio"] in prompt

    def test_stranger_prompt_never_contains_private_memory(self):
        # Even if memories were accidentally passed in, the stranger prompt
        # must not render them
        prompt = _build_system_prompt(AGENT, SKILLS, "stranger", [PRIVATE_MEMORY])
        assert "March 15" not in prompt
        assert "orchids" not in prompt

    def test_stranger_prompt_uses_visitor_bio(self):
        prompt = _build_system_prompt(AGENT, SKILLS, "stranger", [])
        assert AGENT["visitor_bio"] in prompt
        assert AGENT["bio"] not in prompt

    def test_stranger_prompt_instructs_no_private_knowledge(self):
        prompt = _build_system_prompt(AGENT, SKILLS, "stranger", [])
        assert "NO knowledge" in prompt or "no knowledge" in prompt.lower()


# ── Layer 3: data-gating — memory never queried in stranger path ──────────────

def _make_db_mock(memory_rows=None, skill_rows=None):
    """Returns a mock db where table() chains return empty data by default."""
    mock_db = MagicMock()

    def table_side_effect(table_name):
        m = MagicMock()
        if table_name == "living_memory":
            m.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = (
                memory_rows if memory_rows is not None else []
            )
        else:
            # skills and any other table
            m.select.return_value.eq.return_value.execute.return_value.data = (
                skill_rows if skill_rows is not None else []
            )
        return m

    mock_db.table.side_effect = table_side_effect
    return mock_db


class TestFetchAgentDataGating:
    @patch("app.services.chat_service.db")
    def test_stranger_never_queries_living_memory(self, mock_db):
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

        _fetch_agent_data(AGENT["id"], "stranger", agent=AGENT)

        queried_tables = [c.args[0] for c in mock_db.table.call_args_list]
        assert "living_memory" not in queried_tables

    @patch("app.services.chat_service.db")
    def test_owner_does_query_living_memory(self, mock_db):
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []

        _fetch_agent_data(AGENT["id"], "owner", agent=AGENT)

        queried_tables = [c.args[0] for c in mock_db.table.call_args_list]
        assert "living_memory" in queried_tables

    @patch("app.services.chat_service.db")
    def test_stranger_returns_empty_memories(self, mock_db):
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

        _, _, memories = _fetch_agent_data(AGENT["id"], "stranger", agent=AGENT)

        assert memories == []

    @patch("app.services.chat_service.db")
    def test_owner_returns_memories_from_db(self, mock_db):
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
            {"text": PRIVATE_MEMORY}
        ]

        _, _, memories = _fetch_agent_data(AGENT["id"], "owner", agent=AGENT)

        assert PRIVATE_MEMORY in memories
