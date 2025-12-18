import gradio as gr
import requests
import json
# import sseclient  # not used
import pandas as pd
import time  # used in preload and caching sections
import os

API_URL = os.getenv("API_URL", "http://api:8000/api/v1")

# --- Global Cache for Core Data ---
_CORE_DATA_CACHE = {
    "agents": {"data": None, "timestamp": 0},
    "teams": {"data": None, "timestamp": 0},
    "toolsets": {"data": None, "timestamp": 0},
    "securities": {"data": None, "timestamp": 0},
    "financial_terms": {"data": None, "timestamp": 0}
}
CACHE_TTL = 60  # 60 seconds cache (increased from 30)

def _get_cached_or_fetch(cache_key, fetch_url, timeout=5):
    """通用緩存獲取函數"""
    import time
    now = time.time()
    cache = _CORE_DATA_CACHE.get(cache_key)
    
    # 如果緩存有效，直接返回
    # Modify: If data is empty list/dict, reduce TTL to 5s to allow quick retry on startup
    ttl = CACHE_TTL
    if cache and not cache["data"]: # Empty list/dict or None
        ttl = 5
        
    if cache and cache["data"] is not None and (now - cache["timestamp"]) < ttl:
        print(f"DEBUG: Using cached {cache_key} (TTL: {ttl}s)", flush=True)  # noqa
        return cache["data"]
    
    # 如果有舊緩存且距離上次失敗不到 10 秒，直接使用舊緩存避免頻繁重試
    # 修正：只有當 data 不為 None 時才使用舊緩存。如果 data 是 None (第一次就失敗)，應該允許立即重試。
    if cache and cache["data"] is not None and (now - cache.get("last_error_time", 0)) < 10:
        print(f"DEBUG: Using stale cache for {cache_key} (recent error)", flush=True)
        return cache["data"]
    
    # 否則重新獲取
    try:
        print(f"DEBUG: Fetching fresh {cache_key} from API...", flush=True)
        response = requests.get(fetch_url, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        
        # 更新緩存
        _CORE_DATA_CACHE[cache_key] = {"data": data, "timestamp": now, "last_error_time": 0}
        return data
    except Exception as e:
        print(f"ERROR fetching {cache_key}: {e}", flush=True)
        # 記錄錯誤時間
        if cache:
            cache["last_error_time"] = now
        # 如果有舊緩存，即使過期也返回
        if cache and cache["data"] is not None:
            print(f"WARNING: Using stale cache for {cache_key}", flush=True)
            return cache["data"]
        return None

def preload_core_data():
    """預加載核心數據（Agents、Teams、Toolsets、Securities、Financial Terms）"""
    import time
    
    # Wait for API to be ready
    max_retries = 30 # Increased from 10 to 30 (total ~60s)
    retry_delay = 2
    
    print("⏳ Waiting for API service to be ready...", flush=True)
    for attempt in range(max_retries):
        try:
            health_check = requests.get(f"{API_URL.rsplit('/api/v1', 1)[0]}/health", timeout=2)
            if health_check.status_code == 200:
                print("✅ API service is ready!", flush=True)
                break
        except:
            pass
        
        if attempt < max_retries - 1:
            print(f"   Retry {attempt + 1}/{max_retries} in {retry_delay}s...", flush=True)
            time.sleep(retry_delay)
    else:
        print("⚠️  API service not ready, skipping preload (will load on demand)", flush=True)
        return
    
    # Now preload data
    print("🚀 Preloading core data...", flush=True)
    agents_data = _get_cached_or_fetch("agents", f"{API_URL}/agents", timeout=10)
    teams_data = _get_cached_or_fetch("teams", f"{API_URL}/teams", timeout=10)
    toolsets_data = _get_cached_or_fetch("toolsets", f"{API_URL}/toolsets", timeout=10)
    securities_data = _get_cached_or_fetch("securities", f"{API_URL}/internal/securities", timeout=10)
    terms_data = _get_cached_or_fetch("financial_terms", f"{API_URL}/internal/financial_terms", timeout=10)
    
    loaded_count = sum(1 for d in [agents_data, teams_data, toolsets_data, securities_data, terms_data] if d)
    
    if loaded_count >= 2:  # At least agents and teams
        agents_count = len(agents_data.get('items', agents_data) if isinstance(agents_data, dict) else agents_data) if agents_data else 0
        teams_count = len(teams_data.get('items', teams_data) if isinstance(teams_data, dict) else teams_data) if teams_data else 0
        print(f"✅ Core data preloaded: {agents_count} agents, {teams_count} teams, {loaded_count}/5 datasets", flush=True)
    else:
        print("⚠️  Partial preload (will retry on demand)", flush=True)

# --- Helper Functions ---

def extract_id_from_dropdown(value):
    """Helper to extract ID if value is in 'Name (ID)' format"""
    if not value: return None
    value = str(value)
    if "(" in value and value.endswith(")"):
        return value.split("(")[-1].strip(")")
    return value

def get_agents(role=None):
    data = _get_cached_or_fetch("agents", f"{API_URL}/agents")
    if not data:
        return []
    
    print(f"DEBUG: get_agents role={role}, type(data)={type(data)}")
    if isinstance(data, dict):
        items = data.get("items", [])
        print(f"DEBUG: data is dict. keys={list(data.keys())}. items type={type(items)}")
        # Filter by role if specified
        if role:
            items = [a for a in items if a.get("role") == role]
        return items
    else:
        print(f"DEBUG: data is not dict. Returning data directly.")
        return data if not role else [a for a in data if a.get("role") == role]

def create_agent(name, role, specialty, system_prompt, config_json_str):
    try:
        config_json = json.loads(config_json_str) if config_json_str else {}
        payload = {
            "name": name,
            "role": role,
            "specialty": specialty,
            "system_prompt": system_prompt,
            "config_json": config_json
        }
        response = requests.post(f"{API_URL}/agents", json=payload)
        response.raise_for_status()
        return f"Agent '{name}' created successfully!"
    except Exception as e:
        return f"Error creating agent: {e}"

def update_agent(agent_id, name, role, specialty, system_prompt, config_json_str):
    try:
        config_json = json.loads(config_json_str) if config_json_str else {}
        payload = {
            "name": name,
            "role": role,
            "specialty": specialty,
            "system_prompt": system_prompt,
            "config_json": config_json
        }
        response = requests.put(f"{API_URL}/agents/{agent_id}", json=payload)
        response.raise_for_status()
        return f"Agent '{name}' updated successfully!"
    except Exception as e:
        return f"Error updating agent: {e}"

def delete_agent(agent_id):
    try:
        agent_id = extract_id_from_dropdown(agent_id)
        response = requests.delete(f"{API_URL}/agents/{agent_id}")
        response.raise_for_status()
        return "Agent deleted successfully!"
    except Exception as e:
        return f"Error deleting agent: {e}"

def get_agent_choices(role=None):
    agents = get_agents(role)
    print(f"DEBUG: get_agent_choices role={role}, agents type={type(agents)}", flush=True)
    if not isinstance(agents, list):
        print(f"ERROR: agents is not a list! Value: {agents}", flush=True)
        return []
    
    choices = []
    for a in agents:
        if not isinstance(a, dict):
            print(f"ERROR: Agent item is not dict: {a} (type: {type(a)})", flush=True)
            continue
        try:
            choices.append((f"{a.get('name', 'Unknown')} ({a.get('role', 'Unknown')})", a.get('id', '')))
        except Exception as e:
            print(f"ERROR processing agent: {a} - {e}", flush=True)
            
    return choices

def format_agent_list():
    agents = get_agents()
    if not agents:
        return pd.DataFrame(columns=["ID", "Name", "Role", "Specialty"])
    
    data = []
    for a in agents:
        data.append([a['id'], a['name'], a['role'], a.get('specialty', '')])
    return pd.DataFrame(data, columns=["ID", "Name", "Role", "Specialty"])

def get_team_members(team_id):
    if not team_id: return []
    team_id = extract_id_from_dropdown(team_id)
    try:
        res = requests.get(f"{API_URL}/teams/{team_id}")
        if res.status_code == 200:
            return res.json().get("member_ids", [])
    except:
        pass
    return []

def launch_debate_config(topic, chairman_id, rounds, pro_team_id, con_team_id, neutral_team_id):
    print(f"DEBUG: Launching debate config... Topic: {topic}", flush=True)
    try:
        # Extract IDs
        chairman_id = extract_id_from_dropdown(chairman_id)
        if not chairman_id:
            return "錯誤: 請選擇主席", None, "⚠️ 參數錯誤: 未選擇主席"

        # Resolve Team IDs to Agent IDs
        pro_agents = get_team_members(pro_team_id)
        con_agents = get_team_members(con_team_id)
        neutral_agents = get_team_members(neutral_team_id) if neutral_team_id else []

        if not pro_agents or not con_agents:
            return "錯誤: 必須選擇正方與反方團隊，且團隊必須包含成員。", None, "⚠️ 參數錯誤: 團隊無成員或未選擇"

        teams = [
            {"name": "正方", "side": "pro", "agent_ids": pro_agents},
            {"name": "反方", "side": "con", "agent_ids": con_agents}
        ]
        if neutral_agents:
            teams.append({"name": "中立/第三方", "side": "neutral", "agent_ids": neutral_agents})
        
        config_payload = {
            "topic": topic,
            "chairman_id": chairman_id,
            "rounds": int(rounds),
            "enable_cross_examination": True,
            "teams": teams
        }
        
        print(f"DEBUG: Creating config...", flush=True)
        # Timeout 10s for config creation
        config_res = requests.post(f"{API_URL}/debates/config", json=config_payload, timeout=10)
        
        if config_res.status_code != 201:
            return f"建立設定失敗: {config_res.text}", None, "❌ 設定建立失敗"
            
        config_res.raise_for_status()
        config_id = config_res.json()["id"]
        print(f"DEBUG: Config created ID: {config_id}. Launching...", flush=True)
        
        # Timeout 10s for launch
        launch_res = requests.post(f"{API_URL}/debates/launch?config_id={config_id}", timeout=10)
        launch_res.raise_for_status()
        
        task_id = launch_res.json()['task_id']
        print(f"DEBUG: Launch success. Task ID: {task_id}", flush=True)
        return f"辯論已啟動！任務 ID: {task_id}", task_id, "⏳ 正在初始化辯論環境..."
        
    except requests.exceptions.Timeout:
        return "請求超時：API 回應過慢，請檢查後端日誌。", None, "❌ 請求超時"
    except Exception as e:
        print(f"ERROR launching debate: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return f"啟動失敗: {str(e)}", None, f"啟動失敗: {str(e)}"

def stream_debate_log(task_id):
    print(f"DEBUG: stream_debate_log called with task_id: {task_id}", flush=True)
    if not task_id:
        yield "無任務 ID", "❌ 無效的任務 ID", ""
        return

    try:
        # Initial status (Force Yield immediately)
        yield "正在連接後端服務...", "🚀 初始化連接...", "📊 連線中..."
        
        # Use requests with stream=True for robust SSE handling
        print(f"[DEBUG STREAM] Connecting to {API_URL}/debates/{task_id}/stream", flush=True)
        
        # Add timeout for connection (connect=10, read=None for streaming)
        with requests.get(f"{API_URL}/debates/{task_id}/stream", stream=True, timeout=(10, None)) as response:
            if response.status_code != 200:
                yield f"Error: Backend returned {response.status_code}", "❌ 連線失敗", "停止"
                return

            history_list = [] # Store individual entries
            MAX_DISPLAY_ITEMS = 30
            
            # Use iterator to handle timeouts if needed, but requests iter_lines is blocking.
            # We trust the backend to send keepalives (usage updates).
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith("data: "):
                        json_str = decoded_line[6:] # Removing "data: " prefix
                        # print(f"DEBUG STREAM: {json_str[:100]}...", flush=True)
                        if json_str.strip() == "[DONE]":
                            display_md = "\n".join(history_list[-MAX_DISPLAY_ITEMS:])
                            if len(history_list) > MAX_DISPLAY_ITEMS:
                                display_md = f"*... (已隱藏前 {len(history_list)-MAX_DISPLAY_ITEMS} 條訊息，完整內容請下載報告) ...*\n\n" + display_md
                            yield display_md, "🏁 辯論已圓滿結束。", gr.update()
                            break
                        try:
                            # print(f"DEBUG: raw json chunk: {json_str[:50]}...", flush=True)
                            data = json.loads(json_str)
                            
                            # Handle Progress Update Event
                            if data.get("type") == "progress_update":
                                progress = data.get("progress", 0)
                                msg = data.get("message", "")
                                stage = data.get("stage", "")
                                yield gr.update(), f"⏳ {msg} ({progress}%)", gr.update()
                                continue

                            # Handle Score Update Event
                            if data.get("type") == "score_update":
                                side = data.get("side")
                                new_score = data.get("new_score")
                                delta = data.get("delta")
                                reason = data.get("reason")
                                
                                icon = "⚖️"
                                delta_str = f"+{delta}" if delta > 0 else f"{delta}"
                                score_msg = f"**{icon} 評分更新**：【{side}】 {delta_str} 分 (當前: {new_score})\n> 原因：{reason}"
                                
                                entry = f"\n\n### {icon} System (Score)\n{score_msg}\n\n---"
                                history_list.append(entry)
                                
                                # Render
                                display_md = "\n".join(history_list[-MAX_DISPLAY_ITEMS:])
                                if len(history_list) > MAX_DISPLAY_ITEMS:
                                    display_md = f"*... (已隱藏前 {len(history_list)-MAX_DISPLAY_ITEMS} 條訊息，完整內容請下載報告) ...*\n\n" + display_md
                                    
                                yield display_md, f"⚖️ 評分更新: {side} {delta_str}", gr.update()
                                continue
                            
                            # Handle Usage Update Event
                            if data.get("type") == "usage_update":
                                tokens = data.get("tokens", 0)
                                cost = data.get("cost", 0.0)
                                search_count = data.get("search_count", 0)
                                usage_msg = f"### 📊 成本監控\n- **Tokens**: {tokens:,}\n- **Cost**: ${cost:.4f}\n- **Search**: {search_count} calls"
                                yield gr.update(), gr.update(), usage_msg
                                continue
                            
                            role = data.get("role", "System")
                            content = data.get("content", "")
                            
                            icon = "📢"
                            status_msg = f"▶️ {role} 正在發言..."
                            
                            if "Chairman" in role or "主席" in role:
                                icon = "👨‍⚖️"
                                status_msg = f"👨‍⚖️ 主席 {role} 正在主持..."
                                if "總結" in content or "結論" in content:
                                    status_msg = "👨‍⚖️ 主席正在進行總結..."
                            elif "Pro" in role or "正方" in role:
                                icon = "🟦"
                                status_msg = f"🟦 正方 {role} 正在陳述觀點..."
                            elif "Con" in role or "反方" in role:
                                icon = "🟥"
                                status_msg = f"🟥 反方 {role} 正在進行反駁..."
                            elif "Neutral" in role or "中立" in role:
                                icon = "🟩"
                                status_msg = f"🟩 中立觀點 {role} 正在分析..."
                            elif "Tool" in role or "工具" in role:
                                icon = "🛠️"
                                status_msg = f"🛠️ 系統正在調用工具: {role}..."
                            elif "Thinking" in role or "思考" in role:
                                icon = "💭"
                                status_msg = f"💭 {role.replace('(Thinking)', '').strip()} 正在思考中..."
                            elif "System" in role:
                                icon = "🖥️"
                            
                            
                            entry = f"\n\n### {icon} {role}\n{content}\n\n---"
                            history_list.append(entry)
                            
                            # Debug log before yield
                            # print(f"[DEBUG STREAM] Yielding update. MD Len: {len(history_md)}, Status: {status_msg}", flush=True)
                            
                            # Render window
                            display_md = "\n".join(history_list[-MAX_DISPLAY_ITEMS:])
                            if len(history_list) > MAX_DISPLAY_ITEMS:
                                display_md = f"*... (已隱藏前 {len(history_list)-MAX_DISPLAY_ITEMS} 條訊息，完整內容請下載報告) ...*\n\n" + display_md

                            yield display_md, status_msg, gr.update()
                        except json.JSONDecodeError:
                            pass
                        except Exception as inner_e:
                            print(f"[DEBUG STREAM] Inner Loop Error: {inner_e}", flush=True)
    except Exception as e:
        print(f"[DEBUG STREAM] Outer Error: {e}", flush=True)
        yield f"**Error connecting to stream:** {str(e)}", f"❌ 連線錯誤: {str(e)}", ""

def list_prompts():
    try:
        response = requests.get(f"{API_URL}/prompts")
        response.raise_for_status()
        prompts = response.json()
        if not prompts:
            return pd.DataFrame(columns=["key", "content"])
        df = pd.DataFrame(prompts)
        return df[["key", "content"]]
    except Exception as e:
        return pd.DataFrame({"error": [str(e)]})

def get_prompt_content(key):
    try:
        response = requests.get(f"{API_URL}/prompts/{key}")
        if response.status_code == 404:
            return ""
        response.raise_for_status()
        return response.json()["content"]
    except:
        return ""

def update_prompt_content(key, content):
    if not key or not content:
        return "請填寫 Key 和內容"
    try:
        response = requests.put(f"{API_URL}/prompts/{key}", json={"content": content})
        if response.status_code == 404:
            response = requests.post(f"{API_URL}/prompts", json={"key": key, "content": content, "language": "zh-TW"})
        
        response.raise_for_status()
        return f"Prompt '{key}' 保存成功！"
    except Exception as e:
        return f"Error: {e}"

def create_custom_tool(name, tool_type, url, method, headers_json, python_code, schema_json, group, mcp_api_key=None):
    try:
        schema = json.loads(schema_json) if schema_json else {}
        
        payload = {
            "name": name,
            "type": tool_type,
            "json_schema": schema,
            "group": group or "user_defined",
            "enabled": True
        }

        if tool_type == "http":
            headers = json.loads(headers_json) if headers_json else {}
            payload["api_config"] = {
                "url": url,
                "method": method,
                "headers": headers
            }
        elif tool_type == "mcp":
             # [MCP Integration]
             # For MCP, we need the base URL and optionally an API Key.
             # We store api_key in api_config for simplicity (though header injection is better).
             payload["api_config"] = {
                 "url": url,
                 "api_key": mcp_api_key
             }
        elif tool_type == "python":
            payload["python_code"] = python_code
        
        response = requests.post(f"{API_URL}/tools", json=payload)
        response.raise_for_status()
        return f"Tool '{name}' created successfully!"
    except Exception as e:
        return f"Error creating tool: {e}"

def update_tool(tool_id, name, tool_type, description, schema_json, openapi_json, api_config_json, python_code, group, enabled):
    try:
        tool_id = extract_id_from_dropdown(tool_id)
        
        schema = json.loads(schema_json) if schema_json else {}
        openapi = json.loads(openapi_json) if openapi_json else {}
        api_config = json.loads(api_config_json) if api_config_json else {}
        
        payload = {
            "name": name,
            "type": tool_type,
            "description": description,
            "json_schema": schema,
            "openapi_spec": openapi,
            "api_config": api_config,
            "python_code": python_code,
            "group": group,
            "enabled": enabled
        }
        
        response = requests.put(f"{API_URL}/tools/{tool_id}", json=payload)
        response.raise_for_status()
        return f"Tool '{name}' updated successfully!"
    except Exception as e:
        return f"Error updating tool: {e}"

def delete_tool(tool_id):
    try:
        tool_id = extract_id_from_dropdown(tool_id)
        response = requests.delete(f"{API_URL}/tools/{tool_id}")
        response.raise_for_status()
        return "Tool deleted successfully!"
    except Exception as e:
        return f"Error deleting tool: {e}"

def generate_description(tool_type, content):
    if not content:
        return "請先填寫代碼或 Schema"
    try:
        response = requests.post(
            f"{API_URL}/tools/generate-description",
            json={"tool_type": tool_type, "content": content}
        )
        response.raise_for_status()
        return response.json()["description"]
    except Exception as e:
        return f"生成失敗: {e}"

def list_custom_tools():
    try:
        response = requests.get(f"{API_URL}/tools")
        response.raise_for_status()
        tools = response.json()
        
        data = []
        for t in tools:
            data.append([t['id'], t['name'], t['type'], t.get('group', 'basic')])
        
        if not data:
             return pd.DataFrame(columns=["ID", "Name", "Type", "Group"])
             
        return pd.DataFrame(data, columns=["ID", "Name", "Type", "Group"])
    except Exception as e:
        return pd.DataFrame({"error": [str(e)]})

def get_tool_choices():
    tools = _get_cached_or_fetch("toolsets", f"{API_URL}/tools") # Note: toolsets cache key is fine or we add one
    # Actually, let's just use the URL but cache it under its own key for clarity
    tools = _get_cached_or_fetch("tools_raw", f"{API_URL}/tools")
    if not tools:
        return []
    return [(f"{t['name']} ({t['id']})", t['id']) for t in tools]

def list_companies(sector=None, group=None, sub_industry=None):
    try:
        params = {}
        if sector: params['sector'] = sector
        if group: params['group'] = group
        if sub_industry: params['sub_industry'] = sub_industry
        
        response = requests.get(f"{API_URL}/internal/companies", params=params)
        response.raise_for_status()
        companies = response.json()
        
        data = []
        for c in companies:
            data.append([
                c['company_id'], 
                c['company_name'], 
                c['ticker_symbol'], 
                c['industry_sector'],
                c.get('industry_group', ''),
                c.get('sub_industry', '')
            ])
        
        if not data:
             return pd.DataFrame(columns=["ID", "Name", "Ticker", "Sector", "Group", "Sub-industry"])
        
        return pd.DataFrame(data, columns=["ID", "Name", "Ticker", "Sector", "Group", "Sub-industry"])
    except Exception as e:
        return pd.DataFrame({"error": [str(e)]})

def create_company(company_id, company_name, ticker, sector, market_cap):
    try:
        payload = {
            "company_id": company_id,
            "company_name": company_name,
            "ticker_symbol": ticker,
            "industry_sector": sector,
            "market_cap": float(market_cap) if market_cap else None
        }
        response = requests.post(f"{API_URL}/internal/companies", json=payload)
        response.raise_for_status()
        return "Company created successfully!"
    except Exception as e:
        return f"Error: {e}"

def list_securities():
    try:
        securities = _get_cached_or_fetch("securities", f"{API_URL}/internal/securities")
        if not securities:
            return pd.DataFrame(columns=["ID", "Name", "Ticker", "Type", "Issuer ID"])
        
        data = []
        for s in securities:
            data.append([s['security_id'], s['security_name'], s.get('ticker', ''), s['security_type'], s.get('issuer_company_id', '')])
        
        if not data:
             return pd.DataFrame(columns=["ID", "Name", "Ticker", "Type", "Issuer ID"])
        
        return pd.DataFrame(data, columns=["ID", "Name", "Ticker", "Type", "Issuer ID"])
    except Exception as e:
        return pd.DataFrame({"error": [str(e)]})

def create_security(sec_id, sec_name, sec_type, issuer_id, ticker, isin, mcap):
    try:
        payload = {
            "security_id": sec_id,
            "security_name": sec_name,
            "security_type": sec_type,
            "issuer_company_id": issuer_id if issuer_id else None,
            "ticker": ticker if ticker else None,
            "isin": isin if isin else None,
            "market_cap": float(mcap) if mcap else None
        }
        response = requests.post(f"{API_URL}/internal/securities", json=payload)
        response.raise_for_status()
        return "Security created successfully!"
    except Exception as e:
        return f"Error: {e}"

def list_replays():
    data = _get_cached_or_fetch("replays", f"{API_URL}/replays")
    if not data:
        return []
    # If dict with items
    replays = data.get("items", data) if isinstance(data, dict) else data
    return [r['filename'] for r in replays]

def get_replay_markdown(filename):
    try:
        response = requests.get(f"{API_URL}/replays/{filename}")
        response.raise_for_status()
        return response.json()["content"]
    except:
        return "Error loading replay."

def get_replay_download_link(filename):
    return f"{API_URL}/replays/{filename}/download"

def list_financial_terms():
    try:
        terms = _get_cached_or_fetch("financial_terms", f"{API_URL}/internal/financial_terms")
        if not terms:
            return pd.DataFrame(columns=["ID", "Name (ZH)", "Definition (EN)", "Category"])
        
        data = []
        for t in terms:
            data.append([t['term_id'], t['term_name'], t.get('definition', ''), t.get('term_category', '')])
        
        if not data:
             return pd.DataFrame(columns=["ID", "Name (ZH)", "Definition (EN)", "Category"])
        
        return pd.DataFrame(data, columns=["ID", "Name (ZH)", "Definition (EN)", "Category"])
    except Exception as e:
        return pd.DataFrame({"error": [str(e)]})

def update_financial_term(term_id, name, definition, category):
    try:
        payload = {
            "term_name": name,
            "definition": definition,
            "term_category": category
        }
        response = requests.put(f"{API_URL}/internal/financial_terms/{term_id}", json=payload)
        response.raise_for_status()
        return f"Term '{term_id}' updated successfully!"
    except Exception as e:
        return f"Update failed: {e}"

def list_toolsets():
    try:
        toolsets = _get_cached_or_fetch("toolsets", f"{API_URL}/toolsets")
        if not toolsets:
            return pd.DataFrame(columns=["ID", "名稱", "描述", "包含工具", "全局啟用"])
        
        data = []
        for ts in toolsets:
            tool_names_str = ", ".join(ts.get('tool_names', []))
            data.append([ts['id'], ts['name'], ts.get('description', ''), tool_names_str, "✅" if ts.get('is_global') else ""])
        return pd.DataFrame(data, columns=["ID", "名稱", "描述", "包含工具", "全局啟用"])
    except Exception as e:
        return pd.DataFrame({"error": [str(e)]})

def get_all_tool_names():
    try:
        response = requests.get(f"{API_URL}/registry/tools")
        response.raise_for_status()
        tools = response.json()
        return sorted(list(tools.keys()))
    except Exception as e:
        print(f"Error fetching all tool names: {e}")
        return []

def get_all_prompt_keys():
    data = _get_cached_or_fetch("prompts_raw", f"{API_URL}/prompts")
    if not data:
        return []
    prompts = data.get("items", data) if isinstance(data, dict) else data
    return [p['key'] for p in prompts]

def create_toolset(name, description, tool_names, is_global):
    try:
        payload = {
            "name": name,
            "description": description,
            "tool_names": tool_names,
            "is_global": is_global
        }
        response = requests.post(f"{API_URL}/toolsets", json=payload)
        response.raise_for_status()
        return "工具集創建成功！"
    except Exception as e:
        return f"創建失敗: {e}"

def delete_toolset(toolset_id):
    try:
        toolset_id = extract_id_from_dropdown(toolset_id)
        response = requests.delete(f"{API_URL}/toolsets/{toolset_id}")
        response.raise_for_status()
        return "工具集刪除成功！"
    except Exception as e:
        return f"刪除失敗: {e}"



def get_toolset_choices():
    data = _get_cached_or_fetch("toolsets", f"{API_URL}/toolsets")
    if not data:
        return []
    # If API returns a list (old) or dict with items (new)
    toolsets = data.get("items", data) if isinstance(data, dict) else data
    return [(f"{ts['name']} ({ts['id']})", ts['id']) for ts in toolsets]

def get_financial_term_choices():
    data = _get_cached_or_fetch("financial_terms", f"{API_URL}/internal/financial_terms")
    if not data:
        return []
    # Handle list or dict structure
    terms = data.get("items", data) if isinstance(data, dict) else data
    return [(f"{t['term_name']} ({t['term_id']})", t['term_id']) for t in terms]

def get_system_config():
    try:
        # Note: /config is mounted at /api/v1/internal/config
        response = requests.get(f"{API_URL}/internal/config")
        return response.json()
    except Exception as e:
        print(f"Error fetching config: {e}")
        return {}

def get_config_keys():
    config = get_system_config()
    return list(config.keys()) if config else []

def get_llm_info():
    """獲取當前 LLM 與 Embedding 設定，回傳 (標題, 詳細資訊)"""
    try:
        config = get_system_config()
        if not config: return "# 🤖 AI 辯論平台管理系統 (Unknown)", "Unknown"
        
        # Helper to find value by key (list of dicts)
        def get_val(key):
            for item in config:
                if item['key'] == key:
                    return item['value']
            return "N/A"

        provider = get_val("LLM_PROVIDER")
        llm_model = "N/A"
        
        env_label = "Local"
        if provider == "ollama":
            llm_model = get_val("OLLAMA_MODEL")
            env_label = "Local (Ollama)"
        elif provider == "azure_openai":
            llm_model = get_val("AZURE_OPENAI_MODEL_DEPLOYMENT")
            env_label = "Azure"
        elif provider == "openai":
            llm_model = get_val("OPENAI_MODEL")
            env_label = "OpenAI"
            
        emb_provider = get_val("EMBEDDING_PROVIDER")
        if not emb_provider or emb_provider == "N/A":
             emb_provider = provider # Fallback logic
        
        title = f"# 🤖 AI 辯論平台管理系統 ({env_label})"
        details = f"🧠 LLM: {provider.upper()} ({llm_model}) | 📚 Embedding: {emb_provider.upper()}"
        return title, details
    except Exception as e:
        return "# 🤖 AI 辯論平台管理系統 (Error)", f"Error: {e}"

def get_industry_tree_data():
    try:
        response = requests.get(f"{API_URL}/internal/industry-tree")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching industry tree: {e}")
        return {}

def get_sector_choices():
    data = _get_cached_or_fetch("sectors", f"{API_URL}/internal/sectors")
    if not data:
        return []
    return sorted(data)

def get_company_update_status():
    try:
        response = requests.get(f"{API_URL}/internal/companies/last-update")
        data = response.json()
        last_update = data.get("last_update")
        if not last_update:
            return "從未更新", False
        
        # Check if older than 90 days
        from datetime import datetime, timedelta
        dt = datetime.fromisoformat(last_update)
        is_old = (datetime.now() - dt) > timedelta(days=90)
        return last_update, is_old
    except:
        return "未知", False

def trigger_company_update():
    try:
        response = requests.post(f"{API_URL}/internal/companies/update-from-web")
        response.raise_for_status()
        return "更新任務已啟動 (後台執行中)..."
    except Exception as e:
        return f"啟動失敗: {e}"

def update_system_config(key, value):
    try:
        response = requests.post(f"{API_URL}/config", json={"key": key, "value": value})
        response.raise_for_status()
        return "Setting updated!"
    except Exception as e:
        return f"Error: {e}"

def list_teams():
    try:
        # Fetch teams
        teams_res = requests.get(f"{API_URL}/teams")
        teams_res.raise_for_status()
        teams_data = teams_res.json()
        teams = teams_data.get("items", []) if isinstance(teams_data, dict) else teams_data
        
        # Fetch agents to map IDs to Names
        agents_res = requests.get(f"{API_URL}/agents")
        agents_res.raise_for_status()
        agents_data = agents_res.json()
        agents = agents_data.get("items", []) if isinstance(agents_data, dict) else agents_data
        
        agent_map = {a['id']: a['name'] for a in agents}
        
        data = []
        for t in teams:
            member_ids = t.get('member_ids', [])
            member_names = [agent_map.get(mid, mid) for mid in member_ids] # Use ID if name not found
            members_str = ", ".join(member_names)
            
            data.append([t['id'], t['name'], t.get('description', ''), members_str])
            
        return pd.DataFrame(data, columns=["ID", "團隊名稱", "描述", "成員"])
    except Exception as e:
        return pd.DataFrame({"error": [str(e)]})

def create_team(name, description, member_ids):
    try:
        payload = {
            "name": name,
            "description": description,
            "member_ids": member_ids
        }
        response = requests.post(f"{API_URL}/teams", json=payload)
        response.raise_for_status()
        return "團隊創建成功！"
    except Exception as e:
        return f"創建失敗: {e}"

def update_team(team_id, name, description, member_ids):
    try:
        payload = {
            "name": name,
            "description": description,
            "member_ids": member_ids
        }
        response = requests.put(f"{API_URL}/teams/{team_id}", json=payload)
        response.raise_for_status()
        return "團隊更新成功！"
    except Exception as e:
        return f"更新失敗: {e}"

def delete_team(team_id):
    try:
        team_id = extract_id_from_dropdown(team_id)
        response = requests.delete(f"{API_URL}/teams/{team_id}")
        response.raise_for_status()
        return "團隊刪除成功！"
    except Exception as e:
        return f"刪除失敗: {e}"

def get_team_choices():
    data = _get_cached_or_fetch("teams", f"{API_URL}/teams")
    if not data:
        return []
    
    teams = data.get("items", []) if isinstance(data, dict) else data
    print(f"DEBUG: Found {len(teams)} teams (from cache).", flush=True)
    choices = [(f"{t['name']} ({t['id']})", t['id']) for t in teams]
    return choices

# --- UI Construction ---

def main():
    with gr.Blocks(title="AI 辯論平台") as demo:
        with gr.Row():
            title_md = gr.Markdown("# 🤖 AI 辯論平台管理系統 (Loading...)")
            llm_status = gr.Markdown(value="", elem_id="llm_status")
        
        demo.load(get_llm_info, outputs=[title_md, llm_status])

        with gr.Tabs():
            # ==============================
            # Tab 1: 🏛️ 辯論大廳 (Debate Hall)
            # ==============================
            with gr.TabItem("🏛️ 辯論大廳"):
                with gr.Tabs():
                    # Sub-tab 1.1: 發起辯論
                    with gr.TabItem("⚔️ 發起辯論"):
                        # current_step removed - not used
                        # current_step = gr.State(1)
                        
                        with gr.Row():
                            # Left Column: Wizard Steps
                            with gr.Column(scale=1):
                                gr.Markdown("## 🎯 辯論設置嚮導")
                                
                                # Step 1: Basics
                                with gr.Group(visible=True) as step1_group:
                                    gr.Markdown("### 步驟 1/4: 辯論主題設定")
                                    topic_input = gr.Textbox(label="辯論主題", placeholder="例如: AI 是否會取代人類？")
                                    rounds_slider = gr.Slider(minimum=1, maximum=10, value=3, step=1, label="辯論輪次")
                                    step1_next_btn = gr.Button("下一步: 選擇主席 ➡️", variant="primary")

                                # Step 2: Chairman
                                with gr.Group(visible=False) as step2_group:
                                    gr.Markdown("### 步驟 2/4: 選擇主席")
                                    chairman_dropdown = gr.Dropdown(label="主席", choices=[])
                                    refresh_roles_btn = gr.Button("🔄 刷新選項")
                                    with gr.Row():
                                        step2_back_btn = gr.Button("⬅️ 上一步")
                                        step2_next_btn = gr.Button("下一步: 組建團隊 ➡️", variant="primary")

                                # Step 3: Teams
                                with gr.Group(visible=False) as step3_group:
                                    gr.Markdown("### 步驟 3/4: 組建團隊")
                                    gr.Markdown("*請選擇預設的辯論團隊 (Teams)*")
                                    team_warning_msg = gr.Markdown(visible=False)
                                    with gr.Group():
                                        pro_team_dropdown = gr.Dropdown(label="團隊 A (正方/主要視角) - 選擇團隊", multiselect=False, choices=[])
                                    with gr.Group():
                                        con_team_dropdown = gr.Dropdown(label="團隊 B (反方/對立視角) - 選擇團隊", multiselect=False, choices=[])
                                    with gr.Group():
                                        neutral_team_dropdown = gr.Dropdown(label="團隊 C (中立/第三視角) - 選擇團隊", multiselect=False, choices=[])
                                    
                                    with gr.Row():
                                        refresh_teams_btn = gr.Button("🔄 刷新團隊選項")
                                    with gr.Row():
                                        step3_back_btn = gr.Button("⬅️ 上一步")
                                        step3_next_btn = gr.Button("🚀 啟動辯論", variant="primary")
                                    
                                    debate_status_output = gr.Textbox(label="啟動狀態")
                                    task_id_state = gr.State()
                                    # live log moved to right column

                                # Step 4 removed

                            # Right Column: Live Status (Always Visible)
                            with gr.Column(scale=2):
                                gr.Markdown("### 📺 實時戰況")
                                stats_panel = gr.Markdown(value="📊 成本監控: 準備中...")
                                live_log = gr.Markdown(label="辯論日誌串流", value="等待啟動...", height=600)

                        # --- Wizard Logic ---
                        _dropdown_cache = {"timestamp": 0, "data": None}
                        
                        def refresh_dropdowns(force=False):
                            import time
                            # Cache for 3 seconds to avoid excessive API calls (unless forced)
                            now = time.time()
                            if not force and _dropdown_cache["data"] and (now - _dropdown_cache["timestamp"]) < 3:
                                return _dropdown_cache["data"]
                            
                            if force:
                                # Invalidate core cache to fetch fresh data
                                _CORE_DATA_CACHE["agents"]["timestamp"] = 0
                                _CORE_DATA_CACHE["teams"]["timestamp"] = 0
                            
                            chairmen = get_agent_choices()
                            teams = get_team_choices()
                            result = (
                                gr.update(choices=chairmen),
                                gr.update(choices=teams),
                                gr.update(choices=teams),
                                gr.update(choices=teams)
                            )
                            _dropdown_cache["data"] = result
                            _dropdown_cache["timestamp"] = now
                            return result
                        
                        def force_refresh_dropdowns():
                            return refresh_dropdowns(force=True)
                        
                        def refresh_teams_only(chairman_val, team_a_val, team_b_val, team_c_val):
                            try:
                                print(f"DEBUG: Refreshing teams. Chairman: {chairman_val}", flush=True)
                                # 1. Fetch all teams (use cache)
                                data = _get_cached_or_fetch("teams", f"{API_URL}/teams")
                                if not data:
                                    return (gr.update(), gr.update(), gr.update(), gr.update(visible=False))
                                
                                all_teams = data.get("items", []) if isinstance(data, dict) else data
                                
                                # 2. Filter based on Chairman
                                c_id = extract_id_from_dropdown(chairman_val)
                                available_teams = []
                                excluded_team_names = []
                                
                                for t in all_teams:
                                    # If chairman is defined and is a member of this team, exclude it
                                    if c_id and c_id in t.get('member_ids', []):
                                        excluded_team_names.append(t['name'])
                                        continue
                                    available_teams.append(t)
                                
                                warning_update = gr.update(visible=False, value="")
                                if excluded_team_names:
                                    msg = f"⚠️ **注意**：以下團隊因包含所選主席而被隱藏：{', '.join(excluded_team_names)}"
                                    warning_update = gr.update(visible=True, value=msg)
                                
                                # 3. Prepare Choices List
                                full_choices = [(f"{t['name']} ({t['id']})", t['id']) for t in available_teams]
                                
                                # 4. Filter for each dropdown to ensure uniqueness
                                # Extract current selected IDs
                                val_a = extract_id_from_dropdown(team_a_val)
                                val_b = extract_id_from_dropdown(team_b_val)
                                val_c = extract_id_from_dropdown(team_c_val)
                                
                                # Helper to generate choices excluding currently selected others
                                def get_choices_excluding(exclude_ids):
                                    return [c for c in full_choices if c[1] not in exclude_ids]

                                choices_a = get_choices_excluding([val_b, val_c]) if val_b or val_c else full_choices
                                choices_b = get_choices_excluding([val_a, val_c]) if val_a or val_c else full_choices
                                choices_c = get_choices_excluding([val_a, val_b]) if val_a or val_b else full_choices
                                
                                return (
                                    gr.update(choices=choices_a, value=team_a_val if (team_a_val and extract_id_from_dropdown(team_a_val) in [c[1] for c in choices_a]) else None), 
                                    gr.update(choices=choices_b, value=team_b_val if (team_b_val and extract_id_from_dropdown(team_b_val) in [c[1] for c in choices_b]) else None), 
                                    gr.update(choices=choices_c, value=team_c_val if (team_c_val and extract_id_from_dropdown(team_c_val) in [c[1] for c in choices_c]) else None),
                                    warning_update
                                )
                            except Exception as e:
                                print(f"ERROR in refresh_teams_only: {e}", flush=True)
                                return (gr.update(), gr.update(), gr.update(), gr.update(visible=False))

                        def go_to_step1(): return (gr.update(visible=True), gr.update(visible=False), gr.update(visible=False))
                        def go_to_step2(topic):
                            if not topic: return (gr.update(visible=True), gr.update(visible=False), gr.update(visible=False))
                            return (gr.update(visible=False), gr.update(visible=True), gr.update(visible=False))
                        def go_to_step3(chairman):
                            print(f"DEBUG: go_to_step3 called with chairman='{chairman}'")
                            if not chairman: 
                                print("DEBUG: No chairman selected, staying on Step 2")
                                return (
                                    gr.update(visible=False), gr.update(visible=True), gr.update(visible=False),
                                    gr.update(), gr.update(), gr.update()
                                )
                            
                            
                            # Do not reset choices here, leave it to refresh_teams_only
                            return (
                                gr.update(visible=False), gr.update(visible=False), gr.update(visible=True),
                                gr.update(), gr.update(), gr.update()
                            )

                        step1_next_btn.click(
                            go_to_step2,
                            inputs=[topic_input],
                            outputs=[step1_group, step2_group, step3_group]
                        ).then(
                            force_refresh_dropdowns,
                            outputs=[chairman_dropdown, pro_team_dropdown, con_team_dropdown, neutral_team_dropdown],
                            show_progress=True
                        )
                        step2_back_btn.click(go_to_step1, outputs=[step1_group, step2_group, step3_group])
                        step2_next_btn.click(
                            go_to_step3, 
                            inputs=[chairman_dropdown], 
                            outputs=[step1_group, step2_group, step3_group, pro_team_dropdown, con_team_dropdown, neutral_team_dropdown]
                        ).then(
                            refresh_teams_only,
                            inputs=[chairman_dropdown, pro_team_dropdown, con_team_dropdown, neutral_team_dropdown],
                            outputs=[pro_team_dropdown, con_team_dropdown, neutral_team_dropdown, team_warning_msg]
                        ).then(
                            refresh_teams_only,
                            inputs=[chairman_dropdown, pro_team_dropdown, con_team_dropdown, neutral_team_dropdown],
                            outputs=[pro_team_dropdown, con_team_dropdown, neutral_team_dropdown, team_warning_msg]
                        )

                        step3_back_btn.click(go_to_step2, inputs=[topic_input], outputs=[step1_group, step2_group, step3_group])
                        step3_next_btn.click(
                            launch_debate_config,
                            inputs=[topic_input, chairman_dropdown, rounds_slider, pro_team_dropdown, con_team_dropdown, neutral_team_dropdown],
                            outputs=[debate_status_output, task_id_state, live_log]
                        ).success(
                            stream_debate_log,
                            inputs=[task_id_state],
                            outputs=[live_log, debate_status_output, stats_panel]
                        )

                        refresh_roles_btn.click(force_refresh_dropdowns, outputs=[chairman_dropdown, pro_team_dropdown, con_team_dropdown, neutral_team_dropdown])
                        
                        # Full dependency chain for team selection
                        team_inputs = [chairman_dropdown, pro_team_dropdown, con_team_dropdown, neutral_team_dropdown]
                        team_outputs = [pro_team_dropdown, con_team_dropdown, neutral_team_dropdown, team_warning_msg]

                        refresh_teams_btn.click(refresh_teams_only, inputs=team_inputs, outputs=team_outputs)
                        
                        # Auto-refresh and filter when any related dropdown changes
                        chairman_dropdown.change(refresh_teams_only, inputs=team_inputs, outputs=team_outputs)
                        pro_team_dropdown.change(refresh_teams_only, inputs=team_inputs, outputs=team_outputs)
                        con_team_dropdown.change(refresh_teams_only, inputs=team_inputs, outputs=team_outputs)
                        neutral_team_dropdown.change(refresh_teams_only, inputs=team_inputs, outputs=team_outputs)
                        
                        # Initialize dropdowns on page load
                        demo.load(refresh_dropdowns, outputs=[chairman_dropdown, pro_team_dropdown, con_team_dropdown, neutral_team_dropdown])


                    
                    # Sub-tab 1.2: Agent 管理
                    with gr.TabItem("👥 Agent 管理"):
                        agent_id_state = gr.State(value=None) # Store ID for edit mode

                        with gr.Tabs() as agent_tabs:
                            # Sub-tab 1.2.1: Agent List
                            with gr.TabItem("📋 Agent 列表", id="agent_list_tab") as agent_list_tab:
                                gr.Markdown("### 👥 Agent 列表")
                                with gr.Row():
                                    refresh_agents_btn = gr.Button("🔄 刷新列表")
                                
                                agents_table = gr.DataFrame(
                                    headers=["ID", "名稱 (Name)", "角色 (Role)", "專長 (Specialty)"],
                                    interactive=False,
                                    wrap=True
                                )
                                
                                with gr.Row():
                                    selected_agent_id_input = gr.Dropdown(label="選擇要操作的 Agent", choices=[], scale=2, allow_custom_value=True)
                                    refresh_agent_select_btn = gr.Button("🔄 刷新選項", scale=0)
                                    load_agent_btn = gr.Button("✏️ 編輯", scale=1)
                                    delete_agent_btn = gr.Button("🗑️ 刪除", variant="stop", scale=1)
                                
                                agent_op_msg = gr.Textbox(label="系統訊息", interactive=False)

                            # Sub-tab 1.2.2: Create/Edit Agent
                            with gr.TabItem("✨ 創建 / 編輯 Agent", id="agent_edit_tab"):
                                gr.Markdown("### 👤 Agent 詳情編輯")
                                with gr.Row():
                                    agent_name = gr.Textbox(label="名稱 (Name)", placeholder="例如: 邏輯大師")
                                    agent_role = gr.Dropdown(choices=["debater", "chairman", "analyst"], label="角色", value="debater")
                                
                                agent_specialty = gr.Textbox(label="專長", placeholder="例如: 經濟學、哲學")
                                agent_prompt = gr.TextArea(label="系統提示詞 (System Prompt)", lines=10, placeholder="你是...")
                                # Fallback to TextArea for compatibility if Code component is missing or problematic
                                agent_config = gr.TextArea(label="設定 (JSON)", lines=5, value="{}")
                                
                                with gr.Row():
                                    cancel_edit_btn = gr.Button("⬅️ 取消 / 返回列表")
                                    save_agent_btn = gr.Button("💾 保存設定", variant="primary")

                        # --- Agent Logic ---
                        def load_agent_to_edit(agent_id):
                            if not agent_id:
                                return (gr.Tabs(selected="agent_list_tab"), None, "", "debater", "", "", "{}")
                            try:
                                response = requests.get(f"{API_URL}/agents/{agent_id}")
                                response.raise_for_status()
                                data = response.json()
                                return (
                                    gr.Tabs(selected="agent_edit_tab"), # Switch to Edit Tab
                                    agent_id,
                                    data['name'], 
                                    data['role'],
                                    data.get('specialty', ''),
                                    data['system_prompt'],
                                    json.dumps(data.get('config_json', {}), indent=2, ensure_ascii=False)
                                )
                            except:
                                return (gr.Tabs(selected="agent_list_tab"), None, "Error", "debater", "", "", "{}")

                        def save_agent(aid, name, role, spec, prompt, conf):
                            if aid:
                                res = update_agent(aid, name, role, spec, prompt, conf)
                            else:
                                res = create_agent(name, role, spec, prompt, conf)
                            # Return to list tab after save
                            return res, gr.Tabs(selected="agent_list_tab")

                        def reset_edit_form():
                             return (
                                gr.Tabs(selected="agent_list_tab"),
                                None, "", "debater", "", "", "{}" # Clear fields
                            )

                        def update_agent_dropdown():
                            return gr.update(choices=get_agent_choices())

                        refresh_agents_btn.click(format_agent_list, outputs=agents_table)
                        refresh_agent_select_btn.click(update_agent_dropdown, outputs=selected_agent_id_input)
                        
                        # Auto-refresh dropdown on tab load
                        agent_list_tab.select(update_agent_dropdown, outputs=selected_agent_id_input)

                        load_agent_btn.click(
                            load_agent_to_edit, 
                            inputs=[selected_agent_id_input], 
                            outputs=[agent_tabs, agent_id_state, agent_name, agent_role, agent_specialty, agent_prompt, agent_config]
                        )
                        
                        cancel_edit_btn.click(
                            reset_edit_form,
                            outputs=[agent_tabs, agent_id_state, agent_name, agent_role, agent_specialty, agent_prompt, agent_config]
                        )
                        
                        save_agent_btn.click(
                            save_agent,
                            inputs=[agent_id_state, agent_name, agent_role, agent_specialty, agent_prompt, agent_config],
                            outputs=[agent_op_msg, agent_tabs]
                        ).success(format_agent_list, outputs=agents_table).success(update_agent_dropdown, outputs=selected_agent_id_input)
                        
                        delete_agent_btn.click(
                            delete_agent,
                            inputs=[selected_agent_id_input],
                            outputs=[agent_op_msg]
                        ).success(format_agent_list, outputs=agents_table).success(update_agent_dropdown, outputs=selected_agent_id_input)

                        demo.load(format_agent_list, outputs=agents_table)
                        demo.load(update_agent_dropdown, outputs=selected_agent_id_input)

                    # Sub-tab 1.3: 團隊管理
                    with gr.TabItem("👥 團隊管理"):
                        team_id_state = gr.State(value=None) # Store ID for edit mode
                        
                        with gr.Tabs() as team_tabs:
                            with gr.TabItem("📋 團隊列表", id="team_list_tab") as team_list_tab:
                                with gr.Row():
                                    refresh_teams_btn = gr.Button("🔄 刷新列表")
                                
                                teams_table = gr.DataFrame(headers=["ID", "團隊名稱", "描述", "成員"], interactive=False, wrap=True)
                                
                                with gr.Row():
                                    selected_team_id = gr.Dropdown(label="選擇團隊", choices=[], scale=2, allow_custom_value=True)
                                    refresh_team_select_btn = gr.Button("🔄", scale=0)
                                    load_team_btn = gr.Button("✏️ 編輯", scale=1)
                                    delete_team_btn = gr.Button("🗑️ 刪除", variant="stop", scale=1)
                                
                                team_op_msg = gr.Textbox(label="操作結果")
                            
                            with gr.TabItem("✨ 創建 / 編輯團隊", id="team_edit_tab"):
                                team_name = gr.Textbox(label="團隊名稱", placeholder="e.g., Growth Team")
                                team_desc = gr.Textbox(label="描述", placeholder="Focus on technology and innovation")
                                team_members = gr.Dropdown(label="選擇成員 (Agent)", multiselect=True, choices=[])
                                team_validation_msg = gr.Markdown(value="") # Validation feedback
                                
                                with gr.Row():
                                    cancel_team_btn = gr.Button("⬅️ 取消 / 返回列表")
                                    save_team_btn = gr.Button("💾 保存團隊", variant="primary")
                                
                                save_team_msg = gr.Textbox(label="保存結果")

                                # Logic
                                def update_team_dropdown():
                                    return gr.update(choices=get_team_choices())
                                
                                def update_member_dropdown():
                                    return gr.update(choices=get_agent_choices())

                                def check_team_balance(member_ids):
                                    """
                                    檢查團隊組成的平衡性 (Overlap & Complementarity)
                                    """
                                    if not member_ids: return ""
                                    
                                    # Fetch agents details
                                    # Since we need specialty text, we need full agent objects.
                                    # _CORE_DATA_CACHE might be stale or partial if not preloaded.
                                    # But we can try to fetch if cache miss.
                                    
                                    # For simplicity, fetch all agents (it's cached in _get_cached_or_fetch)
                                    all_agents = get_agents()
                                    selected_agents = [a for a in all_agents if a['id'] in member_ids]
                                    
                                    if not selected_agents:
                                        return ""

                                    roles = [a.get('role', 'unknown').lower() for a in selected_agents]
                                    specialties = [a.get('specialty', '') for a in selected_agents]
                                    names = [a.get('name', 'Unknown') for a in selected_agents]
                                    
                                    warnings = []
                                    
                                    # 1. 人數警告 (Lean Teams)
                                    if len(member_ids) > 2:
                                        warnings.append("⚠️ **人數過多**：建議每隊不超過 2 人以達最佳協調效能。人多可能導致觀點重複與協調內耗。")

                                    # 2. 角色重疊檢查 (Overlap)
                                    from collections import Counter
                                    role_counts = Counter(roles)
                                    for role, count in role_counts.items():
                                        if count > 1:
                                            # Check specialty similarity via API
                                            # Filter agents with this role
                                            same_role_indices = [i for i, r in enumerate(roles) if r == role]
                                            same_role_specs = [specialties[i] for i in same_role_indices]
                                            same_role_names = [names[i] for i in same_role_indices]
                                            
                                            # If any specialty is empty, can't compare properly, just warn about role
                                            if any(not s.strip() for s in same_role_specs):
                                                 warnings.append(f"⚠️ **角色重疊**：已選擇 {count} 位 '{role}'。建議多元化配置。")
                                            else:
                                                try:
                                                    # Call Backend Similarity API
                                                    resp = requests.post(f"{API_URL}/internal/similarity", json={"texts": same_role_specs}, timeout=3)
                                                    if resp.status_code == 200:
                                                        matrix = resp.json()['matrix']
                                                        found_high_sim = False
                                                        for i in range(len(matrix)):
                                                            for j in range(i+1, len(matrix)):
                                                                if matrix[i][j] > 0.85:
                                                                    warnings.append(f"⚠️ **專長高度重疊**：'{same_role_names[i]}' 與 '{same_role_names[j]}' 的專長語意極為接近 (相似度 {matrix[i][j]:.0%})。建議更換以增加觀點多樣性。")
                                                                    found_high_sim = True
                                                        if not found_high_sim:
                                                            # Role overlap but specialty diff -> OK-ish, but still worth a hint
                                                            pass
                                                    else:
                                                        warnings.append(f"⚠️ **角色重疊**：已選擇 {count} 位 '{role}'。")
                                                except:
                                                    # API fail, fallback
                                                    warnings.append(f"⚠️ **角色重疊**：已選擇 {count} 位 '{role}'。")

                                    # 3. 互補性檢查 (Complementarity)
                                    if "debater" in roles:
                                        if not any(r in ["analyst", "researcher", "quant", "risk_officer"] for r in roles):
                                            warnings.append("💡 **互補建議**：團隊擁有辯手，但缺乏數據專家 (Analyst/Quant)。建議加入以強化論證深度。")
                                            
                                    if "chairman" in roles:
                                        warnings.append("❌ **配置錯誤**：主席角色 (Chairman) 通常不應加入辯論團隊，應擔任裁判。")

                                    return "\n\n".join(warnings) if warnings else "✅ **團隊結構配置均衡**"

                                def load_team_to_edit(team_id):
                                    if not team_id:
                                        return (gr.Tabs(selected="team_list_tab"), None, "", "", [])
                                    try:
                                        team_id = extract_id_from_dropdown(team_id)
                                        response = requests.get(f"{API_URL}/teams/{team_id}")
                                        response.raise_for_status()
                                        data = response.json()
                                        return (
                                            gr.Tabs(selected="team_edit_tab"),
                                            team_id,
                                            data['name'],
                                            data.get('description', ''),
                                            data.get('member_ids', [])
                                        )
                                    except:
                                        return (gr.Tabs(selected="team_list_tab"), None, "Error", "", [])

                                def save_team(tid, name, desc, members):
                                    if tid:
                                        res = update_team(tid, name, desc, members)
                                    else:
                                        res = create_team(name, desc, members)
                                    return res, gr.Tabs(selected="team_list_tab")

                                def reset_team_form():
                                    return (gr.Tabs(selected="team_list_tab"), None, "", "", [])

                                refresh_teams_btn.click(list_teams, outputs=teams_table)
                                refresh_team_select_btn.click(update_team_dropdown, outputs=selected_team_id)
                                
                                # Auto-refresh
                                team_list_tab.select(update_team_dropdown, outputs=selected_team_id)
                                
                                # Validation Hook
                                team_members.change(check_team_balance, inputs=[team_members], outputs=[team_validation_msg])

                                load_team_btn.click(
                                    load_team_to_edit,
                                    inputs=[selected_team_id],
                                    outputs=[team_tabs, team_id_state, team_name, team_desc, team_members]
                                )

                                delete_team_btn.click(
                                    delete_team,
                                    inputs=[selected_team_id],
                                    outputs=[team_op_msg]
                                ).then(list_teams, outputs=teams_table)
                                
                                cancel_team_btn.click(
                                    reset_team_form,
                                    outputs=[team_tabs, team_id_state, team_name, team_desc, team_members]
                                )

                                save_team_btn.click(
                                    save_team,
                                    inputs=[team_id_state, team_name, team_desc, team_members],
                                    outputs=[save_team_msg, team_tabs]
                                ).then(list_teams, outputs=teams_table)

                                # Init
                                demo.load(list_teams, outputs=teams_table)
                                demo.load(update_team_dropdown, outputs=selected_team_id)
                                demo.load(update_member_dropdown, outputs=team_members)


            # ==============================
            # Tab 2: 🛠️ 工具庫 (Tool Library)
            # ==============================
            with gr.TabItem("🛠️ 工具庫"):
                with gr.Tabs():
                    # Sub-tab 2.1: 工具清單
                    with gr.TabItem("🧰 工具清單"):
                        gr.Markdown("### 可用工具一覽")
                        def get_tools_df():
                            try:
                                res = requests.get(f"{API_URL}/registry/tools")
                                res.raise_for_status()
                                data = res.json()
                                if not data:
                                    return pd.DataFrame(columns=["Name", "Description", "Group", "Version"])
                                
                                # Process dict into list for better DataFrame control
                                rows = []
                                for name, info in data.items():
                                    rows.append({
                                        "Name": name,
                                        "Description": info.get("description", ""),
                                        "Group": info.get("group", ""),
                                        "Version": info.get("version", "")
                                    })
                                return pd.DataFrame(rows)
                            except Exception as e:
                                print(f"Error fetching tools df: {e}")
                                return pd.DataFrame(columns=["Error"], data=[[str(e)]])
                        
                        tools_df = gr.DataFrame()
                        refresh_tools_btn = gr.Button("刷新工具")
                        refresh_tools_btn.click(get_tools_df, outputs=tools_df)
                        demo.load(get_tools_df, outputs=tools_df)
                    
                    # Sub-tab 2.2: 編輯/管理工具
                    with gr.TabItem("✏️ 編輯/管理工具", id="tool_edit_tab"):
                        tool_id_state = gr.State(value=None)
                        
                        with gr.Row():
                            select_tool_dropdown = gr.Dropdown(label="選擇要編輯的工具 (僅限自定義工具)", choices=[], scale=2, allow_custom_value=True)
                            refresh_tool_select_btn = gr.Button("🔄 刷新", scale=0)
                            load_tool_btn = gr.Button("📂 載入設定", scale=1)
                        
                        gr.Markdown("*注意：ChinaTimes、TEJ 等系統內建工具無法在此編輯，僅能編輯透過本介面創建的工具。*")
                        gr.Markdown("---")
                        
                        with gr.Row():
                            edit_tool_name = gr.Textbox(label="工具名稱 (Name)", placeholder="e.g., tej.stock_price")
                            edit_tool_type = gr.Dropdown(choices=["api", "http", "python"], label="工具類型 (Type)")
                            edit_tool_group = gr.Dropdown(choices=["tej", "user_defined", "browser_use", "financial_data"], label="工具組 (Group)", allow_custom_value=True)
                        
                        edit_tool_desc = gr.TextArea(label="工具描述 (Description)", lines=3)
                        
                        with gr.Accordion("詳細配置 (JSON)", open=True):
                            edit_tool_schema = gr.TextArea(label="JSON Schema", lines=5, value="{}")
                            edit_tool_openapi = gr.TextArea(label="OpenAPI Spec", lines=5, value="{}")
                            edit_tool_config = gr.TextArea(label="API Config (HTTP Only)", lines=5, value="{}")
                            edit_tool_code = gr.TextArea(label="Python Code (Python Only)", lines=10, value="")
                        
                        edit_tool_enabled = gr.Checkbox(label="啟用 (Enabled)", value=True)
                        
                        with gr.Row():
                            save_tool_btn = gr.Button("💾 保存修改", variant="primary")
                            delete_tool_btn = gr.Button("🗑️ 刪除工具", variant="stop")
                        
                        tool_edit_msg = gr.Textbox(label="操作結果")

                        # Logic
                        def update_tool_dropdown():
                            return gr.update(choices=get_tool_choices())

                        def load_tool_to_edit(tool_id):
                            if not tool_id: return (None, "", "api", "basic", "", "{}", "{}", "{}", "", True)
                            try:
                                tool_id = extract_id_from_dropdown(tool_id)
                                res = requests.get(f"{API_URL}/tools/{tool_id}")
                                res.raise_for_status()
                                data = res.json()
                                return (
                                    data['id'],
                                    data['name'],
                                    data['type'],
                                    data.get('group', 'basic'),
                                    data.get('description', ''),
                                    json.dumps(data.get('json_schema') or {}, indent=2, ensure_ascii=False),
                                    json.dumps(data.get('openapi_spec') or {}, indent=2, ensure_ascii=False),
                                    json.dumps(data.get('api_config') or {}, indent=2, ensure_ascii=False),
                                    data.get('python_code', ''),
                                    data.get('enabled', True)
                                )
                            except Exception as e:
                                return (None, "Error", "api", "basic", str(e), "{}", "{}", "{}", "", True)

                        refresh_tool_select_btn.click(update_tool_dropdown, outputs=select_tool_dropdown)
                        
                        load_tool_btn.click(
                            load_tool_to_edit,
                            inputs=[select_tool_dropdown],
                            outputs=[tool_id_state, edit_tool_name, edit_tool_type, edit_tool_group, edit_tool_desc,
                                     edit_tool_schema, edit_tool_openapi, edit_tool_config, edit_tool_code, edit_tool_enabled]
                        )
                        
                        save_tool_btn.click(
                            update_tool,
                            inputs=[tool_id_state, edit_tool_name, edit_tool_type, edit_tool_desc,
                                    edit_tool_schema, edit_tool_openapi, edit_tool_config, edit_tool_code, edit_tool_group, edit_tool_enabled],
                            outputs=[tool_edit_msg]
                        ).then(update_tool_dropdown, outputs=select_tool_dropdown)
                        
                        delete_tool_btn.click(
                            delete_tool,
                            inputs=[select_tool_dropdown],
                            outputs=[tool_edit_msg]
                        ).then(update_tool_dropdown, outputs=select_tool_dropdown)

                        # Init
                        demo.load(update_tool_dropdown, outputs=select_tool_dropdown)

                    # Sub-tab 2.3: 自定義工具註冊
                    with gr.TabItem("🔧 自定義工具註冊"):
                        with gr.Row():
                            with gr.Column(scale=1):
                                gr.Markdown("### 新增自定義工具")
                                tool_name = gr.Textbox(label="工具名稱", placeholder="e.g., my_tool (for MCP, this will be the prefix)")
                                tool_type = gr.Dropdown(choices=["http", "python", "mcp"], label="工具類型", value="http")
                                tool_group = gr.Dropdown(choices=["user_defined", "browser_use", "financial_data", "data_analysis", "mcp"], label="工具組", value="user_defined", allow_custom_value=True)
                                tool_schema = gr.TextArea(label="參數 Schema (JSON Schema) [MCP 無需填寫]", lines=5, value='{"type": "object", "properties": {"q": {"type": "string"}}}')
                                
                                with gr.Group(visible=True) as http_config_group:
                                    tool_url = gr.Textbox(label="API URL", placeholder="https://api.example.com/data")
                                    tool_method = gr.Dropdown(choices=["GET", "POST"], label="HTTP Method", value="GET")
                                    tool_headers = gr.TextArea(label="Headers (JSON)", lines=3, value='{}')

                                with gr.Group(visible=False) as mcp_config_group:
                                    mcp_url = gr.Textbox(label="MCP Endpoint URL", placeholder="https://mcp.alphavantage.co/mcp")
                                    mcp_key = gr.Textbox(label="API Key (Optional)", type="password", placeholder="Paste API Key here")
                                    gr.Markdown("ℹ️ **MCP 說明**: 註冊後，系統會自動從 Endpoint 獲取工具列表，並以 `[工具名稱].[MCP工具名]` 格式註冊多個工具。")

                                with gr.Group(visible=False) as python_config_group:
                                    tool_python_code = gr.TextArea(label="Python Code", lines=10, value='def main(arg1):\n    return f"Hello {arg1}"')

                                tool_description = gr.Textbox(label="工具描述 (可自動生成)")
                                with gr.Row():
                                    generate_desc_btn = gr.Button("✨ 自動生成描述")
                                    load_tej_tpl_btn = gr.Button("📥 載入 TEJ 範例模板")

                                # Try-it 區塊
                                gr.Markdown("#### 🔬 Try it 測試 (不入庫) [MCP 暫不支援在此預覽]")
                                data_path = gr.Dropdown(choices=["auto", "data", "datatable.data", "items", "results"], value="auto", label="資料路徑")
                                try_params = gr.TextArea(label="測試參數 Params (JSON)", lines=3, value='{}')
                                try_headers = gr.TextArea(label="附加 Headers (JSON)", lines=3, value='{}')  # 目前僅展示，後端以 tool_headers 為主
                                try_status = gr.Markdown(value="")
                                try_btn = gr.Button("▶️ Try it", variant="primary")
                                preview_table = gr.DataFrame(label="預覽資料", wrap=True)

                                add_custom_tool_btn = gr.Button("➕ 新增工具", variant="primary")
                                add_custom_tool_output = gr.Textbox(label="新增結果")

                                def update_visibility(type_val):
                                    return (
                                        gr.update(visible=(type_val=="http")),
                                        gr.update(visible=(type_val=="python")),
                                        gr.update(visible=(type_val=="mcp"))
                                    )

                                tool_type.change(fn=update_visibility, inputs=tool_type, outputs=[http_config_group, python_config_group, mcp_config_group])

                            with gr.Column(scale=1):
                                gr.Markdown("### 已註冊自定義工具")
                                refresh_custom_tools_btn = gr.Button("🔄 刷新列表")
                                custom_tools_table = gr.DataFrame(headers=["ID", "Name", "Type", "Group"], wrap=True)

                        def wrap_generate(t_type, py_code, schema):
                            content = py_code if t_type == "python" else schema
                            return generate_description(t_type, content)

                        def load_tej_template():
                            try:
                                res = requests.get(f"{API_URL}/tools/templates/tej-stock-price", timeout=10)
                                res.raise_for_status()
                                tpl = res.json()
                                # 回填表單
                                api_conf = tpl.get("api_config", {})
                                headers = api_conf.get("headers", {})
                                schema = tpl.get("json_schema", {})
                                example_params = tpl.get("example_params", {})
                                return (
                                    gr.update(value=tpl.get("name", "custom.stock_price")), # tool_name
                                    gr.update(value="http"),                                   # tool_type
                                    gr.update(value=json.dumps(schema, ensure_ascii=False, indent=2)),
                                    gr.update(value=api_conf.get("url", "")),
                                    gr.update(value=api_conf.get("method", "GET")),
                                    gr.update(value=json.dumps(headers, ensure_ascii=False, indent=2)),
                                    gr.update(value=json.dumps(example_params, ensure_ascii=False, indent=2)),
                                    gr.update(value="已載入 TEJ 範例模板，請先修改 URL 與必要參數後按 Try it 驗證。")
                                )
                            except Exception as e:
                                return (
                                    gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
                                    gr.update(value=f"❌ 載入失敗：{e}")
                                )

                        def try_run_tool_handler(name, t_type, schema_json, url, method, headers_json, params_json, data_path_sel):
                            try:
                                schema = json.loads(schema_json) if schema_json else {}
                                headers_base = json.loads(headers_json) if headers_json else {}
                                params = json.loads(params_json) if params_json else {}
                                api_config = {"url": url, "method": method, "headers": headers_base}
                                req = {
                                    "name": name or "try_tool",
                                    "type": t_type,
                                    "api_config": api_config,
                                    "json_schema": schema,
                                    "params": params
                                }
                                resp = requests.post(f"{API_URL}/tools/try-run", json=req, timeout=60)
                                resp.raise_for_status()
                                data = resp.json()
                                # 依資料路徑切換
                                preview = data.get("preview_rows") or []
                                if data_path_sel != "auto":
                                    # 嘗試從 response 取出指定路徑
                                    body = data.get("response") or {}
                                    if data_path_sel == "data":
                                        preview = body.get("data") or []
                                    elif data_path_sel == "datatable.data":
                                        dt = body.get("datatable") or {}
                                        preview = dt.get("data") or []
                                    elif data_path_sel == "items":
                                        preview = body.get("items") or []
                                    elif data_path_sel == "results":
                                        preview = body.get("results") or []
                                # 只顯示前 10 筆
                                df = pd.DataFrame(preview[:10]) if isinstance(preview, list) else pd.DataFrame()
                                status = f"✅ 成功，預覽 {len(df)} 筆，耗時 {data.get('elapsed_ms', 0)} ms"
                                if not len(df):
                                    status = "⚠️ 呼叫成功但沒有可預覽的資料，請檢查參數與資料路徑。"
                                return (
                                    gr.update(value=df),
                                    gr.update(value=status)
                                )
                            except Exception as e:
                                return (
                                    gr.update(value=pd.DataFrame()),
                                    gr.update(value=f"❌ 失敗：{e}")
                                )

                        generate_desc_btn.click(
                            wrap_generate,
                            inputs=[tool_type, tool_python_code, tool_schema],
                            outputs=tool_description,
                            show_progress=True
                        )

                        load_tej_tpl_btn.click(
                            load_tej_template,
                            outputs=[tool_name, tool_type, tool_schema, tool_url, tool_method, tool_headers, try_params, try_status],
                            show_progress=True
                        )

                        try_btn.click(
                            try_run_tool_handler,
                            inputs=[tool_name, tool_type, tool_schema, tool_url, tool_method, tool_headers, try_params, data_path],
                            outputs=[preview_table, try_status],
                            show_progress=True
                        )

                        def create_tool_wrapper(name, t_type, t_group, t_schema, http_url, http_method, http_headers, mcp_url_val, mcp_key_val, py_code):
                            # Decide final URL based on type
                            final_url = http_url
                            if t_type == "mcp":
                                final_url = mcp_url_val
                            
                            return create_custom_tool(
                                name=name,
                                tool_type=t_type,
                                url=final_url,
                                method=http_method,
                                headers_json=http_headers,
                                python_code=py_code,
                                schema_json=t_schema,
                                group=t_group,
                                mcp_api_key=mcp_key_val
                            )

                        add_custom_tool_btn.click(
                            create_tool_wrapper,
                            inputs=[tool_name, tool_type, tool_group, tool_schema, tool_url, tool_method, tool_headers, mcp_url, mcp_key, tool_python_code],
                            outputs=add_custom_tool_output,
                            show_progress=True
                        ).then(list_custom_tools, outputs=custom_tools_table)
                        
                        refresh_custom_tools_btn.click(list_custom_tools, outputs=custom_tools_table, show_progress=True)
                        demo.load(list_custom_tools, outputs=custom_tools_table)
                    
                    # Sub-tab 2.3: 工具集管理
                    with gr.TabItem("📦 工具集管理"):
                        gr.Markdown("### 管理工具集 (ToolSets)")
                        with gr.Tabs():
                            with gr.TabItem("📋 工具集列表"):
                                with gr.Row():
                                    refresh_toolsets_btn = gr.Button("🔄 刷新列表")
                                
                                toolsets_table = gr.DataFrame(
                                    headers=["ID", "名稱", "描述", "包含工具", "全局啟用"],
                                    interactive=False,
                                    wrap=True
                                )
                                
                                with gr.Row():
                                    selected_toolset_id = gr.Dropdown(label="選擇要刪除的工具集", choices=[], scale=2, allow_custom_value=True)
                                    refresh_ts_select_btn = gr.Button("🔄", scale=0)
                                    delete_toolset_btn = gr.Button("🗑️ 刪除工具集", variant="stop", scale=1)
                                
                                toolset_op_msg = gr.Textbox(label="操作結果")

                            with gr.TabItem("✨ 創建工具集"):
                                ts_name = gr.Textbox(label="工具集名稱", placeholder="e.g., Financial Tools")
                                ts_desc = gr.Textbox(label="描述", placeholder="用於財務分析的工具集合")
                                ts_tools = gr.Dropdown(label="選擇工具", multiselect=True, choices=[])
                                ts_global = gr.Checkbox(label="設為全局默認 (所有 Agent 可用)")
                                create_ts_btn = gr.Button("💾 創建工具集", variant="primary")
                                create_ts_msg = gr.Textbox(label="創建結果")

                                # Logic
                                def refresh_tool_choices():
                                    return gr.update(choices=get_all_tool_names())
                                
                                def update_toolset_dropdown():
                                    return gr.update(choices=get_toolset_choices())

                                refresh_toolsets_btn.click(list_toolsets, outputs=toolsets_table)
                                refresh_ts_select_btn.click(update_toolset_dropdown, outputs=selected_toolset_id)
                                
                                delete_toolset_btn.click(
                                    delete_toolset,
                                    inputs=[selected_toolset_id],
                                    outputs=[toolset_op_msg]
                                ).then(list_toolsets, outputs=toolsets_table)
                                
                                create_ts_btn.click(
                                    create_toolset,
                                    inputs=[ts_name, ts_desc, ts_tools, ts_global],
                                    outputs=[create_ts_msg]
                                ).then(list_toolsets, outputs=toolsets_table)
                                
                                # Init
                                demo.load(list_toolsets, outputs=toolsets_table)
                                demo.load(refresh_tool_choices, outputs=ts_tools)
                                demo.load(update_toolset_dropdown, outputs=selected_toolset_id)


                    # Sub-tab 2.4: 產業數據管理 (Renamed from Entities)
                    with gr.TabItem("🏦 產業數據管理 (Industry Data)"):
                        gr.Markdown("""
                        管理辯手可使用的內部實體數據（如公司、證券、術語、產業關係）。這些數據通過 `internal.*` 工具暴露給辯手。
                        """)
                        
                        # --- Status Bar ---
                        with gr.Row(variant="panel"):
                            update_status_md = gr.Markdown("檢查更新狀態...")
                            update_btn = gr.Button("🚀 立即更新產業資料")
                        
                        def check_update_status():
                            last_update, is_old = get_company_update_status()
                            msg = f"### 📅 資料最後更新: {last_update}"
                            if is_old:
                                msg += "\n\n⚠️ **資料已超過 90 天未更新，建議立即更新！**"
                            else:
                                msg += "\n\n✅ 資料尚新。"
                            return msg

                        demo.load(check_update_status, outputs=update_status_md)
                        update_btn.click(trigger_company_update, outputs=None).then(
                            lambda: "🔄 更新中... 請稍後刷新頁面查看時間。", outputs=update_status_md
                        )

                        with gr.Tabs():
                            # 1. 產業地圖 (Moved from Tab 3)
                            with gr.TabItem("🗺️ 產業地圖"):
                                with gr.Row():
                                    sector_select = gr.Dropdown(label="選擇產業 (Sector)", choices=[], allow_custom_value=True)
                                    refresh_tree_btn = gr.Button("🔄 刷新地圖")
                                
                                tree_view = gr.JSON(label="產業結構樹 (Sector -> Stream -> Companies)")
                                
                                def update_sector_choices():
                                    return gr.update(choices=get_sector_choices())
                                
                                def load_tree(sector):
                                    if not sector:
                                        return {"info": "請選擇一個產業以檢視結構圖 (Select a sector to view details)"}
                                    
                                    # Optimization: Fetch only when needed
                                    full_tree = get_industry_tree_data()
                                    return {sector: full_tree.get(sector, {})}
                                
                                refresh_tree_btn.click(update_sector_choices, outputs=sector_select).then(
                                    load_tree, inputs=[sector_select], outputs=tree_view
                                )
                                sector_select.change(load_tree, inputs=[sector_select], outputs=tree_view)
                                
                                # Init choices
                                demo.load(update_sector_choices, outputs=sector_select)

                            # 2. 公司管理 (Merged: Create + Filter/List)
                            with gr.TabItem("🏢 公司管理"):
                                with gr.Row():
                                    # Left: Create
                                    with gr.Column(scale=1):
                                        gr.Markdown("### 新增公司")
                                        company_id = gr.Textbox(label="公司 ID (統編/GUID)", placeholder="12345678")
                                        company_name = gr.Textbox(label="公司名稱", placeholder="台積電")
                                        company_ticker = gr.Textbox(label="股票代碼", placeholder="2330")
                                        company_sector = gr.Textbox(label="產業類別", placeholder="半導體")
                                        company_mcap = gr.Number(label="市值 (億)", precision=2)
                                        
                                        create_company_btn = gr.Button("新增", variant="primary")
                                        create_company_output = gr.Textbox(label="結果")
                                    
                                    # Right: List & Filter
                                    with gr.Column(scale=2):
                                        gr.Markdown("### 公司列表")
                                        with gr.Row():
                                            filter_sector = gr.Dropdown(label="篩選產業", choices=[], allow_custom_value=True)
                                            filter_group = gr.Dropdown(label="篩選環節 (Stream)", choices=["上游", "中游", "下游"], allow_custom_value=True)
                                            filter_sub = gr.Textbox(label="篩選子產業")
                                            refresh_list_btn = gr.Button("🔍 搜尋 / 刷新")

                                        companies_table = gr.DataFrame(headers=["ID", "Name", "Ticker", "Sector", "Group", "Sub-industry"], wrap=True)
                                
                                # Actions
                                def update_list(sec, grp, sub):
                                    return list_companies(sec, grp, sub)
                                    
                                def update_filter_choices():
                                    return gr.update(choices=get_sector_choices())

                                create_company_btn.click(
                                    create_company,
                                    inputs=[company_id, company_name, company_ticker, company_sector, company_mcap],
                                    outputs=create_company_output
                                ).then(
                                    update_list, inputs=[filter_sector, filter_group, filter_sub], outputs=companies_table
                                )
                                
                                refresh_list_btn.click(
                                    update_list,
                                    inputs=[filter_sector, filter_group, filter_sub],
                                    outputs=companies_table
                                )
                                
                                # Init
                                demo.load(update_filter_choices, outputs=filter_sector)
                                demo.load(update_list, inputs=[filter_sector, filter_group, filter_sub], outputs=companies_table)

                            # 3. 證券管理 (Existing)
                            with gr.TabItem("📈 證券管理"):
                                with gr.Row():
                                    with gr.Column(scale=1):
                                        gr.Markdown("### 新增證券")
                                        sec_id = gr.Textbox(label="證券 ID (ISIN/GUID)", placeholder="US0378331005")
                                        sec_name = gr.Textbox(label="證券名稱", placeholder="Apple Inc. Common Stock")
                                        sec_type = gr.Dropdown(choices=["Stock", "Bond", "ETF", "Fund", "Option"], label="證券類型", value="Stock")
                                        sec_issuer = gr.Textbox(label="發行公司 ID", placeholder="Optional")
                                        sec_ticker = gr.Textbox(label="Ticker / 代碼", placeholder="AAPL")
                                        sec_isin = gr.Textbox(label="ISIN", placeholder="Optional")
                                        sec_mcap = gr.Number(label="市值 (億)", precision=2)
                                        
                                        create_sec_btn = gr.Button("新增證券", variant="primary")
                                        create_sec_output = gr.Textbox(label="結果")
                                    
                                    with gr.Column(scale=2):
                                        gr.Markdown("### 證券列表")
                                        refresh_sec_btn = gr.Button("刷新")
                                        sec_table = gr.DataFrame(headers=["ID", "Name", "Ticker", "Type", "Issuer ID"], wrap=True)
                                
                                create_sec_btn.click(
                                    create_security,
                                    inputs=[sec_id, sec_name, sec_type, sec_issuer, sec_ticker, sec_isin, sec_mcap],
                                    outputs=create_sec_output
                                ).then(list_securities, outputs=sec_table)
                                
                                refresh_sec_btn.click(list_securities, outputs=sec_table)
                                demo.load(list_securities, outputs=sec_table)

                            # 4. 金融術語管理 (Existing)
                            with gr.TabItem("📚 金融術語管理"):
                                gr.Markdown("### 編輯金融術語 (Balance Sheet, Income Statement, Cash Flow)")
                                with gr.Row():
                                    with gr.Column(scale=2):
                                        gr.Markdown("### 術語列表")
                                        refresh_terms_btn = gr.Button("🔄 刷新")
                                        terms_table = gr.DataFrame(headers=["ID", "Name (ZH)", "Definition (EN)", "Category"], wrap=True, interactive=False)
                                    
                                    with gr.Column(scale=1):
                                        gr.Markdown("### 編輯選中術語")
                                        with gr.Row():
                                            edit_term_id = gr.Dropdown(label="選擇術語", choices=[], interactive=True, scale=3, allow_custom_value=True)
                                            refresh_term_select_btn = gr.Button("🔄", scale=1)
                                        
                                        edit_term_name = gr.Textbox(label="中文名稱 (Name)")
                                        edit_term_def = gr.Textbox(label="英文對照 (Definition)")
                                        edit_term_cat = gr.Dropdown(choices=["Balance Sheet", "Income Statement", "Cash Flow"], label="類別 (Category)", allow_custom_value=True)
                                        
                                        save_term_btn = gr.Button("💾 保存修改", variant="primary")
                                        term_op_msg = gr.Textbox(label="操作結果")

                                def update_term_dropdown():
                                    return gr.update(choices=get_financial_term_choices())

                                # Load term details when selected
                                def load_term_details(term_id):
                                    try:
                                        term_id = extract_id_from_dropdown(term_id)
                                        response = requests.get(f"{API_URL}/internal/financial_terms")
                                        terms = response.json()
                                        for t in terms:
                                            if t['term_id'] == term_id:
                                                return t['term_name'], t.get('definition', ''), t.get('term_category', '')
                                    except:
                                        pass
                                    return "", "", ""

                                refresh_terms_btn.click(list_financial_terms, outputs=terms_table)
                                refresh_term_select_btn.click(update_term_dropdown, outputs=edit_term_id)
                                
                                edit_term_id.change(
                                    load_term_details,
                                    inputs=[edit_term_id],
                                    outputs=[edit_term_name, edit_term_def, edit_term_cat]
                                )

                                save_term_btn.click(
                                    update_financial_term,
                                    inputs=[edit_term_id, edit_term_name, edit_term_def, edit_term_cat],
                                    outputs=[term_op_msg]
                                ).then(list_financial_terms, outputs=terms_table)
                                
                                demo.load(list_financial_terms, outputs=terms_table)
                                demo.load(update_term_dropdown, outputs=edit_term_id)

            # ==============================
            # Tab 4: 📝 提示詞控制台 (Prompt Console)
            # ==============================
            with gr.TabItem("📝 提示詞控制台"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 編輯提示詞")
                        with gr.Row():
                            prompt_key_dropdown = gr.Dropdown(
                                label="選擇模板 (或手動輸入 Key)",
                                choices=[],
                                allow_custom_value=True,
                                scale=3
                            )
                            refresh_prompt_select_btn = gr.Button("🔄", scale=1)
                        
                        prompt_content_area = gr.TextArea(label="提示詞內容", lines=20, placeholder="選擇模板後載入，或直接輸入...")
                        save_prompt_btn = gr.Button("💾 保存設定", variant="primary")
                        save_output = gr.Textbox(label="保存結果")

                    with gr.Column(scale=1):
                        gr.Markdown("### 現有提示詞列表")
                        refresh_prompts_btn = gr.Button("🔄 刷新列表")
                        prompts_table = gr.DataFrame(wrap=True)

                def update_prompt_dropdown():
                    return gr.update(choices=get_all_prompt_keys())

                refresh_prompt_select_btn.click(update_prompt_dropdown, outputs=prompt_key_dropdown)

                prompt_key_dropdown.change(
                    get_prompt_content,
                    inputs=[prompt_key_dropdown],
                    outputs=[prompt_content_area]
                )
                
                save_prompt_btn.click(
                    update_prompt_content,
                    inputs=[prompt_key_dropdown, prompt_content_area],
                    outputs=[save_output]
                ).then(list_prompts, outputs=prompts_table)
                
                refresh_prompts_btn.click(list_prompts, outputs=prompts_table)
                demo.load(list_prompts, outputs=prompts_table)
                demo.load(update_prompt_dropdown, outputs=prompt_key_dropdown)
            
            # ==============================
            # Tab 5: 📜 歷史復盤 (History Replay)
            # ==============================
            with gr.TabItem("📜 歷史復盤"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 選擇歷史辯論")
                        replay_file_dropdown = gr.Dropdown(label="報告文件 (.md)", choices=[])
                        refresh_replays_btn = gr.Button("🔄 刷新列表")
                        
                        gr.Markdown("### 操作")
                        load_replay_btn = gr.Button("📖 讀取報告", variant="primary")
                        download_file = gr.File(label="下載報告", interactive=False)

                    with gr.Column(scale=3):
                        gr.Markdown("### 報告內容")
                        replay_viewer = gr.Markdown(label="報告預覽", height=800)

                # Event Handlers
                def update_replay_list():
                    return gr.update(choices=list_replays())
                
                refresh_replays_btn.click(update_replay_list, outputs=replay_file_dropdown)
                
                def on_load_replay(filename):
                    content = get_replay_markdown(filename)
                    if not content or content == "Error loading replay.":
                        return "無法讀取報告。", None
                        
                    # Save to temp file for download
                    tmp_path = f"/tmp/{filename}"
                    try:
                        with open(tmp_path, "w", encoding="utf-8") as f:
                            f.write(content)
                        return content, tmp_path
                    except Exception as e:
                        print(f"Error writing temp file: {e}")
                        return content, None
                
                load_replay_btn.click(
                    on_load_replay,
                    inputs=[replay_file_dropdown],
                    outputs=[replay_viewer, download_file]
                )
                
                # Init list
                demo.load(update_replay_list, outputs=replay_file_dropdown)
            
            # ==============================
            # Tab 6: ⚙️ 系統設置 (Settings)
            # ==============================
            with gr.TabItem("⚙️ 系統設置"):
                gr.Markdown("### 系統環境變數設置 (.env)")
                gr.Markdown("*直接編輯表格中的「數值 (Value)」欄位，然後點擊保存。*")
                
                with gr.Row():
                    refresh_config_btn = gr.Button("🔄 刷新配置")
                    save_config_btn = gr.Button("💾 保存所有修改", variant="primary")
                
                sys_config_df = gr.DataFrame(
                    headers=["配置項 (Key)", "數值 (Value)", "說明 (Description)"],
                    datatype=["str", "str", "str"],
                    col_count=(3, "fixed"),
                    interactive=True,
                    wrap=True
                )
                
                config_msg = gr.Textbox(label="操作結果")
                
                def load_config_data():
                    try:
                        # Fetch from backend which returns list of dicts
                        response = requests.get(f"{API_URL}/internal/config")
                        data = response.json()
                        # Convert to List of Lists for Dataframe
                        df_data = []
                        for item in data:
                            df_data.append([item["key"], item["value"], item["description"]])
                        return df_data
                    except Exception as e:
                        print(f"Error loading config: {e}")
                        return []

                def save_config_data(df):
                    try:
                        # df is a pandas DataFrame or list of lists depending on gradio version/config
                        success_count = 0
                        
                        # Iterate rows (handle both dataframe and list)
                        if hasattr(df, 'iterrows'):
                            iterator = df.iterrows()
                        else:
                            iterator = df

                        for item in iterator:
                            if hasattr(df, 'iterrows'):
                                _, row = item
                                key = row[0]
                                value = row[1]
                            else:
                                key = item[0]
                                value = item[1]
                                
                            try:
                                requests.post(f"{API_URL}/internal/config", json={"key": key, "value": str(value)})
                                success_count += 1
                            except:
                                pass
                        
                        return f"成功保存 {success_count} 項配置！(部分設定需重啟生效)"
                    except Exception as e:
                        return f"保存失敗: {e}"

                refresh_config_btn.click(load_config_data, outputs=sys_config_df)
                
                save_config_btn.click(
                    save_config_data,
                    inputs=[sys_config_df],
                    outputs=[config_msg]
                ).then(load_config_data, outputs=sys_config_df)
                
                # Init
                demo.load(load_config_data, outputs=sys_config_df)

    return demo

if __name__ == "__main__":
    print("🚀 Starting Web App initialization...", flush=True)
    try:
        # Preload core data before starting the app (Best effort)
        try:
            preload_core_data()
        except Exception as e:
            print(f"⚠️ Warning: Core data preload failed: {e}", flush=True)
            print("   The app will still start, but initial data may be missing.", flush=True)
        
        demo = main()
        # Enable queue for SSE
        demo.queue(max_size=20).launch(
            server_name="0.0.0.0",
            server_port=7860,
            show_error=True
        )
    except Exception as e:
        print(f"❌ FATAL ERROR starting Web App: {e}", flush=True)
        import traceback
        traceback.print_exc()
