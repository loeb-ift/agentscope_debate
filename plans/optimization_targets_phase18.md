# Phase 18: Rationality Optimization & Robustness Targets

Based on the analysis of `debate_debug_8a254928...txt` (Debate Topic: "敦陽為什麼一直跌"), distinct irrational behaviors were identified. Specifically, agents hallucinated reasons for a stock decline despite having **zero** data returned from the database, and they entered retry loops when data was missing.

This checklist defines the concrete implementation steps to resolve these issues.

## 1. Preventing "Sycophantic Hallucination" (Data Honesty)
**Problem:** Agents (Growth_Strategist, Innovation_Believer) invented narratives about "market demand" and "cost structure" to explain a stock decline, even though their tool calls `tej.stock_price` returned `[]` (empty list).
**Goal:** Enforce strict adherence to retrieved evidence.

- [ ] **Implement `EvidenceCheck` Middleware**: 
    - Create a validation layer in `DebateCycle` that inspects the last tool result before the LLM generates a speech.
    - Logic: If `tool_result.is_empty()` or `tool_result.is_error()`, inject a temporary system prompt: *"CRITICAL WARNING: Your last tool call returned NO DATA. You generally CANNOT answer the 'Why' question. You must explicitly state that data is unavailable and refrain from making causal claims."*
- [ ] **Update System Prompts (Analyst Role)**:
    - Add specific directive: *"Negative Constraint: If you cannot retrieve quantitative data (price, revenue), do NOT fabricate qualitative reasons. State 'Insufficient Data' and propose a hypothesis instead of a fact."*
- [ ] **Implement `FactCheck` Flagging**:
    - In the `Chairman.summarize_round()` method, automatically flag any argument that makes a definitive claim (e.g., "Costs are rising") without a corresponding non-empty entry in the `evidence_log`.

## 2. Fixing "Infinite Loop" (Retry Policy)
**Problem:** Agents (Macro_Economist, Policy_Analyst) repeatedly called `tej.stock_price` with nearly identical parameters after failures, hitting token limits or tool call limits without progress.
**Goal:** Fail fast and switch strategies.

- [ ] **Implement `ToolHistory` Deduplication**:
    - In `Agent.execute_tool()`, maintain a hash list of recent call parameters.
    - Logic: If `hash(new_params)` exists in `history[-3:]`, block the call and return a System Message: *"You just tried this. Do not repeat. Switch tool (e.g., use Search instead of Database) or change query entirely."*
- [ ] **Smart Error Handling for TEJ**:
    - Specific fix for `date_span_too_large` error seen in logs.
    - Wrapper logic: If error == `date_span_too_large`, automatically split the request into smaller chunks or suggest the agent to use a shorter range, rather than letting the agent retry blindly.
- [ ] **"Three Strikes" Rule**:
    - If an agent fails 3 tool calls in a row (error or empty), force a `strategy_switch` state where the agent is prompted to use a fallback tool (e.g., `duckduckgo.search` instead of `tej`).

## 3. Implementing "Emergency Research Mode" (Chairman)
**Problem:** The debate proceeded through 3 rounds despite the fundamental premise (stock price data) being completely missing. The Chairman merely summarized the lack of data but did not fix it.
**Goal:** Active intervention by the Chairman.

- [ ] **Implement `DataHealthCheck` Hook**:
    - Run this hook after the "Opening Statements" (Round 1).
    - Check: `percentage_of_agents_with_data`. If < 50%, trigger Emergency Mode.
- [ ] **Chairman Intervention Action**:
    - Pause the debate flow.
    - Chairman executes a high-level `searxng.search` for "Company Name + Stock Price + News".
    - Chairman injects the findings into the `SharedMemory` of all agents.
    - Chairman issues a "System Directive": *"Internal DB is unresponsive. I have found X, Y, Z from the web. Base your arguments on this new context."*

## 4. Implementing "Database Handshake" (Date Awareness)
**Problem:** Agents queried for 2025 data (`2025-06-13` to `2025-12-13`) because the simulated system time was set to 2025, but the TEJ database likely only contains historical data up to 2024. This caused the empty results.
**Goal:** Align simulation time with available data.

- [ ] **Implement `check_latest_data_date(ticker)`**:
    - Before the debate starts (in `DebateCycle.initialize`), perform a "Handshake" query to the DB for the target company's latest stock price record.
- [ ] **Dynamic Context Setting**:
    - If `Latest_DB_Date` < `Simulation_Current_Date`:
        - Update System Prompt: *"Context Warning: The simulation date is [2025], but internal database records end at [2024-10]. For events after [2024-10], you MUST use Web Search tools; do not query the DB for future dates."*
- [ ] **Smart Date Ranges**:
    - Automatically cap `mdate.lte` in tool calls to the `Latest_DB_Date` to prevent empty queries.

## Summary of Work
This plan moves the system from "Passive Failure" (logging errors) to "Active Recovery" (detecting errors and adapting strategy).