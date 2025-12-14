# 多智能體海馬迴記憶系統：驗證與優化方案 (Memory V2)

本文件基於 2024-12-14 的架構反饋，詳述了海馬迴記憶系統的升級路徑。目標是解決「集體偏見」、「驗證成本」與「分數膨脹」三大問題。

## 核心設計

### 1. 記憶資料結構 (Schema V2)

```json
{
  "memory_id": "mem_uuid",
  "content": "...",
  "created_at": "iso_timestamp",
  
  "metadata": {
    "trust_level": "unverified | verified | highly_trusted | disputed",
    
    "verification_history": [
      {
        "timestamp": "iso",
        "agents": ["agent_a", "agent_b"],
        "result": "consensus | conflict",
        "summary": "..."
      }
    ],
    
    "scores": {
      "base": 50,
      "bonus_verification": 0,
      "bonus_adoption": 0,
      "penalty_decay": 0,
      "total": 50
    },
    
    "usage_stats": {
      "retrieved": 0,
      "adopted": 0,
      "success": 0,
      "misleading": 0
    }
  }
}
```

### 2. 挑戰者機制 (Challenger)

引入 `Challenger Agent` (紅隊)，專門針對高分記憶 (Score > 100) 進行周期性挑戰。

*   **觸發條件**: 分數 > 100 且 > 90天未挑戰。
*   **行為**: 要求提供原始證據、尋找反例。

### 3. 分數與衰減 (Scoring & Decay)

*   **動態評分**: 總分 = (採用率加權) + (驗證加分) - (時間衰減)。
*   **加速衰減**: 高分記憶若長期未被使用，衰減速度加倍。
*   **軟上限**: 超過 100 分後，加分邊際效益遞減。

---

## 實作階段 (Implementation Phases)

### Phase 1: 結構與基礎評分 (Current Focus)
- [ ] 更新 `worker/memory.py` Schema，支援 `metadata` 欄位。
- [ ] 實作 `_calculate_v2_score`，納入驗證狀態與基礎衰減。
- [ ] 建立 `prompts/agents/challenger.yaml`。

### Phase 2: 驗證流程 (Verification Loop)
- [ ] 在 `DebateCycle` 中實作「驗證觸發器」。
- [ ] 實作 `VerificationRound`：多 Agent 針對單一記憶進行快速辯論。

### Phase 3: 長期維護 (Maintenance)
- [ ] 實作「睡眠整合」任務 (Background Cron)。
- [ ] 實作挑戰者自動排程。