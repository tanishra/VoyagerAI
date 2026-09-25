"""Tests for the deterministic plan pipeline + pipeline tools.

Covers the hybrid architecture: orchestrator calls generate_trip_plans /
refine_itinerary tools; the pipeline runs research fan-out, structured
generation, code validation, and reconciliation; the full payload travels
via side channel so the model never re-emits plan JSON.
"""

import asyncio
import json
from typing import ClassVar

import agents.deep_agent as deep_agent_module
import agents.pipeline as pipeline_module
import agents.tools.pipeline_tools as pipeline_tools_module
from agents.constraints import TripConstraints
from agents.pipeline import (
    get_latest_comparison,
    is_pipeline_tool,
    pop_payload,
    store_payload,
)
from agents.tools.pipeline_tools import (
    generate_trip_plans,
    refine_itinerary,
    set_pipeline_context,
)


def _constraints(**overrides):
    base = {
        "destination": "Delhi, India",
        "total_days": 5,
        "budget_amount": 50000,
        "budget_currency": "INR",
        "travel_style": "balanced",
        "group_type": "friends",
        "dietary_restrictions": ["vegetarian"],
    }
    base.update(overrides)
    return TripConstraints(**base)


def _valid_comparison(constraints=None):
    c = constraints or _constraints()
    tiers = ("budget", "balanced", "premium")
    totals = (0.6 * c.budget_amount, c.budget_amount, 1.5 * c.budget_amount)
    return {
        "plans": [
            {
                "tier": t,
                "itinerary": {
                    "destination": c.destination,
                    "total_days": c.total_days,
                    "currency": c.budget_currency,
                    "estimated_total_cost_usd": total,
                },
                "cost_breakdown": {"total": total},
                "tradeoffs": [f"{t} tradeoff"],
            }
            for t, total in zip(tiers, totals)
        ],
        "comparison_matrix": {
            "total_cost": dict(zip(tiers, totals)),
        },
    }


def _valid_itinerary(constraints=None):
    c = constraints or _constraints()
    return {
        "destination": c.destination,
        "total_days": c.total_days,
        "currency": c.budget_currency,
        "estimated_total_cost_usd": c.budget_amount,
        "days": [
            {
                "day": i + 1,
                "daily_cost_usd": c.budget_amount / c.total_days,
                "morning": {"activity": f"Morning {i+1}"},
                "afternoon": {"activity": f"Afternoon {i+1}"},
                "evening": {"activity": f"Evening {i+1}"},
            }
            for i in range(c.total_days)
        ],
    }


class TestSideChannel:
    def setup_method(self):
        pipeline_module._reset_for_tests()
        pipeline_tools_module._reset_for_tests()

    def test_store_pop_roundtrip(self):
        pid = asyncio.run(store_payload("t1", "comparison", {"plans": []}))
        assert asyncio.run(pop_payload(pid)) == {"kind": "comparison", "data": {"plans": []}}
        assert asyncio.run(pop_payload(pid)) is None  # one-shot

    def test_latest_comparison_tracked_per_thread(self):
        asyncio.run(store_payload("t1", "comparison", {"plans": ["a"]}))
        asyncio.run(store_payload("t2", "comparison", {"plans": ["b"]}))
        assert asyncio.run(get_latest_comparison("t1")) == {"plans": ["a"]}
        assert asyncio.run(get_latest_comparison("t2")) == {"plans": ["b"]}

    def test_itinerary_payload_does_not_overwrite_comparison(self):
        asyncio.run(store_payload("t1", "comparison", {"plans": ["a"]}))
        asyncio.run(store_payload("t1", "itinerary", {"days": []}))
        assert asyncio.run(get_latest_comparison("t1")) == {"plans": ["a"]}

    def test_is_pipeline_tool(self):
        assert is_pipeline_tool("generate_trip_plans")
        assert is_pipeline_tool("refine_itinerary")
        assert not is_pipeline_tool("internet_search")


