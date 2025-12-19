
import asyncio
import sys
import os
from datetime import datetime

# Set up path to import modules
sys.path.insert(0, '/app')

# 模擬環境變數 (如果不在 Docker 內但需要模擬)
if not os.environ.get("REDIS_HOST"):
    os.environ["REDIS_HOST"] = "redis"

async def test_chairman_eda_tsmc():
    """
    測試主席使用 EDA 工具分析台積電
    
    模擬場景：
    - 辯論主題：台積電投資價值分析
    - 主席需要生成總結
    - 調用 EDA 工具獲取實證數據
    """
    print("=" * 80)
    print("🔍 主席 EDA 工具驗證 - 台積電分析")
    print("=" * 80)
    print(f"測試時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 初始化 EDA Tool
    print("📊 步驟 1: 初始化環境與 EDA Tool Adapter")
    
    # 確保 ODS Internal Tool 也被註冊 (模擬 Docker 環境的完整載入)
    # 注意：這裡依賴 api.tool_registry，它需要 redis
    # 如果環境中沒有 redis 模組，會報錯。
    # 假設這是在 docker 容器內運行，應該要有 redis。
    try:
        from api.tool_registry import tool_registry
        from adapters.ods_internal_adapter import ODSInternalAdapter
        tool_registry.register(ODSInternalAdapter())
        print("✓ ODS Internal Adapter 註冊成功")
    except ImportError as e:
        print(f"⚠️ Import Error: {e}")
        print("如果是缺少 redis 模組，請確認容器內是否已安裝 (pip install redis)")
        return
    except Exception as e:
        print(f"⚠️ ODS Internal Adapter 註冊失敗: {e}")

    try:
        from adapters.eda_tool_adapter import EDAToolAdapter
        adapter = EDAToolAdapter()
        print(f"✓ EDA Tool 名稱: {adapter.name}")
        print(f"✓ 版本: {adapter.version}")
    except ImportError as e:
        print(f"❌ 無法導入 EDAToolAdapter: {e}")
        return
        
    print()
    
    if os.environ.get("DOCKER_ENV") or os.path.exists("/.dockerenv"):
         print("🐳 檢測到 Docker 環境")
    else:
         print("💻 檢測到本地環境")

    # 準備參數
    test_params = {
        "symbol": "2330.TW",           # 台積電
        "debate_id": "tsmc_test_001",  # 測試辯論 ID
        "lookback_days": 60,           # 回溯 60 天
        "include_financials": True     # 包含財務數據
    }
    
    print("📊 步驟 2: 準備分析參數")
    print(f"  - 股票代碼: {test_params['symbol']}")
    print(f"  - 辯論 ID: {test_params['debate_id']}")
    print(f"  - 回溯天數: {test_params['lookback_days']}")
    print(f"  - 包含財務數據: {test_params['include_financials']}")
    print()
    
    # 執行分析
    print("📊 步驟 3: 執行 EDA 分析（這可能需要 20-30 秒）")
    print("-" * 80)
    
    start_time = datetime.now()
    
    try:
        result = await adapter._invoke_async(**test_params)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        print("-" * 80)
        print(f"⏱️  執行時間: {elapsed:.2f} 秒")
        print()
        
        # 驗證結果
        print("📊 步驟 4: 驗證分析結果")
        print()
        
        if result.get("success"):
            print("✅ 分析成功！")
            print()
            
            # 檢查是否降級
            if result.get("degraded"):
                print("⚠️  降級模式（部分功能失敗）")
                print(f"問題: {result.get('issues', [])}")
                print()
            
            # 顯示摘要
            print("📄 生成的摘要:")
            print("=" * 80)
            print(result.get("summary", "無摘要"))
            print("=" * 80)
            print()
            
            # 檢查財務數據
            if result.get("financial_data"):
                fin_data = result["financial_data"]
                print("💰 財務數據狀態:")
                print(f"  - 拉取成功: {fin_data.get('success')}")
                
                if fin_data.get("fundamental"):
                    print(f"  - 基本面數據: ✓")
                    fund = fin_data["fundamental"]
                    if fund.get("eps"):
                        print(f"    • EPS: ${fund['eps']:.2f}")
                    if fund.get("roe"):
                        print(f"    • ROE: {fund['roe']:.2f}%")
                    if fund.get("pe_ratio"):
                        print(f"    • 本益比: {fund['pe_ratio']:.2f}x")
                
                if fin_data.get("ratios"):
                    print(f"  - 財務比率: ✓")
                    ratios = fin_data["ratios"]
                    if ratios.get("debt_ratio"):
                        print(f"    • 負債比率: {ratios['debt_ratio']:.2f}%")
                    if ratios.get("current_ratio"):
                        print(f"    • 流動比率: {ratios['current_ratio']:.2f}")
                print()
            
            # 檢查 Evidence
            if result.get("evidence_ids"):
                print(f"📚 Evidence 文件: {len(result['evidence_ids'])} 個")
                for i, eid in enumerate(result['evidence_ids'][:3], 1):
                    print(f"  [{i}] {eid}")
                print()
            
            # 檢查 Artifacts
            if result.get("artifacts"):
                artifacts = result["artifacts"]
                print("📁 生成的 Artifacts:")
                if artifacts.get("report"):
                    print(f"  - 報表: {artifacts['report']}")
                if artifacts.get("plots"):
                    print(f"  - 圖表: {len(artifacts['plots'])} 個")
                if artifacts.get("tables"):
                    print(f"  - 表格: {len(artifacts['tables'])} 個")
                print()
            
            # 最終驗證
            print("✅ 驗證結果:")
            checks = []
            
            # 必要檢查
            checks.append(("摘要生成", "summary" in result and result["summary"]))
            
            # 財務數據檢查
            if test_params["include_financials"]:
                has_fin = result.get("financial_data", {}).get("success", False)
                checks.append(("財務數據拉取", has_fin))
                
                if has_fin:
                    has_fundamental = bool(result["financial_data"].get("fundamental"))
                    has_ratios = bool(result["financial_data"].get("ratios"))
                    checks.append(("基本面數據", has_fundamental))
                    checks.append(("財務比率", has_ratios))
            
            # 顯示檢查結果
            all_passed = True
            for check_name, passed in checks:
                status = "✓" if passed else "✗"
                print(f"  {status} {check_name}")
                if not passed:
                    all_passed = False
            
            print()
            if all_passed:
                print("🎉 所有檢查通過！主席可以正常使用 EDA 工具。")
            else:
                print("⚠️  部分檢查未通過，請查看上方詳情。")
            
        else:
            print("❌ 分析失敗")
            print(f"錯誤: {result.get('error', '未知錯誤')}")
            print()
            print("可能原因:")
            print("  1. ChinaTimes API 不可用")
            print("  2. Yahoo Finance 連線問題")
            print("  3. 網路連線問題")
            print("  4. Docker 服務未啟動")
        
    except Exception as e:
        print(f"❌ 執行異常: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 80)
    print("測試完成")
    print("=" * 80)


def main():
    """主函數"""
    print()
    asyncio.run(test_chairman_eda_tsmc())
    print()


if __name__ == "__main__":
    main()
