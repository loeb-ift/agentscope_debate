"""
Test ODS Internal Adapter (Layer 2).
"""
import pytest
from unittest.mock import Mock, patch
import httpx


def test_ods_adapter_basic_properties():
    """Test adapter basic properties."""
    from adapters.ods_internal_adapter import ODSInternalAdapter
    
    adapter = ODSInternalAdapter()
    
    assert adapter.name == "ods.eda_describe"
    assert adapter.version == "v1"
    assert adapter.cache_ttl == 3600
    assert "csv_path" in adapter.schema["properties"]


def test_ods_adapter_describe():
    """Test adapter describe method."""
    from adapters.ods_internal_adapter import ODSInternalAdapter
    
    adapter = ODSInternalAdapter()
    desc = adapter.describe()
    
    assert desc["name"] == "ods.eda_describe"
    assert desc["version"] == "v1"
    assert "schema" in desc
    assert "description" in desc


def test_ods_adapter_cache_key():
    """Test cache key generation."""
    from adapters.ods_internal_adapter import ODSInternalAdapter
    
    adapter = ODSInternalAdapter()
    
    params1 = {"csv_path": "/data/test.csv", "sample": 1000}
    params2 = {"csv_path": "/data/test.csv", "sample": 1000}
    params3 = {"csv_path": "/data/other.csv", "sample": 1000}
    
    # Same params should generate same key
    assert adapter.cache_key(params1) == adapter.cache_key(params2)
    
    # Different params should generate different key
    assert adapter.cache_key(params1) != adapter.cache_key(params3)


@patch('httpx.Client')
def test_ods_adapter_invoke_success(mock_client_class):
    """Test successful API invocation."""
    from adapters.ods_internal_adapter import ODSInternalAdapter
    
    # Mock API response
    mock_response = Mock()
    mock_response.json.return_value = {
        "report_path": "/data/reports/test/eda_profile.html",
        "plot_paths": ["/data/plots/test/hist.png"],
        "table_paths": ["/data/tables/test/summary.csv"],
        "meta": {
            "rows": 100,
            "cols": 5,
            "missing_rate": 0.01,
            "generated_at": "2023-10-27T10:00:00Z",
            "engine": "ydata-profiling"
        }
    }
    mock_response.raise_for_status = Mock()
    
    mock_client = Mock()
    mock_client.post.return_value = mock_response
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client_class.return_value = mock_client
    
    # Test invocation
    adapter = ODSInternalAdapter()
    result = adapter.invoke(csv_path="/data/test.csv", lang="zh")
    
    assert result["success"] is True
    assert "data" in result
    assert result["data"]["report_path"] == "/data/reports/test/eda_profile.html"
    assert len(result["data"]["plot_paths"]) == 1


@patch('httpx.Client')
def test_ods_adapter_invoke_api_error(mock_client_class):
    """Test API error handling."""
    from adapters.ods_internal_adapter import ODSInternalAdapter
    
    # Mock API error
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404 Not Found",
        request=Mock(),
        response=Mock(status_code=404)
    )
    
    mock_client = Mock()
    mock_client.post.return_value = mock_response
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client_class.return_value = mock_client
    
    # Test invocation
    adapter = ODSInternalAdapter()
    result = adapter.invoke(csv_path="/data/test.csv")
    
    assert result["success"] is False
    assert "error" in result


def test_ods_adapter_invoke_missing_csv_path():
    """Test error handling for missing csv_path."""
    from adapters.ods_internal_adapter import ODSInternalAdapter
    
    adapter = ODSInternalAdapter()
    
    with pytest.raises(ValueError, match="csv_path is required"):
        adapter.invoke()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