class TestComparisonPipeline:
    def setup_method(self):
        pipeline_module._reset_for_tests()
        pipeline_tools_module._reset_for_tests()

    def _stub_specialists(self, monkeypatch):
        async def _fake_specialist(name, prompt, task, tools=None):
            return f"[{name} brief]", {"input_tokens": 0, "output_tokens": 0, "model": ""}
        monkeypatch.setattr(pipeline_module, "_run_specialist", _fake_specialist)

    def test_happy_path(self, monkeypatch):
        self._stub_specialists(monkeypatch)
        comparison = _valid_comparison()

        async def _fake_gen(schema, prompt, task, stage):
            return comparison, {"input_tokens": 0, "output_tokens": 0, "model": ""}
        monkeypatch.setattr(pipeline_module, "_generate_structured", _fake_gen)

        out = asyncio.run(pipeline_module.run_comparison_pipeline(_constraints()))
        assert out is not None
        assert len(out[0]["plans"]) == 3
        assert out[0]["plans"][1]["itinerary"]["currency"] == "INR"
        # Constraints are enforced, not trusted
        assert all(
            p["itinerary"]["total_days"] == 5 for p in out[0]["plans"]
        )

    def test_constraints_override_model_output(self, monkeypatch):
        """Model says USD / 2 days — constraints say INR / 5 days. Constraints win."""
        self._stub_specialists(monkeypatch)
        bad = _valid_comparison()
        for p in bad["plans"]:
            p["itinerary"]["currency"] = "USD"
            p["itinerary"]["total_days"] = 2

        async def _fake_gen(schema, prompt, task, stage):
            return bad, {"input_tokens": 0, "output_tokens": 0, "model": ""}
        monkeypatch.setattr(pipeline_module, "_generate_structured", _fake_gen)

        out = asyncio.run(pipeline_module.run_comparison_pipeline(_constraints()))
        assert all(p["itinerary"]["currency"] == "INR" for p in out[0]["plans"])
        assert all(p["itinerary"]["total_days"] == 5 for p in out[0]["plans"])

    def test_validation_retry_then_success(self, monkeypatch):
        self._stub_specialists(monkeypatch)
        bad = _valid_comparison()
        # matrix contradicts itinerary totals — error severity
        bad["comparison_matrix"]["total_cost"] = {"budget": 999, "balanced": 999, "premium": 999}
        good = _valid_comparison()
        calls = []

        async def _fake_gen(schema, prompt, task, stage):
            calls.append(task)
            return (bad if len(calls) == 1 else good), {"input_tokens": 0, "output_tokens": 0, "model": ""}
        monkeypatch.setattr(pipeline_module, "_generate_structured", _fake_gen)

        out = asyncio.run(pipeline_module.run_comparison_pipeline(_constraints()))
        assert out[0]["plans"][1]["itinerary"]["estimated_total_cost_usd"] == 50000
        assert len(calls) == 2
        assert "issues_to_fix" in calls[1]

    def test_all_attempts_fail_returns_none(self, monkeypatch):
        self._stub_specialists(monkeypatch)

        async def _fake_gen(schema, prompt, task, stage):
            return None, {"input_tokens": 0, "output_tokens": 0, "model": ""}
        monkeypatch.setattr(pipeline_module, "_generate_structured", _fake_gen)

        assert asyncio.run(pipeline_module.run_comparison_pipeline(_constraints())) is None

    def test_cancel_short_circuits(self, monkeypatch):
        self._stub_specialists(monkeypatch)
        ev = asyncio.Event()
        ev.set()
        assert asyncio.run(
            pipeline_module.run_comparison_pipeline(_constraints(), cancel_event=ev)
        ) is None

    def test_budget_check_short_circuits(self, monkeypatch):
        self._stub_specialists(monkeypatch)
        assert asyncio.run(
            pipeline_module.run_comparison_pipeline(_constraints(), budget_check=lambda: True)
        ) is None

    def test_specialist_failure_degrades(self, monkeypatch):
        async def _failing(name, prompt, task, tools=None):
            raise RuntimeError("provider down")
        monkeypatch.setattr(pipeline_module, "_run_specialist", _failing)

        async def _fake_gen(schema, prompt, task, stage):
            return _valid_comparison(), {"input_tokens": 0, "output_tokens": 0, "model": ""}
        monkeypatch.setattr(pipeline_module, "_generate_structured", _fake_gen)

        # _run_specialist failure is internal to it; here we simulate the
        # gather itself failing — pipeline must not crash.
        out = asyncio.run(pipeline_module.run_comparison_pipeline(_constraints()))
        assert out is None or isinstance(out[0], dict)


class TestRefinementPipeline:
    def setup_method(self):
        pipeline_module._reset_for_tests()
        pipeline_tools_module._reset_for_tests()

    def test_happy_path(self, monkeypatch):
        itinerary = _valid_itinerary()

        async def _fake_gen(schema, prompt, task, stage):
            return itinerary, {"input_tokens": 0, "output_tokens": 0, "model": ""}
        monkeypatch.setattr(pipeline_module, "_generate_structured", _fake_gen)

        async def _fake_enrich(it):
            return it
        monkeypatch.setattr(
            deep_agent_module, "_enrich_itinerary_with_coordinates", _fake_enrich
        )

        out = asyncio.run(
            pipeline_module.run_refinement_pipeline(_constraints(), "balanced")
        )
        assert out is not None
        assert len(out[0]["days"]) == 5
        assert out[0]["currency"] == "INR"

    def test_wrong_day_count_retries(self, monkeypatch):
        """The production bug: 2-day output for a 5-day request → retry."""
        bad = _valid_itinerary()
        bad["days"] = bad["days"][:2]
        good = _valid_itinerary()
        calls = []

        async def _fake_gen(schema, prompt, task, stage):
            calls.append(task)
            return (bad if len(calls) == 1 else good), {"input_tokens": 0, "output_tokens": 0, "model": ""}
        monkeypatch.setattr(pipeline_module, "_generate_structured", _fake_gen)

        async def _fake_enrich(it):
            return it
        monkeypatch.setattr(
            deep_agent_module, "_enrich_itinerary_with_coordinates", _fake_enrich
        )

        out = asyncio.run(
            pipeline_module.run_refinement_pipeline(_constraints(), "balanced")
        )
        assert out is not None
        assert len(out[0]["days"]) == 5
        assert len(calls) == 2


class TestEditValidationPipeline:
    def setup_method(self):
        pipeline_module._reset_for_tests()
        pipeline_tools_module._reset_for_tests()

    def test_clean_edit_skips_llm(self, monkeypatch):
        """A structurally-valid manual edit needs zero LLM calls."""
        async def _boom(*a, **k):
            raise AssertionError("LLM fix-pass must not run on a clean edit")
        monkeypatch.setattr(pipeline_module, "_generate_structured", _boom)

        async def _fake_enrich(it):
            return it
        monkeypatch.setattr(
            deep_agent_module, "_enrich_itinerary_with_coordinates", _fake_enrich
        )

        edited = _valid_itinerary()
        out = asyncio.run(pipeline_module.run_edit_validation_pipeline(edited))
        assert out is not None
        assert out[1] == {}  # no stage usage — code only
        assert len(out[0]["days"]) == 5

    def test_broken_edit_triggers_fix_pass(self, monkeypatch):
        """A day emptied by the user → LLM repair, then re-validate."""
        fixed = _valid_itinerary()
        calls = []

        async def _fake_gen(schema, prompt, task, stage):
            calls.append(task)
            return fixed, {"input_tokens": 5, "output_tokens": 5, "model": "m"}
        monkeypatch.setattr(pipeline_module, "_generate_structured", _fake_gen)

        async def _fake_enrich(it):
            return it
        monkeypatch.setattr(
            deep_agent_module, "_enrich_itinerary_with_coordinates", _fake_enrich
        )

        edited = _valid_itinerary()
        edited["days"][2] = {"day": 3}  # user emptied day 3
        out = asyncio.run(pipeline_module.run_edit_validation_pipeline(edited))
        assert out is not None
        assert len(calls) == 1
        assert "empty" in calls[0] or "Day 3" in calls[0]
        # Fix-pass result flows through reconcile (which adds budget_status)
        assert out[0]["days"] == fixed["days"]
        assert out[0]["destination"] == fixed["destination"]
        assert out[1]["edit_validator"]["input_tokens"] == 5

    def test_cancel_short_circuits(self):
        ev = asyncio.Event()
        ev.set()
        assert asyncio.run(
            pipeline_module.run_edit_validation_pipeline(
                _valid_itinerary(), cancel_event=ev
            )
        ) is None


