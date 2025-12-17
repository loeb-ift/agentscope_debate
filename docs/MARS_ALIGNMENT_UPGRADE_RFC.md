以下為「多代理研究系統（MARS）對齊升級」設計 RFC 工作表（繁體中文），可直接用於記錄與追蹤落地，內含規劃圖與 Artifact │
│ Graph 圖（Mermaid）。本文件採工作表格式，便於團隊在開發過程中逐步填寫與維護。                                        │
│                                                                                                                      │
│ 設計 RFC 工作表：多代理研究系統（MARS）對齊升級                                                                      │
│                                                                                                                      │
│ 一、專案背景與目標                                                                                                   │
│                                                                                                                      │
│  • 背景                                                                                                              │
│     • 目前系統以「辯論輪次」為主，具多角色（分析師、交易員、主席）與工具（SearxNG、yfinance、TEJ）整合，透過 Redis   │
│       SSE 輸出過程訊息。                                                                                             │
│     • 實務痛點：工具治理與驗證環節不夠明確、缺乏統一 Artifact 與溯源、偶發工具重置風暴、觀測/重現能力需強化。        │
│  • 對齊框架：Anthropic MARS（Plan → Execute → Critique 循環 + Artifact 中心化 + 嚴謹工具治理 + 強化觀測/重現）       │
│  • 本次目標                                                                                                          │
│     • 建立計畫—執行—批判閉環（Planner/Coordinator/Verifier）                                                         │
│     • 以 Artifact（Evidence/Claim/ModelResult/Summary）作為單位，形成 Artifact Graph（含溯源）                       │
│     • 強化工具治理（Schema 驗證、退避、後驗 sanity check、速率限制、斷路器）                                         │
│     • 提升觀測可視化與可重現性（結構化 Trace、Run 報表、可再現）                                                     │
│                                                                                                                      │
│ 二、範圍與不在範圍                                                                                                   │
│                                                                                                                      │
│  • 範圍                                                                                                              │
│     • 新增 Planner/Verifier 代理與計畫式協作流程                                                                     │
│     • 新增 Artifact 模型與儲存層（SQLite/Qdrant）                                                                    │
│     • 強化工具治理與反循環策略                                                                                       │
│     • 增加結構化追蹤並輸出 Run 報表                                                                                  │
│  • 不在範圍                                                                                                          │
│     • 深度改造前端 UI（先以最小可視化：表格 + 基礎圖形）                                                             │
│     • 更換核心 LLM 供應商與 Prompt 框架（保留現有）                                                                  │
│                                                                                                                      │
│ 三、角色與責任                                                                                                       │
│                                                                                                                      │
│  • Planner（規劃代理）                                                                                               │
│     • 任務：將 Topic 轉為計畫節點（初期以線性為主，後續支援 DAG）                                                    │
│     • 輸出：Plan（PlanNode[]）                                                                                       │
│  • Coordinator（協調/執行）                                                                                          │
│     • 任務：按計畫節點調度角色與工具；強制驗證 Gate；遇到失敗回退或重規劃                                            │
│     • 輸出：Trace、Artifact 與狀態                                                                                   │
│  • Verifier/Critic（驗證/批判）                                                                                      │
│     • 任務：檢查 Claim 的引用覆蓋、證據新鮮度、矛盾；針對關鍵點做 Second Sourcing                                    │
│     • 輸出：VerificationReport、改進建議                                                                             │
│  • Domain Agents（各分析角色）                                                                                       │
│     • 任務：依節點任務產出標準化 Artifact                                                                            │
│     • 輸出：EvidenceDoc、Claim、ModelResult 等                                                                       │
│                                                                                                                      │
│ 四、流程設計（計畫圖）                                                                                               │
│                                                                                                                      │
│  • Mermaid 流程圖（可放入 diagrams/plan.mmd）                                                                        │
│                                                                                                                      │
│                                                                                                                      │
│  flowchart TD                                                                                                        │
│      A[輸入 Topic/任務] --> B[Planner 生成初步計畫(Plan)]                                                            │
│      B --> C[Coordinator 執行節點]                                                                                   │
│      C --> D[搜尋/資料擷取節點 → EvidenceDoc]                                                                        │
│      C --> E[建構主張節點 → Claim/Counterclaim]                                                                      │
│      C --> F[模型/計算節點 → ModelResult]                                                                            │
│      D --> G[Verifier 驗證(引用、新鮮度、Sanity)]                                                                    │
│      E --> G                                                                                                         │
│      F --> G                                                                                                         │
│      G -->|通過| H[綜整/決策(產出 Summary/Decision)]                                                                 │
│      G -->|未通過| I[Planner/Coordinator 調整計畫或擴充查證]                                                         │
│      I --> C                                                                                                         │
│      H --> J[Run 報表/Trace/Artifact Graph]                                                                          │
│                                                                                                                      │
│                                                                                                                      │
│ 五、Artifact 設計（模型與欄位）                                                                                      │
│                                                                                                                      │
│  • EvidenceDoc                                                                                                       │
│     • id: str（UUID）                                                                                                │
│     • source: str（URL/DB/Tool）                                                                                     │
│     • snippet: str（節錄）                                                                                           │
│     • fulltext_ref: Optional[str]（儲存位置）                                                                        │
│     • timestamp: datetime                                                                                            │
│     • tool: str（來源工具）                                                                                          │
│     • citation: str（標準引用格式）                                                                                  │
│     • provenance: {agent, inputs_hash, outputs_hash, run_id}                                                         │
│     • embedding: vector（儲存於向量庫）                                                                              │
│  • Claim                                                                                                             │
│     • id: str                                                                                                        │
│     • text: str                                                                                                      │
│     • evidence_ids: List[str]                                                                                        │
│     • confidence: float（0–1）                                                                                       │
│     • assumptions: List[str]                                                                                         │
│     • scope: str（適用範圍/條件）                                                                                    │
│     • provenance: {...}                                                                                              │
│  • Counterclaim                                                                                                      │
│     • id: str                                                                                                        │
│     • target_claim_id: str                                                                                           │
│     • text: str                                                                                                      │
│     • evidence_ids: List[str]                                                                                        │
│     • provenance: {...}                                                                                              │
│  • ModelResult                                                                                                       │
│     • id: str                                                                                                        │
│     • inputs: dict                                                                                                   │
│     • outputs: dict                                                                                                  │
│     • params: dict                                                                                                   │
│     • metrics: dict（如 RMSE、coverage）                                                                             │
│     • provenance: {...}                                                                                              │
│  • Summary/Decision                                                                                                  │
│     • id: str                                                                                                        │
│     • inputs: List[str]（引用的 artifact ids）                                                                       │
│     • claim_ids: List[str]                                                                                           │
│     • caveats: List[str]                                                                                             │
│     • decision: Optional[str]（若為交易建議）                                                                        │
│     • confidence: float                                                                                              │
│     • provenance: {...}                                                                                              │
│                                                                                                                      │
│ 六、Artifact Graph 圖（Mermaid）                                                                                     │
│                                                                                                                      │
│  • Mermaid（可放入 diagrams/artifact_graph.mmd）                                                                     │
│                                                                                                                      │
│                                                                                                                      │
│  graph LR                                                                                                            │
│      E1[EvidenceDoc: News A] --> C1[Claim: 市場熱度下降]                                                             │
│      E2[EvidenceDoc: Price Data] --> C1                                                                              │
│      M1[ModelResult: 回歸/評分] --> C1                                                                               │
│      C2[Counterclaim: 長期需求仍強] --> C1                                                                           │
│      E3[EvidenceDoc: 需求報告] --> C2                                                                                │
│      C1 --> S1[Summary/Decision]                                                                                     │
│      C2 --> S1                                                                                                       │
│                                                                                                                      │
│                                                                                                                      │
│ 七、工具治理（政策與技術）                                                                                           │
│                                                                                                                      │
│  • 輸入/輸出 Schema 驗證                                                                                             │
│     • 每個工具在註冊時提供 JSON Schema                                                                               │
│     • 調用前後均驗證；不符合則標記工具錯誤與回退                                                                     │
│  • 重試與退避                                                                                                        │
│     • 指數退避（exponential backoff + jitter）、最大重試次數                                                         │
│  • 後驗 Sanity Check                                                                                                 │
│     • 數值欄位（價格、成交量）格式與範圍                                                                             │
│     • 日期解析、空集合保護、HTML 錯頁檢測                                                                            │
│  • 速率限制                                                                                                          │
│     • per-tool、per-agent 配額；超出即排隊或降級                                                                     │
│  • 反循環斷路器                                                                                                      │
│     • 偵測重複 Meta-Tool Reset 或無意義重試                                                                          │
│     • 通知 Planner 調整策略或標記節點為「需人工介入」                                                                │
│                                                                                                                      │
│ 八、記憶與檢索（短期/長期）                                                                                          │
│                                                                                                                      │
│  • 短期記憶（回合/計畫級）                                                                                           │
│     • Coordinator 管理，保存當前計畫上下文與最新 artifacts                                                           │
│  • 長期記憶（跨執行）                                                                                                │
│     • SQLite（metadata）+ Qdrant（embedding）                                                                        │
│     • TTL 政策：市場數據 TTL 短、基本面 TTL 長；到期優先重新驗證                                                     │
│  • 檢索策略                                                                                                          │
│     • 代理推理前先從向量庫檢索相關 Evidence/Claim                                                                    │
│     • 檢索紀錄與得分（similarity）寫入 trace                                                                         │
│                                                                                                                      │
│ 九、可觀測性與重現                                                                                                   │
│                                                                                                                      │
│  • 結構化 Trace 欄位（每個步驟）                                                                                     │
│     • agent, tool, plan_node_id                                                                                      │
│     • inputs_hash, outputs_hash                                                                                      │
│     • tokens, latency_ms, retries, rate_limited                                                                      │
│     • verification_status, errors                                                                                    │
│  • Run 級報表（輸出）                                                                                                │
│     • 計畫節點執行情況（完成/失敗/回退）                                                                             │
│     • Artifact 清單與 Graph                                                                                          │
│     • 驗證結果（通過率/矛盾）                                                                                        │
│     • 工具調用統計與錯誤分佈                                                                                         │
│                                                                                                                      │
│ 十、評測與驗收標準（可量化 KPI）                                                                                     │
│                                                                                                                      │
│  • 功能正確性                                                                                                        │
│     • 引用覆蓋率：≥ 80% 的 Claim 具 ≥ 2 個獨立 Evidence                                                              │
│     • 新鮮度合格率：市場資料 Evidence ≥ 90% 在時效窗內                                                               │
│     • 矛盾檢測：未解矛盾數趨近 0（或全數註記於 caveats）                                                             │
│  • 穩定性                                                                                                            │
│     • 工具失敗後成功恢復率 ≥ 95%                                                                                     │
│     • 無限迴圈/重置風暴次數趨近 0（斷路器觸發即中斷並上報）                                                          │
│  • 可觀測性                                                                                                          │
│     • 100% 步驟具備 trace 與 hash；Run 可重放                                                                        │
│  • 交付                                                                                                              │
│     • Artifact Graph 與 Run 報表可視化可用（簡版 UI）                                                                │
│                                                                                                                      │
│ 十一、風險與對策                                                                                                     │
│                                                                                                                      │
│  • 複雜度上升                                                                                                        │
│     • 先線性計畫，後續再引入 DAG 與自適應分支                                                                        │
│  • 效能負擔（嵌入/檢索）                                                                                             │
│     • 批量嵌入、結果快取、異步執行                                                                                   │
│  • 資料新鮮度                                                                                                        │
│     • TTL + Verifier 檢查，逾期自動排程 re-validate                                                                  │
│  • 兼容性                                                                                                            │
│     • 舊辯論模式保留為開關，灰度上線切換                                                                             │
│                                                                                                                      │
│ 十二、里程碑與排程                                                                                                   │
│                                                                                                                      │
│  • Phase 1（1–2 週）基建                                                                                             │
│     • artifacts.py + artifact_store.py（SQLite + Qdrant）                                                            │
│     • planner.py（線性計畫原型）                                                                                     │
│     • tool_invoker 強化：schema 驗證/退避/sanity/速率限制/斷路器                                                     │
│     • 基礎 trace 與 Run 報表（後端）                                                                                 │
│  • Phase 2（2–3 週）閉環                                                                                             │
│     • Coordinator 執行計畫節點與驗證 Gate                                                                            │
│     • Verifier/Critic 代理、矛盾檢測、second sourcing                                                                │
│     • 角色輸出契約化（型別 Artifact）                                                                                │
│     • 簡版 Artifact Graph 可視化                                                                                     │
│  • Phase 3（2 週）最佳化                                                                                             │
│     • Planner 自適應策略（信心/回退/分支）                                                                           │
│     • 記憶 TTL 與自動 re-validate 任務                                                                               │
│     • 評測儀表板與穩定性提升                                                                                         │
│                                                                                                                      │
│ 十三、決策點（需會簽/核准）                                                                                          │
│                                                                                                                      │
│  • Artifact schema 定稿                                                                                              │
│  • 工具 schema 驗證與限制策略                                                                                        │
│  • Verifier 門檻（citation、新鮮度、矛盾嚴格度）                                                                     │
│  • UI 可視化優先級（簡版 vs 進階）                                                                                   │
│                                                                                                                      │
│ 十四、責任分工與聯絡人                                                                                               │
│                                                                                                                      │
│  • 架構與協調（Coordinator/Planner 整合）：Owner：＿＿＿＿＿                                                         │
│  • Artifact 與儲存層：Owner：＿＿＿＿＿                                                                              │
│  • 工具治理（schema/退避/斷路器）：Owner：＿＿＿＿＿                                                                 │
│  • Verifier 代理與評測：Owner：＿＿＿＿＿                                                                            │
│  • 觀測與報表：Owner：＿＿＿＿＿                                                                                     │
│  • 前端可視化（簡版 Graph）：Owner：＿＿＿＿＿                                                                       │
│                                                                                                                      │
│ 十五、落地檢查清單（Checklist）                                                                                      │
│                                                                                                                      │
│  • [ ] artifacts.py 定義並合併                                                                                       │
│  • [ ] artifact_store.py（SQLite + Qdrant）可用                                                                      │
│  • [ ] planner.py（線性）接入 Coordinator                                                                            │
│  • [ ] tool_invoker（schema、退避、sanity、速率限制、斷路器）                                                        │
│  • [ ] verifier_agent.py（引用/新鮮度/矛盾）                                                                         │
│  • [ ] 結構化 trace + Run 報表                                                                                       │
│  • [ ] 基礎 Artifact Graph 視覺化                                                                                    │
│  • [ ] 測試：單元/整合/迴歸（含品質指標）                                                                            │
│                                                                                                                      │
│ 十六、附錄：初始資料字典與範例                                                                                       │
│                                                                                                                      │
│  • EvidenceDoc 範例                                                                                                  │
│     • source: https://example.com/news/oracle-q                                                                      │
│     • snippet: “Oracle AI 雲收入增長低於預期…”                                                                       │
│     • tool: searxng.search                                                                                           │
│     • citation: “Oracle Qx FY2024, Example News”                                                                     │
│     • timestamp: 2025-12-12T03:20:00Z                                                                                │
│  • Claim 範例                                                                                                        │
│     • text: “AI 概念股短期估值修正壓力增加”                                                                          │
│     • evidence_ids: [E1, E2]                                                                                         │
│     • confidence: 0.72                                                                                               │
│     • assumptions: [“利率維持高檔”]                                                                                  │
│     • scope: “1–3 個月”                                                                                              │
│  • VerificationReport（內部結構）                                                                                    │
│     • coverage_score: 0.85                                                                                           │
│     • freshness_ok: true                                                                                             │
│     • contradictions: []                                                                                             │
│     • actions: [“進入綜整節點”] 