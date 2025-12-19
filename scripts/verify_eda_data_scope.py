
import sys
import os
import pandas as pd
import asyncio
from datetime import datetime, timedelta
import importlib.util

# 添加專案根目錄到 path
sys.path.insert(0, os.getcwd())

def print_header(title):
    print(f"\n{'='*60}")
    print(f"🔍 驗證項目: {title}")
    print(f"{'='*60}")

def check_library(lib_name):
    """檢查庫是否已安裝"""
    spec = importlib.util.find_spec(lib_name)
    if spec is not None:
        print(f"✅ 庫 '{lib_name}' 已安裝")
        return True
    else:
        print(f"❌ 庫 '{lib_name}' 未安裝 (這是擴展技術指標所必需的)")
        return False

async def verify_current_ohlcv_scope():
    """驗證當前 OHLCV 數據範圍與結構"""
    print_header("1. 當前 OHLCV 數據範圍驗證")
    
    try:
        import yfinance as yf
        symbol = "2330.TW"
        print(f"📥 嘗試從 Yahoo Finance 拉取 {symbol} 數據...")
        
        # 拉取最近 5 天
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="5d")
        
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if not missing_cols:
            print(f"✅ OHLCV 數據欄位完整: {required_cols}")
            print(f"📊 數據範例:\n{df.head(2)[required_cols]}")
        else:
            print(f"❌ 缺少必要欄位: {missing_cols}")
            
    except Exception as e:
        print(f"❌ 數據拉取失敗: {e}")

async def verify_financial_data_adapters():
    """驗證財務數據 Adapter 是否可用"""
    print_header("2. 財務數據 Adapter 可用性驗證")
    
    adapters_to_check = [
        ("adapters.chinatimes_suite", "ChinaTimesFinancialRatiosAdapter", "財務比率"),
        ("adapters.chinatimes_suite", "ChinaTimesStockFundamentalAdapter", "基本面數據"), # 假設名稱，需確認
        ("adapters.chinatimes_suite", "ChinaTimesBalanceSheetAdapter", "資產負債表"),
        ("adapters.chinatimes_suite", "ChinaTimesIncomeStatementAdapter", "損益表"),
        ("adapters.chinatimes_suite", "ChinaTimesCashFlowAdapter", "現金流量表"),
    ]
    
    for module_name, class_name, desc in adapters_to_check:
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, class_name):
                adapter_cls = getattr(module, class_name)
                adapter = adapter_cls()
                print(f"✅ {desc} Adapter 存在: {class_name} (Tool: {adapter.name})")
            else:
                print(f"⚠️ {desc} Adapter '{class_name}' 未在 {module_name} 中找到")
        except ImportError:
            print(f"⚠️ 無法導入模組: {module_name}")
        except Exception as e:
            print(f"❌ 檢查 {class_name} 時發生錯誤: {e}")

async def verify_technical_indicator_capability():
    """驗證技術指標計算能力 (pandas-ta / ta-lib)"""
    print_header("3. 技術指標計算能力驗證")
    
    has_pandas_ta = check_library("pandas_ta")
    
    if has_pandas_ta:
        try:
            import pandas_ta as ta
            import yfinance as yf
            
            # 準備測試數據
            df = yf.Ticker("2330.TW").history(period="1mo")
            
            # 測試計算 MA
            df.ta.sma(length=5, append=True)
            if 'SMA_5' in df.columns:
                print("✅ 成功計算 SMA (移動平均線)")
            
            # 測試計算 RSI
            df.ta.rsi(length=14, append=True)
            if 'RSI_14' in df.columns:
                print("✅ 成功計算 RSI (相對強弱指標)")
                
            print(f"📊 計算後欄位: {df.columns.tolist()}")
            
        except Exception as e:
            print(f"❌ 技術指標計算測試失敗: {e}")
    else:
        print("💡 建議安裝 'pandas_ta' 以支援文檔中的技術指標擴展")

async def verify_data_merge_logic():
    """模擬數據合併邏輯 (股價 + 財務)"""
    print_header("4. 數據整合邏輯模擬")
    
    print("🔄 模擬合併 OHLCV 與財務數據...")
    
    # 模擬股價數據 (日頻)
    dates = pd.date_range(start="2024-01-01", periods=10, freq="D")
    price_df = pd.DataFrame({
        "date": dates,
        "close": [100 + i for i in range(10)]
    })
    
    # 模擬財務數據 (季頻/不定期) - 假設財報發布日
    fin_data = [
        {"date": pd.Timestamp("2024-01-02"), "eps": 2.5, "roe": 15.0},
        {"date": pd.Timestamp("2024-01-08"), "eps": 2.6, "roe": 15.2} # 假設新的數據點
    ]
    fin_df = pd.DataFrame(fin_data)
    
    print("   Price DF (前 3 筆):")
    print(price_df.head(3))
    print("\n   Financial DF:")
    print(fin_df)
    
    # 測試 Merge (Left Join on Date) - 這是文檔建議的方式
    # 注意：財報通常是發布日之後才有效，簡單 merge 可能會導致很多 NaN
    # 文檔建議: df_combined = pd.merge(df_price, df_financial, on='date', how='left')
    
    merged_df = pd.merge(price_df, fin_df, on='date', how='left')
    
    # Forward Fill (填補財報發布日之間的空值)
    merged_df_ffill = merged_df.ffill()
    
    print("\n   Merged DF (With Forward Fill):")
    print(merged_df_ffill)
    
    if 'eps' in merged_df_ffill.columns and not merged_df_ffill['eps'].isnull().all():
        print("\n✅ 數據合併與填充邏輯驗證成功")
    else:
        print("\n❌ 數據合併失敗或全為空值")

async def main():
    print("🚀 開始 EDA 數據範圍驗證...\n")
    
    await verify_current_ohlcv_scope()
    await verify_financial_data_adapters()
    await verify_technical_indicator_capability()
    await verify_data_merge_logic()
    
    print("\n🏁 驗證完成")

if __name__ == "__main__":
    asyncio.run(main())