class TestPipelineTools:
    def setup_method(self):
        pipeline_module._reset_for_tests()
        pipeline_tools_module._reset_for_tests()

    def test_generate_trip_plans_returns_marker_and_parks_payload(self, monkeypatch):
        comparison = _valid_comparison()

        async def _fake_pipeline(constraints, **kwargs):
            return comparison, {"researcher": {"input_tokens": 10, "output_tokens": 5, "model": "m"}}
        monkeypatch.setattr(
            pipeline_tools_module, "run_comparison_pipeline", _fake_pipeline
        )

        from agents.tools.visuals import set_current_thread_id
        set_current_thread_id("thread-1")
        set_pipeline_context(locale="en")

        raw = asyncio.run(generate_trip_plans.ainvoke({
            "constraints": _constraints().model_dump()
        }))
        result = json.loads(raw)
        pid = result["_pipeline_payload_id"]
        assert "compare" in result["message"].lower() or "tier" in result["message"].lower()

        payload = asyncio.run(pop_payload(pid))
        assert payload["kind"] == "comparison"
        assert payload["data"] == comparison
        assert asyncio.run(get_latest_comparison("thread-1")) == comparison

    def test_generate_trip_plans_budget_reached(self, monkeypatch):
        set_pipeline_context(budget_check=lambda: True)
        raw = asyncio.run(generate_trip_plans.ainvoke({
            "constraints": _constraints().model_dump()
        }))
        assert "budget" in raw.lower()

    def test_generate_trip_plans_pipeline_failure_graceful(self, monkeypatch):
        async def _fake_pipeline(constraints, **kwargs):
            return None
        monkeypatch.setattr(
            pipeline_tools_module, "run_comparison_pipeline", _fake_pipeline
        )
        set_pipeline_context(budget_check=lambda: False)
        raw = asyncio.run(generate_trip_plans.ainvoke({
            "constraints": _constraints().model_dump()
        }))
        assert "failed" in raw.lower()

    def test_refine_without_constraints_asks_first(self):
        from agents.tools.visuals import set_current_thread_id
        set_current_thread_id("empty-thread")
        set_pipeline_context()
        raw = asyncio.run(refine_itinerary.ainvoke({"tier": "balanced"}))
        assert "constraints" in raw.lower()

    def test_sanity_check_rejects_mismatch(self, monkeypatch):
        async def _fake_pipeline(constraints, **kwargs):
            raise AssertionError("pipeline must not run on mismatch")
        monkeypatch.setattr(
            pipeline_tools_module, "run_comparison_pipeline", _fake_pipeline
        )
        set_pipeline_context(stated_constraints={"days": 3})
        raw = asyncio.run(generate_trip_plans.ainvoke({
            "constraints": _constraints().model_dump()
        }))
        assert "3 days" in raw and "confirm" in raw.lower()

    def test_sanity_check_rejects_budget_mismatch(self, monkeypatch):
        async def _fake_pipeline(constraints, **kwargs):
            raise AssertionError("pipeline must not run on mismatch")
        monkeypatch.setattr(
            pipeline_tools_module, "run_comparison_pipeline", _fake_pipeline
        )
        set_pipeline_context(
            stated_constraints={"budget_amount": 80000, "budget_currency": "INR"}
        )
        raw = asyncio.run(generate_trip_plans.ainvoke({
            "constraints": _constraints().model_dump()
        }))
        assert "80,000" in raw and "confirm" in raw.lower()

    def test_sanity_check_passes_when_matching(self, monkeypatch):
        comparison = _valid_comparison()
        async def _fake_pipeline(constraints, **kwargs):
            return comparison, {}
        monkeypatch.setattr(
            pipeline_tools_module, "run_comparison_pipeline", _fake_pipeline
        )
        from agents.tools.visuals import set_current_thread_id
        set_current_thread_id("thread-ok")
        set_pipeline_context(
            stated_constraints={"days": 5, "budget_amount": 50000, "budget_currency": "INR"}
        )
        raw = asyncio.run(generate_trip_plans.ainvoke({
            "constraints": _constraints().model_dump()
        }))
        assert "_pipeline_payload_id" in raw

    def test_sanity_check_ignores_absent_fields(self, monkeypatch):
        """User never wrote a number in text → no false positive."""
        comparison = _valid_comparison()
        async def _fake_pipeline(constraints, **kwargs):
            return comparison, {}
        monkeypatch.setattr(
            pipeline_tools_module, "run_comparison_pipeline", _fake_pipeline
        )
        from agents.tools.visuals import set_current_thread_id
        set_current_thread_id("thread-none")
        set_pipeline_context(stated_constraints={})
        raw = asyncio.run(generate_trip_plans.ainvoke({
            "constraints": _constraints().model_dump()
        }))
        assert "_pipeline_payload_id" in raw

    def test_refine_after_generate(self, monkeypatch):
        comparison = _valid_comparison()
        itinerary = _valid_itinerary()

        async def _fake_cmp(constraints, **kwargs):
            return comparison, {}
        async def _fake_itin(constraints, tier, adjustments=None, **kwargs):
            return itinerary, {}
        monkeypatch.setattr(
            pipeline_tools_module, "run_comparison_pipeline", _fake_cmp
        )
        monkeypatch.setattr(
            pipeline_tools_module, "run_refinement_pipeline", _fake_itin
        )

        from agents.tools.visuals import set_current_thread_id
        set_current_thread_id("thread-2")
        set_pipeline_context(budget_check=lambda: False)

        asyncio.run(generate_trip_plans.ainvoke({"constraints": _constraints().model_dump()}))
        raw = asyncio.run(refine_itinerary.ainvoke({"tier": "balanced"}))
        result = json.loads(raw)
        payload = asyncio.run(pop_payload(result["_pipeline_payload_id"]))
        assert payload["kind"] == "itinerary"
        assert payload["data"] == itinerary


