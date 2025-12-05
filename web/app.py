import gradio as gr
import requests
import gradio as gr
import requests
import json
import sseclient
import pandas as pd

API_URL = "http://api:8000/api/v1"

def create_debate(topic: str, config_json: str):
    """
    創建一個新的辯論，並串流其思考過程。
    """
    try:
        config = json.loads(config_json)
        response = requests.post(f"{API_URL}/debates", json={"topic": topic, "config": config})
        response.raise_for_status()
        
        task_id = response.json()["task_id"]
        
        # 連接到事件串流
        client = sseclient.SSEClient(f"{API_URL}/debates/{task_id}/stream")
        
        for event in client.events():
            try:
                # 解析 JSON 數據
                data = json.loads(event.data)
                yield data
            except json.JSONDecodeError:
                # 如果不是 JSON，直接返回原始數據
                yield event.data

    except requests.exceptions.RequestException as e:
        yield f"API request failed: {e}"
    except json.JSONDecodeError:
        yield "Invalid JSON format for config."

def add_tool(name: str, description: str, config_json: str):
    """
    新增一個工具。
    """
    try:
        config = json.loads(config_json)
        response = requests.post(f"{API_URL}/tools", json={"name": name, "description": description, "config": config})
        response.raise_for_status()
        return "工具新增成功！"
    except requests.exceptions.RequestException as e:
        return f"API request failed: {e}"
    except json.JSONDecodeError:
        return "工具設定的 JSON 格式無效。"

def update_tool(name: str, description: str, config_json: str):
    """
    更新一個現有的工具。
    """
    try:
        config = json.loads(config_json)
        response = requests.put(f"{API_URL}/tools/{name}", json={"description": description, "config": config})
        response.raise_for_status()
        return "工具更新成功！"
    except requests.exceptions.RequestException as e:
        return f"API request failed: {e}"
    except json.JSONDecodeError:
        return "工具設定的 JSON 格式無效。"

def delete_tool(name: str):
    """
    刪除一個工具。
    """
    try:
        response = requests.delete(f"{API_URL}/tools/{name}")
        response.raise_for_status()
        return "工具刪除成功！"
    except requests.exceptions.RequestException as e:
        return f"API request failed: {e}"

def list_tools():
    """
    獲取所有已註冊的工具列表。
    """
    try:
        response = requests.get(f"{API_URL}/tools")
        response.raise_for_status()
        tools = response.json()
        
        # 將工具轉換為 DataFrame 格式
        df = pd.DataFrame.from_dict(tools, orient='index')
        
        # 提取工具名稱列表
        tool_names = list(tools.keys())
        
        return df, tool_names

    except requests.exceptions.RequestException as e:
        return pd.DataFrame({"error": [f"API request failed: {e}"]}), []

def get_debate_replay(task_id: str):
    """
    獲取指定辯論的歷史復盤數據。
    """
    try:
        response = requests.get(f"{API_URL}/debates/{task_id}/replay")
        response.raise_for_status()
        replay_data = response.json()
        return replay_data
    except requests.exceptions.RequestException as e:
        return f"API request failed: {e}"

def list_debates():
    """
    獲取所有已存檔的辯論列表。
    """
    try:
        response = requests.get(f"{API_URL}/debates")
        response.raise_for_status()
        debates = response.json()
        
        # 將辯論轉換為 DataFrame 格式
        df = pd.DataFrame(debates)
        
        # 提取辯論 ID 列表
        debate_ids = [debate["task_id"] for debate in debates]
        
        return df, debate_ids

    except requests.exceptions.RequestException as e:
        return pd.DataFrame({"error": [f"API request failed: {e}"]}), []

def main():
    """
    主函式，用於建立並啟動 Gradio 介面。
    """
    with gr.Blocks(title="AI 辯論平台") as demo:
        gr.Markdown("# AI 辯論平台")
        
        with gr.Tabs():
            with gr.TabItem("辯論大廳"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("## 建立新的辯論")
                        topic_input = gr.Textbox(label="辯論主題")
                        config_input = gr.Code(label="辯論設定 (JSON)", language="json", value='{\n  "pro_team": ["c0a89a80-3292-421b-a481-912a78e1a14a", "b790d2a7-b2e3-4b6e-b62f-1d8f7a9e5b2c"],\n  "con_team": ["c0a89a80-3292-421b-a481-912a78e1a14a", "b790d2a7-b2e3-4b6e-b62f-1d8f7a9e5b2c"],\n  "rounds": 5\n}')
                        create_button = gr.Button("開始辯論")
                    with gr.Column(scale=2):
                        gr.Markdown("## 進行中與歷史辯論")
                        refresh_deates_button = gr.Button("刷新列表")
                        debates_table = gr.DataFrame(headers=["任務 ID", "主題", "狀態"])
                
                gr.Markdown("## 思考流")
                thinking_stream_output = gr.JSON(label="實時日誌")

                create_button.click(
                    fn=create_debate,
                    inputs=[topic_input, config_input],
                    outputs=thinking_stream_output
                )
                
                refresh_deates_button.click(
                    fn=list_debates,
                    outputs=[debates_table]
                )
            
            with gr.TabItem("工具庫"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("## 新增工具")
                        tool_name_input = gr.Textbox(label="工具名稱")
                        tool_description_input = gr.Textbox(label="工具描述")
                        tool_config_input = gr.Code(label="工具設定 (JSON)", language="json")
                        add_tool_button = gr.Button("新增工具")
                        add_tool_output = gr.Textbox(label="新增結果", interactive=False)
                    with gr.Column(scale=2):
                        gr.Markdown("## 現有工具")
                        refresh_tools_button = gr.Button("重新整理")
                        tools_table = gr.DataFrame()
                        
                        gr.Markdown("### 操作工具")
                        selected_tool_dropdown = gr.Dropdown(label="選擇工具")
                        update_tool_button = gr.Button("更新工具")
                        delete_tool_button = gr.Button("刪除工具")
                        tool_operation_output = gr.Textbox(label="操作結果", interactive=False)

                update_tool_button.click(
                    fn=update_tool,
                    inputs=[selected_tool_dropdown, tool_description_input, tool_config_input],
                    outputs=tool_operation_output
                )

                delete_tool_button.click(
                    fn=delete_tool,
                    inputs=selected_tool_dropdown,
                    outputs=tool_operation_output
                )

                add_tool_button.click(
                    fn=add_tool,
                    inputs=[tool_name_input, tool_description_input, tool_config_input],
                    outputs=add_tool_output
                )

                refresh_tools_button.click(
                    fn=list_tools,
                    outputs=[tools_table, selected_tool_dropdown]
                )
            with gr.TabItem("提示詞控制台"):
                gr.Markdown("提示詞控制台的內容將會在這裡呈現。")

            with gr.TabItem("歷史復盤"):
                with gr.Column():
                    gr.Markdown("## 選擇一場辯論進行復盤")
                    replay_debate_dropdown = gr.Dropdown(label="選擇辯論")
                    get_replay_button = gr.Button("觀看復盤")
                    replay_output = gr.JSON(label="辯論紀錄")
                
                get_replay_button.click(
                    fn=get_debate_replay,
                    inputs=replay_debate_dropdown,
                    outputs=replay_output
                )

    demo.launch(server_name="0.0.0.0", server_port=7860)

if __name__ == "__main__":
    main()
