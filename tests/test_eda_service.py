"""
Test EDA API endpoints (Layer 1).
"""
import pytest
import os
import pandas as pd
from pathlib import Path


# Create a sample CSV for testing
@pytest.fixture
def sample_csv(tmp_path):
    """Create a sample CSV file for testing."""
    data = {
        'date': pd.date_range('2023-01-01', periods=100),
        'close': [100 + i * 0.5 for i in range(100)],
        'volume': [1000000 + i * 10000 for i in range(100)],
        'high': [105 + i * 0.5 for i in range(100)],
        'low': [95 + i * 0.5 for i in range(100)]
    }
    df = pd.DataFrame(data)
    
    csv_path = tmp_path / "staging" / "test_debate" / "test.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False)
    
    return str(csv_path)


def test_eda_service_load_csv(sample_csv):
    """Test EDA service can load CSV file."""
    from api.eda_service import EDAService
    
    service = EDAService()
    df = service.load_csv(sample_csv)
    
    assert len(df) == 100
    assert 'close' in df.columns
    assert 'volume' in df.columns


def test_eda_service_load_csv_with_column_filter(sample_csv):
    """Test CSV loading with column filtering."""
    from api.eda_service import EDAService
    
    service = EDAService()
    df = service.load_csv(sample_csv, include_cols=['date', 'close'])
    
    assert len(df.columns) == 2
    assert 'close' in df.columns
    assert 'volume' not in df.columns


def test_eda_service_load_csv_with_sampling(sample_csv):
    """Test CSV loading with sampling."""
    from api.eda_service import EDAService
    
    service = EDAService()
    df = service.load_csv(sample_csv, sample=50)
    
    assert len(df) == 50


def test_eda_service_generate_plots(sample_csv, tmp_path):
    """Test plot generation."""
    from api.eda_service import EDAService
    
    service = EDAService()
    df = service.load_csv(sample_csv)
    
    output_dir = tmp_path / "plots"
    output_dir.mkdir(exist_ok=True)
    
    plot_paths = service.generate_basic_plots(df, output_dir)
    
    # Should generate 3 plots: histogram, correlation matrix, boxplot
    assert len(plot_paths) == 3
    
    # Verify files exist
    for path in plot_paths:
        assert os.path.exists(path)


def test_eda_service_extract_summary_stats(sample_csv, tmp_path):
    """Test summary statistics extraction."""
    from api.eda_service import EDAService
    
    service = EDAService()
    df = service.load_csv(sample_csv)
    
    output_path = tmp_path / "summary.csv"
    result_path = service.extract_summary_stats(df, str(output_path))
    
    assert os.path.exists(result_path)
    
    # Load and verify summary
    summary = pd.read_csv(result_path)
    assert 'missing_rate' in summary.columns


def test_eda_service_full_analysis(sample_csv, tmp_path):
    """Test full EDA analysis pipeline."""
    from api.eda_service import EDAService
    
    # Use tmp_path as base_data_dir
    service = EDAService(base_data_dir=str(tmp_path))
    
    result = service.analyze(
        csv_path=sample_csv,
        debate_id="test_debate_001",
        lang="zh"
    )
    
    # Verify response structure
    assert 'report_path' in result
    assert 'plot_paths' in result
    assert 'table_paths' in result
    assert 'meta' in result
    
    # Verify metadata
    meta = result['meta']
    assert meta['rows'] == 100
    assert meta['cols'] == 5
    assert meta['engine'] == 'ydata-profiling'
    
    # Verify files exist
    assert os.path.exists(result['report_path'])
    for plot_path in result['plot_paths']:
        assert os.path.exists(plot_path)
    for table_path in result['table_paths']:
        assert os.path.exists(table_path)


def test_eda_service_invalid_csv():
    """Test error handling for invalid CSV path."""
    from api.eda_service import EDAService
    
    service = EDAService()
    
    with pytest.raises(FileNotFoundError):
        service.load_csv("/nonexistent/path.csv")


def test_eda_service_invalid_columns(sample_csv):
    """Test error handling for invalid column names."""
    from api.eda_service import EDAService
    
    service = EDAService()
    
    with pytest.raises(ValueError, match="Invalid columns"):
        service.load_csv(sample_csv, include_cols=['nonexistent_column'])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