class _Chunk:
    def __init__(self, content):
        self.content = content


class TestModelStreamPipelineWiring:
    """_ModelStream must emit the parked payload on pipeline tool_end and
    keep inner pipeline chunks out of the token stream."""

    def test_payload_emitted_and_inner_text_filtered(self):
        class _FakeAgent:
            async def astream_events(self, *args, **kwargs):
                yield {"event": "on_chat_model_stream", "run_id": "orch",
                       "data": {"chunk": _Chunk("Let me plan that.")}, "parent_ids": []}
                yield {"event": "on_tool_start", "name": "generate_trip_plans",
                       "run_id": "pipe-1",
                       "data": {"input": {"constraints": {}}}, "parent_ids": ["orch"]}
                # Inner specialist/generator text must NOT reach _texts
                yield {"event": "on_chat_model_stream", "run_id": "inner-1",
                       "data": {"chunk": _Chunk('{"plans": [{"tier": "budget"}]}')},
                       "parent_ids": ["pipe-1"]}
                yield {"event": "on_tool_end", "name": "generate_trip_plans",
                       "run_id": "pipe-1",
                       "data": {"output": json.dumps({"_pipeline_payload_id": PID})},
                       "parent_ids": ["orch"]}
                yield {"event": "on_chat_model_stream", "run_id": "orch2",
                       "data": {"chunk": _Chunk("Here are your options!")}, "parent_ids": []}

        pipeline_module._reset_for_tests()
        comparison = _valid_comparison()
        PID = asyncio.run(store_payload("t1", "comparison", comparison))

        stream = deep_agent_module._ModelStream(_FakeAgent(), {"configurable": {}})
        events = asyncio.run(self._collect(stream))
        kinds = [e["event"] for e in events]

        assert "comparison" in kinds
        comp_event = next(e for e in events if e["event"] == "comparison")
        assert comp_event["data"] == comparison

        # Inner structured output never entered the text accumulator
        assert stream.last_text() == "Here are your options!"
        # Pipeline tool registered for cost attribution + nested filtering
        assert "pipe-1" in stream._pipeline_run_ids
        assert stream._active_task_names.get("pipe-1") == "generate_trip_plans"

    async def _collect(self, stream):
        return [e async for e in stream.events({"messages": []})]

    def test_stage_usage_lands_in_subagent_costs(self):
        """_stage_usage on the tool result → per-stage rows in _subagent_costs,
        and bubbled inner model usage does NOT double-count under the tool name."""
        class _Out:
            usage_metadata: ClassVar = {"input_tokens": 100, "output_tokens": 50}
            response_metadata: ClassVar = {"model_name": "gpt-4o-mini"}

        class _FakeAgent:
            async def astream_events(self, *args, **kwargs):
                yield {"event": "on_tool_start", "name": "generate_trip_plans",
                       "run_id": "pipe-1", "data": {"input": {}}, "parent_ids": []}
                # Inner model call bubbles up under the pipeline run_id
                yield {"event": "on_chat_model_end", "run_id": "inner-llm",
                       "data": {"output": _Out()}, "parent_ids": ["pipe-1"]}
                yield {"event": "on_tool_end", "name": "generate_trip_plans",
                       "run_id": "pipe-1",
                       "data": {"output": json.dumps({
                           "_pipeline_payload_id": PID2,
                           "_stage_usage": {
                               "researcher": {"input_tokens": 100, "output_tokens": 50,
                                              "model": "gpt-4o-mini"},
                           },
                       })},
                       "parent_ids": []}

        pipeline_module._reset_for_tests()
        PID2 = asyncio.run(store_payload("t9", "comparison", _valid_comparison()))

        stream = deep_agent_module._ModelStream(_FakeAgent(), {"configurable": {}})
        asyncio.run(self._collect(stream))

        assert stream._subagent_costs["researcher"]["input_tokens"] == 100
        # Inner bubbled usage attributed nowhere per-name (session cost still counts it)
        assert "generate_trip_plans" not in stream._subagent_costs
        assert stream._session_cost > 0

    def test_pipeline_tool_inner_events_get_progress(self):
        """Inner tool calls (e.g. internet_search inside the pipeline) should
        surface progress under the pipeline tool's run_id, like task children."""
        class _FakeAgent:
            async def astream_events(self, *args, **kwargs):
                yield {"event": "on_tool_start", "name": "generate_trip_plans",
                       "run_id": "pipe-9", "data": {"input": {}}, "parent_ids": []}
                yield {"event": "on_tool_start", "name": "internet_search",
                       "run_id": "inner-search",
                       "data": {"input": {"query": "Delhi hotels"}},
                       "parent_ids": ["pipe-9"]}

        stream = deep_agent_module._ModelStream(_FakeAgent(), {"configurable": {}})
        events = asyncio.run(self._collect(stream))
        progress = [e for e in events if e["event"] == "subagent_progress"]
        assert progress  # at least the pipeline-start progress
        descs = [p["data"]["description"] for p in progress]
        assert any("Searching" in d or "plan" in d.lower() for d in descs)


