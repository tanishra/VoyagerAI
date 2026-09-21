"""Tests for _ObsQueue — ordered, referenced observability writes (Bug #12)."""

from __future__ import annotations

import asyncio

import pytest

from main import _ObsQueue, _send_obs_event


class TestObsQueue:
    @pytest.mark.asyncio
    async def test_fifo_ordering(self):
        calls = []

        async def rec(i):
            calls.append(i)

        obs = _ObsQueue()
        for i in range(10):
            obs.send(rec, i)
        await obs.close()
        assert calls == list(range(10))

    @pytest.mark.asyncio
    async def test_close_drains_pending(self):
        done = asyncio.Event()

        async def slow():
            await asyncio.sleep(0.05)
            done.set()

        obs = _ObsQueue()
        obs.send(slow)
        await obs.close()
        assert done.is_set()

    @pytest.mark.asyncio
    async def test_failed_write_does_not_kill_consumer(self):
        calls = []

        async def boom():
            raise RuntimeError("store down")

        async def ok():
            calls.append("ok")

        obs = _ObsQueue()
        obs.send(boom)
        obs.send(ok)
        await obs.close()
        assert calls == ["ok"]

    @pytest.mark.asyncio
    async def test_close_without_sends(self):
        obs = _ObsQueue()
        await obs.close()  # no consumer ever started — must not hang
        assert obs._task is None

    @pytest.mark.asyncio
    async def test_send_after_close_enqueues_but_safe(self):
        obs = _ObsQueue()

        async def rec():
            pass

        obs.send(rec)
        await obs.close()
        obs.send(rec)  # queued but consumer gone — must not raise

    @pytest.mark.asyncio
    async def test_consumer_task_is_referenced(self):
        obs = _ObsQueue()

        async def rec():
            pass

        obs.send(rec)
        assert obs._task is not None
        await obs.close()
        assert obs._task.done()

    @pytest.mark.asyncio
    async def test_close_timeout_cancels_hung_write(self):
        started = asyncio.Event()

        async def hang():
            started.set()
            await asyncio.sleep(60)

        obs = _ObsQueue()
        obs.send(hang)
        await asyncio.sleep(0.01)
        assert started.is_set()
        await obs.close(timeout=0.05)
        await asyncio.sleep(0)
        assert obs._task.done()


class TestSendObsEvent:
    @pytest.mark.asyncio
    async def test_extracts_fields_from_sse_payload(self):
        captured = []

        async def rec(**kwargs):
            captured.append(kwargs)

        obs = _ObsQueue()
        payload = {
            "event": "tool_start",
            "data": '{"name": "search", "run_id": "r1", "input_tokens": 5}',
        }
        _send_obs_event(obs, "chat:x:y", payload)
        # patch the store call — _send_obs_event uses observability_store; swap via monkeypatch-free approach
        await obs.close()
        # record_event on real store would be called; here just ensure no raise

    @pytest.mark.asyncio
    async def test_malformed_payload_data_does_not_raise(self):
        obs = _ObsQueue()
        _send_obs_event(obs, "t", {"event": "token", "data": "not-json{{{"})
        _send_obs_event(obs, "t", {"event": "token"})
        _send_obs_event(obs, "t", {"event": "token", "data": '"just a string"'})
        await obs.close()

    @pytest.mark.asyncio
    async def test_sends_to_store_with_mapped_fields(self, monkeypatch):
        captured = []

        async def rec(**kwargs):
            captured.append(kwargs)

        import main as main_module
        monkeypatch.setattr(main_module.observability_store, "record_event", rec)

        obs = _ObsQueue()
        payload = {
            "event": "tool_start",
            "data": '{"name": "search", "run_id": "r1", "parent_run_id": "p0", "input_tokens": 5, "model": "m"}',
        }
        _send_obs_event(obs, "chat:x:y", payload)
        await obs.close()
        assert captured == [{
            "thread_id": "chat:x:y",
            "event_type": "tool_start",
            "name": "search",
            "run_id": "r1",
            "parent_run_id": "p0",
            "input_data": None,
            "output": "",
            "error": "",
            "tokens_in": 5,
            "tokens_out": 0,
            "model": "m",
        }]
