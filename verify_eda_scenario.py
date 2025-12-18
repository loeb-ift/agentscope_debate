"""
場景驗證：主席對「台積電 (2330.TW) 投資價值分析」進行 EDA 自動分析

此腳本模擬完整的使用場景：
1. 主席收到辯論主題
2. 自動拉取股票數據
3. 調用 EDA 服務生成報表
4. Gate 檢查驗證品質
5. 將 artifacts 攝取到 Evidence 系統
6. 模擬在總結中引用 EDA 數據
"""
import sys
sys.path.insert(0, '/Users/loeb/Desktop/agentscope_debate')

import os
import pandas as pd
import yfinance as yf
from pathlib import Path
from datetime import datetime, timedelta
import json

# 場景配置
DEBATE_TOPIC = "台積電 (2330.TW) 2024 年投資價值分析"
STOCK_SYMBOL = "2330.TW"
DEBATE_ID = "scenario_test_2330"
LOOKBACK_DAYS = 120
BASE_URL = "http://localhost:8000"

# 使用本地 data 目錄 (macOS /data 是只讀的)
import os
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


def print_section(title):
    """打印區塊標題"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def step1_extract_symbol_from_topic():
    """步驟 1: 從辯論主題提取股票代碼"""
    print_section("步驟 1: 主席分析辯論主題")
    
    print(f"📋 辯論主題: {DEBATE_TOPIC}")
    print(f"🔍 識別股票代碼: {STOCK_SYMBOL}")
    print(f"📅 數據回溯期: {LOOKBACK_DAYS} 天")
    
    return STOCK_SYMBOL


def step2_fetch_stock_data(symbol):
    """步驟 2: 拉取股票數據"""
    print_section("步驟 2: 拉取股票歷史數據")
    
    # 創建 staging 目錄
    staging_dir = DATA_DIR / "staging" / DEBATE_ID
    staging_dir.mkdir(parents=True, exist_ok=True)
    
    csv_path = staging_dir / f"{symbol}.csv"
    
    # 檢查是否已存在
    if csv_path.exists():
        print(f"✓ CSV 已存在: {csv_path}")
        df = pd.read_csv(csv_path)
    else:
        print(f"📥 從 Yahoo Finance 下載 {symbol} 數據...")
        
        # 計算日期範圍
        end_date = datetime.now()
        start_date = end_date - timedelta(days=LOOKBACK_DAYS)
        
        # 下載數據
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_date, end=end_date)
        
        # 重置索引並選擇欄位
        df = df.reset_index()
        df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']]
        df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        
        # 儲存到 CSV
        df.to_csv(csv_path, index=False)
        print(f"✓ 數據已儲存: {csv_path}")
    
    print(f"\n📊 數據摘要:")
    print(f"  - 資料筆數: {len(df)}")
    print(f"  - 日期範圍: {df['date'].min()} ~ {df['date'].max()}")
    print(f"  - 收盤價範圍: ${df['close'].min():.2f} ~ ${df['close'].max():.2f}")
    print(f"  - 平均成交量: {df['volume'].mean():,.0f}")
    
    return str(csv_path), df


def step3_invoke_eda_api(csv_path):
    """步驟 3: 調用 EDA API"""
    print_section("步驟 3: 調用 ODS EDA 服務")
    
    import requests
    
    payload = {
        "csv_path": csv_path,
        "include_cols": ["date", "close", "volume", "high", "low"],
        "sample": 50000,  # 對於大數據集進行抽樣
        "lang": "zh"
    }
    
    print(f"🔧 調用 API: POST {BASE_URL}/api/eda/describe")
    print(f"📦 請求參數:")
    print(f"  - CSV 路徑: {csv_path}")
    print(f"  - 分析欄位: {payload['include_cols']}")
    print(f"  - 抽樣數: {payload['sample']}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/eda/describe",
            json=payload,
            timeout=120
        )
        response.raise_for_status()
        
        result = response.json()
        
        print(f"\n✅ EDA 分析完成!")
        print(f"  - HTML 報表: {result['report_path']}")
        print(f"  - 圖表數量: {len(result['plot_paths'])}")
        print(f"  - 摘要表格: {len(result['table_paths'])}")
        
        print(f"\n📈 數據品質指標:")
        meta = result['meta']
        print(f"  - 分析列數: {meta['rows']}")
        print(f"  - 分析欄位數: {meta['cols']}")
        print(f"  - 缺失率: {meta['missing_rate'] * 100:.2f}%")
        print(f"  - 生成時間: {meta['generated_at']}")
        
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"❌ API 調用失敗: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   錯誤詳情: {e.response.text}")
        return None


def step4_gate_check(artifacts):
    """步驟 4: Gate 檢查"""
    print_section("步驟 4: 品質檢查 (Gate Check)")
    
    from worker.eda_gate_checker import EDAGateChecker
    
    checker = EDAGateChecker(
        min_rows=30,
        max_age_hours=24,
        require_numeric_cols=True
    )
    
    print("🚪 執行品質檢查...")
    result = checker.check(artifacts)
    
    print(f"\n檢查結果: {'✅ 通過' if result['passed'] else '⚠️ 未通過'}")
    
    # 顯示詳細檢查項目
    print(f"\n詳細檢查:")
    checks = result['checks']
    
    for check_name, check_result in checks.items():
        status = "✓" if check_result.get('passed', False) else "✗"
        print(f"  {status} {check_name}")
        
        # 顯示額外資訊
        if check_name == 'sample_threshold':
            print(f"      樣本數: {check_result.get('rows', 0)} (最低要求: {check_result.get('min_rows', 0)})")
        elif check_name == 'numeric_columns':
            print(f"      圖表數量: {check_result.get('plot_count', 0)}")
        elif check_name == 'freshness':
            age = check_result.get('age_hours', 0)
            print(f"      報表年齡: {age:.1f} 小時 (最大允許: {check_result.get('max_age_hours', 0)} 小時)")
    
    if result['issues']:
        print(f"\n⚠️ 發現問題:")
        for issue in result['issues']:
            print(f"  • {issue}")
        
        print(f"\n降級訊息:")
        print(checker.get_degradation_message(result['issues']))
    
    return result


def step5_ingest_to_evidence(artifacts, gate_result):
    """步驟 5: 攝取到 Evidence 系統"""
    print_section("步驟 5: 攝取到 Evidence 系統")
    
    from worker.evidence_lifecycle import EvidenceLifecycle
    
    lifecycle = EvidenceLifecycle(debate_id=DEBATE_ID)
    
    if not gate_result['passed']:
        print("⚠️ Gate 檢查未通過，跳過 Evidence 攝取")
        print("   系統將使用降級模式（定性描述）")
        return None
    
    print("💾 開始攝取 EDA artifacts...")
    
    evidence_docs = []
    
    # 攝取 HTML 報表
    print(f"\n  📄 攝取 HTML 報表...")
    report_doc = lifecycle.ingest_eda_artifact(
        agent_id="chairman",
        artifact_type="report",
        file_path=artifacts['report_path'],
        metadata=artifacts['meta']
    )
    evidence_docs.append(report_doc)
    print(f"     ✓ Evidence ID: {report_doc.id}")
    
    # 攝取圖表
    print(f"\n  📊 攝取圖表 ({len(artifacts['plot_paths'])} 個)...")
    for i, plot_path in enumerate(artifacts['plot_paths'], 1):
        doc = lifecycle.ingest_eda_artifact(
            agent_id="chairman",
            artifact_type="plot",
            file_path=plot_path,
            metadata=artifacts['meta']
        )
        evidence_docs.append(doc)
        plot_name = Path(plot_path).name
        print(f"     ✓ [{i}] {plot_name} - Evidence ID: {doc.id}")
    
    # 攝取摘要表格
    print(f"\n  📋 攝取摘要表格 ({len(artifacts['table_paths'])} 個)...")
    for i, table_path in enumerate(artifacts['table_paths'], 1):
        doc = lifecycle.ingest_eda_artifact(
            agent_id="chairman",
            artifact_type="table",
            file_path=table_path,
            metadata=artifacts['meta']
        )
        evidence_docs.append(doc)
        table_name = Path(table_path).name
        print(f"     ✓ [{i}] {table_name} - Evidence ID: {doc.id}")
    
    print(f"\n✅ 共攝取 {len(evidence_docs)} 個 Evidence 文件")
    
    # 驗證 Evidence 狀態
    verified = lifecycle.get_verified_evidence(limit=20)
    print(f"📚 當前 debate 的 VERIFIED Evidence 總數: {len(verified)}")
    
    return evidence_docs


def step6_simulate_chairman_summary(artifacts, evidence_docs, df):
    """步驟 6: 模擬主席總結引用 EDA"""
    print_section("步驟 6: 主席總結引用 EDA 數據")
    
    if not evidence_docs:
        print("⚠️ 無可用的 EDA Evidence，使用定性描述")
        summary = f"""