class TestResearchLimitedFlag:
    """R5 — specialist failures must flag the payload, not ship silently."""

    def setup_method(self):
        pipeline_module._reset_for_tests()
        pipeline_tools_module._reset_for_tests()

    def test_failed_specialist_flags_comparison(self, monkeypatch):
        async def _partial(name, prompt, task, tools=None):
            if name == "researcher":
                return f"[{name} unavailable — proceed with remaining context]", {
                    "input_tokens": 0, "output_tokens": 0, "model": ""}
            return f"[{name} brief]", {"input_tokens": 0, "output_tokens": 0, "model": ""}
        monkeypatch.setattr(pipeline_module, "_run_specialist", _partial)

        async def _fake_gen(schema, prompt, task, stage):
            return _valid_comparison(), {"input_tokens": 0, "output_tokens": 0, "model": ""}
        monkeypatch.setattr(pipeline_module, "_generate_structured", _fake_gen)

        out = asyncio.run(pipeline_module.run_comparison_pipeline(_constraints()))
        assert out is not None
        assert out[0]["research_limited"] is True
        assert out[0]["research_gaps"] == ["researcher"]

    def test_all_specialists_ok_no_flag(self, monkeypatch):
        async def _ok(name, prompt, task, tools=None):
            return f"[{name} brief]", {"input_tokens": 0, "output_tokens": 0, "model": ""}
        monkeypatch.setattr(pipeline_module, "_run_specialist", _ok)

        async def _fake_gen(schema, prompt, task, stage):
            return _valid_comparison(), {"input_tokens": 0, "output_tokens": 0, "model": ""}
        monkeypatch.setattr(pipeline_module, "_generate_structured", _fake_gen)

        out = asyncio.run(pipeline_module.run_comparison_pipeline(_constraints()))
        assert out is not None
        assert "research_limited" not in out[0]

    def test_flag_propagates_to_itinerary(self, monkeypatch):
        async def _fake_latest(tid):
            return {"research_limited": True, "research_gaps": ["researcher"], "plans": []}
        monkeypatch.setattr(pipeline_module, "get_latest_comparison", _fake_latest)

        async def _fake_gen(schema, prompt, task, stage):
            return _valid_itinerary(), {"input_tokens": 0, "output_tokens": 0, "model": ""}
        monkeypatch.setattr(pipeline_module, "_generate_structured", _fake_gen)

        async def _fake_enrich(it):
            return it
        monkeypatch.setattr(
            deep_agent_module, "_enrich_itinerary_with_coordinates", _fake_enrich
        )

        out = asyncio.run(
            pipeline_module.run_refinement_pipeline(_constraints(), "balanced")
        )
        assert out is not None
        assert out[0]["research_limited"] is True
        assert out[0]["research_gaps"] == ["researcher"]


class TestRetryAttempts:
    """R3 — retries accumulate token usage and expose an attempts count."""

    def setup_method(self):
        pipeline_module._reset_for_tests()
        pipeline_tools_module._reset_for_tests()

    def test_attempts_and_tokens_accumulate(self, monkeypatch):
        async def _ok(name, prompt, task, tools=None):
            return f"[{name} brief]", {"input_tokens": 0, "output_tokens": 0, "model": ""}
        monkeypatch.setattr(pipeline_module, "_run_specialist", _ok)

        good = _valid_comparison()
        calls = []

        async def _fake_gen(schema, prompt, task, stage):
            calls.append(task)
            # First call returns None (generation failure) but still cost
            # tokens — must not be dropped from stage usage.
            return (None if len(calls) == 1 else good), {
                "input_tokens": 100, "output_tokens": 50, "model": "m"}
        monkeypatch.setattr(pipeline_module, "_generate_structured", _fake_gen)

        out = asyncio.run(pipeline_module.run_comparison_pipeline(_constraints()))
        assert out is not None
        usage = out[1]["multi_plan_generator"]
        assert usage["attempts"] == 2
        assert usage["input_tokens"] == 200
        assert usage["output_tokens"] == 100

    def test_single_attempt_reports_one(self, monkeypatch):
        async def _ok(name, prompt, task, tools=None):
            return f"[{name} brief]", {"input_tokens": 0, "output_tokens": 0, "model": ""}
        monkeypatch.setattr(pipeline_module, "_run_specialist", _ok)

        async def _fake_gen(schema, prompt, task, stage):
            return _valid_comparison(), {"input_tokens": 0, "output_tokens": 0, "model": ""}
        monkeypatch.setattr(pipeline_module, "_generate_structured", _fake_gen)

        out = asyncio.run(pipeline_module.run_comparison_pipeline(_constraints()))
        assert out[1]["multi_plan_generator"]["attempts"] == 1

    def test_record_retries_fires_on_retry(self, monkeypatch):
        import agents.tools.pipeline_tools as pt
        events = []

        async def _fake_record(tid, event_type, **kw):
            events.append((tid, event_type, kw.get("output")))
        monkeypatch.setattr(
            "observability_store.observability_store.record_event", _fake_record
        )

        asyncio.run(pt._record_retries(
            "t1", {"multi_plan_generator": {"attempts": 3, "input_tokens": 5,
                                          "output_tokens": 5, "model": "m"}}
        ))
        assert events and events[0][1] == "pipeline_retries"

    def test_record_retries_silent_on_single_attempt(self, monkeypatch):
        import agents.tools.pipeline_tools as pt
        events = []

        async def _fake_record(tid, event_type, **kw):
            events.append(event_type)
        monkeypatch.setattr(
            "observability_store.observability_store.record_event", _fake_record
        )

        asyncio.run(pt._record_retries(
            "t1", {"multi_plan_generator": {"attempts": 1}}
        ))
        assert events == []


