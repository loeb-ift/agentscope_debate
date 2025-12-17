# 辯論中的記憶與快取實務（Debate Memory & Cache Playbook）

本文件深入描述在多代理辯論（Debate）過程中「短期/長期記憶」與「多層快取」的使用時機、決策邏輯與技術技巧，作為 MEMORY_AND_CACHE_DESIGN.md 的補充實務手冊。

—

## 1. 辯論階段與資料流總覽

```mermaid
flowchart LR
  A[Pre-Round 預備] --> B[In-Round 執行]
  B --> C[Verify 驗證]
  C --> D[Summarize/Decide 綜整/決策]
  D -->|必要| E[Re-plan/Next Round]

  subgraph Memory & Cache
    STM[短期記憶(回合暫存)]
    LTM[(長期記憶(Artifact Store + Vec))]
    LPC[進程級快取(Local)]
    RC[Redis 快取(共享)]
  end

  B --> STM
  B --> LTM
  B --> LPC
  B --> RC
  C --> LTM
  D --> LTM
```

—

## 2. 使用時機（When）

- 短期記憶（STM）
  - 回合上下文：當輪已收集之工具結果摘要、臨時主張（暫未驗證）、待辦查證清單
  - 快速迭代：需要高即時性的中間態、對 UI 實時回饋
  - 清理時機：回合結束；或在綜整後將必要內容下沉至 LTM

- 長期記憶（LTM）
  - 穩定知識：經驗證可重用的 Evidence/Claim/ModelResult/Summary
  - 跨回合/跨任務檢索：避免重複查詢，提升可靠性與可重現性
  - 新鮮度管理：以 TTL 驗證過期，必要時排程 revalidate

- 本地快取（LPC）
  - 單進程內重用：同一工具參數/小型計算結果/Prompt 模板/Schema
  - 時效極短：TTL 秒級或回合級

- Redis 快取（RC）
  - 跨進程共享：重覆性的外部查詢結果（搜尋/報價）
  - 合適 TTL：市場資料短、基本面長；關鍵結果可加 ETag/版本

—

## 3. 決策邏輯（How）

### 3.1 工具調用決策樹

```text
收到查詢需求 →
  1) 先查 STM（是否已有當回合新鮮結果？）→ 命中：使用
  2) 再查 LPC（進程內）→ 命中：使用
  3) 再查 RC（共享快取）→ 命中且 TTL 足夠：使用
  4) 查 LTM（Artifact 檢索 + TTL 過濾）→ 命中且新鮮：使用
  5) 最後才調用工具（外部 IO）→ 成功後：
       - 寫入 STM（回合摘要）
       - 視重要性/穩定性：
         a. 直接入庫 LTM（EvidenceDoc/ModelResult）
         b. 先放 STM、待驗證通過後下沉 LTM
       - 更新 LPC/RC（按工具策略與 TTL）
```

### 3.2 記憶更新策略
- 暫存到 STM 的條件
  - 中間結果需即時回饋，但尚未過驗證（e.g., 初步主張/搜索片段）
- 下沉到 LTM 的條件
  - 通過 Verifier 的引用覆蓋/新鮮度/一致性檢查
  - 綜整/決策引用的關鍵證據/主張
  - 重要模型結果（含參數/評估指標），便於重現

—

## 4. 技術技巧（Tips & Patterns）

### 4.1 鍵設計與雜湊（Keys & Hashing）
- 工具快取 Key：`tool:{name}:sha256(canonical_args)`
  - canonical_args：需排序/正規化（移除不影響語義的雜訊欄位）
- STM Key：`stm:{debate_id}:{round}:{key}`
- LTM Artifact ID：`{type}:{uuid}`，並保留 inputs_hash/outputs_hash

### 4.2 TTL 與 Freshness 建議
- 市場報價/成交量：TTL 30–300 秒（依需求）
- 新聞快照：TTL 1–7 天（提供來源與時間戳）
- 基本面/財務報表：TTL 30–180 天（依來源更新週期）
- Claim 跟隨最短證據 TTL；任一 evidence 過期即標注需再驗證

### 4.3 冪等與去重
- 記憶寫入：以（type + inputs_hash）做冪等，避免重複 Artifact
- SSE 日誌：去重與節流（已於 `_publish_log` 實作），UI 以摘要顯示

### 4.4 後驗 Sanity Check
- 數值範圍：價格/量需可解析且在合理範圍
- 時間檢查：日期可解析且在期望窗格
- 內容檢查：避免抓到錯誤頁/登入頁/反爬提示
- Schema 驗證：工具 I/O JSON Schema 必檢

### 4.5 Second Sourcing（次級驗證）
- 對關鍵 Claim：至少兩個獨立來源 Evidence
- 差異對齊：來源間矛盾需標注並記錄於 Counterclaim 或 caveats

