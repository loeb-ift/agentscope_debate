"""
EDA 財務數據整合測試

測試範圍:
- 財務數據拉取 (ChinaTimes API)
- 數據標準化
- 錯誤處理與降級
"""
import pytest
import asyncio
from adapters.eda_tool_adapter import EDAToolAdapter


class TestFinancialDataBasic:
    """測試基本面財務數據拉取"""
    
    @pytest.fixture
    def adapter(self):
        """創建 EDA Tool Adapter 實例"""
        return EDAToolAdapter()
    
    @pytest.mark.asyncio
    async def test_prepare_financial_data_basic(self, adapter):
        """測試財務數據拉取方法"""
        # 使用台積電作為測試標的
        result = await adapter._prepare_financial_data_basic("2330.TW", "test_debate")
        
        # 驗證返回結構
        assert "fundamental" in result
        assert "ratios" in result
        assert "success" in result
        
        # 如果成功，應該至少有一個數據源
        if result["success"]:
            assert result["fundamental"] or result["ratios"]
            print(f"✓ Financial data fetched successfully")
            print(f"  - Fundamental: {bool(result['fundamental'])}")
            print(f"  - Ratios: {bool(result['ratios'])}")
        else:
            print(f"⚠️ Financial data fetch failed (may be API issue)")
    
    def test_normalize_chinatimes_fundamental(self, adapter):
        """測試基本面數據標準化"""
        # 模擬 ChinaTimes API 返回
        raw_data = {
            "Code": "2330",
            "Name": "台積電",
            "SectorName": "半導體業",
            "EPS": "8.5",
            "ROE": "25.6",
            "PERatio": "22.5",
            "DividendYield": "2.8"
        }
        
        normalized = adapter._normalize_chinatimes_fundamental(raw_data)
        
        # 驗證標準化結果
        assert normalized["code"] == "2330"
        assert normalized["name"] == "台積電"
        assert normalized["sector"] == "半導體業"
        assert normalized["eps"] == 8.5  # 應轉為 float
        assert normalized["roe"] == 25.6
        assert normalized["pe_ratio"] == 22.5
        assert normalized["dividend_yield"] == 2.8
        
        print(f"✓ Fundamental data normalized correctly")
    
    def test_normalize_chinatimes_ratios(self, adapter):
        """測試財務比率標準化"""
        # 模擬 ChinaTimes API 返回
        raw_data = {
            "pe_ratio": 22.5,
            "pb_ratio": 5.2,
            "roe": 25.6,
            "debt_ratio": 35.2,
            "current_ratio": 1.8,
            "gross_margin": 52.3
        }
        
        normalized = adapter._normalize_chinatimes_ratios(raw_data)
        
        # 驗證標準化結果
        assert normalized["pe_ratio"] == 22.5
        assert normalized["pb_ratio"] == 5.2
        assert normalized["roe"] == 25.6
        assert normalized["debt_ratio"] == 35.2
        assert normalized["current_ratio"] == 1.8
        assert normalized["gross_margin"] == 52.3
        
        print(f"✓ Financial ratios normalized correctly")
    
    def test_normalize_empty_data(self, adapter):
        """測試空數據處理"""
        # 測試 None
        assert adapter._normalize_chinatimes_fundamental(None) == {}
        assert adapter._normalize_chinatimes_ratios(None) == {}
        
        # 測試空字典
        assert adapter._normalize_chinatimes_fundamental({}) == {}
        assert adapter._normalize_chinatimes_ratios({}) == {}
        
        print(f"✓ Empty data handled correctly")
    
    def test_normalize_invalid_values(self, adapter):
        """測試無效值處理"""
        raw_data = {
            "EPS": "invalid",  # 無法轉為 float
            "ROE": None,
            "PERatio": "22.5"  # 有效值
        }
        
        normalized = adapter._normalize_chinatimes_fundamental(raw_data)
        
        # 無效值應轉為 None
        assert normalized.get("eps") is None
        assert normalized.get("roe") is None
        assert normalized["pe_ratio"] == 22.5  # 有效值應正常轉換
        
        print(f"✓ Invalid values handled correctly")


class TestEDAIntegration:
    """測試完整 EDA + 財務數據整合"""
    
    @pytest.fixture
    def adapter(self):
        """創建 EDA Tool Adapter 實例"""
        return EDAToolAdapter()
    
    def test_schema_includes_financials(self, adapter):
        """測試 schema 包含 include_financials 參數"""
        schema = adapter.schema
        
        assert "include_financials" in schema["properties"]
        assert schema["properties"]["include_financials"]["type"] == "boolean"
        assert schema["properties"]["include_financials"]["default"] == True
        
        print(f"✓ Schema includes include_financials parameter")
    
    def test_format_summary_with_financials(self, adapter):
        """測試摘要格式包含財務數據"""
        # 模擬 artifacts
        artifacts = {
            "report_path": "/path/to/report.html",
            "plot_paths": ["/path/to/plot1.png"],
            "table_paths": ["/path/to/table.csv"],
            "metadata": {
                "rows": 100,
                "missing_rate": 0.0,
                "generated_at": "2024-12-18T06:00:00Z"
            }
        }
        
        # 模擬 evidence_docs
        class MockEvidenceDoc:
            def __init__(self, id, artifact_type):
                self.id = id
                self.artifact_type = artifact_type
        
        evidence_docs = [
            MockEvidenceDoc("e1", "report"),
            MockEvidenceDoc("e2", "plot")
        ]
        
        # 模擬財務數據
        financial_data = {
            "success": True,
            "fundamental": {
                "eps": 8.5,
                "roe": 25.6,
                "pe_ratio": 22.5,
                "dividend_yield": 2.8
            },
            "ratios": {
                "debt_ratio": 35.2,
                "current_ratio": 1.8,
                "gross_margin": 52.3
            }
        }
        
        # 生成摘要
        summary = adapter._format_summary(artifacts, evidence_docs, "2330.TW", financial_data)
        
        # 驗證摘要包含財務數據
        assert "基本面分析" in summary
        assert "EPS" in summary
        assert "8.5" in summary
        assert "ROE" in summary
        assert "25.6" in summary
        assert "財務健康度" in summary
        assert "負債比率" in summary
        assert "健康" in summary  # 35.2% < 50%
        
        print(f"✓ Summary includes financial analysis")
        print(f"\nGenerated Summary:\n{summary}")
    
    def test_format_summary_without_financials(self, adapter):
        """測試摘要格式在無財務數據時正常運作"""
        artifacts = {
            "report_path": "/path/to/report.html",
            "plot_paths": [],
            "table_paths": [],
            "metadata": {
                "rows": 100,
                "missing_rate": 0.0,
                "generated_at": "2024-12-18T06:00:00Z"
            }
        }
        
        class MockEvidenceDoc:
            def __init__(self, id, artifact_type):
                self.id = id
                self.artifact_type = artifact_type
        
        evidence_docs = [MockEvidenceDoc("e1", "report")]
        
        # 無財務數據
        summary = adapter._format_summary(artifacts, evidence_docs, "2330.TW", None)
        
        # 驗證摘要不包含財務分析
        assert "基本面分析" not in summary
        assert "EPS" not in summary
        
        # 但應包含基本資訊
        assert "2330.TW" in summary
        assert "價格分析" in summary
        
        print(f"✓ Summary works without financial data")


if __name__ == "__main__":
    # 運行測試
    pytest.main([__file__, "-v", "-s"])
