# 海馬迴（Hippocampal）記憶與快取實務指南

本指南聚焦於辯論（Debate）系統中的「海馬迴記憶（短/長期）」與「多層快取」之持久性、顆粒性與隔離策略，並提供避免快取污染、確保可用性與一致性的實務技巧。

—

## 1. 定義與目標
- 海馬迴記憶（Hippocampal Memory）
  - 短期（STM）：回合/計畫上下文的即時記憶區，存放臨時工具結果、候選主張、待驗證清單。
  - 長期（LTM）：跨回合/跨任務可重用的穩定知識，存放已驗證的 Evidence/Claim/ModelResult/Summary 等 Artifact。
- 多層快取（Cache）
  - L1：進程級快取（Local/In-process）
  - L2：共享快取（Redis/分散式）
  - L3：Artifact 檢索層（向量庫 + DB metadata）
- 目標
  - 提升反應速度、可靠性與可重現性
  - 降低外部 IO 與重複計算
  - 保障數據品質，避免污染與交叉干擾

—

## 2. 持久性（Persistence）

### 2.1 短期記憶（STM）
- 儲存位置：
  - 主要：進程內（in-memory 結構）
  - 選用：Redis（鍵含 debate_id、round_no）
- 保留週期：
  - 回合存活（Round-scoped）；回合結束時清理或下沉 LTM
- 建議策略：
  - Write-through to STM：外部工具成功後先寫 STM（摘要/取樣），供 UI 即時回饋
  - Verified write-down：通過驗證（Verifier Gate）才下沉為 LTM Artifact

### 2.2 長期記憶（LTM）
- 儲存位置：
  - Artifact metadata：SQLite/SQLAlchemy（或 Postgres）
  - 內容嵌入：Qdrant（或 Milvus Lite）
- 保留週期：
  - 永續 + TTL/新鮮度（Freshness）策略：不同型別各自 TTL
- 建議策略：
  - 只納入經過 Schema 驗證與後驗 Sanity Check 的資料
  - 以 provenance（agent/tool/inputs_hash/outputs_hash/run_id/ts）完整溯源

—

## 3. 顆粒性（Granularity）

### 3.1 Artifact 級（推薦）
- EvidenceDoc、Claim、Counterclaim、ModelResult、Summary 等為基本單位，顆粒適中、易於溯源與檢索。
- 以引用關係構成 Artifact Graph，支援重現與可視化。

### 3.2 欄位級（選用）
- 對高價值欄位（如價格、時間戳、來源 URL）建立二級索引/快取，以強化查詢效率與一致性檢查。

### 3.3 回合/計畫節點級
- 以 plan_node_id/round_no 為範圍的 STM 分組，便於清理與隔離。

—

## 4. 使用時機與邏輯（辯論實務）

### 4.1 查詢決策順序
1) 先 STM（是否已有同議題最近結果？）
2) 再 L1（進程級快取）
3) 再 L2（Redis 快取）
4) 再 LTM（向量檢索 + TTL 過濾）
5) 最後才外部工具呼叫（成功後寫 STM/快取，並視規則入 LTM）

### 4.2 下沉（Sink-down）規則
- 進入 LTM 的必要條件：
  - 通過 Verifier Gate：引用覆蓋（≥2 獨立來源）、新鮮度、矛盾檢查
  - 通過 Schema 驗證與 Sanity Check（數值/日期/錯頁）
  - 關鍵產出（被 Summary/Decision 引用）

### 4.3 重新驗證（Revalidate）
- TTL 到期：對 Evidence/Claim 啟動再驗證任務，過期前可預熱
- 再驗證失敗：標記失效，衍生的 Claim/Decision 標注 caveats 或降級信心

—

## 5. 避免快取污染（Cache Pollution）
- 嚴格入口：外部工具結果必須通過 I/O Schema 驗證 + Sanity Check 才快取
- 階段化寫入：未驗證結果只允許進 STM，不可直接進 L2/LTM
- 版本化/ETag：對資料源標記版本，一致性檢查不符則拒收
- 異常隔離：對於可疑來源（高 4XX/5XX 比例、反爬頁面、重定向），設黑名單/降權
- 毒化防禦：
  - 來源多樣性：重要 Claim 需多源支撐
  - 二次查證（Second Sourcing）
  - 反常偵測：和歷史統計/相鄰資料對比

—

## 6. 隔離性（Isolation）
- 命名空間（Namespace）：
  - STM：`stm:{debate_id}:{round}:{key}`
  - L1：`l1:{proc_id}:{hash}`
  - L2：`l2:{tool}:{sha256(canonical_args)}`
  - LTM：`{type}:{uuid}` + 索引 `run_id/agent/plan_node`
- 權限與可見性：
  - 不同 debate_id/tenant 之間默認不可互見
  - 共享快取（L2）對敏感結果加密或遮罩敏感欄位
- 觀察隔離：Trace 中帶 `run_id/trace_id/plan_node_id`，便於串聯

—

