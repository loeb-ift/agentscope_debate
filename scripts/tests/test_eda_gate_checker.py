"""
Test EDA Gate Checker (Layer 3).
"""
import pytest
import os
from pathlib import Path
from datetime import datetime, timedelta


@pytest.fixture
def sample_artifacts(tmp_path):
    """Create sample EDA artifacts for testing."""
    # Create directories
    report_dir = tmp_path / "reports" / "test_debate"
    plot_dir = tmp_path / "plots" / "test_debate"
    table_dir = tmp_path / "tables" / "test_debate"
    
    report_dir.mkdir(parents=True)
    plot_dir.mkdir(parents=True)
    table_dir.mkdir(parents=True)
    
    # Create sample files
    report_path = report_dir / "eda_profile.html"
    report_path.write_text("<html>EDA Report</html>")
    
    plot1_path = plot_dir / "hist.png"
    plot1_path.write_bytes(b"fake png data")
    
    plot2_path = plot_dir / "corr.png"
    plot2_path.write_bytes(b"fake png data")
    
    table_path = table_dir / "summary.csv"
    table_path.write_text("col1,col2\n1,2\n")
    
    return {
        "report_path": str(report_path),
        "plot_paths": [str(plot1_path), str(plot2_path)],
        "table_paths": [str(table_path)],
        "meta": {
            "rows": 100,
            "cols": 5,
            "missing_rate": 0.01,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "engine": "ydata-profiling"
        }
    }


def test_gate_checker_all_pass(sample_artifacts):
    """Test gate checker when all checks pass."""
    from worker.eda_gate_checker import EDAGateChecker
    
    checker = EDAGateChecker(min_rows=30)
    result = checker.check(sample_artifacts)
    
    assert result["passed"] is True
    assert result["degraded_mode"] is False
    assert len(result["issues"]) == 0


def test_gate_checker_min_rows_fail(sample_artifacts):
    """Test gate checker fails when rows below threshold."""
    from worker.eda_gate_checker import EDAGateChecker
    
    # Set high threshold
    checker = EDAGateChecker(min_rows=200)
    result = checker.check(sample_artifacts)
    
    assert result["passed"] is False
    assert result["degraded_mode"] is True
    assert any("樣本數不足" in issue for issue in result["issues"])


def test_gate_checker_missing_files():
    """Test gate checker fails when files don't exist."""
    from worker.eda_gate_checker import EDAGateChecker
    
    artifacts = {
        "report_path": "/nonexistent/report.html",
        "plot_paths": ["/nonexistent/plot.png"],
        "table_paths": [],
        "meta": {
            "rows": 100,
            "cols": 5,
            "missing_rate": 0.01,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "engine": "ydata-profiling"
        }
    }
    
    checker = EDAGateChecker()
    result = checker.check(artifacts)
    
    assert result["passed"] is False
    assert result["degraded_mode"] is True
    assert len(result["issues"]) > 0


def test_gate_checker_no_numeric_columns():
    """Test gate checker fails when no numeric columns (no plots)."""
    from worker.eda_gate_checker import EDAGateChecker
    
    artifacts = {
        "report_path": "/tmp/report.html",
        "plot_paths": [],  # No plots generated
        "table_paths": [],
        "meta": {
            "rows": 100,
            "cols": 5,
            "missing_rate": 0.01,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "engine": "ydata-profiling"
        }
    }
    
    # Create dummy report file
    Path("/tmp/report.html").write_text("test")
    
    checker = EDAGateChecker(require_numeric_cols=True)
    result = checker.check(artifacts)
    
    assert result["passed"] is False
    assert any("數值欄位" in issue for issue in result["issues"])


def test_gate_checker_stale_artifacts():
    """Test gate checker fails when artifacts are too old."""
    from worker.eda_gate_checker import EDAGateChecker
    
    # Create artifacts with old timestamp
    old_time = datetime.utcnow() - timedelta(hours=48)
    
    artifacts = {
        "report_path": "/tmp/report.html",
        "plot_paths": ["/tmp/plot.png"],
        "table_paths": [],
        "meta": {
            "rows": 100,
            "cols": 5,
            "missing_rate": 0.01,
            "generated_at": old_time.isoformat() + "Z",
            "engine": "ydata-profiling"
        }
    }
    
    # Create dummy files
    Path("/tmp/report.html").write_text("test")
    Path("/tmp/plot.png").write_bytes(b"test")
    
    checker = EDAGateChecker(max_age_hours=24)
    result = checker.check(artifacts)
    
    assert result["passed"] is False
    assert any("過期" in issue for issue in result["issues"])


def test_gate_checker_degradation_message():
    """Test degradation message generation."""
    from worker.eda_gate_checker import EDAGateChecker
    
    checker = EDAGateChecker()
    issues = ["樣本數不足", "檔案不存在"]
    
    message = checker.get_degradation_message(issues)
    
    assert "樣本數不足" in message
    assert "檔案不存在" in message
    assert "定性描述" in message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
