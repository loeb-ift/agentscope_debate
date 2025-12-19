你ㄉㄜ"""
驗證主席 EDA 工具 - 通過 API 端點

正確的驗證方式：直接調用 API 服務，而非在本地運行
"""
import requests
import json
from datetime import datetime


def test_eda_tool_via_api():
    """
    通過 API 端點測試 EDA 工具
    """
    print("=" * 80)
    print("🔍 主席 EDA 工具驗證 - 通過 API 端點")
    print("=" * 80)
    print(f"測試時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    base_url = "http://localhost:8000"
    
    # 步驟 1: 檢查工具是否註冊
    print("📊 步驟 1: 檢查工具註冊狀態")
    try:
        response = requests.get(f"{base_url}/api/v1/tools")
        tools = response.json()
        
        # 查找 EDA 相關工具
        ods_tool = next((t for t in tools if t['name'] == 'ods.eda_describe:v1'), None)
        chairman_tool = next((t for t in tools if t['name'] == 'chairman.eda_analysis:v1'), None)
        
        if ods_tool:
            print(f"✅ ODS EDA 工具已註冊: {ods_tool['name']}")
        else:
            print(f"❌ ODS EDA 工具未找到")
            
        if chairman_tool:
            print(f"✅ Chairman EDA 工具已註冊: {chairman_tool['name']}")
            print(f"   描述: {chairman_tool.get('description', 'N/A')[:100]}...")
        else:
            print(f"❌ Chairman EDA 工具未找到")
            return False
            
        print()
        
    except Exception as e:
        print(f"❌ 無法連接到 API: {e}")
        return False
    
    # 步驟 2: 測試工具執行
    print("📊 步驟 2: 測試 Chairman EDA 工具執行")
    print("  參數:")
    print("    - symbol: 2330.TW")
    print("    - debate_id: api_test_001")
    print("    - lookback_days: 30")
    print("    - include_financials: True")
    print()
    
    try:
        payload = {
            "tool_name": "chairman.eda_analysis:v1",
            "parameters": {
                "symbol": "2330.TW",
                "debate_id": "api_test_001",
                "lookback_days": 30,
                "include_financials": True
            }
        }
        
        print("⏳ 執行中（這可能需要 20-30 秒）...")
        print("-" * 80)
        
        start_time = datetime.now()
        response = requests.post(
            f"{base_url}/api/v1/tools/execute",
            json=payload,
            timeout=120
        )
        elapsed = (datetime.now() - start_time).total_seconds()
        
        print("-" * 80)
        print(f"⏱️  執行時間: {elapsed:.2f} 秒")
        print()
        
        if response.status_code == 200:
            result = response.json()
            
            print("✅ 工具執行成功！")
            print()
            
            # 顯示結果
            if result.get("success"):
                print("📄 執行結果:")
                print(f"  - 成功: {result['success']}")
                print(f"  - 降級模式: {result.get('degraded', False)}")
                
                if result.get("summary"):
                    print()
                    print("📋 生成的摘要:")
                    print("=" * 80)
                    print(result["summary"])
                    print("=" * 80)
                    print()
                
                if result.get("financial_data"):
                    fin_data = result["financial_data"]
                    print("💰 財務數據:")
                    print(f"  - 拉取成功: {fin_data.get('success')}")
                    if fin_data.get("fundamental"):
                        print(f"  - 基本面數據: ✓")
                    if fin_data.get("ratios"):
                        print(f"  - 財務比率: ✓")
                    print()
                
                if result.get("evidence_ids"):
                    print(f"📚 Evidence 文件: {len(result['evidence_ids'])} 個")
                    print()
                
                # 驗證檢查
                print("✅ 驗證結果:")
                checks = [
                    ("工具執行成功", result.get("success")),
                    ("摘要生成", bool(result.get("summary"))),
                    ("執行時間 < 60秒", elapsed < 60),
                ]
                
                all_passed = True
                for check_name, passed in checks:
                    status = "✓" if passed else "✗"
                    print(f"  {status} {check_name}")
                    if not passed:
                        all_passed = False
                
                print()
                if all_passed:
                    print("🎉 所有檢查通過！主席可以正常使用 EDA 工具。")
                    return True
                else:
                    print("⚠️  部分檢查未通過")
                    return False
                    
            else:
                print(f"❌ 工具執行失敗: {result.get('error', '未知錯誤')}")
                return False
                
        else:
            print(f"❌ API 請求失敗: {response.status_code}")
            print(f"   錯誤: {response.text}")
            return False
            
    except requests.Timeout:
        print(f"❌ 請求超時（> 120 秒）")
        return False
    except Exception as e:
        print(f"❌ 執行異常: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        print()
        print("=" * 80)
        print("測試完成")
        print("=" * 80)


if __name__ == "__main__":
    print()
    success = test_eda_tool_via_api()
    print()
    exit(0 if success else 1)