## 7. 可用性（Availability）
- 快取降級策略：
  - L1/L2 命中失敗 → 查 STM/LTM
  - LTM 不可用 → 暫時僅以 STM 服務並警示
- 冗餘與備援：
  - L2 使用 Redis Cluster 或具備持久化（AOF/RDB）
  - LTM 使用資料庫備援/快照 + 向量庫副本
- 預熱（Warm-up）：
  - Pre-Round 根據 Topic/歷史主題預先檢索 LTM，提升首輪命中
- 回退（Fallback）：
  - 外部工具不可用時觸發替代工具/資料源

—

## 8. 長/短期記憶詳細策略

### 8.1 STM 策略
- TTL：回合級；可設定 5–30 分鐘保留視情境
- 容量限制：LRU/LFU；超量時優先淘汰低價值鍵
- 入庫規則：
  - 工具成功 → 入 STM；
  - 重要資料 → 標記待驗證；通過後下沉 LTM
- 清理：回合結束後批次掃描與釋放；必要內容同步至 LTM

### 8.2 LTM 策略
- TTL/Freshness：
  - 市場價量：30–300 秒（或以交易日作為邊界）
  - 新聞/媒體：1–7 天（保留來源與抓取時間）
  - 基本面/年報：30–180 天（依來源發佈週期）
- 再驗證：到期自動排程；失敗則降級信心並標註
- 變更傳染：Evidence 失效 → 依引用鏈影響 Claim/Decision（artifact graph 追蹤）

—

## 9. 技術技巧（Patterns）
- Key 正規化：canonical_args 去除無關欄位、排序鍵值，避免快取分裂
- Hash 防重：inputs_hash/outputs_hash 組合保證冪等，避免重複 Artifact
- Sanity 模板：為常見工具建立可重用的後驗檢查模板（價量/日期/HTML）
- 超時護欄：外部 IO 設定合理 timeout + 重試退避（exponential+jitter）
- 斷路器：同代理/工具短時失敗超閾值 → 暫停外呼並改由 Planner 調整
- 觀測標籤：所有寫入/命中事件加上 `source:{STM|L1|L2|LTM|TOOL}` 便於分析

—

## 10. 程式碼片段（Pseudo）

### 10.1 寫入 STM 與條件下沉 LTM
```python
def write_memory(result, ctx, ltm, verifier, cache):
    # 進 STM（回合即時）
    k = f"stm:{ctx.debate_id}:{ctx.round}:{sha256(result.key)}"
    ctx.stm.set(k, summarize(result), ttl_s=ctx.round_ttl)

    # 高價值資料 → 先驗證
    if is_high_value(result):
        if not sanity_check(result) or not schema_ok(result):
            return {"status": "rejected"}
        rep = verifier.run(make_claim_or_evidence(result))
        if rep.ok:
            art_id = ltm.upsert_artifact(make_artifact(result))
            cache.redis.set(f"l2:{result.tool}:{result.hash}", result, ttl_s=result.ttl)
            return {"status": "persisted", "artifact_id": art_id}
        else:
            return {"status": "needs_revision", "issues": rep.issues}
    return {"status": "buffered"}
```

### 10.2 TTL 到期再驗證
```python
def revalidate_artifact(artifact_id, ltm, tools):
    art = ltm.get_artifact(artifact_id)
    if art.type == "EvidenceDoc":
        fresh = tools.fetch_again(art.source)
        if not sanity_check(fresh):
            ltm.mark_stale(artifact_id)
            ltm.propagate_caveats(artifact_id)
            return False
        ltm.update(artifact_id, fresh)
        return True
    # 其他型別依規則處理
```

—

## 11. 監控與指標（SLO / Metrics）
- 命中率：STM/L1/L2/LTM 個別與整體
- 外部 IO 比例：外呼 / 總查詢、失敗率、重試次數、斷路器觸發次數
- 再驗證狀態：到期量、成功率、失敗原因分類
- 污染攔截：Schema/Sanity 拒收次數、來源黑名單命中
- 延遲：平均、P95/P99（依來源與層級）

—

## 12. 反模式與避坑
- 未經驗證即寫入 LTM 或共享快取 → 造成長尾污染
- 無命名空間與權限隔離 → 跨議題互相干擾
- 無 TTL 與再驗證 → 靜態資料長期過期卻未被發覺
- 過度細粒度的快取鍵 → 命中率低且維護困難
- 無斷路器 → 工具重試風暴/成本爆炸

—

## 13. 落地清單（Checklist）
- [ ] STM/LTM 結構與 API 定義完成
- [ ] TTL 與 Freshness 政策按型別落地
- [ ] I/O Schema 驗證 + Sanity Check 上線
- [ ] 快取鍵正規化與命名空間策略到位
- [ ] 再驗證排程器與傳染（artifact graph）處理
- [ ] 觀測：來源標籤、命中率、外呼比、延遲、斷路器
- [ ] 安全：隔離/權限/敏感欄位遮罩/來源黑名單