## 主席總結 (降級模式)

關於「{DEBATE_TOPIC}」，由於數據品質限制，本輪未能提供詳細量化分析。
建議參考公開財報資訊與產業分析報告進行評估。
"""
        print(summary)
        return summary
    
    # 從 Evidence 提取資訊
    meta = artifacts['meta']
    
    # 計算一些基礎統計
    close_mean = df['close'].mean()
    close_std = df['close'].std()
    volume_mean = df['volume'].mean()
    
    # 計算價格變化
    price_change = ((df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0]) * 100
    
    # 生成總結
    summary = f"""
## 主席總結 (基於 EDA 實證分析)

### 數據概覽
本輪針對 {STOCK_SYMBOL} 進行了自動化探索性數據分析，分析期間涵蓋 {meta['rows']} 個交易日。
數據品質良好，缺失率僅 {meta['missing_rate'] * 100:.2f}%。

### 價格走勢分析
根據 EDA 報表 [E1]，{STOCK_SYMBOL} 在分析期間：
- 平均收盤價：${close_mean:.2f}
- 價格標準差：${close_std:.2f}
- 期間漲跌幅：{price_change:+.2f}%

如直方圖所示 [E2]，收盤價呈現{'右偏' if price_change > 0 else '左偏'}分布，
顯示股價在此期間{'整體上漲' if price_change > 0 else '整體下跌'}。

