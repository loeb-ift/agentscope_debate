import json
from mars.types.artifact import Task, Evidence, ArtifactType
from mars.tools.tool_wrapper import MarsToolWrapper
from worker.llm_utils import call_llm_async

class ExecutorAgent:
    """
    MARS Executor Agent
    Responsible for executing a specific Task by selecting and calling Tools.
    Produces Evidence artifacts.
    """
    def __init__(self, name: str, role: str, system_prompt_template: str = None, allowed_tools: list = None):
        self.name = name
        self.role = role
        self.tool_wrapper = MarsToolWrapper()
        self.system_prompt_template = system_prompt_template
        self.allowed_tools = allowed_tools

    async def execute_task(self, task: Task) -> Evidence:
        """
        Execute the task and return Evidence.
        """
        print(f"[{self.name}] Executing task: {task.description}")
        
        if self.allowed_tools:
            all_tools = self.tool_wrapper.list_tools()
            available_tools = {k: v for k, v in all_tools.items() if k in self.allowed_tools}
        else:
            available_tools = self.tool_wrapper.list_tools()

        print(f"[{self.name}] Available tools count: {len(available_tools)}") # DEBUG
        
        # Simple categorization for prompt clarity
        tej_tools = {k:v for k,v in available_tools.items() if "tej" in k}
        internal_tools = {k:v for k,v in available_tools.items() if "internal" in k}
        search_tools = {k:v for k,v in available_tools.items() if "search" in k and "internal" not in k}
        other_tools = {k:v for k,v in available_tools.items() if k not in tej_tools and k not in internal_tools and k not in search_tools}
        
        def fmt_tools(tools):
            if not tools: return "(無)"
            return "\n".join([f"- {k}: {v}" for k, v in tools.items()])

        base_prompt = self.system_prompt_template if self.system_prompt_template else f"你是由 MARS 系統指派的 {self.role} ({self.name})。"

        system_prompt = f"""
{base_prompt}
你的目前任務是：{task.description}

請從以下可用工具中，選擇**最合適**的一個來執行任務。

【可用工具清單】
[台灣財經資料庫 (TEJ)]
{fmt_tools(tej_tools)}

[內部資料庫]
{fmt_tools(internal_tools)}

[網路搜尋]
{fmt_tools(search_tools)}

[其他工具]
{fmt_tools(other_tools)}

【指令】
請回傳標準 JSON 格式，不要包含其他文字：
{{
  "tool": "工具名稱 (必須完全符合清單)",
  "params": {{ "參數名": "參數值", ... }}
}}

【範例】
- 任務："查詢台積電(2330)的股價" -> {{"tool": "tej.stock_price", "params": {{"coid": "2330", "start_date": "2023-01-01"}}}}
- 任務："查詢 2330 的基本資料" -> {{"tool": "internal.get_company_details", "params": {{"company_id": "2330.TW"}}}}
"""
        
        try:
            # 2. Call LLM to select tool
            response = await call_llm_async("Please execute the task.", system_prompt=system_prompt)
            print(f"[{self.name}] Tool Selection Raw Response: {response}")
            
            # Parse Tool Call
            clean_response = response.strip()
            if clean_response.startswith("```json"):
                 clean_response = clean_response[7:]
            if clean_response.endswith("```"):
                 clean_response = clean_response[:-3]
            
            tool_call = json.loads(clean_response)
            tool_name = tool_call.get("tool")
            params = tool_call.get("params", {})
            
            # Fallback if LLM returns null/empty tool
            if not tool_name or tool_name.lower() == "none" or tool_name.lower() == "null":
                print(f"[{self.name}] Tool selection returned None. Defaulting to Web Search.")
                tool_name = "searxng.search"
                if not params:
                     # Use task description as query if params empty
                     params = {"query": task.description}

            # Enforce Chinese results for search
            if "search" in tool_name:
                params["language"] = "zh-TW"
                # Schema expects string, not list
                # params["engines"] = "google,bing,yahoo"
            
            # 3. Execute Tool
            print(f"[{self.name}] Selected tool: {tool_name}")
            result = self.tool_wrapper.execute(tool_name, params)
            
            # 4. Create Evidence
            return Evidence(
                id=f"ev_{task.id}",
                content=json.dumps(result, ensure_ascii=False),
                source_agent=self.name,
                metadata={"tool": tool_name, "params": params}
            )

        except Exception as e:
            print(f"[{self.name}] Execution failed: {e}")
            return Evidence(
                id=f"ev_{task.id}_fail",
                content=f"Execution failed: {str(e)}",
                source_agent=self.name,
                metadata={"error": str(e)}
            )