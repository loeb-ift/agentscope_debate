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
    if cache and cache["data"] is not None and (now - cache["timestamp"]) < CACHE_TTL:
        print(f"DEBUG: Using cached {cache_key}", flush=True)  # noqa
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
    max_retries = 10
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
    try:
        # Extract IDs
        chairman_id = extract_id_from_dropdown(chairman_id)
        
        # Resolve Team IDs to Agent IDs
        pro_agents = get_team_members(pro_team_id)
        con_agents = get_team_members(con_team_id)
        neutral_agents = get_team_members(neutral_team_id) if neutral_team_id else []

        if not pro_agents or not con_agents:
            return "錯誤: 必須選擇正方與反方團隊，且團隊必須包含成員。", None

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
        
        config_res = requests.post(f"{API_URL}/debates/config", json=config_payload)
        config_res.raise_for_status()
        config_id = config_res.json()["id"]
        
        launch_res = requests.post(f"{API_URL}/debates/launch?config_id={config_id}")
        launch_res.raise_for_status()
        
        return f"辯論已啟動！任務 ID: {launch_res.json()['task_id']}", launch_res.json()['task_id'], "⏳ 正在初始化辯論環境..."
        
    except Exception as e:
        return f"啟動失敗: {e}", None, f"啟動失敗: {e}"

def stream_debate_log(task_id):
    if not task_id:
        yield "無任務 ID", "❌ 無效的任務 ID"
        return

    try:
        # Initial status
        yield "", "🚀 連接辯論串流..."

        # Use requests with stream=True for robust SSE handling
        with requests.get(f"{API_URL}/debates/{task_id}/stream", stream=True) as response:
            history_md = ""
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith("data: "):
                        json_str = decoded_line[6:] # Removing "data: " prefix
                        # print(f"DEBUG STREAM: {json_str[:100]}...", flush=True)
                        if json_str.strip() == "[DONE]":
                            yield history_md, "🏁 辯論已圓滿結束。"
                            break
                        try:
                            data = json.loads(json_str)
                            
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
                                history_md += entry
                                yield history_md, f"⚖️ 評分更新: {side} {delta_str}"
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
                            history_md += entry
                            
                            yield history_md, status_msg
                        except json.JSONDecodeError:
                            pass
    except Exception as e:
        yield f"**Error connecting to stream:** {str(e)}", f"❌ 連線錯誤: {str(e)}"

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

def create_custom_tool(name, tool_type, url, method, headers_json, python_code, schema_json, group):
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
    try:
        response = requests.get(f"{API_URL}/tools")
        response.raise_for_status()
        tools = response.json()
        return [(f"{t['name']} ({t['id']})", t['id']) for t in tools]
    except:
        return []

def list_companies():
    try:
        response = requests.get(f"{API_URL}/internal/companies")
        response.raise_for_status()
        companies = response.json()
        
        data = []
        for c in companies:
            data.append([c['company_id'], c['company_name'], c['ticker_symbol'], c['industry_sector']])
        
        if not data:
             return pd.DataFrame(columns=["ID", "Name", "Ticker", "Sector"])
        
        return pd.DataFrame(data, columns=["ID", "Name", "Ticker", "Sector"])
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
    try:
        response = requests.get(f"{API_URL}/replays")
        response.raise_for_status()
        replays = response.json()
        return [r['filename'] for r in replays]
    except:
        return []

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
        return list(tools.keys())
    except:
        return []

def get_all_prompt_keys():
    try:
        response = requests.get(f"{API_URL}/prompts")
        response.raise_for_status()
        prompts = response.json()
        return [p['key'] for p in prompts]
    except:
        return []

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
    try:
        response = requests.get(f"{API_URL}/toolsets")
        response.raise_for_status()
        toolsets = response.json()
        return [(f"{ts['name']} ({ts['id']})", ts['id']) for ts in toolsets]
    except:
        return []

def get_financial_term_choices():
    try:
        response = requests.get(f"{API_URL}/internal/financial_terms")
        response.raise_for_status()
        terms = response.json()
        return [(f"{t['term_name']} ({t['term_id']})", t['term_id']) for t in terms]
    except:
        return []

