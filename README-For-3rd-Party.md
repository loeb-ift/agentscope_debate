# 第三方開發者入門指南（快速開始）

> 本文件由 SSOT（docs/DEBATE_OPTIMIZATION_WORKLIST_zh-TW.md）引導，請以 SSOT 為唯一權威來源；所有設計與流程變更請先更新 SSOT 並回鏈本文件。

本專案以 docs/DEBATE_OPTIMIZATION_WORKLIST_zh-TW.md 作為單一事實來源（SSOT）。第三方只需依此文件即可開發、提 PR 與驗收。

## 1. 必讀章節（從哪裡開始）
- 0. 開發者快速開始（第三方智能體）
- 2. JSON Schema 規格（topic/artifact/summary/checkpoint/token）
- 4. 微單元實作矩陣（U1→U4 優先）
- 5. 追蹤表格（將負責的 U 項改為 [WIP] 並填 Owner/ETA）
- 6. CI 驗證 Gate、7. PR/ADR 模板
- 8. 開發智能體開發原則、9. 多供應商/接續規範

## 2. 本地檢查指令

### Wave 1 ETA 與日常更新規則（務必遵守）
- ETA 目標（可調整）：
  - U1 Owner:A → ETA 2025-12-15
  - U2 Owner:B → ETA 2025-12-16
  - U3 Owner:C → ETA 2025-12-17
  - U4 Owner:D → ETA 2025-12-18
- 每日更新：
  - 每日 10:00 前由各 Owner 更新 SSOT 的「追蹤表格」與「狀態總覽」
  - 若遇阻，立即將狀態改為 [BLOCKED]，並在 SSOT「阻塞原因（當日）」新增條目：`<U編號> - <原因> - <需要的協助>`
  - 完成時：將狀態改為 [DONE]，於 DoD 欄位打 ✔ 並填入 PR 編號

```bash
# Schema 自我驗證（需 Node 20+）
npm i -g ajv-cli
for f in docs/schemas/*.json; do ajv validate -s "$f" -d "$f" || exit 1; done

# 後端測試（若存在 requirements）
pip install -r api/requirements.txt 2>/dev/null || true
pytest -q || true

# 前端測試（若存在 web/）
npm ci --prefix web 2>/dev/null || true
npm test --prefix web --silent || true
```

## 2.5 搜尋工具合併策略（重要）
- 我們已將 duckduckgo.search 併入 SearXNG 路徑（shim）：
  - 建議優先使用 `searxng.search`，並以 `engines` 參數控制底層引擎
  - 例：
    - `{ "q": "TSMC ADR", "limit": 10, "engines": "duckduckgo" }`
    - `{ "q": "台積電 財報", "category": "news", "engines": "google cse" }`（需 CSE 設定）
    - `{ "q": "半導體 市場需求", "engines": "brave api" }`（需 Brave API key）
- 角色導向建議：
  - 中立/監督者（Chairman/Reviewer/Guardrail）：關鍵 Claim 使用 `google cse` / `brave api`；至少一條高級來源 + 第二獨立來源（二次查證）
  - 其他代理：先用免費（`duckduckgo`/`qwant`/聚合），不足再升級
- 清理時間表：duckduckgo_adapter 保留 2–4 週過渡；之後全面使用 `searxng.search + engines`

### 2.6 engines 可用情況（SearXNG 端配置）
- 設定檔位於 `searxng/settings.yml`；實際可用引擎由該檔決定
- 本倉庫設定檔中可見（選摘）：
  - google / google images / google news / google cse
  - brave / brave api（需 API key）
  - qwant（含 images/news）
  - duckduckgo（目前看到 images/videos/news，請確認 text 搜尋也已啟用）
  - baidu（含 images/kaifa）
  - wikipedia / reddit
- API Key 檢查清單：
  - Google CSE：`GOOGLE_CSE_API_KEY`, `GOOGLE_CSE_ID`
  - Brave API：`BRAVE_API_KEY`
  - Bing API：`BING_API_KEY`（若啟用）
  - Reddit/Twitter API：`REDDIT_CLIENT_ID/SECRET`、`TWITTER_BEARER_TOKEN`（若啟用）
- 驗收：直接訪問 `searxng/search?q=test&engines=duckduckgo` 應有結果；`engines=google cse` / `engines=brave api` 需確認金鑰與白名單

## 3. Wave 1（U1–U4）快速路線
- U1：docs/schemas/topic.schema.json、worker/topic_validator.py、tests/test_topic_validator.py
- U2：worker/debate_gate_sample.py、tests/test_debate_gate.py
- U3：worker/tool_invoker_decision.py、tests/test_tool_mediator.py
- U4：worker/circuit_breaker.py、tests/test_circuit_breaker.py

## 4. 提交 PR 規範（摘要）
- 使用 .github/pull_request_template.md
- 回鏈 SSOT 的 U 任務編號
- CI 必須通過（schema + 測試 + 觀測欄位覆蓋）

## 5. 問題與貢獻
- 變更設計需新增/更新 docs/adr/ 下的 ADR 檔
- 所有變更需同步更新 SSOT 的相關章節（links/追蹤/狀態）
