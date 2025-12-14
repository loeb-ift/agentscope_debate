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

## 8. 開發智能體開發原則（務必遵循）
…（同前版，略）

## 9. 多供應商/多智能體接續規範（新）
…（同前版，含 Checkpoint/Token schema 與 handoff 測試條款，略）

## 10. 測試矩陣與 SLO（摘要）
…（同前版，略）

## 11. DoR/DoD 與變更管理（摘要）
…（同前版，略）

—

附註：本文件為 SSOT，任何設計與流程變更需在此更新並回鏈至對應 PR/ADR/Issues。請於每日站會後更新「狀態總覽」與「追蹤表格」。