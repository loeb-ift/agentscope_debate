import os
import pytest

from adapters.tej_adapter import TEJAdapter
from adapters.base import UpstreamError


class TestTEJAdapter:
    def setup_method(self):
        self.adapter = TEJAdapter(api_key="DUMMY_KEY")

    def test_schema_shape(self):
        schema = self.adapter.describe()
        assert schema["name"] == "tej.financials"
        assert schema["parameters"]["type"] == "object"
        assert "symbol" in schema["parameters"]["properties"]

    @pytest.mark.parametrize(
        "symbol, ok",
        [("2330.TW", True), ("2330", False), ("ABC.TW", False)],
    )
    def test_validate_symbol(self, symbol, ok):
        if ok:
            self.adapter.validate({"symbol": symbol})
        else:
            with pytest.raises(ValueError):
                self.adapter.validate({"symbol": symbol})

    def test_auth_missing_key(self):
        adapter = TEJAdapter(api_key=None)
        with pytest.raises(UpstreamError):
            adapter.auth({"headers": {}})

    def test_invoke_mock(self):
        out = self.adapter.invoke({"symbol": "2330.TW", "period": "annual", "limit": 5})
        assert out.data["symbol"] == "2330.TW"
        assert out.citations and out.citations[0]["source"] == "TEJ"
