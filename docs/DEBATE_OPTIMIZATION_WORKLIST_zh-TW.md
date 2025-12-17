# 辯論流程優化工作清單（Worklist / SSOT）

目的：針對目前辯論流程的結構性問題（命題不清、立場重疊、證據層級混亂、工具反客為主、交叉詰問失真、主席角色錯置），提出「可落地、可驗收」的優化任務，分階段推進。本文件同時作為「驅動開發的單一事實來源（Single Source of Truth）」與執行準則，內含 JSON Schema 草案、實作步驟、微單元矩陣與追蹤表格，以及 CI/PR/ADR 規範，提醒所有「開發智能體」遵循開發原則。

文件頭（元資料）
- version: 1.0.2-ssot
- status: Approved for implementation
- DRI/Owner: TBD
- reviewers: TBD
- last_updated: 2025-12-14
- links:
  - schemas: docs/schemas/ (topic|artifact|summary|checkpoint|continuation_token)
  - PR template: .github/pull_request_template.md
  - ADR template: docs/adr/ADR_TEMPLATE.md
  - CI: .github/workflows/ci.yml
  - 3rd-party README: README-For-3rd-Party.md

—

## 0. 開發者快速開始（第三方智能體）

> 必讀外部連結（請先閱讀）：
> - 3rd-party 快速入門指南：README-For-3rd-Party.md（含 Wave 1 ETA 與日常更新規則、本地檢查指令）
> - PR 模板：.github/pull_request_template.md
> - ADR 模板：docs/adr/ADR_TEMPLATE.md

1) 先看這些章節，照順序完成 Wave 1：
   - 2. JSON Schema 規格（topic/artifact/summary/checkpoint/token）
   - 4. 微單元實作矩陣（U1→U4）
   - 5. 追蹤表格（把 U1–U4 狀態改為 [WIP] 並填 Owner/ETA）
   - 6. CI 驗證 Gate（確保本地可通過 schema 驗證與測試）
   - 7. PR/ADR 模板（PR 必回鏈本 SSOT 的 U 編號，必要時新增/更新 ADR）
   - 8. 開發智能體原則（Topic Gate、Evidence Tiering、工具治理、可觀測性）
   - 9. 多供應商/接續規範（實作 Checkpoint/Continuation Token）

2) Wave 1 的實作順序（示例）：
   - U1：拆出 topic.schema.json → 新增 worker/topic_validator.py → 加 tests/test_topic_validator.py
   - U2：在 worker/debate_cycle 注入 Topic Gate → 產出 SSE: TopicClarificationRequired → 加 tests/test_debate_gate.py
   - U3：tool_invoker 決策樹（STM→L1/L2→LTM→外部工具）→ 加 tests/test_tool_mediator.py
   - U4：斷路器 v1（打開/半開/關閉）→ 加 tests/test_circuit_breaker.py

3) 提交規範：
   - PR 模板勾選：Schema 驗證 / 單元 / 整合 / E2E / 觀測欄位覆蓋
   - 在 5. 追蹤表格將 U任務狀態改為 [DONE]，DoD 欄加 ✔ 與 PR 編號

4) 禁止事項：
   - 跳過 Topic Gate；未通過 schema 的辯題不得進入 Round 1
   - 直連外部工具繞過 Tool Mediator；未經 schema/sanity 的結果下沉 LTM
   - 不產生 Checkpoint、不附 trace/provider/model_family 欄位

5) 驗收關鍵：
   - Wave 1 全綠；CI 通過；指標無異常（斷路器風暴=0）
   - 後續 Wave 2–4 依矩陣推進；handoff 測試成功率 ≥ 95%

—

## 1. 狀態總覽（顯示區 / 即時更新）
- 全域狀態：
  - 完成數：`[0/15]`
  - 目前波次：`Wave 1 (U1–U4 WIP)`
  - 風險/阻塞：`None`
- 狀態標示約定
  - [DONE] 已完成且通過 DoD 與測試
  - [WIP] 進行中（追蹤表填 ETA/阻塞）
  - [TODO] 尚未開始
  - [BLOCKED] 被依賴/外部條件阻擋

- 日常更新規則（必遵）
  - 每日 10:00 前由各 Owner 更新 U 項狀態與備註（含 ETA 是否變更）
  - 若遇阻，立即將狀態改為 [BLOCKED]，並在下方「阻塞原因（當日）」新增條目：`<U編號> - <原因> - <需要的協助>`
  - 完成時：將狀態改為 [DONE]，於 DoD 欄位打 ✔ 並填入 PR 編號

