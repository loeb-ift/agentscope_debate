# Tests (E2E-friendly, side-effect-free)

This suite provides a minimal smoke/E2E coverage for the FastAPI app without starting external services.

Key characteristics:
- Uses FastAPI TestClient; does not start an HTTP server
- Patches startup hooks to avoid DB migrations and heavy adapter registrations
- Replaces Redis and Celery interactions with in-memory fakes
- Exercises health, OpenAPI, registry list, tool test, and debate status endpoints

Run:
```
pytest -q
```

If you need full integration tests (real Redis/Celery/DB), restore archived tests from `_archive/tests_tmp`.
