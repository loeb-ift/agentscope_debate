import gradio as gr
import requests
import json
import sseclient
import pandas as pd
import time

API_URL = "http://api:8000/api/v1"

# --- Helper Functions ---

def extract_id_from_dropdown(value):
    """Helper to extract ID if value is in 'Name (ID)' format"""
    if not value: return None
    value = str(value)
    if "(" in value and value.endswith(")"):
        return value.split("(")[-1].strip(")")
    return value

def get_agents(role=None):
    try:
        params = {"role": role} if role else {}
        response = requests.get(f"{API_URL}/agents", params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching agents: {e}")
        return []

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
    return [(f"{a['name']} ({a['role']})", a['id']) for a in agents]

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
        
        return f"辯論已啟動！任務 ID: {launch_res.json()['task_id']}", launch_res.json()['task_id']
        
    except Exception as e:
        return f"啟動失敗: {e}", None

def stream_debate_log(task_id):
    if not task_id:
        yield "無任務 ID"
        return

    try:
        client = sseclient.SSEClient(f"{API_URL}/debates/{task_id}/stream")
        history_md = ""
        
        for event in client.events():
            try:
                data = json.loads(event.data)
                role = data.get("role", "System")
                content = data.get("content", "")
                
                icon = "📢"
                if "Chairman" in role: icon = "👨‍⚖️"
                elif "Pro" in role or "正方" in role: icon = "🟦"
                elif "Con" in role or "反方" in role: icon = "🟥"
                elif "Neutral" in role or "中立" in role: icon = "🟩"
                elif "Tool" in role: icon = "🛠️"
                elif "System" in role: icon = "🖥️"
                
                entry = f"\n\n### {icon} {role}\n{content}\n\n---"
                history_md += entry
                
                yield history_md
            except json.JSONDecodeError:
                pass
    except Exception as e:
        yield f"**Error connecting to stream:** {str(e)}"

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
        response = requests.get(f"{API_URL}/internal/securities")
        response.raise_for_status()
        securities = response.json()
        
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
        response = requests.get(f"{API_URL}/internal/financial_terms")
        response.raise_for_status()
        terms = response.json()
        
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
        response = requests.get(f"{API_URL}/toolsets")
        response.raise_for_status()
        toolsets = response.json()
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
        teams = teams_res.json()
        
        # Fetch agents to map IDs to Names
        agents_res = requests.get(f"{API_URL}/agents")
        agents_res.raise_for_status()
        agents = agents_res.json()
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
    try:
        response = requests.get(f"{API_URL}/teams")
        response.raise_for_status()
        teams = response.json()
        return [(f"{t['name']} ({t['id']})", t['id']) for t in teams]
    except:
        return []

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
                        current_step = gr.State(1)
                        
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
                                    with gr.Group():
                                        pro_team_dropdown = gr.Dropdown(label="團隊 A (正方/主要視角) - 選擇團隊", multiselect=False, choices=[])
                                    with gr.Group():
                                        con_team_dropdown = gr.Dropdown(label="團隊 B (反方/對立視角) - 選擇團隊", multiselect=False, choices=[])
                                    with gr.Group():
                                        neutral_team_dropdown = gr.Dropdown(label="團隊 C (中立/第三視角) - 選擇團隊", multiselect=False, choices=[])
                                    with gr.Row():
                                        step3_back_btn = gr.Button("⬅️ 上一步")
                                        step3_next_btn = gr.Button("下一步: 確認並啟動 ➡️", variant="primary")

                                # Step 4: Review
                                with gr.Group(visible=False) as step4_group:
                                    gr.Markdown("### 步驟 4/4: 確認配置")
                                    config_summary = gr.JSON(label="配置摘要")
                                    start_debate_btn = gr.Button("🚀 確認並啟動辯論", variant="primary", size="lg")
                                    step4_back_btn = gr.Button("⬅️ 修改配置")
                                    debate_status_output = gr.Textbox(label="啟動狀態")
                                    task_id_state = gr.State()

                            # Right Column: Live Status (Always Visible)
                            with gr.Column(scale=2):
                                gr.Markdown("### 📺 實時戰況")
                                live_log = gr.Markdown(label="辯論日誌串流", value="等待啟動...", height=600)

                        # --- Wizard Logic ---
                        def refresh_dropdowns():
                            chairmen = get_agent_choices() # Allow any agent to be Chairman
                            teams = get_team_choices()
                            return (
                                gr.Dropdown(choices=chairmen),
                                gr.Dropdown(choices=teams),
                                gr.Dropdown(choices=teams),
                                gr.Dropdown(choices=teams)
                            )

                        def go_to_step1(): return (gr.Group(visible=True), gr.Group(visible=False), gr.Group(visible=False), gr.Group(visible=False))
                        def go_to_step2(topic):
                            if not topic: return (gr.Group(visible=True), gr.Group(visible=False), gr.Group(visible=False), gr.Group(visible=False))
                            return (gr.Group(visible=False), gr.Group(visible=True), gr.Group(visible=False), gr.Group(visible=False))
                        def go_to_step3(chairman):
                            if not chairman: return (gr.Group(visible=False), gr.Group(visible=True), gr.Group(visible=False), gr.Group(visible=False))
                            return (gr.Group(visible=False), gr.Group(visible=False), gr.Group(visible=True), gr.Group(visible=False))
                        def go_to_step4(topic, rounds, chairman, pro, con, neutral):
                            summary = {
                                "Topic": topic,
                                "Rounds": rounds,
                                "Chairman": chairman,
                                "Team A": pro,
                                "Team B": con,
                                "Team C": neutral
                            }
                            return (gr.Group(visible=False), gr.Group(visible=False), gr.Group(visible=False), gr.Group(visible=True), summary)

                        step1_next_btn.click(go_to_step2, inputs=[topic_input], outputs=[step1_group, step2_group, step3_group, step4_group])
                        step2_back_btn.click(go_to_step1, outputs=[step1_group, step2_group, step3_group, step4_group])
                        step2_next_btn.click(go_to_step3, inputs=[chairman_dropdown], outputs=[step1_group, step2_group, step3_group, step4_group])
                        step3_back_btn.click(go_to_step2, inputs=[topic_input], outputs=[step1_group, step2_group, step3_group, step4_group])
                        step3_next_btn.click(go_to_step4, 
                            inputs=[topic_input, rounds_slider, chairman_dropdown, pro_team_dropdown, con_team_dropdown, neutral_team_dropdown],
                            outputs=[step1_group, step2_group, step3_group, step4_group, config_summary]
                        )
                        step4_back_btn.click(go_to_step3, inputs=[chairman_dropdown], outputs=[step1_group, step2_group, step3_group, step4_group])

                        refresh_roles_btn.click(refresh_dropdowns, outputs=[chairman_dropdown, pro_team_dropdown, con_team_dropdown, neutral_team_dropdown])
                        step1_next_btn.click(refresh_dropdowns, outputs=[chairman_dropdown, pro_team_dropdown, con_team_dropdown, neutral_team_dropdown])

                        start_debate_btn.click(
                            launch_debate_config,
                            inputs=[topic_input, chairman_dropdown, rounds_slider, pro_team_dropdown, con_team_dropdown, neutral_team_dropdown],
                            outputs=[debate_status_output, task_id_state]
                        ).success(
                            stream_debate_log,
                            inputs=[task_id_state],
                            outputs=[live_log]
                        )
                    
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
                                    json.dumps(data.get('config_json', {}), indent=2)
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
                            return gr.Dropdown(choices=get_agent_choices())

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
                        ).then(format_agent_list, outputs=agents_table)
                        
                        delete_agent_btn.click(
                            delete_agent,
                            inputs=[selected_agent_id_input],
                            outputs=[agent_op_msg]
                        ).then(format_agent_list, outputs=agents_table)

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
                                    return gr.Dropdown(choices=get_team_choices())
                                
                                def update_member_dropdown():
                                    return gr.Dropdown(choices=get_agent_choices())

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
                    
                    # Sub-tab 2.2: 自定義工具註冊
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
                                generate_desc_btn = gr.Button("✨ 自動生成描述")

                                add_custom_tool_btn = gr.Button("➕ 新增工具", variant="primary")
                                add_custom_tool_output = gr.Textbox(label="新增結果")

                                def update_visibility(type_val):
                                    return (gr.Group(visible=(type_val=="http")),
                                            gr.Group(visible=(type_val=="python")))

                                tool_type.change(fn=update_visibility, inputs=tool_type, outputs=[http_config_group, python_config_group])

                            with gr.Column(scale=1):
                                gr.Markdown("### 已註冊自定義工具")
                                refresh_custom_tools_btn = gr.Button("🔄 刷新列表")
                                custom_tools_table = gr.DataFrame(headers=["ID", "Name", "Type", "Group"], wrap=True)

                        def wrap_generate(t_type, py_code, schema):
                            content = py_code if t_type == "python" else schema
                            return generate_description(t_type, content)

                        generate_desc_btn.click(
                            wrap_generate,
                            inputs=[tool_type, tool_python_code, tool_schema],
                            outputs=tool_description
                        )

                        add_custom_tool_btn.click(
                            create_custom_tool,
                            inputs=[tool_name, tool_type, tool_url, tool_method, tool_headers, tool_python_code, tool_schema, tool_group],
                            outputs=add_custom_tool_output
                        ).then(list_custom_tools, outputs=custom_tools_table)
                        
                        refresh_custom_tools_btn.click(list_custom_tools, outputs=custom_tools_table)
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
                                    return gr.Dropdown(choices=get_all_tool_names())

                                def update_toolset_dropdown():
                                    return gr.Dropdown(choices=get_toolset_choices())

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
                                    return gr.Dropdown(choices=get_financial_term_choices())

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
                    return gr.Dropdown(choices=get_all_prompt_keys())

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
                        download_link = gr.Markdown("") # For download link

                    with gr.Column(scale=3):
                        gr.Markdown("### 報告內容")
                        replay_viewer = gr.Markdown(label="報告預覽", height=800)

                # Event Handlers
                def update_replay_list():
                    return gr.Dropdown(choices=list_replays())
                
                refresh_replays_btn.click(update_replay_list, outputs=replay_file_dropdown)
                
                def on_load_replay(filename):
                    content = get_replay_markdown(filename)
                    link = f"[📥 點擊下載原始文件]({get_replay_download_link(filename)})"
                    return content, link
                
                load_replay_btn.click(
                    on_load_replay,
                    inputs=[replay_file_dropdown],
                    outputs=[replay_viewer, download_link]
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
    demo = main()
    demo.queue().launch(server_name="0.0.0.0", server_port=7860)
