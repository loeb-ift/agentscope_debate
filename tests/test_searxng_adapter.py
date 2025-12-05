import pytest

from adapters.searxng_adapter import SearxngAdapter


class TestSearxngAdapter:
    def setup_method(self):
        self.adapter = SearxngAdapter(base_url="http://searxng:8080")

    def test_schema_shape(self):
        schema = self.adapter.describe()
        assert schema["name"] == "searxng.search"
        assert schema["parameters"]["type"] == "object"
        assert "q" in schema["parameters"]["properties"]

    @pytest.mark.parametrize(
        "params, ok",
        [({"q": "tsmc"}, True), ({"q": "a"}, False), ({"q": "tsmc", "limit": 100}, False)],
    )
    def test_validate(self, params, ok):
        if ok:
            self.adapter.validate(params)
        else:
            with pytest.raises(ValueError):
                self.adapter.validate(params)

    def test_invoke_mock(self):
        out = self.adapter.invoke({"q": "台積電", "category": "news", "limit": 5})
        assert out.data["q"] == "台積電"
        assert out.data["category"] == "news"