- Wave 1 ETA（目標日期，可按需調整）
  - U1 Owner:A → ETA 2025-12-15
  - U2 Owner:B → ETA 2025-12-16
  - U3 Owner:C → ETA 2025-12-17
  - U4 Owner:D → ETA 2025-12-18

- 阻塞原因（當日，滾動記錄）
  - （例）U2 - 等待 Topic Schema 決策審核 - 需要 Reviewer: X

—

## 2. JSON Schema 規格（將拆分為 docs/schemas/*.json）

本段為規格草案。實作時請將以下 schema 拆至 docs/schemas/ 並在 CI 中接入驗證。

### topic.schema.json（草案）
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.com/schemas/topic.schema.json",
  "title": "Debate Topic",
  "type": "object",
  "required": ["title", "timeframe", "metric", "question_type"],
  "properties": {
    "title": { "type": "string", "minLength": 3 },
    "description": { "type": "string" },
    "timeframe": { "type": "string", "enum": ["1m", "3m", "6m", "1y"] },
    "metric": { "type": "string", "enum": ["abs_price", "rel_to_index", "valuation"] },
    "baseline": { "type": "string", "description": "參考指數/同業/產業" },
    "question_type": { "type": "string", "enum": ["attribution", "market_explanations", "hypothesis_test"] },
    "acceptance_criteria": { "type": "array", "items": { "type": "string" }, "minItems": 1 },
    "metadata": { "type": "object", "additionalProperties": true }
  },
  "additionalProperties": false
}
```

### artifact.schema.json（草案）
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.com/schemas/artifact.schema.json",
  "title": "Debate Artifact",
  "type": "object",
  "required": ["id", "type", "provenance", "ts"],
  "properties": {
    "id": { "type": "string" },
    "type": { "type": "string", "enum": ["EvidenceDoc", "Claim", "Counterclaim", "ModelResult", "Summary", "VerificationTask", "Checkpoint"] },
    "tier": { "type": "integer", "minimum": 1, "maximum": 3 },
    "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
    "citations": { "type": "array", "items": { "type": "string" } },
    "evidence_ids": { "type": "array", "items": { "type": "string" } },
    "target_claim_id": { "type": "string" },
    "inputs": { "type": "object" },
    "outputs": { "type": "object" },
    "params": { "type": "object" },
    "metrics": { "type": "object" },
    "provenance": {
      "type": "object",
      "required": ["agent", "tool", "run_id", "provider", "model_family"],
      "properties": {
        "agent": { "type": "string" },
        "tool": { "type": "string" },
        "plan_node_id": { "type": "string" },
        "inputs_hash": { "type": "string" },
        "outputs_hash": { "type": "string" },
        "run_id": { "type": "string" },
        "provider": { "type": "string" },
        "model_family": { "type": "string" }
      },
      "additionalProperties": true
    },
    "ts": { "type": "string", "format": "date-time" },
    "ttl_s": { "type": "integer", "minimum": 0 },
    "stale": { "type": "boolean" },
    "verified": { "type": "boolean" }
  },
  "additionalProperties": true
}
```