class TestEditDiff:
    """U5 — the validator's changes must be visible, not silent."""

    def setup_method(self):
        pipeline_module._reset_for_tests()
        pipeline_tools_module._reset_for_tests()

    def test_changed_activity(self):
        before = _valid_itinerary()
        after = _valid_itinerary()
        after["days"][0]["morning"]["activity"] = "Different Museum"
        changes = pipeline_module._diff_itineraries(before, after)
        assert any(
            c["type"] == "changed" and c["day"] == 1 and c["slot"] == "morning"
            for c in changes
        )

    def test_added_and_removed(self):
        before = _valid_itinerary()
        before["days"][1]["evening"] = {}  # empty slot for the validator to fill
        after = _valid_itinerary()
        after["days"][0]["morning"] = {}
        after["days"][1]["evening"] = {"activity": "Night market", "location": "Old town"}
        changes = pipeline_module._diff_itineraries(before, after)
        assert any(c["type"] == "removed" and c["slot"] == "morning" for c in changes)
        assert any(c["type"] == "added" and c["slot"] == "evening" for c in changes)

    def test_moved_detection(self):
        before = _valid_itinerary()
        before["days"][1]["evening"] = {}  # destination slot must be empty
        after = _valid_itinerary()
        name = before["days"][0]["morning"]["activity"]
        after["days"][0]["morning"] = {}
        after["days"][1]["evening"] = {"activity": name, "location": "x"}
        changes = pipeline_module._diff_itineraries(before, after)
        assert any(
            c["type"] == "moved" and c["activity"] == name and "day 1 morning" in c["detail"]
            for c in changes
        )
        assert not any(c["type"] in ("added", "removed") for c in changes)

    def test_cost_delta(self):
        before = _valid_itinerary()
        after = _valid_itinerary()
        after["estimated_total_cost_usd"] = 99999
        changes = pipeline_module._diff_itineraries(before, after)
        assert any(c["type"] == "cost" and c["after"] == 99999 for c in changes)

    def test_identical_no_changes(self):
        assert pipeline_module._diff_itineraries(_valid_itinerary(), _valid_itinerary()) == []

    def test_fix_pass_attaches_edit_changes(self, monkeypatch):
        """Broken edit → LLM fix → result carries edit_changes."""
        fixed = _valid_itinerary()
        fixed["days"][2] = {
            "day": 3, "theme": "Fixed",
            "morning": {"activity": "Museum", "location": "x", "cost_usd": 10},
            "afternoon": {"activity": "Park", "location": "x", "cost_usd": 5},
            "evening": {"activity": "Dinner", "location": "x", "cost_usd": 20},
            "transport": "", "accommodation": "", "daily_cost_usd": 35, "tips": [],
        }

        async def _fake_gen(schema, prompt, task, stage):
            return fixed, {"input_tokens": 5, "output_tokens": 5, "model": "m"}
        monkeypatch.setattr(pipeline_module, "_generate_structured", _fake_gen)

        async def _fake_enrich(it):
            return it
        monkeypatch.setattr(
            deep_agent_module, "_enrich_itinerary_with_coordinates", _fake_enrich
        )

        edited = _valid_itinerary()
        edited["days"][2] = {"day": 3}  # emptied day → fix-pass fills it
        out = asyncio.run(pipeline_module.run_edit_validation_pipeline(edited))
        assert out is not None
        assert out[0]["edit_changes"], "validator filled day 3 — diff must be attached"

    def test_clean_edit_no_edit_changes(self, monkeypatch):
        async def _fake_enrich(it):
            return it
        monkeypatch.setattr(
            deep_agent_module, "_enrich_itinerary_with_coordinates", _fake_enrich
        )
        out = asyncio.run(pipeline_module.run_edit_validation_pipeline(_valid_itinerary()))
        assert out is not None
        assert "edit_changes" not in out[0]


class TestCurrencyFieldDocs:
    """R2 — the *_usd field names lie; the schema must say so."""

    def test_cost_fields_document_currency(self):
        schema = pipeline_module.ItineraryPlan.model_json_schema()
        props = schema["properties"]
        assert "currency" in props["estimated_total_cost_usd"]["description"]
        assert "THIS currency" in props["currency"]["description"]
        day_props = schema["$defs"]["ItineraryDay"]["properties"]
        assert "not USD" in day_props["daily_cost_usd"]["description"]
        slot_props = schema["$defs"]["DaySlot"]["properties"]
        assert "not USD" in slot_props["cost_usd"]["description"]

    def test_stub_schema_documents_currency(self):
        schema = pipeline_module.PlanItineraryStub.model_json_schema()
        assert "currency" in schema["properties"]["estimated_total_cost_usd"]["description"]


class TestClarifyAnswerTracking:
    """Clarify replies carry a machine-readable field map — already-answered
    fields must never be re-asked and must constrain generation."""

    def setup_method(self):
        pipeline_module._reset_for_tests()
        pipeline_tools_module._reset_for_tests()

    @staticmethod
    def _clarify_call(fields):
        from agents.tools.pipeline_tools import ask_clarifying_questions
        from agents.tools.visuals import set_current_thread_id
        set_current_thread_id("t-clar")
        qs = [
            {
                "field": f,
                "header": f,
                "question": f"{f}?",
                "options": [],
                "multi_select": False,
            }
            for f in fields
        ]
        raw = asyncio.run(ask_clarifying_questions.ainvoke({"questions": qs}))
        return json.loads(raw)

    async def _payload_questions(self, result):
        payload = await pop_payload(result["_pipeline_payload_id"])
        return [q["field"] for q in payload["data"]["questions"]]

    def test_drops_already_answered_fields(self):
        set_pipeline_context(stated_constraints={"travel_style": "relaxed"})
        result = self._clarify_call(["travel_style", "destination"])
        assert asyncio.run(self._payload_questions(result)) == ["destination"]
        assert result["answered_fields"]["travel_style"] == "relaxed"

    def test_all_answered_returns_no_card(self):
        set_pipeline_context(stated_constraints={
            "travel_style": "relaxed",
            "group_type": "solo",
        })
        result = self._clarify_call(["travel_style", "group_type"])
        assert "_pipeline_payload_id" not in result
        assert "generate_trip_plans" in result["message"]

    def test_reports_still_missing_required_fields(self):
        set_pipeline_context(stated_constraints={"destination": "Goa"})
        result = self._clarify_call(["total_days"])
        assert "travel_style" in result["message"]
        assert "budget_amount" in result["message"]
        assert asyncio.run(self._payload_questions(result)) == ["total_days"]

    def test_days_alias_marks_total_days_answered(self):
        set_pipeline_context(stated_constraints={"days": 5})
        result = self._clarify_call(["total_days", "destination"])
        assert asyncio.run(self._payload_questions(result)) == ["destination"]

    def test_range_budget_passes_inside_and_rejects_outside(self, monkeypatch):
        async def _fake_pipeline(constraints, **kwargs):
            return _valid_comparison(), {}
        monkeypatch.setattr(
            pipeline_tools_module, "run_comparison_pipeline", _fake_pipeline
        )
        from agents.tools.visuals import set_current_thread_id
        set_current_thread_id("t-range")
        stated = {
            "budget_min": 25000,
            "budget_max": 60000,
            "budget_currency": "INR",
        }
        set_pipeline_context(stated_constraints=stated)
        raw = asyncio.run(generate_trip_plans.ainvoke({
            "constraints": _constraints().model_dump()
        }))
        assert "_pipeline_payload_id" in raw

        async def _boom(constraints, **kwargs):
            raise AssertionError("pipeline must not run outside the range")
        monkeypatch.setattr(
            pipeline_tools_module, "run_comparison_pipeline", _boom
        )
        raw = asyncio.run(generate_trip_plans.ainvoke({
            "constraints": _constraints(budget_amount=90000).model_dump()
        }))
        assert "budget range" in raw and "25,000" in raw

    def test_budget_cap_rejects_above(self, monkeypatch):
        async def _boom(constraints, **kwargs):
            raise AssertionError("pipeline must not run above the cap")
        monkeypatch.setattr(
            pipeline_tools_module, "run_comparison_pipeline", _boom
        )
        set_pipeline_context(stated_constraints={
            "budget_max": 25000,
            "budget_currency": "INR",
        })
        raw = asyncio.run(generate_trip_plans.ainvoke({
            "constraints": _constraints(budget_amount=40000).model_dump()
        }))
        assert "cap" in raw.lower()

    def test_enum_answer_rejects_conflicting_constraints(self, monkeypatch):
        async def _boom(constraints, **kwargs):
            raise AssertionError("pipeline must not run on enum mismatch")
        monkeypatch.setattr(
            pipeline_tools_module, "run_comparison_pipeline", _boom
        )
        set_pipeline_context(stated_constraints={"travel_style": "relaxed"})
        raw = asyncio.run(generate_trip_plans.ainvoke({
            "constraints": _constraints(travel_style="adventurous").model_dump()
        }))
        assert "relaxed" in raw and "Confirm" in raw

    def test_free_text_enum_answer_not_rejected(self, monkeypatch):
        """An 'Other' answer that isn't an enum member must not false-positive."""
        comparison = _valid_comparison()
        async def _fake_pipeline(constraints, **kwargs):
            return comparison, {}
        monkeypatch.setattr(
            pipeline_tools_module, "run_comparison_pipeline", _fake_pipeline
        )
        from agents.tools.visuals import set_current_thread_id
        set_current_thread_id("t-free")
        set_pipeline_context(stated_constraints={"travel_style": "Very fast"})
        raw = asyncio.run(generate_trip_plans.ainvoke({
            "constraints": _constraints().model_dump()
        }))
        assert "_pipeline_payload_id" in raw


