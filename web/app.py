import gradio as gr
import requests
import json
import sseclient
import pandas as pd
import time

API_URL = "http://api:8000/api/v1"

# --- Helper Functions ---

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
        # Filter out None/Empty values for partial update if needed
        # But here we assume full update for simplicity in UI
        response = requests.put(f"{API_URL}/agents/{agent_id}", json=payload)
        response.raise_for_status()
        return f"Agent '{name}' updated successfully!"
    except Exception as e:
        return f"Error updating agent: {e}"

def delete_agent(agent_id):
    try:
        response = requests.delete(f"{API_URL}/agents/{agent_id}")
        response.raise_for_status()
        return "Agent deleted successfully!"
    except Exception as e:
        return f"Error deleting agent: {e}"

def get_agent_choices(role=None):
    agents = get_agents(role)
    # Return list of (name, id) tuples for Dropdown
    return [(f"{a['name']} ({a['role']})", a['id']) for a in agents]

def format_agent_list():
    agents = get_agents()
    if not agents:
        return pd.DataFrame(columns=["ID", "Name", "Role", "Specialty"])
    
    data = []
    for a in agents:
        data.append([a['id'], a['name'], a['role'], a.get('specialty', '')])
    return pd.DataFrame(data, columns=["ID", "Name", "Role", "Specialty"])

def launch_debate_config(topic, chairman_id, rounds, pro_agent_ids, con_agent_ids, neutral_agent_ids):
    try:
        # 1. Create Config
        teams = [
            {"name": "正方", "side": "pro", "agent_ids": pro_agent_ids},
            {"name": "反方", "side": "con", "agent_ids": con_agent_ids}
        ]
        if neutral_agent_ids:
             teams.append({"name": "中立/第三方", "side": "neutral", "agent_ids": neutral_agent_ids})
        
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
        
        # 2. Launch Debate
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
                
                # Format log entry
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
            return pd.DataFrame(columns=["key", "language", "version", "content"])
        df = pd.DataFrame(prompts)
        return df[["key", "language", "version", "content"]]
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
        # 嘗試更新
        response = requests.put(f"{API_URL}/prompts/{key}", json={"content": content})
        if response.status_code == 404:
            # 如果不存在則創建
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

# --- UI Construction ---

