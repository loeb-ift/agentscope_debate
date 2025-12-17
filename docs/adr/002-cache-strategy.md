# ADR-002: 快取策略設計 (Cache Strategy for Agent + Financial APIs)

## Status
Accepted

## Date
2025-12-13

## Context（背景）

在多 Agent × 金融 API 架構中，快取不只是效能元件，而是正確性邊界的一部分。

既有問題包含：
*   語義相同查詢因參數順序不同導致 Cache Miss
*   空資料與警告結果被快取，污染後續分析
*   長時間區間查詢難以命中快取
*   並發寫入導致 Access Count 歸零，影響淘汰策略
*   高頻寫入造成 Qdrant I/O 壓力

錯誤的快取行為會使系統：**錯得更快、錯得更穩定**。

## Decision（架構決策）

本 ADR 以 **Correctness > Hit Rate > Performance** 為原則，重新定義快取策略。

### 1. Cache Key 正規化 (Parameter Normalization)
**決策：**
*   移除語義無關參數
*   統一參數排序
*   使用正規化後參數生成 Cache Key
*   Format: `<tool_name>:<semantic_version>:<normalized_params_hash>`

**理由：**
*   防止語義等價但 key 不同
*   提升快取命中率與可預測性

### 2. 語義版本號 (Semantic Versioning)
**決策：**
*   Cache Key 必須包含語義版本號（v1 / v2 …）

**理由：**
*   對齊策略、補值邏輯、視窗切分一旦變更
*   舊快取不得被新邏輯誤用

### 3. 日期軟對齊 (Soft Date Alignment)
**決策：**
*   長週期查詢 (>32天) 自動對齊至月首 / 月尾
*   不改變查詢語義，只改變快取邊界

**理由：**
*   大幅提升長期查詢命中率
*   不影響分析結果正確性

### 4. 毒藥防護 (Poison Cache Prevention)
**決策：**
禁止快取以下結果：
*   空資料（data = []）
*   含 warning 的成功回應
*   任何 Exception

**理由：**
*   防止錯誤結果被永久放大
*   確保快取內容一定「可用」

### 5. 原子 Access Count 與並發安全
**決策：**
*   Access Count 改為 Redis 原子操作 (`INCR`)
*   避免並發寫入導致計數歸零

**理由：**
*   正確的淘汰與熱度判斷依賴計數正確性

### 6. 語義快取解鎖 (Semantic Cache Unlock)
**決策：**
*   靜態資料（如公司基本資料）即使 Agent 同時持有動態工具（股價查詢），仍允許命中快取
*   僅當 Prompt 包含時間關鍵字（如「今天」、「最新」）且涉及 Volatile 工具時才跳過

**理由：**
*   靜態資料不應被動態能力綁架
*   顯著降低不必要 API 呼叫

### 7. 寫入緩衝 (Batching & Buffering)
**決策：**
*   對 Qdrant 實施批次寫入 (Buffer)
*   合併多筆小寫入為單一請求，於回合結束時 Flush

**理由：**
*   降低 I/O 負載
*   提升高併發穩定性

## Consequences（影響）

**正面：**
*   快取命中率顯著提升
*   污染資料被完全隔離
*   系統行為更可預測

**代價：**
*   Cache 邏輯複雜度上升
*   Key 管理需更嚴謹

## Future Work
*   Soft TTL（熱度越高，更新越頻繁）
*   Cache 使用情境可觀測性指標