class TestFillStatedClarifyAnswers:
    """_fill_stated must prefer the machine-readable clarify_answers block
    over regex extraction on the pretty text."""

    def test_reads_field_map(self):
        from agents.deep_agent import _fill_stated
        found: dict = {}
        _fill_stated(
            found,
            'Trip budget: ₹25,000–₹60,000; Travel style: Relaxed\n'
            '<clarify_answers>{"budget_amount": "₹25,000–₹60,000", '
            '"travel_style": "relaxed"}</clarify_answers>',
        )
        assert found["budget_min"] == 25000
        assert found["budget_max"] == 60000
        assert found["travel_style"] == "relaxed"
        assert found["budget_currency"] == "INR"

    def test_range_text_does_not_poison_point_extraction(self):
        """Without the tag the first number in '25,000–₹60,000' would be
        read as a point budget; the tag's bounds must win instead."""
        from agents.deep_agent import _fill_stated
        found: dict = {}
        _fill_stated(
            found,
            'Trip budget: ₹25,000–₹60,000\n'
            '<clarify_answers>{"budget_amount": "₹25,000–₹60,000"}</clarify_answers>',
        )
        assert found.get("budget_amount") in (None, 25000)
        assert found["budget_max"] == 60000


class TestEnrichmentFields:
    """Phase 2: optional enrichment fields on slots/days — generated by the
    model, rendered by the frontend, always optional so old payloads and
    old itineraries keep working."""

    def setup_method(self):
        pipeline_module._reset_for_tests()
        pipeline_tools_module._reset_for_tests()

    def test_day_slot_accepts_enrichment_fields(self):
        from agents.pipeline import DaySlot
        slot = DaySlot(
            activity="Amber Fort",
            location="Jaipur",
            cost_usd=500,
            duration="3h",
            time="09:00",
            why="Beat the midday crowds",
            book="Entry ₹500 — buy at gate",
            food="Pyaaz kachori at Rawat",
        )
        d = slot.model_dump()
        assert d["time"] == "09:00"
        assert d["why"] == "Beat the midday crowds"
        assert d["book"].startswith("Entry")
        assert d["food"] == "Pyaaz kachori at Rawat"

    def test_day_slot_enrichment_defaults_none(self):
        """Old payloads without enrichment fields still validate."""
        from agents.pipeline import DaySlot
        slot = DaySlot(activity="X")
        d = slot.model_dump()
        for f in ("time", "why", "book", "food"):
            assert d[f] is None

    def test_itinerary_day_weather_and_walking(self):
        from agents.pipeline import ItineraryDay
        day = ItineraryDay(day=1, weather="28°C sunny", walking_km=4.5)
        d = day.model_dump()
        assert d["weather"] == "28°C sunny"
        assert d["walking_km"] == 4.5

    def test_itinerary_plan_roundtrips_enrichment(self):
        """Full ItineraryPlan dump carries enrichment through to the dict
        that flows into the payload store / SSE."""
        from agents.pipeline import DaySlot, ItineraryDay, ItineraryPlan
        plan = ItineraryPlan(
            destination="Delhi",
            total_days=1,
            currency="INR",
            estimated_total_cost_usd=10000,
            days=[
                ItineraryDay(
                    day=1,
                    weather="32°C humid",
                    walking_km=6.0,
                    morning=DaySlot(
                        activity="Red Fort", time="09:30", why="Opens early",
                    ),
                )
            ],
        )
        d = plan.model_dump()
        assert d["days"][0]["weather"] == "32°C humid"
        assert d["days"][0]["morning"]["time"] == "09:30"
        assert d["days"][0]["morning"]["book"] is None

    def test_refinement_injects_stored_research_brief(self, monkeypatch):
        """Briefs stashed by the comparison stage land in the refinement
        prompt — weather/food fields are grounded, not guessed."""
        from agents.tools.visuals import set_current_thread_id
        set_current_thread_id("enrich-thread")
        asyncio.run(pipeline_module.payload_store.set_thread_state(
            "enrich-thread",
            "latest_research",
            {"research": "Jaipur: hot, 38°C days", "risk": "Heat wave risk"},
        ))

        tasks = []

        async def _fake_gen(schema, prompt, task, stage):
            tasks.append(task)
            return _valid_itinerary(), {"input_tokens": 0, "output_tokens": 0, "model": ""}
        monkeypatch.setattr(pipeline_module, "_generate_structured", _fake_gen)

        async def _fake_enrich(it):
            return it
        monkeypatch.setattr(
            deep_agent_module, "_enrich_itinerary_with_coordinates", _fake_enrich
        )

        out = asyncio.run(
            pipeline_module.run_refinement_pipeline(_constraints(), "balanced")
        )
        assert out is not None
        assert "<research_brief>" in tasks[0]
        assert "38°C" in tasks[0]
        assert "<risk_assessment>" in tasks[0]

    def test_refinement_without_brief_still_works(self, monkeypatch):
        """No stashed brief → no research block, generation still succeeds."""
        from agents.tools.visuals import set_current_thread_id
        set_current_thread_id("no-brief-thread")

        tasks = []

        async def _fake_gen(schema, prompt, task, stage):
            tasks.append(task)
            return _valid_itinerary(), {"input_tokens": 0, "output_tokens": 0, "model": ""}
        monkeypatch.setattr(pipeline_module, "_generate_structured", _fake_gen)

        async def _fake_enrich(it):
            return it
        monkeypatch.setattr(
            deep_agent_module, "_enrich_itinerary_with_coordinates", _fake_enrich
        )

        out = asyncio.run(
            pipeline_module.run_refinement_pipeline(_constraints(), "balanced")
        )
        assert out is not None
        assert "<research_brief>" not in tasks[0]

    def test_comparison_stashes_research_brief(self, monkeypatch):
        """The comparison stage persists briefs per thread for later use."""
        from agents.tools.visuals import set_current_thread_id
        set_current_thread_id("stash-thread")

        async def _fake_specialist(name, prompt, task, tools=None):
            return f"[{name} brief text]", {"input_tokens": 0, "output_tokens": 0, "model": ""}
        monkeypatch.setattr(pipeline_module, "_run_specialist", _fake_specialist)

        async def _fake_gen(schema, prompt, task, stage):
            return _valid_comparison(), {"input_tokens": 0, "output_tokens": 0, "model": ""}
        monkeypatch.setattr(pipeline_module, "_generate_structured", _fake_gen)

        out = asyncio.run(pipeline_module.run_comparison_pipeline(_constraints()))
        assert out is not None
        stashed = asyncio.run(
            pipeline_module.payload_store.get_thread_state(
                "stash-thread", "latest_research"
            )
        )
        assert stashed is not None
        assert "researcher brief text" in stashed["research"]
        assert "risk_detector brief text" in stashed["risk"]

    def test_edit_fix_prompt_preserves_enrichment(self):
        """The repair prompt must tell the model to keep enrichment fields."""
        assert "walking_km" in pipeline_module._EDIT_FIX_PROMPT
        assert "time, why, book, food" in pipeline_module._EDIT_FIX_PROMPT

    def test_itinerary_day_date_field(self):
        """Optional calendar date — emitted only when the user stated dates."""
        from agents.pipeline import ItineraryDay
        d = ItineraryDay(day=1, date="2026-03-10").model_dump()
        assert d["date"] == "2026-03-10"
        assert ItineraryDay(day=2).model_dump()["date"] is None