def main():
    with gr.Blocks(title="AI 辯論平台", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# 🤖 AI 辯論平台管理系統")
        
        with gr.Tabs():
            # Tab 1: Agent Management
            with gr.TabItem("👥 Agent 管理"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 創建/編輯 Agent")
                        agent_id_state = gr.State(value=None) # Store ID for edit mode
                        
                        agent_name = gr.Textbox(label="名稱", placeholder="例如: 邏輯大師")
                        agent_role = gr.Dropdown(choices=["debater", "chairman", "analyst"], label="角色", value="debater")
                        agent_specialty = gr.Textbox(label="專長", placeholder="例如: 經濟學、哲學")
                        agent_prompt = gr.TextArea(label="系統 Prompt", lines=5, placeholder="你是...")
                        agent_config = gr.Code(label="配置 (JSON)", language="json", value="{}")
                        
                        with gr.Row():
                            create_btn = gr.Button("✨ 創建新 Agent", variant="primary")
                            update_btn = gr.Button("💾 保存修改")
                            clear_btn = gr.Button("🧹 清空表單")

                        operation_output = gr.Textbox(label="操作結果")

                    with gr.Column(scale=2):
                        gr.Markdown("### Agent 列表")
                        refresh_agents_btn = gr.Button("🔄 刷新列表")
                        agents_table = gr.DataFrame(
                            headers=["ID", "Name", "Role", "Specialty"],
                            interactive=False,
                            wrap=True
                        )
                        
                        with gr.Row():
                            load_agent_btn = gr.Button("✏️ 載入選中 Agent 進行編輯")
                            delete_agent_btn = gr.Button("🗑️ 刪除選中 Agent", variant="stop")
                        
                        # Helper text input to select agent by ID (workaround for dataframe selection)
                        selected_agent_id_input = gr.Textbox(label="輸入要操作的 Agent ID (從上表複製)")

                # Event Handlers - Agent
                create_btn.click(
                    create_agent,
                    inputs=[agent_name, agent_role, agent_specialty, agent_prompt, agent_config],
                    outputs=operation_output
                ).then(format_agent_list, outputs=agents_table)

                update_btn.click(
                    update_agent,
                    inputs=[selected_agent_id_input, agent_name, agent_role, agent_specialty, agent_prompt, agent_config],
                    outputs=operation_output
                ).then(format_agent_list, outputs=agents_table)

                delete_btn_click = delete_agent_btn.click(
                    delete_agent,
                    inputs=[selected_agent_id_input],
                    outputs=operation_output
                ).then(format_agent_list, outputs=agents_table)

                refresh_agents_btn.click(format_agent_list, outputs=agents_table)
                
                # Load Agent Data
                def load_agent_data(agent_id):
                    try:
                        response = requests.get(f"{API_URL}/agents/{agent_id}")
                        response.raise_for_status()
                        data = response.json()
                        return (
                            data['name'], 
                            data['role'], 
                            data.get('specialty', ''), 
                            data['system_prompt'], 
                            json.dumps(data.get('config_json', {}), indent=2)
                        )
                    except:
                        return "Error", "debater", "", "", "{}"

                load_agent_btn.click(
                    load_agent_data,
                    inputs=[selected_agent_id_input],
                    outputs=[agent_name, agent_role, agent_specialty, agent_prompt, agent_config]
                )

                # Initialize table
                demo.load(format_agent_list, outputs=agents_table)

            # Tab 2: Debate Configuration
            with gr.TabItem("⚔️ 辯論配置"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 1. 基礎設定")
                        topic_input = gr.Textbox(label="辯論主題", placeholder="例如: AI 是否會取代人類？")
                        rounds_slider = gr.Slider(minimum=1, maximum=10, value=3, step=1, label="辯論輪數")
                        
                        gr.Markdown("### 2. 選擇主席")
                        # Need to refresh these dropdowns dynamically
                        chairman_dropdown = gr.Dropdown(label="主席 Agent", choices=[])
                        refresh_roles_btn = gr.Button("🔄 刷新 Agent 選項")

                        gr.Markdown("### 3. 組建團隊")
                        with gr.Group():
                            gr.Markdown("**正方團隊**")
                            pro_team_dropdown = gr.Dropdown(label="選擇正方辯手", multiselect=True, choices=[])
                        
                        with gr.Group():
                            gr.Markdown("**反方團隊**")
                            con_team_dropdown = gr.Dropdown(label="選擇反方辯手", multiselect=True, choices=[])
                        
                        with gr.Group():
                            gr.Markdown("**第三方/中立團隊 (可選)**")
                            neutral_team_dropdown = gr.Dropdown(label="選擇中立辯手", multiselect=True, choices=[])

                        start_debate_btn = gr.Button("🚀 啟動辯論", variant="primary", size="lg")
                        debate_status_output = gr.Textbox(label="啟動狀態")
                        task_id_state = gr.State()

                    with gr.Column(scale=2):
                        gr.Markdown("### 📺 實時戰況")
                        live_log = gr.Markdown(label="辯論日誌串流", value="等待啟動...", height=600)
                        # Using Markdown component for readable log

                # Event Handlers - Debate
                def refresh_dropdowns():
                    chairmen = get_agent_choices("chairman")
                    debaters = get_agent_choices("debater")
                    return (
                        gr.Dropdown.update(choices=chairmen),
                        gr.Dropdown.update(choices=debaters),
                        gr.Dropdown.update(choices=debaters),
                        gr.Dropdown.update(choices=debaters)
                    )

                refresh_roles_btn.click(
                    refresh_dropdowns,
                    outputs=[chairman_dropdown, pro_team_dropdown, con_team_dropdown, neutral_team_dropdown]
                )
                
                # Auto-refresh on tab select (workaround using demo load for now)
                # demo.load(refresh_dropdowns, outputs=[chairman_dropdown, pro_team_dropdown, con_team_dropdown])

                start_debate_btn.click(
                    launch_debate_config,
                    inputs=[topic_input, chairman_dropdown, rounds_slider, pro_team_dropdown, con_team_dropdown, neutral_team_dropdown],
                    outputs=[debate_status_output, task_id_state]
                ).success(
                    stream_debate_log,
                    inputs=[task_id_state],
                    outputs=[live_log]
                )

            # Tab 3: Tools (Simplified)
            with gr.TabItem("🛠️ 工具箱"):
                gr.Markdown("API 提供的工具列表")
                def get_tools_df():
                    try:
                        res = requests.get(f"{API_URL}/tools")
                        data = res.json()
                        return pd.DataFrame.from_dict(data, orient='index')
                    except:
                        return pd.DataFrame()
                
                tools_df = gr.DataFrame()
                refresh_tools_btn = gr.Button("刷新工具")
                refresh_tools_btn.click(get_tools_df, outputs=tools_df)
                demo.load(get_tools_df, outputs=tools_df)

            # Tab 4: Prompt Console
            with gr.TabItem("📝 提示詞控制台"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 編輯 Prompt")
                        prompt_key_dropdown = gr.Dropdown(
                            choices=[
                                "chairman.pre_debate_analysis",
                                "chairman.summarize_round",
                                "chairman.summarize_debate",
                                "debater.system_instruction",
                                "debater.tool_instruction",
                                "debate.team_summary_system",
                                "debate.team_summary_user",
                                "debate.tool_selection_system",
                                "debate.tool_selection_user",
                                "debate.history_compression_system",
                                "debate.history_compression_user",
                                "tool.generate_description_system",
                                "tool.generate_description_user"
                            ],
                            label="選擇 Prompt 模板 (或手動輸入 Key)",
                            allow_custom_value=True
                        )
                        prompt_content_area = gr.TextArea(label="Prompt 內容", lines=20, placeholder="選擇模板後載入，或直接輸入...")
                        save_prompt_btn = gr.Button("💾 保存 Prompt", variant="primary")
                        save_output = gr.Textbox(label="保存結果")

                    with gr.Column(scale=1):
                        gr.Markdown("### 現有 Prompt 列表")
                        refresh_prompts_btn = gr.Button("🔄 刷新列表")
                        prompts_table = gr.DataFrame(wrap=True)

                # Event Handlers
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

            # Tab 5: Custom Tools
            with gr.TabItem("🔧 自定義工具"):
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

                        # Dynamic UI Switching
                        def update_visibility(type_val):
                            return (gr.Group.update(visible=(type_val=="http")),
                                    gr.Group.update(visible=(type_val=="python")))

                        tool_type.change(fn=update_visibility, inputs=tool_type, outputs=[http_config_group, python_config_group])

                    with gr.Column(scale=1):
                        gr.Markdown("### 已註冊自定義工具")
                        refresh_custom_tools_btn = gr.Button("🔄 刷新列表")
                        custom_tools_table = gr.DataFrame(headers=["ID", "Name", "Type", "Group"], wrap=True)

                # Event Handlers
                # 根據類型選擇內容來源
                def get_content_for_gen(t_type, py_code, schema):
                    return py_code if t_type == "python" else schema

                generate_desc_btn.click(
                    generate_description,
                    inputs=[tool_type, tool_python_code], # 簡化：目前只傳 Python Code 或 schema 其實有點混亂，應該動態取值
                    # 更好的方式是寫一個 wrapper
                    outputs=tool_description
                )
                
                # 修正 Generate Handler 的 inputs
                # 由於 Gradio 的限制，我們簡單地將兩個都傳進去，函數內部判斷
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

    return demo

if __name__ == "__main__":
    demo = main()
    demo.queue().launch(server_name="0.0.0.0", server_port=7860)
