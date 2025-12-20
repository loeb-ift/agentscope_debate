import pytest
from fastapi.testclient import TestClient

class FakeRedisPubSub:
    def subscribe(self, *args, **kwargs):
        return None
    def listen(self):
        if False:
            yield None
        return

class FakeRedis:
    def __init__(self):
        self._store = {}
    def get(self, key):
        return self._store.get(key)
    def set(self, key, value):
        self._store[key] = value
    def pubsub(self):
        return FakeRedisPubSub()

class FakeAsyncResult:
    def __init__(self, task_id, status="PENDING"):
        self.id = task_id
        self.status = status

@pytest.fixture(scope="function")
def test_client(monkeypatch):
    # Prepare dummy modules before importing app to avoid heavy deps
    import sys, types
    # Dummy celery module and worker.celery_app
    if 'celery' not in sys.modules:
        sys.modules['celery'] = types.SimpleNamespace(Celery=object)
    dummy_celery_app = types.ModuleType('worker.celery_app')
    dummy_celery_app.load_dynamic_tools = lambda: None
    class _DummyApp:
        @staticmethod
        def AsyncResult(task_id):
            return FakeAsyncResult(task_id, status="SUCCESS")
    dummy_celery_app.app = _DummyApp()
    sys.modules['worker.celery_app'] = dummy_celery_app

    # Import app after we prepare monkeypatch targets
    import api.main as main

    # Patch startup dependencies to no-ops
    monkeypatch.setattr(main, "init_db", lambda: None, raising=False)
    try:
        from api.init_data import initialize_all as _init
        monkeypatch.setattr("api.init_data.initialize_all", lambda db: None, raising=False)
    except Exception:
        pass

    # Ensure DB tables exist for tests (create all models)
    try:
        from api.database import engine
        from api import models as _models
        _models.Base.metadata.create_all(bind=engine)
    except Exception:
        pass

    # Tool registry and dynamic tools
    class _FakeRegistry:
        def __init__(self):
            self._tools = {}
        def register(self, adapter):
            # no-op during tests
            pass
        def list_tools(self):
            return {
                "searxng.search:v1": {
                    "description": "search",
                    "group": "basic",
                    "schema": {"type": "object"},
                    "version": "v1",
                }
            }
        def invoke_tool(self, name, kwargs):
            return {"ok": True, "echo": {"name": name, "kwargs": kwargs}}
    fake_registry = _FakeRegistry()
    monkeypatch.setattr(main, "tool_registry", fake_registry, raising=False)

    # Patch dynamic tool loader
    try:
        from worker.celery_app import load_dynamic_tools as _ldt
        monkeypatch.setattr("worker.celery_app.load_dynamic_tools", lambda: None, raising=False)
    except Exception:
        pass

    # Patch Redis client instance used by routes
    monkeypatch.setattr(main, "redis_client", FakeRedis(), raising=False)

    # Patch Celery AsyncResult to avoid broker
    class _FakeCeleryApp:
        @staticmethod
        def AsyncResult(task_id):
            return FakeAsyncResult(task_id, status="SUCCESS")
    monkeypatch.setattr(main, "celery_app", _FakeCeleryApp(), raising=False)

    # Finally return TestClient (startup will run but is safe due to patches)
    client = TestClient(main.app)
    return client