### summary.schema.json（草案）
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.com/schemas/summary.schema.json",
  "title": "Debate Summary/Decision",
  "type": "object",
  "required": ["id", "topic", "claims", "citations", "conclusion", "ts"],
  "properties": {
    "id": { "type": "string" },
    "topic": { "$ref": "topic.schema.json" },
    "claims": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["claim_id", "tier"],
        "properties": {
          "claim_id": { "type": "string" },
          "tier": { "type": "integer", "minimum": 1, "maximum": 3 },
          "confidence": { "type": "number", "minimum": 0, "maximum": 1 }
        }
      },
      "minItems": 1
    },
    "citations": { "type": "array", "items": { "type": "string" } },
    "caveats": { "type": "array", "items": { "type": "string" } },
    "conclusion": { "type": "string", "minLength": 5 },
    "verdict": { "type": "string", "enum": ["affirm", "negate", "ranked_factors"] },
    "ts": { "type": "string", "format": "date-time" }
  },
  "additionalProperties": false
}
```

—

## 3. 實作步驟（後端/前端/運維）
摘錄：K1–K10（詳見文件完整版），含 Topic Gate、工具決策樹、Verifier Gate、主席裁決契約、前端 Topic Builder、Artifact Index + Filters、Cross-Exam、觀測與灰度。

—

## 4. 微單元實作矩陣（0.5–1人日/項）
波次與依賴：Wave1(U1–U4), Wave2(U5–U8), Wave3(U9–U12), Wave4(U13–U15)。
（各 U 任務詳見前版內容，狀態標示位：[TODO]/[WIP]/[DONE]/[BLOCKED]）

—

## 5. 追蹤表格（監督視圖 / 即時標記）
使用說明：狀態採 [DONE]/[WIP]/[TODO]/[BLOCKED]；完成時在 DoD 確認加 ✔ 與 PR 編號；每日更新全域狀態與波次。

| ID  | 名稱                            | Owner | 估時 | 狀態    | 依賴   | 主要檔案                                   | 測試                                  | DoD 確認 |
|-----|---------------------------------|-------|------|---------|--------|--------------------------------------------|---------------------------------------|----------|
| U1  | Topic Schema 拆分              | Owner:A | 1d   | [WIP]  | -      | schemas/topic.schema.json, topic_validator | test_topic_validator.py               |          |
| U2  | Debate 前置 Gate               | Owner:B | 1d   | [WIP]  | U1     | worker/debate_cycle.py                     | test_debate_gate.py                   |          |
| U3  | 工具決策樹 v1                 | Owner:C | 1d   | [WIP]  | -      | worker/tool_invoker.py, adapters/*         | test_tool_mediator.py                 |          |
| U4  | 斷路器 v1                       | Owner:D | 1d   | [WIP]  | U3     | tool_invoker.py, debate_cycle.py           | test_circuit_breaker.py               |          |
| U5  | Artifact 模型雛形              | TBD   | 1d   | [TODO]  | -      | models/artifact.py, artifact.schema.json   | test_artifact_model.py                |          |
| U6  | Verifier Gate（最小規則）      | TBD   | 1d   | [TODO]  | U5     | worker/verifier_agent.py                   | test_verifier_gate.py                 |          |
| U7  | 主席裁決分支                   | TBD   | 1d   | [TODO]  | U2,U6  | chairman_summary.yaml, debate_cycle.py     | test_chairman_decision.py             |          |
| U8  | Summary 契約驗證               | TBD   | 1d   | [TODO]  | U5,U6  | summary.schema.json, debate_cycle.py       | test_summary_contract.py              |          |
| U9  | Topic Builder（FE）            | TBD   | 1d   | [TODO]  | U1,U2  | TopicBuilder.tsx                           | e2e/topic-builder.spec.ts             |          |
| U10 | SSE 澄清事件（FE）             | TBD   | 0.5d | [TODO]  | U2     | useDebateSSE.ts                            | e2e/sse-topic-clarify.spec.ts         |          |
| U11 | Cross-Exam 題庫+模板           | TBD   | 1d   | [TODO]  | -      | cross_exam_templates.yaml, CrossExamPanel  | e2e/cross-exam.spec.ts                |          |
| U12 | VerificationTask 回寫          | TBD   | 1d   | [TODO]  | U6,U11 | routes/verification.py, verifier_agent.py  | e2e/verification-task.spec.ts         |          |
| U13 | 追蹤欄位與指標埋點             | TBD   | 1d   | [TODO]  | -      | worker/*, api/*                            | test_tracing_coverage.py              |          |
| U14 | 儀表（命中/風暴/通過率）       | TBD   | 1d   | [TODO]  | U13    | DiagnosticsBar, metrics API                | smoke                                  |          |
| U15  | Feature flags 與灰度           | TBD   | 0.5d | [TODO]  | -      | api/config/flags, debate_cycle.py          | flags 單測+e2e                        |          |
| U16  | Base Contract 注入機制         | TBD   | 1d   | [DONE]  | -      | api/prompt_service.py, base_contract.yaml  | test_prompt_injection.py              | ✔        |
| U17  | Guardrail Agent 實作           | TBD   | 1d   | [DONE]  | U16    | worker/guardrail_agent.py, guardrail.yaml  | test_guardrail_agent.py               | ✔        |
| U18  | Debate Cycle 審核攔截整合      | TBD   | 1d   | [DONE]  | U17    | worker/debate_cycle.py                     | test_debate_guardrail.py              | ✔        |

—

## 6. CI 驗證 Gate（必須遵循）
…（同前版，略）

## 7. PR 模板與 ADR 模板（必須遵循）
…（同前版，略）

| U16 | 更新 chairman_summary.yaml    | Owner:E | 0.5d | [WIP]  | U1     | prompts/system/chairman_summary.yaml       | prompt lint / review                   |          |
| U17 | SSOT 加入行為-事件對照表       | Owner:F | 0.5d | [WIP]  | U16    | docs/DEBATE_OPTIMIZATION_WORKLIST_zh-TW.md | doc lint                                |          |
| U18 | SSOT 導引策略/模式切換/Gate 清單| Owner:G | 0.5d | [WIP]  | U16    | docs/DEBATE_OPTIMIZATION_WORKLIST_zh-TW.md | doc lint                                |          |
| U19 | chairman 事件欄位規範（trace等）| Owner:H | 0.5d | [TODO] | U16    | docs/DEBATE_OPTIMIZATION_WORKLIST_zh-TW.md | N/A                                      |          |
| U20 | 測試樣板：Plan/Requests/Mode    | Owner:I | 1d   | [DONE] | U16–U18| tests/*                                    | unit/integration                         | ✔        |

## 8. 開發智能體開發原則（務必遵循）
…（同前版，略）

### 8.1 Chairman 行為-事件對照表（新增）
- 行為 / 事件
  - GeneratePlanNodes → 事件：ChairmanRequestsPublished（含 plan_nodes 摘要、requests、trace_id/run_id）
  - PublishRequests → 事件：ChairmanRequestsPublished（重複發佈時需去重註記）
  - DetectModeSwitch → 事件：ChairmanModeSwitch（包含 rationale 與切換至 ranking_debate）
  - SummarizeWithoutConclusion → 事件：ChairmanDecisionLog（記錄 Gate 結果、coverage、issues）
- Gate 檢查清單（主席需檢查下列是否達標，未達標須退回或降權）
  - Topic Gate（題目 Schema 完整）
  - Evidence Gate（Tier / 來源數 / 新鮮度 / verified）
  - Verifier Gate（引用覆蓋率、矛盾檢測）
- 導引策略（主席不給結論，只導引方法與資料）
  - 子問題拆解 → 工具/證據優先序 → Cross-Exam 模板 → 合法「不知道」 → 模式切換

## 9. 多供應商/多智能體接續規範（新）
…（同前版，含 Checkpoint/Token schema 與 handoff 測試條款，略）

## 10. 測試矩陣與 SLO（摘要）
…（同前版，略）

## 11. DoR/DoD 與變更管理（摘要）
…（同前版，略）

—

## 12. 搜尋工具合併計畫（U31–U36）

| ID  | 名稱                                              | Owner  | 估時 | 狀態  | 依賴 | 主要檔案/說明                                 |
|-----|---------------------------------------------------|--------|------|-------|------|----------------------------------------------|
| U31 | SearXNG 啟用 DuckDuckGo 引擎與 engines 白名單     | TBD    | 0.5d | [WIP] | -    | searxng/settings.yml                          |
| U32 | duckduckgo_adapter 改為 Deprecated shim           | Owner:J| 0.5d | [DONE]| U31? | adapters/duckduckgo_adapter.py → searxng 路由 |
| U33 | tool_registry 路由調整（duckduckgo→searxng+engines)| Owner:K| 0.5d | [DONE]| U32  | api/tool_registry.py                           |
| U34 | 測試更新（shim 與 engines='duckduckgo' 驗證）     | Owner:L| 0.5d | [DONE]| U32  | tests/test_duckduckgo_shim.py                 |
| U35 | 文件更新（合併策略/engines示例/移除時間表）        | Owner:M| 0.5d | [WIP] | U32  | SSOT/README 更新                               |
| U36 | 清理移除（過渡期後刪除 shim）                     | TBD    | 0.5d | [TODO]| U35  | 移除 adapters/duckduckgo_adapter.py            |

- 合併策略：duckduckgo.search 已由 searxng.search 代理（engines='duckduckgo'）。新開發請使用 searxng.search + engines 指定。
- engines 使用示例：{"q": "tsmc adr", "limit": 10, "engines": "duckduckgo"}；中立/監督者建議使用 'google cse' / 'brave api'（付費）。
- 清理時間表：過渡期 2–4 週，完成 U31/U35 後執行 U36。

## 13. 再辯論（新辯論）操作準則與核對表（新增）

### 13.1 操作準則
- 前端
  - UI：「以此設定新開一局」按鈕（位於辯論結果頁）。點擊彈出可編輯的預填參數表單（題目、團隊、工具）。
  - 防錯提示：若使用者在舊辯論頁直接改題目/團隊並送出，彈出提醒「將建立新辯論，避免沿用舊狀態」，並提供確認框。
  - SSE 切換：建立成功（POST /debates）取得新 debate_id 後，前端停止舊 SSE、訂閱新 debate_id 的 channel。
- 後端
  - API：建議直接使用 POST /debates 建立新辯論（可選提供「複製/新建」端點）。
  - 防汙染：對舊 debate_id 的 Redis/STMs 設定 TTL 或顯式釋放；新 id 開始前清理工作環境。
  - 返回欄位：POST /debates 返回新 debate_id 與初始化狀態，以便前端立即接管。
  - （可選）parent_debate_id：新辯論可記錄其來源辯論 id，便於回放與審計。
- 測試
  - E2E：從舊辯論結果頁按「以此設定新開一局」→ POST → SSE 訂閱切換 → 新事件流正常顯示。
  - 邊界：舊 SSE 停止；新辯論不含上一輪 evidence/log；團隊與工具初始化一致。
- 指標與觀測
  - 追蹤「再辯論（新辯論）使用率」、新/舊 debate_id 的時序切換、重跑成功率。
  - 指標最小集合：新辯論轉換率、平均建立時間、新/舊 SSE 切換延遲、舊訂閱存活時間。
  - 一律以 debate_id 斷開、隔離所有狀態（evidence/log/metrics）。

### 13.2 就緒核對表
- [ ] 再辯論按鈕改為「新辯論（複製設定）」
- [ ] POST /debates 回傳新 debate_id，前端切換 SSE
- [ ] 舊 debate_id 的 SSE 停止訂閱
- [ ] 新辯論初始化（團隊/工具/回合/STM）無殘留
- [ ] SSOT/README 已更新操作準則
- [ ] E2E 測試通過（以此設定新開一局）
- [ ] 監控新/舊 id 切換與成功率

### 13.3 追蹤任務（新增）
| ID  | 名稱                                    | Owner  | 估時 | 狀態  | 依賴 | 主要檔案/說明                  |
|-----|-----------------------------------------|--------|------|-------|------|-------------------------------|
| U43 | 前端「以此設定新開一局」表單與流程      | TBD    | 1d   | [TODO]| -    | web 前端（結果頁/表單）         |
| U44 | 前端防錯提示與 SSE 訂閱切換            | TBD    | 0.5d | [TODO]| U43  | web SSE 管理/提示              |
| U45 | 後端 POST /debates 返回欄位與清理策略  | TBD    | 0.5d | [TODO]| -    | api/debate_routes.py / Redis   |
| U46 | E2E 測試：新建→訂閱切換→新事件流       | TBD    | 1d   | [TODO]| U43–U45 | e2e 測試                      |
| U47 | 指標與觀測：切換延遲/成功率/使用率      | TBD    | 0.5d | [TODO]| U43–U46 | metrics / dashboard          |

附註：本文件為 SSOT，任何設計與流程變更需在此更新並回鏈至對應 PR/ADR/Issues。請於每日站會後更新「狀態總覽」與「追蹤表格」。

—

## 13. 智慧搜尋路由與驗證增強（U39–U42）

| ID  | 名稱                                              | Owner  | 估時 | 狀態  | 依賴 | 主要檔案/說明                                 |
|-----|---------------------------------------------------|--------|------|-------|------|----------------------------------------------|
| U39 | 搜尋路由策略（Role/Group/Tier）                   | TBD    | 1d   | [TODO]| -    | adapters/search_router.py, api/tool_registry.py|
| U40 | Verifier Gate 擴充（Coverage/Tier1 Source）       | TBD    | 1d   | [TODO]| U39  | worker/verifier_agent.py, worker/gate_utils.py|
| U41 | 快取/配額/儀表板（Paid Search Quota/TTL）         | TBD    | 1d   | [TODO]| U39  | api/cache_service.py, web/app.py             |
| U42 | 文檔與 Prompt 更新（SSOT/Chairman Prompts）       | TBD    | 0.5d | [TODO]| U40  | prompts/agents/*.yaml, SSOT                  |

- 路由策略：
  - Chairman/Reviewer/Guardrail → 使用 `search.paid` (Google CSE, Brave)。
  - 一般辯手 → 使用 `search.free` (SearXNG Default)；若 Gate 驗證失敗可升級為 Paid。
- Verifier Gate 擴充：
  - 要求關鍵 Claim 至少 2 個獨立來源，且至少 1 個 Tier 1 (Google/Brave/Bing)。
- Quota Management：
  - 設定每日 Paid Search 配額，超額則降級為 Free 並發送告警。