def get_system_config():
    try:
        response = requests.get(f"{API_URL}/config")
        return response.json()
    except:
        return {}

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
        gr.Markdown("# 🤖 AI 辯論平台管理系統")
        
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

                                # Step 4 removed

                            # Right Column: Live Status (Always Visible)
                            with gr.Column(scale=2):
                                gr.Markdown("### 📺 實時戰況")
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
                            refresh_dropdowns,
                            outputs=[chairman_dropdown, pro_team_dropdown, con_team_dropdown, neutral_team_dropdown],
                            show_progress=True
                        ).then(
                            go_to_step2,
                            inputs=[topic_input],
                            outputs=[step1_group, step2_group, step3_group]
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
                            outputs=[live_log, debate_status_output]
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
                                agent_config = gr.Code(label="設定 (JSON)", language="json", value="{}")
                                
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
                                
                                with gr.Row():
                                    cancel_team_btn = gr.Button("⬅️ 取消 / 返回列表")
                                    save_team_btn = gr.Button("💾 保存團隊", variant="primary")
                                
                                save_team_msg = gr.Textbox(label="保存結果")

                                # Logic
                                def update_team_dropdown():
                                    return gr.update(choices=get_team_choices())
                                
                                def update_member_dropdown():
                                    return gr.update(choices=get_agent_choices())

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
                                data = res.json()
                                return pd.DataFrame.from_dict(data, orient='index')
                            except:
                                return pd.DataFrame()
                        
                        tools_df = gr.DataFrame()
                        refresh_tools_btn = gr.Button("刷新工具")
                        refresh_tools_btn.click(get_tools_df, outputs=tools_df)
                        demo.load(get_tools_df, outputs=tools_df)
                    
                    # Sub-tab 2.2: 編輯/管理工具
                    with gr.TabItem("✏️ 編輯/管理工具", id="tool_edit_tab"):
                        tool_id_state = gr.State(value=None)
                        
                        with gr.Row():
                            select_tool_dropdown = gr.Dropdown(label="選擇要編輯的工具", choices=[], scale=2, allow_custom_value=True)
                            refresh_tool_select_btn = gr.Button("🔄 刷新", scale=0)
                            load_tool_btn = gr.Button("📂 載入設定", scale=1)
                        
                        gr.Markdown("---")
                        
                        with gr.Row():
                            edit_tool_name = gr.Textbox(label="工具名稱 (Name)", placeholder="e.g., tej.stock_price")
                            edit_tool_type = gr.Dropdown(choices=["api", "http", "python"], label="工具類型 (Type)")
                            edit_tool_group = gr.Dropdown(choices=["tej", "user_defined", "browser_use", "financial_data"], label="工具組 (Group)", allow_custom_value=True)
                        
                        edit_tool_desc = gr.TextArea(label="工具描述 (Description)", lines=3)
                        
                        with gr.Accordion("詳細配置 (JSON)", open=True):
                            edit_tool_schema = gr.Code(label="JSON Schema", language="json", value="{}")
                            edit_tool_openapi = gr.Code(label="OpenAPI Spec", language="json", value="{}")
                            edit_tool_config = gr.Code(label="API Config (HTTP Only)", language="json", value="{}")
                            edit_tool_code = gr.Code(label="Python Code (Python Only)", language="python", value="")
                        
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
                                tool_name = gr.Textbox(label="工具名稱", placeholder="e.g., my_tool")
                                tool_type = gr.Dropdown(choices=["http", "python"], label="工具類型", value="http")
                                tool_group = gr.Dropdown(choices=["user_defined", "browser_use", "financial_data", "data_analysis"], label="工具組", value="user_defined", allow_custom_value=True)
                                tool_schema = gr.Code(label="參數 Schema (JSON Schema)", language="json", value='{"type": "object", "properties": {"q": {"type": "string"}}}')
                                
                                with gr.Group(visible=True) as http_config_group:
                                    tool_url = gr.Textbox(label="API URL", placeholder="https://api.example.com/data")
                                    tool_method = gr.Dropdown(choices=["GET", "POST"], label="HTTP Method", value="GET")
                                    tool_headers = gr.Code(label="Headers (JSON)", language="json", value='{}')

                                with gr.Group(visible=False) as python_config_group:
                                    tool_python_code = gr.Code(label="Python Code", language="python", value='def main(arg1):\n    return f"Hello {arg1}"')

                                tool_description = gr.Textbox(label="工具描述 (可自動生成)")
                                with gr.Row():
                                    generate_desc_btn = gr.Button("✨ 自動生成描述")
                                    load_tej_tpl_btn = gr.Button("📥 載入 TEJ 範例模板")

                                # Try-it 區塊
                                gr.Markdown("#### 🔬 Try it 測試 (不入庫)")
                                data_path = gr.Dropdown(choices=["auto", "data", "datatable.data", "items", "results"], value="auto", label="資料路徑")
                                try_params = gr.Code(label="測試參數 Params (JSON)", language="json", value='{}')
                                try_headers = gr.Code(label="附加 Headers (JSON)", language="json", value='{}')  # 目前僅展示，後端以 tool_headers 為主
                                try_status = gr.Markdown(value="")
                                try_btn = gr.Button("▶️ Try it", variant="primary")
                                preview_table = gr.DataFrame(label="預覽資料", wrap=True)

                                add_custom_tool_btn = gr.Button("➕ 新增工具", variant="primary")
                                add_custom_tool_output = gr.Textbox(label="新增結果")

                                def update_visibility(type_val):
                                    return (gr.update(visible=(type_val=="http")),
                                            gr.update(visible=(type_val=="python")))

                                tool_type.change(fn=update_visibility, inputs=tool_type, outputs=[http_config_group, python_config_group])

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

                        add_custom_tool_btn.click(
                            create_custom_tool,
                            inputs=[tool_name, tool_type, tool_url, tool_method, tool_headers, tool_python_code, tool_schema, tool_group],
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


                    # Sub-tab 2.4: 實體管理
                    with gr.TabItem("🏦 實體管理 (Entities)"):
                        gr.Markdown("""
                        管理辯手可使用的內部實體數據（如公司、金融商品）。這些數據通過 `internal.*` 工具暴露給辯手。
                        """)
                        
                        with gr.Tabs():
                            with gr.TabItem("🏢 公司管理"):
                                with gr.Row():
                                    with gr.Column(scale=1):
                                        gr.Markdown("### 新增公司")
                                        company_id = gr.Textbox(label="公司 ID (統編/GUID)", placeholder="12345678")
                                        company_name = gr.Textbox(label="公司名稱", placeholder="台積電")
                                        company_ticker = gr.Textbox(label="股票代碼", placeholder="2330")
                                        company_sector = gr.Textbox(label="產業類別", placeholder="半導體")
                                        company_mcap = gr.Number(label="市值 (億)", precision=2)
                                        
                                        create_company_btn = gr.Button("新增", variant="primary")
                                        create_company_output = gr.Textbox(label="結果")
                                    
                                    with gr.Column(scale=2):
                                        gr.Markdown("### 公司列表")
                                        refresh_companies_btn = gr.Button("刷新")
                                        companies_table = gr.DataFrame(headers=["ID", "Name", "Ticker", "Sector"], wrap=True)
                                
                                create_company_btn.click(
                                    create_company,
                                    inputs=[company_id, company_name, company_ticker, company_sector, company_mcap],
                                    outputs=create_company_output
                                ).then(list_companies, outputs=companies_table)
                                
                                refresh_companies_btn.click(list_companies, outputs=companies_table)
                                demo.load(list_companies, outputs=companies_table)

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
            # Tab 3: 📝 提示詞控制台 (Prompt Console)
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
            # Tab 4: 📜 歷史復盤 (History Replay)
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
            # Tab 5: ⚙️ 系統設置 (Settings)
            # ==============================
            with gr.TabItem("⚙️ 系統設置"):
                gr.Markdown("### 系統環境變數設置 (.env)")
                gr.Markdown("*修改後設定將寫入 .env 文件，部分設定可能需要重啟容器生效。*")
                
                with gr.Row():
                    config_key = gr.Dropdown(
                        label="配置項", 
                        choices=["MAX_TEAMS_PER_DEBATE", "MAX_MEMBERS_PER_TEAM", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"],
                        allow_custom_value=True
                    )
                    config_value = gr.Textbox(label="設定值")
                    save_config_btn = gr.Button("💾 保存設定", variant="primary")
                
                config_msg = gr.Textbox(label="操作結果")
                
                save_config_btn.click(
                    update_system_config,
                    inputs=[config_key, config_value],
                    outputs=[config_msg]
                )

    return demo

if __name__ == "__main__":
    # Preload core data before starting the app
    preload_core_data()
    
    demo = main()
    demo.queue().launch(server_name="0.0.0.0", server_port=7860)

