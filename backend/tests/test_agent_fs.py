"""Bug #11: each user's agent filesystem must live under a per-user directory."""

import asyncio
import hashlib

import agents.deep_agent as deep_agent_module


def _run_create(user_id):
    """Call create_chat_agent with everything external stubbed; return captured root_dir."""
    captured = {}

    class _FakeFSBackend:
        def __init__(self, root_dir):
            captured["root_dir"] = root_dir

    class _FakeAgent:
        pass

    async def _run():
        import agents.deep_agent as m

        orig_fs = m.FilesystemBackend
        orig_create = m.create_deep_agent
        orig_model = m.get_orchestrator_model
        orig_file_store = m.get_redis_file_store
        try:
            m.FilesystemBackend = _FakeFSBackend
            m.create_deep_agent = lambda **kw: _FakeAgent()
            m.get_orchestrator_model = lambda: object()
            m.get_redis_file_store = lambda: object()
            from langgraph.checkpoint.memory import MemorySaver
            from langgraph.store.memory import InMemoryStore
            return await m.create_chat_agent(
                checkpointer=MemorySaver(),
                store=InMemoryStore(),
                user_id=user_id,
            ), captured
        finally:
            m.FilesystemBackend = orig_fs
            m.create_deep_agent = orig_create
            m.get_orchestrator_model = orig_model
            m.get_redis_file_store = orig_file_store

    return asyncio.run(_run())


class TestPerUserFilesystem:
    def test_root_dir_is_per_user_hash(self):
        _, cap = _run_create("alice")
        expected = hashlib.sha256("alice".encode()).hexdigest()[:12]
        assert cap["root_dir"] == f"/tmp/agent_fs/{expected}"

    def test_different_users_get_different_dirs(self):
        _, cap_a = _run_create("alice")
        _, cap_b = _run_create("bob")
        assert cap_a["root_dir"] != cap_b["root_dir"]
        assert cap_a["root_dir"].startswith("/tmp/agent_fs/")
        assert cap_b["root_dir"].startswith("/tmp/agent_fs/")

    def test_same_user_stable_across_calls(self):
        _, cap1 = _run_create("alice")
        _, cap2 = _run_create("alice")
        assert cap1["root_dir"] == cap2["root_dir"]

    def test_raw_user_id_never_in_path(self):
        sneaky = "../etc/passwd/../../root"
        _, cap = _run_create(sneaky)
        assert sneaky not in cap["root_dir"]
        assert ".." not in cap["root_dir"]

    def test_anonymous_user_gets_hashed_dir(self):
        _, cap = _run_create(None)
        expected = hashlib.sha256("anonymous".encode()).hexdigest()[:12]
        assert cap["root_dir"] == f"/tmp/agent_fs/{expected}"
