"""Tests for the subagent registry and Phase 4.2 parallel dispatch prompts."""

from __future__ import annotations

from agents.prompts import (
    CHAT_AGENT_SYSTEM_PROMPT,
    CONSTRAINT_ANALYZER_SYSTEM_PROMPT,
    MULTI_PLAN_GENERATOR_SYSTEM_PROMPT,
    QUALITY_SCORER_SYSTEM_PROMPT,
    RESEARCHER_SYSTEM_PROMPT,
    RISK_DETECTOR_SYSTEM_PROMPT,
)
from agents.subagents import get_subagents


class TestSubagentRegistry:
    def test_all_eight_subagents_registered(self):
        names = [s["name"] for s in get_subagents()]
        assert names == [
            "researcher",
            "validator",
            "enricher",
            "cost_optimizer",
            "risk_detector",
            "constraint_analyzer",
            "multi_plan_generator",
            "quality_scorer",
        ]

    def test_risk_detector_has_internet_tools(self):
        by_name = {s["name"]: s for s in get_subagents()}
        tool_names = [getattr(t, "name", None) for t in by_name["risk_detector"]["tools"]]
        assert "internet_search" in tool_names

    def test_constraint_analyzer_has_no_tools(self):
        by_name = {s["name"]: s for s in get_subagents()}
        assert by_name["constraint_analyzer"]["tools"] == []

    def test_subagents_use_subagent_model(self):
        from config.settings import settings

        by_name = {s["name"]: s for s in get_subagents()}
        for name in ("risk_detector", "constraint_analyzer"):
            assert getattr(by_name[name]["model"], "model", None) == settings.LLM_SUBAGENT_MODEL

    def test_subagent_descriptions_mention_purpose(self):
        by_name = {s["name"]: s for s in get_subagents()}
        assert "risks" in by_name["risk_detector"]["description"].lower()
        assert "constraints" in by_name["constraint_analyzer"]["description"].lower()
        assert "itinerary" in by_name["multi_plan_generator"]["description"].lower() or "plan" in by_name["multi_plan_generator"]["description"].lower()
        assert "score" in by_name["quality_scorer"]["description"].lower() or "quality" in by_name["quality_scorer"]["description"].lower()


class TestParallelDispatchPrompts:
    def test_chat_prompt_has_parallel_dispatch(self):
        assert "<parallel_dispatch>" in CHAT_AGENT_SYSTEM_PROMPT

    def test_chat_dispatch_dispatches_all_workers(self):
        for worker in ("researcher", "constraint_analyzer", "risk_detector"):
            assert worker in CHAT_AGENT_SYSTEM_PROMPT

    def test_dispatch_mentions_parallel_execution(self):
        assert "ONE message" in CHAT_AGENT_SYSTEM_PROMPT
        assert "parallel" in CHAT_AGENT_SYSTEM_PROMPT

    def test_dispatch_handles_subagent_failure(self):
        assert "continue with the remaining results" in CHAT_AGENT_SYSTEM_PROMPT

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


class TestMultiPlanGeneratorPrompt:
    def test_defines_three_tiers(self):
        for tier in ("Budget", "Balanced", "Premium"):
            assert tier in MULTI_PLAN_GENERATOR_SYSTEM_PROMPT

    def test_has_comparison_matrix_output(self):
        assert "comparison_matrix" in MULTI_PLAN_GENERATOR_SYSTEM_PROMPT

    def test_has_cost_breakdown(self):
        assert "cost_breakdown" in MULTI_PLAN_GENERATOR_SYSTEM_PROMPT

    def test_has_tradeoffs(self):
        assert "tradeoffs" in MULTI_PLAN_GENERATOR_SYSTEM_PROMPT

    def test_budget_tiers_target_percentages(self):
        assert "60%" in MULTI_PLAN_GENERATOR_SYSTEM_PROMPT
        assert "100%" in MULTI_PLAN_GENERATOR_SYSTEM_PROMPT
        assert "150%" in MULTI_PLAN_GENERATOR_SYSTEM_PROMPT


class TestChatPromptComparisonMode:
    def test_chat_prompt_has_comparison_format(self):
        assert "<comparison_format>" in CHAT_AGENT_SYSTEM_PROMPT

    def test_chat_prompt_has_comparison_tags(self):
        assert "<comparison>" in CHAT_AGENT_SYSTEM_PROMPT

    def test_chat_prompt_mentions_multi_plan_generator(self):
        assert "multi_plan_generator" in CHAT_AGENT_SYSTEM_PROMPT

    def test_chat_prompt_has_itinerary_format(self):
        assert "<itinerary_format>" in CHAT_AGENT_SYSTEM_PROMPT


class TestQualityScorerPrompt:
    def test_covers_all_ten_criteria(self):
        for check in ("Budget accuracy", "Constraint satisfaction", "Route efficiency",
                      "Activity density", "Seasonal appropriateness", "Safety",
                      "Diversity", "Local authenticity", "Internal consistency", "Completeness"):
            assert check in QUALITY_SCORER_SYSTEM_PROMPT

    def test_has_structured_output_format(self):
        assert "<output_format>" in QUALITY_SCORER_SYSTEM_PROMPT
        assert '"score"' in QUALITY_SCORER_SYSTEM_PROMPT
        assert '"issues"' in QUALITY_SCORER_SYSTEM_PROMPT
        assert '"improved_plan"' in QUALITY_SCORER_SYSTEM_PROMPT

    def test_has_severity_levels(self):
        assert '"error"' in QUALITY_SCORER_SYSTEM_PROMPT
        assert '"warning"' in QUALITY_SCORER_SYSTEM_PROMPT

    def test_has_fix_guidance(self):
        assert '"fix"' in QUALITY_SCORER_SYSTEM_PROMPT

    def test_score_threshold_rule(self):
        assert "80" in QUALITY_SCORER_SYSTEM_PROMPT


class TestChatPromptSelfCritique:
    def test_chat_prompt_has_self_critique_block(self):
        assert "<self_critique>" in CHAT_AGENT_SYSTEM_PROMPT

    def test_chat_prompt_mentions_quality_scorer(self):
        assert "quality_scorer" in CHAT_AGENT_SYSTEM_PROMPT

    def test_self_critique_mentions_parallel_scoring(self):
        assert "ONE message" in CHAT_AGENT_SYSTEM_PROMPT.split("<self_critique>")[1].split("</self_critique>")[0]

    def test_self_critique_mentions_max_iterations(self):
        assert "2 fix iterations" in CHAT_AGENT_SYSTEM_PROMPT