class TestSavedPreferencesInjection:
    """_saved_preferences_text feeds pipeline task text (PF2)."""

    def _seed(self, monkeypatch, user_id="prefs@example.com", content=None):
        from langgraph.store.memory import InMemoryStore

        from agents.deep_agent import user_memory_namespace

        store = InMemoryStore()
        if content is not None:
            store.put((user_memory_namespace(user_id),), "/preferences.md", {"content": content})
        monkeypatch.setattr(
            pipeline_tools_module, "get_redis_file_store", lambda: store, raising=False
        )
        monkeypatch.setattr(
            "agents.deep_agent.get_redis_file_store", lambda: store
        )
        return store

    def test_returns_prefs_when_seeded(self, monkeypatch):
        self._seed(
            monkeypatch,
            content="<user_instructions>\nNo museums.\n</user_instructions>\n\n"
            "<learned_preferences>\ntravel_style: relaxed\n</learned_preferences>",
        )
        set_pipeline_context(user_id="prefs@example.com")
        text = pipeline_module._saved_preferences_text()
        assert "No museums." in text
        assert "travel_style: relaxed" in text

    def test_legacy_namespace_fallback(self, monkeypatch):
        # Legacy raw-id namespace — only valid for dotless ids (store rejects
        # '.' in namespace labels; real emails could never write this path).
        from langgraph.store.memory import InMemoryStore

        store = InMemoryStore()
        store.put(("dev@localhost",), "/preferences.md", {"content": "Legacy pref line"})
        monkeypatch.setattr("agents.deep_agent.get_redis_file_store", lambda: store)
        set_pipeline_context(user_id="dev@localhost")
        assert "Legacy pref line" in pipeline_module._saved_preferences_text()

    def test_empty_without_user_id(self, monkeypatch):
        self._seed(monkeypatch, content="<user_instructions>\nHi\n</user_instructions>")
        set_pipeline_context(user_id=None)
        pipeline_tools_module._pipeline_user_id.set("")
        assert pipeline_module._saved_preferences_text() == ""

    def test_empty_on_store_error(self, monkeypatch):
        class _Broken:
            def get(self, *a, **k):
                raise RuntimeError("store down")

        monkeypatch.setattr("agents.deep_agent.get_redis_file_store", lambda: _Broken())
        set_pipeline_context(user_id="prefs@example.com")
        assert pipeline_module._saved_preferences_text() == ""