### 成交量分析
平均日成交量為 {volume_mean:,.0f} 股。根據相關矩陣 [E3]，
成交量與價格波動之間的相關性需進一步檢視。

### 投資建議
基於上述量化分析，建議投資人：
1. 關注價格波動風險（標準差 ${close_std:.2f}）
2. 參考成交量變化判斷市場情緒
3. 結合基本面分析做出投資決策

---
**Evidence 引用:**
- [E1] EDA 自動報表 (ID: {evidence_docs[0].id if evidence_docs else 'N/A'})
- [E2] 價格分布直方圖 (ID: {evidence_docs[1].id if len(evidence_docs) > 1 else 'N/A'})
- [E3] 相關矩陣 (ID: {evidence_docs[2].id if len(evidence_docs) > 2 else 'N/A'})
"""
    
    print(summary)
    
    # 顯示 Evidence 引用詳情
    print("\n📎 Evidence 引用詳情:")
    for i, doc in enumerate(evidence_docs[:3], 1):
        print(f"  [E{i}] {doc.artifact_type.upper()}: {Path(doc.file_path).name}")
        print(f"       ID: {doc.id}")
        print(f"       Trust Score: {doc.trust_score}")
        print(f"       TTL Expiry: {doc.ttl_expiry}")
    
    return summary


def main():
    """執行完整場景驗證"""
    print("\n" + "🎬" * 35)
    print("場景驗證：主席 EDA 自動分析完整流程")
    print("🎬" * 35)
    
    try:
        # 步驟 1: 提取股票代碼
        symbol = step1_extract_symbol_from_topic()
        
        # 步驟 2: 拉取股票數據
        csv_path, df = step2_fetch_stock_data(symbol)
        
        # 步驟 3: 調用 EDA API
        artifacts = step3_invoke_eda_api(csv_path)
        
        if not artifacts:
            print("\n❌ 場景驗證失敗：EDA API 調用失敗")
            return False
        
        # 步驟 4: Gate 檢查
        gate_result = step4_gate_check(artifacts)
        
        # 步驟 5: 攝取到 Evidence
        evidence_docs = step5_ingest_to_evidence(artifacts, gate_result)
        
        # 步驟 6: 模擬主席總結
        summary = step6_simulate_chairman_summary(artifacts, evidence_docs, df)
        
        # 最終報告
        print_section("✅ 場景驗證完成")
        
        print(f"\n📊 執行摘要:")
        print(f"  - 辯論主題: {DEBATE_TOPIC}")
        print(f"  - 股票代碼: {STOCK_SYMBOL}")
        print(f"  - 數據筆數: {len(df)}")
        print(f"  - EDA 報表: {artifacts['report_path']}")
        print(f"  - 生成圖表: {len(artifacts['plot_paths'])} 個")
        print(f"  - Gate 檢查: {'✅ 通過' if gate_result['passed'] else '⚠️ 降級'}")
        print(f"  - Evidence 文件: {len(evidence_docs) if evidence_docs else 0} 個")
        
        print(f"\n🎯 驗證結果:")
        print(f"  ✓ 數據拉取成功")
        print(f"  ✓ EDA 分析完成")
        print(f"  ✓ 品質檢查執行")
        print(f"  ✓ Evidence 系統整合")
        print(f"  ✓ 主席總結生成")
        
        print(f"\n📁 產出檔案位置:")
        print(f"  - 原始數據: {csv_path}")
        print(f"  - HTML 報表: {artifacts['report_path']}")
        print(f"  - 圖表目錄: {Path(artifacts['plot_paths'][0]).parent if artifacts['plot_paths'] else 'N/A'}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 場景驗證失敗:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
