"""
Integration test for EDA functionality (Layer 1-3).

This script tests the full EDA pipeline:
1. Create sample CSV data
2. Call EDA API endpoint
3. Validate artifacts generation
4. Run gate checker
5. Ingest artifacts into Evidence system
"""
import sys
sys.path.insert(0, '/Users/loeb/Desktop/agentscope_debate')

import os
import pandas as pd
from pathlib import Path
import requests
import json

# Test configuration
BASE_URL = "http://localhost:8000"
TEST_DEBATE_ID = "integration_test_001"
DATA_DIR = Path("/data")


def setup_test_data():
    """Create sample CSV data for testing."""
    print("📝 Setting up test data...")
    
    # Create staging directory
    staging_dir = DATA_DIR / "staging" / TEST_DEBATE_ID
    staging_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate sample stock data
    data = {
        'date': pd.date_range('2023-01-01', periods=120),
        'open': [100 + i * 0.3 for i in range(120)],
        'high': [105 + i * 0.3 for i in range(120)],
        'low': [95 + i * 0.3 for i in range(120)],
        'close': [100 + i * 0.5 for i in range(120)],
        'volume': [1000000 + i * 10000 for i in range(120)]
    }
    df = pd.DataFrame(data)
    
    csv_path = staging_dir / "2330.TW.csv"
    df.to_csv(csv_path, index=False)
    
    print(f"✓ Created test CSV: {csv_path}")
    print(f"  - Rows: {len(df)}")
    print(f"  - Columns: {list(df.columns)}")
    
    return str(csv_path)


def test_eda_api(csv_path):
    """Test EDA API endpoint."""
    print("\n🔬 Testing EDA API endpoint...")
    
    payload = {
        "csv_path": csv_path,
        "include_cols": ["date", "close", "volume"],
        "sample": 100,
        "lang": "zh"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/eda/describe",
            json=payload,
            timeout=120
        )
        response.raise_for_status()
        
        result = response.json()
        
        print("✓ EDA API call successful")
        print(f"  - Report: {result['report_path']}")
        print(f"  - Plots: {len(result['plot_paths'])} generated")
        print(f"  - Tables: {len(result['table_paths'])} generated")
        print(f"  - Metadata: {result['meta']}")
        
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"✗ EDA API call failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"  Response: {e.response.text}")
        return None


def test_gate_checker(artifacts):
    """Test gate checker on generated artifacts."""
    print("\n🚪 Testing Gate Checker...")
    
    from worker.eda_gate_checker import EDAGateChecker
    
    checker = EDAGateChecker(min_rows=30, max_age_hours=24)
    result = checker.check(artifacts)
    
    print(f"✓ Gate check completed")
    print(f"  - Passed: {result['passed']}")
    print(f"  - Degraded mode: {result['degraded_mode']}")
    
    if result['issues']:
        print(f"  - Issues found:")
        for issue in result['issues']:
            print(f"    • {issue}")
    else:
        print(f"  - No issues found")
    
    # Print detailed check results
    print(f"\n  Detailed checks:")
    for check_name, check_result in result['checks'].items():
        status = "✓" if check_result.get('passed', False) else "✗"
        print(f"    {status} {check_name}")
    
    return result


def test_evidence_ingestion(artifacts):
    """Test ingesting EDA artifacts into Evidence system."""
    print("\n💾 Testing Evidence Ingestion...")
    
    from worker.evidence_lifecycle import EvidenceLifecycle
    
    lifecycle = EvidenceLifecycle(debate_id=TEST_DEBATE_ID)
    
    # Ingest report
    report_doc = lifecycle.ingest_eda_artifact(
        agent_id="chairman_test",
        artifact_type="report",
        file_path=artifacts['report_path'],
        metadata=artifacts['meta']
    )
    print(f"✓ Ingested report artifact: {report_doc.id}")
    
    # Ingest plots
    plot_docs = []
    for plot_path in artifacts['plot_paths']:
        doc = lifecycle.ingest_eda_artifact(
            agent_id="chairman_test",
            artifact_type="plot",
            file_path=plot_path,
            metadata=artifacts['meta']
        )
        plot_docs.append(doc)
    print(f"✓ Ingested {len(plot_docs)} plot artifacts")
    
    # Ingest tables
    table_docs = []
    for table_path in artifacts['table_paths']:
        doc = lifecycle.ingest_eda_artifact(
            agent_id="chairman_test",
            artifact_type="table",
            file_path=table_path,
            metadata=artifacts['meta']
        )
        table_docs.append(doc)
    print(f"✓ Ingested {len(table_docs)} table artifacts")
    
    # Verify evidence
    verified = lifecycle.get_verified_evidence(limit=10)
    print(f"\n✓ Total verified evidence: {len(verified)}")
    
    return {
        "report": report_doc,
        "plots": plot_docs,
        "tables": table_docs
    }


def test_ods_adapter():
    """Test ODS adapter."""
    print("\n🔧 Testing ODS Adapter...")
    
    from adapters.ods_internal_adapter import ODSInternalAdapter
    
    adapter = ODSInternalAdapter(base_url=BASE_URL)
    
    # Test adapter properties
    print(f"✓ Adapter name: {adapter.name}")
    print(f"✓ Adapter version: {adapter.version}")
    print(f"✓ Cache TTL: {adapter.cache_ttl}s")
    
    return adapter


def cleanup():
    """Clean up test data."""
    print("\n🧹 Cleaning up...")
    
    import shutil
    
    # Remove test data directories
    for subdir in ["staging", "reports", "plots", "tables"]:
        test_dir = DATA_DIR / subdir / TEST_DEBATE_ID
        if test_dir.exists():
            shutil.rmtree(test_dir)
            print(f"✓ Removed {test_dir}")


def main():
    """Run integration tests."""
    print("=" * 60)
    print("EDA Integration Test (Layer 1-3)")
    print("=" * 60)
    
    try:
        # Step 1: Setup test data
        csv_path = setup_test_data()
        
        # Step 2: Test ODS Adapter
        adapter = test_ods_adapter()
        
        # Step 3: Test EDA API
        artifacts = test_eda_api(csv_path)
        
        if not artifacts:
            print("\n❌ Integration test FAILED: EDA API call failed")
            return False
        
        # Step 4: Test Gate Checker
        gate_result = test_gate_checker(artifacts)
        
        if not gate_result['passed']:
            print(f"\n⚠️  Gate check failed, but this is expected behavior")
            print(f"    System will use degraded mode")
        
        # Step 5: Test Evidence Ingestion
        evidence_docs = test_evidence_ingestion(artifacts)
        
        print("\n" + "=" * 60)
        print("✅ Integration test PASSED")
        print("=" * 60)
        print("\nSummary:")
        print(f"  - CSV data created: {csv_path}")
        print(f"  - EDA artifacts generated: {len(artifacts['plot_paths'])} plots")
        print(f"  - Gate check: {'PASSED' if gate_result['passed'] else 'DEGRADED'}")
        print(f"  - Evidence docs created: {len(evidence_docs['plots']) + len(evidence_docs['tables']) + 1}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Integration test FAILED with exception:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        cleanup()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
