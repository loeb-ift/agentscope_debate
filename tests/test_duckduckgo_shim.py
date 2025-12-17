import types
import pytest

from adapters.duckduckgo_adapter import DuckDuckGoAdapter


def test_duckduckgo_shim_calls_searxng(monkeypatch):
    # Prepare a fake searxng adapter
    called = {}

    class FakeSearx:
        def invoke(self, **kwargs):
            called['kwargs'] = kwargs
            return {
                'data': [
                    {'title': 't', 'url': 'https://ex', 'snippet': 's', 'source': 'duckduckgo'}
                ],
                'raw': {'results': []},
                'cost': 0,
                'citations': []
            }

    # Patch SearXNGAdapter inside duckduckgo_adapter module
    monkeypatch.setattr('adapters.duckduckgo_adapter.SearXNGAdapter', FakeSearx)

    # Invoke shim
    adapter = DuckDuckGoAdapter()
    out = adapter.invoke(q='hello world', max_results=5)

    # Verify searxng called with mapped params
    assert called['kwargs']['q'] == 'hello world'
    assert called['kwargs']['engines'] == 'duckduckgo'
    assert called['kwargs']['limit'] == 5

    # Output shape stable
    assert 'data' in out and isinstance(out['data'], list)
    assert out['data'][0]['source'] == 'duckduckgo'