### 4.6 反循環斷路器
- 偵測條件：同一代理/工具在短時間連續失敗或重置
- 行為：阻斷後續重試，向 Planner/Coordinator 報告並改變策略（改用替代工具或降低頻率）

—

## 5. 在辯論回合中的具體操作建議

### 5.1 Pre-Round 預備
- 清理上輪 STM；保留必要上下文（如本輪目標/限制）
- 熱身快取：預載常用 Schema/Prompt；完成進程內的冷啟動
- 根據 Topic 先檢索 LTM（歷史相關 Evidence/Claim），帶入回合上下文

### 5.2 In-Round 執行
- 每次查詢：依「工具調用決策樹」先查 STM/LPC/RC/LTM，再決定是否外呼
- 外呼成功：即時寫 STM，若屬高價值資訊，進行驗證以決定是否入 LTM
- 代理產出：盡量產出型別化 Artifact（Evidence/Claim/ModelResult）

### 5.3 Verify 驗證
- 引用覆蓋率（≥ 2 來源）與新鮮度檢查
- 矛盾偵測：同主題 Claims 比對，必要時產 Counterclaim
- 未通過：標注並退回補充；過多失敗觸發斷路器與計畫調整

### 5.4 Summarize/Decide 綜整/決策
- 只引用通過驗證的 Artifact；保留 caveats
- 將 Summary/Decision 下沉 LTM（含 provenance 與引用 IDs）
- 將關鍵 Evidence/Claim/ModelResult 一併下沉，便於重放

—

## 6. 程式碼片段（Pseudo/Python）

### 6.1 查詢與快取決策
```python
def fetch_with_caching(q: dict, ctx: RoundContext, cache, ltm, tool):
    key = f"tool:{tool.name}:{sha256(canonicalize(q))}"

    # 1) STM
    if (hit := ctx.stm.get(key)):
        return hit, "STM"

    # 2) LPC
    if (hit := cache.local.get(key)):
        ctx.stm.set(key, hit, ttl_s=60)
        return hit, "LPC"

    # 3) RC
    if (hit := cache.redis.get(key)) and hit.ttl_ok():
        ctx.stm.set(key, hit.value, ttl_s=60)
        return hit.value, "RC"

    # 4) LTM（向量 + TTL 過濾）
    hits = ltm.search(query=q.get("query"), filters={"ttl_ok": True}, top_k=3)
    if hits:
        ctx.stm.set(key, hits[0], ttl_s=60)
        return hits[0], "LTM"

    # 5) 工具外呼
    res = tool.invoke(q)
    validate_schema(tool.output_schema, res)
    sanity_check(res)

    ctx.stm.set(key, res, ttl_s=60)
    cache.local.set(key, res, ttl_s=120)
    cache.redis.set(key, res, ttl_s=tool.ttl)

    # 視重要性決定是否入 LTM（EvidenceDoc/ModelResult）
    if is_high_value(res):
        art_id = ltm.upsert_artifact(make_evidence(res))
        return {**res, "artifact_id": art_id}, "TOOL+LTM"

    return res, "TOOL"
```

### 6.2 記憶寫入與驗證
```python
def write_claim_with_verify(claim: dict, verifier, ltm):
    # 先入 STM（由上層處理）…

    # 驗證：引用、新鮮度、矛盾
    report = verifier.run(claim)
    if not report.ok:
        return {"status": "need_revision", "issues": report.issues}

    # 通過才寫 LTM
    claim_id = ltm.upsert_artifact(claim)
    return {"status": "ok", "artifact_id": claim_id}
```

—

## 7. 反模式與常見問題（Anti-patterns）
- 過度依賴 STM：回合結束未下沉 LTM，導致知識無法重用
- 無 TTL/新鮮度：沿用舊資料造成誤判
- 無 Schema 驗證/後驗檢查：髒資料流入記憶與快取
- 無斷路器：重複工具重置/失敗造成風暴
- 過多細粒度快取鍵：命中率低且管理成本高

—

## 8. 指標與監控（Metrics）
- 快取命中率（STM/LPC/RC/LTM）
- 工具外呼比例（外呼/總查詢）與失敗率、重試次數
- 記憶下沉率（STM→LTM）與驗證通過率
- TTL 重建次數、再驗證排程量
- 平均延遲、P95/P99

—

## 9. 落地清單（Debate 專項）
- [ ] 在辯論管線中加入 fetch_with_caching 決策流程
- [ ] 為主要工具定義 TTL 與快取鍵規則
- [ ] 在代理角色中強制輸出 Artifact（Evidence/Claim/ModelResult）
- [ ] 導入 Verifier Gate，未通過不得綜整
- [ ] 導入斷路器：針對 meta-tool reset/連續失敗
- [ ] 加入指標匯集：命中率/外呼比/TTL 重建/驗證通過率
