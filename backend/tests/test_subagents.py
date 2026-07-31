"""Tests for the subagent registry and Phase 4.2 parallel dispatch prompts."""

from __future__ import annotations

from agents.prompts import (
    CHAT_AGENT_SYSTEM_PROMPT,
    RESEARCHER_SYSTEM_PROMPT,
    TRAVEL_AGENT_SYSTEM_PROMPT,
)
from agents.subagents import get_subagents
from agents.subagents.constraint_analyzer import CONSTRAINT_ANALYZER_SYSTEM_PROMPT
from agents.subagents.risk_detector import RISK_DETECTOR_SYSTEM_PROMPT


class TestSubagentRegistry:
    def test_all_six_subagents_registered(self):
        names = [s["name"] for s in get_subagents()]
        assert names == [
            "researcher",
            "validator",
            "enricher",
            "cost_optimizer",
            "risk_detector",
            "constraint_analyzer",
        ]

    def test_risk_detector_has_internet_tools(self):
        by_name = {s["name"]: s for s in get_subagents()}
        tool_names = [getattr(t, "name", None) for t in by_name["risk_detector"]["tools"]]
        assert "internet_search" in tool_names

    def test_constraint_analyzer_has_no_tools(self):
        by_name = {s["name"]: s for s in get_subagents()}
        assert by_name["constraint_analyzer"]["tools"] == []

    def test_subagents_use_flash_model(self):
        by_name = {s["name"]: s for s in get_subagents()}
        for name in ("risk_detector", "constraint_analyzer"):
            assert getattr(by_name[name]["model"], "model", None) == "gemini-2.5-flash"

    def test_subagent_descriptions_mention_purpose(self):
        by_name = {s["name"]: s for s in get_subagents()}
        assert "risks" in by_name["risk_detector"]["description"].lower()
        assert "constraints" in by_name["constraint_analyzer"]["description"].lower()


class TestParallelDispatchPrompts:
    def test_travel_prompt_has_parallel_dispatch(self):
        assert "<parallel_dispatch>" in TRAVEL_AGENT_SYSTEM_PROMPT

    def test_chat_prompt_has_parallel_dispatch(self):
        assert "<parallel_dispatch>" in CHAT_AGENT_SYSTEM_PROMPT

    def test_travel_dispatch_dispatches_all_workers(self):
        for worker in ("researcher", "constraint_analyzer", "risk_detector"):
            assert worker in TRAVEL_AGENT_SYSTEM_PROMPT

    def test_chat_dispatch_dispatches_all_workers(self):
        for worker in ("researcher", "constraint_analyzer", "risk_detector"):
            assert worker in CHAT_AGENT_SYSTEM_PROMPT

    def test_dispatch_mentions_parallel_execution(self):
        assert "ONE message" in TRAVEL_AGENT_SYSTEM_PROMPT
        assert "parallel" in TRAVEL_AGENT_SYSTEM_PROMPT

    def test_dispatch_handles_subagent_failure(self):
        assert "continue with the remaining results" in TRAVEL_AGENT_SYSTEM_PROMPT

    def test_researcher_prompt_parallel_searches(self):
        assert "MULTIPLE internet_search" in RESEARCHER_SYSTEM_PROMPT


class TestRiskDetectorPrompt:
    def test_covers_all_five_risk_checks(self):
        for check in ("Seasonal closures", "Weather risks", "Transit gaps",
                      "Safety advisories", "Holiday impacts"):
            assert check in RISK_DETECTOR_SYSTEM_PROMPT

    def test_has_structured_output_format(self):
        assert "<output_format>" in RISK_DETECTOR_SYSTEM_PROMPT
        assert '"overall_risk"' in RISK_DETECTOR_SYSTEM_PROMPT
        assert '"mitigation"' in RISK_DETECTOR_SYSTEM_PROMPT

    def test_news_search_rule(self):
        assert 'topic="news"' in RISK_DETECTOR_SYSTEM_PROMPT


class TestConstraintAnalyzerPrompt:
    def test_covers_all_constraint_categories(self):
        for check in ("Budget", "Dietary", "Accessibility", "Group composition", "Travel style"):
            assert check in CONSTRAINT_ANALYZER_SYSTEM_PROMPT

    def test_reads_preferences_file(self):
        assert "/memories/preferences.md" in CONSTRAINT_ANALYZER_SYSTEM_PROMPT

    def test_budget_math(self):
        assert "per-day maximum" in CONSTRAINT_ANALYZER_SYSTEM_PROMPT

    def test_distinguishes_active_and_inferred(self):
        assert '"active"' in CONSTRAINT_ANALYZER_SYSTEM_PROMPT
        assert '"inferred"' in CONSTRAINT_ANALYZER_SYSTEM_PROMPT
