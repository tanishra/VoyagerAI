"""Tests for the subagent registry and orchestrator prompts.

Post-cutover: only the researcher is dispatchable via the task tool —
plan generation, validation, and enrichment live in the deterministic
pipeline (agents/pipeline.py). The specialist system prompts remain
because the pipeline stages use them directly.
"""

from __future__ import annotations

from agents.prompts import (
    CHAT_AGENT_SYSTEM_PROMPT,
    COMPARISON_SUMMARY_PROMPT,
    CONSTRAINT_ANALYZER_SYSTEM_PROMPT,
    RESEARCHER_SYSTEM_PROMPT,
    RISK_DETECTOR_SYSTEM_PROMPT,
)
from agents.subagents import get_subagents, _ResilientModel, wrap_subagent_for_resilience


class TestSubagentRegistry:
    def test_only_researcher_registered(self):
        names = [s["name"] for s in get_subagents()]
        assert names == ["researcher"]

    def test_researcher_has_internet_tools(self):
        by_name = {s["name"]: s for s in get_subagents()}
        tool_names = [getattr(t, "name", None) for t in by_name["researcher"]["tools"]]
        assert "internet_search" in tool_names

    def test_researcher_uses_subagent_model(self):
        from config.settings import settings

        model = get_subagents()[0]["model"]
        inner = getattr(model, "inner", model)
        assert getattr(inner, "model", None) == settings.LLM_SUBAGENT_MODEL

    def test_all_subagents_wrapped_with_resilient_model(self):
        for spec in get_subagents():
            assert isinstance(spec["model"], _ResilientModel)

    def test_resilient_model_preserves_name_and_description(self):
        from agents.subagents import build_researcher
        from agents.llm import get_subagent_model

        raw = build_researcher(get_subagent_model())
        wrapped = wrap_subagent_for_resilience(raw)
        assert wrapped["name"] == raw["name"]
        assert wrapped["description"] == raw["description"]
        assert wrapped["system_prompt"] == raw["system_prompt"]
        assert isinstance(wrapped["model"], _ResilientModel)
        assert wrapped["model"].subagent_name == raw["name"]


class TestChatPrompt:
    def test_prompt_has_required_fields_gate(self):
        assert "<required_fields>" in CHAT_AGENT_SYSTEM_PROMPT
        for field in ("destination", "total_days", "budget", "travel_style", "group_type"):
            assert field in CHAT_AGENT_SYSTEM_PROMPT

    def test_prompt_delegates_generation_to_pipeline(self):
        assert "generate_trip_plans" in CHAT_AGENT_SYSTEM_PROMPT
        assert "refine_itinerary" in CHAT_AGENT_SYSTEM_PROMPT

    def test_prompt_prohibits_inline_plan_json(self):
        assert "NEVER write plan or itinerary JSON" in CHAT_AGENT_SYSTEM_PROMPT

    def test_prompt_prohibits_tags_in_conversation_mode(self):
        conv_section = CHAT_AGENT_SYSTEM_PROMPT.split('<mode type="conversation">')[1].split("</mode>")[0]
        assert "NEVER output <itinerary> or <comparison> tags" in conv_section

    def test_prompt_requires_all_fields_before_structured_mode(self):
        struct_section = CHAT_AGENT_SYSTEM_PROMPT.split('<mode type="structured">')[1].split("</mode>")[0]
        assert "ALL required fields" in struct_section

    def test_chat_prompt_has_anti_loop_rules(self):
        assert "<anti_loop_rules>" in CHAT_AGENT_SYSTEM_PROMPT
        assert "STOP" in CHAT_AGENT_SYSTEM_PROMPT

    def test_researcher_prompt_parallel_searches(self):
        assert "MULTIPLE internet_search" in RESEARCHER_SYSTEM_PROMPT


class TestComparisonSummaryPrompt:
    def test_defines_three_tiers(self):
        for tier in ("budget", "balanced", "premium"):
            assert tier in COMPARISON_SUMMARY_PROMPT

    def test_summary_only_no_days(self):
        assert "NO \"days\" array" in COMPARISON_SUMMARY_PROMPT

    def test_has_comparison_matrix(self):
        assert "comparison_matrix" in COMPARISON_SUMMARY_PROMPT

    def test_budget_tiers_target_percentages(self):
        for pct in ("60%", "100%", "150%"):
            assert pct in COMPARISON_SUMMARY_PROMPT


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


class TestResilientModel:
    def test_agenerate_returns_fallback_on_exception(self):
        import asyncio
        from langchain_core.language_models import BaseChatModel
        from langchain_core.messages import HumanMessage

        class _FailingModel(BaseChatModel):
            @property
            def _llm_type(self):
                return "failing"

            def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                raise RuntimeError("model crashed")

            async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
                raise RuntimeError("model crashed")

        wrapper = _ResilientModel(_FailingModel(), "test_agent")
        result = asyncio.new_event_loop().run_until_complete(
            wrapper._agenerate([HumanMessage(content="hi")])
        )
        assert len(result.generations) == 1
        msg = result.generations[0].message
        assert "[SUBAGENT FAILED]" in msg.content
        assert "test_agent" in msg.content
        assert "model crashed" in msg.content

    def test_agenerate_passes_through_on_success(self):
        import asyncio
        from langchain_core.language_models import BaseChatModel
        from langchain_core.messages import AIMessage, HumanMessage
        from langchain_core.outputs import ChatGeneration, ChatResult

        class _OkModel(BaseChatModel):
            @property
            def _llm_type(self):
                return "ok"

            def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content="ok"))])

            async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content="ok"))])

        wrapper = _ResilientModel(_OkModel(), "test_agent")
        result = wrapper._agenerate([HumanMessage(content="hi")])
        result = asyncio.new_event_loop().run_until_complete(result)
        assert result.generations[0].message.content == "ok"

    def test_llm_type_includes_inner(self):
        from langchain_core.language_models import BaseChatModel

        class _InnerModel(BaseChatModel):
            @property
            def _llm_type(self):
                return "gemini"

            def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                pass

            async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
                pass

        wrapper = _ResilientModel(_InnerModel(), "test")
        assert "gemini" in wrapper._llm_type
