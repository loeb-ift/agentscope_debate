# Archive Log

Date (UTC): 2025-12-10T13:10:35Z
Author: Rovo Dev

Purpose
- Reduce runtime footprint and avoid accidental execution of non-runtime assets (tests and temporary files) in production environments.
- No service-impacting files were modified or removed.

Scope
- Archived only test-related and temporary files clearly not required by runtime services (API, worker, adapters, agentscope runtime code, configs, Dockerfiles remain untouched).

Archive Destination
- `_archive/tests_tmp/`
  - Contains archived tests and temporary sample data.
  - A README is included with restoration instructions.

Items Archived (moved)
1) Top-level tests directory
- from: `tests/`
- to: `_archive/tests_tmp/tests/`

2) Agentscope test suite
- from: `agentscope/tests/`
- to: `_archive/tests_tmp/agentscope_tests/`

3) Root-level standalone test files
- from: `test_debate_config.py`, `test_yfinance_direct.py`
- to: `_archive/tests_tmp/`

4) Temporary samples
- from: `tmp_rovodev_*` (specifically `tmp_rovodev_samples/`)
- to: `_archive/tests_tmp/tmp_rovodev_samples/`

Verification Performed
- Code search to verify no runtime imports or references to archived paths:
  - Patterns: `from tests`, `import tests`, `tmp_rovodev_samples`
  - Result: No matches found (indicates safe to move without affecting runtime)
- Did not change any code under: `api/`, `worker/`, `adapters/`, `agentscope/src/`, configs, or Dockerfiles.

Archive Snapshot (depth 3)
```
_archive/tests_tmp
_archive/tests_tmp/test_debate_config.py
_archive/tests_tmp/agentscope_tests
_archive/tests_tmp/agentscope_tests/model_ollama_test.py
_archive/tests_tmp/agentscope_tests/tool_dashscope_test.py
_archive/tests_tmp/agentscope_tests/test.docx
_archive/tests_tmp/agentscope_tests/formatter_openai_test.py
_archive/tests_tmp/agentscope_tests/token_anthropic_test.py
_archive/tests_tmp/agentscope_tests/mcp_streamable_http_client_test.py
_archive/tests_tmp/agentscope_tests/memory_reme_test.py
_archive/tests_tmp/agentscope_tests/formatter_ollama_test.py
_archive/tests_tmp/agentscope_tests/pipeline_test.py
_archive/tests_tmp/agentscope_tests/react_agent_test.py
_archive/tests_tmp/agentscope_tests/formatter_deepseek_test.py
_archive/tests_tmp/agentscope_tests/model_anthropic_test.py
_archive/tests_tmp/agentscope_tests/formatter_anthropic_test.py
_archive/tests_tmp/agentscope_tests/model_openai_test.py
_archive/tests_tmp/agentscope_tests/user_input_test.py
_archive/tests_tmp/agentscope_tests/model_gemini_test.py
_archive/tests_tmp/agentscope_tests/token_openai_test.py
_archive/tests_tmp/agentscope_tests/tool_openai_test.py
_archive/tests_tmp/agentscope_tests/tracer_test.py
_archive/tests_tmp/agentscope_tests/formatter_gemini_test.py
_archive/tests_tmp/agentscope_tests/tool_test.py
_archive/tests_tmp/agentscope_tests/formatter_dashscope_test.py
_archive/tests_tmp/agentscope_tests/model_dashscope_test.py
_archive/tests_tmp/agentscope_tests/toolkit_meta_tool_test.py
_archive/tests_tmp/agentscope_tests/plan_test.py
_archive/tests_tmp/agentscope_tests/rag_reader_test.py
_archive/tests_tmp/agentscope_tests/rag_knowledge_test.py
_archive/tests_tmp/agentscope_tests/toolkit_basic_test.py
_archive/tests_tmp/agentscope_tests/hook_test.py
_archive/tests_tmp/agentscope_tests/rag_store_test.py
_archive/tests_tmp/agentscope_tests/embedding_cache_test.py
_archive/tests_tmp/agentscope_tests/evaluation_test.py
_archive/tests_tmp/agentscope_tests/model_trinity_test.py
_archive/tests_tmp/agentscope_tests/mcp_sse_client_test.py
_archive/tests_tmp/agentscope_tests/config_test.py
_archive/tests_tmp/agentscope_tests/tune_test.py
_archive/tests_tmp/agentscope_tests/session_test.py
_archive/tests_tmp/tmp_rovodev_samples
_archive/tests_tmp/tmp_rovodev_samples/tej_ifrs_account_descriptions.json
_archive/tests_tmp/tmp_rovodev_samples/tej_financial_cover_cumulative.json
_archive/tests_tmp/tmp_rovodev_samples/tej_financial_cover_quarterly.json
_archive/tests_tmp/tmp_rovodev_samples/tej_margin_trading.json
_archive/tests_tmp/tmp_rovodev_samples/tej_shareholder_meeting.json
_archive/tests_tmp/tmp_rovodev_samples/tej_financial_summary_quarterly.json
_archive/tests_tmp/tmp_rovodev_samples/tej_stock_price.json
_archive/tests_tmp/tmp_rovodev_samples/tej_company_info.json
_archive/tests_tmp/tmp_rovodev_samples/tej_foreign_holdings.json
_archive/tests_tmp/tmp_rovodev_samples/tej_institutional_holdings.json
_archive/tests_tmp/tmp_rovodev_samples/tej_financial_summary.json
_archive/tests_tmp/tests
_archive/tests_tmp/tests/test_celery.py
_archive/tests_tmp/tests/__pycache__
_archive/tests_tmp/tests/test_tej_integration_live.py
_archive/tests_tmp/tests/test_e2e.py
_archive/tests_tmp/tests/test_api.py
_archive/tests_tmp/tests/test_searxng_adapter.py
_archive/tests_tmp/tests/test_tej_adapter.py
_archive/tests_tmp/README.txt
_archive/tests_tmp/test_yfinance_direct.py
```

How to Restore
- To restore a directory to its original location, move it back:
  - `mv _archive/tests_tmp/tests ./tests`
  - `mv _archive/tests_tmp/agentscope_tests ./agentscope/tests`
- To restore individual files:
  - `mv _archive/tests_tmp/test_debate_config.py ./`
  - `mv _archive/tests_tmp/test_yfinance_direct.py ./`
  - `mv _archive/tests_tmp/tmp_rovodev_samples ./`

Notes
- No files were deleted.
- No changes were made to any runtime or service code.
- If CI needs to run tests, restore them as above or update CI to point to `_archive/tests_tmp` temporarily.
