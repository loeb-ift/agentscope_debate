from typing import Dict, Any
from api.tool_registry import tool_registry

class MarsToolWrapper:
    """
    Wrapper to expose V1 tools to MARS Agents.
    Handles schema introspection and execution.
    """
    @staticmethod
    def get_tool_description(tool_name: str) -> str:
        try:
            tool_data = tool_registry.get_tool_data(tool_name)
            desc = tool_data.get("description", "")
            if isinstance(desc, dict):
                return desc.get("description") or str(desc)
            return desc
        except Exception as e:
            return f"Error loading tool description: {e}"

    @staticmethod
    def list_tools(group: str = None) -> Dict[str, str]:
        """Returns {tool_name: description}"""
        all_tools = tool_registry.list_tools()
        result = {}
        for tid, data in all_tools.items():
            # Filter by group if needed
            if group and data.get("group") != group:
                continue
            
            name = tid.split(":")[0]
            desc = data.get("description", "")
            if isinstance(desc, dict):
                desc = desc.get("description") or str(desc)
            
            schema = data.get("schema", {})
            # Format schema into a readable string
            params_str = ""
            if schema and "properties" in schema:
                props = schema["properties"]
                required = schema.get("required", [])
                params_list = []
                for prop_name, prop_data in props.items():
                    req_mark = "*" if prop_name in required else ""
                    p_desc = prop_data.get("description", "")
                    params_list.append(f"{prop_name}{req_mark}: {p_desc}")
                params_str = f" Params: {{{', '.join(params_list)}}}"
            
            result[name] = f"{desc}{params_str}"
        return result

    @staticmethod
    def execute(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a V1 tool.
        """
        print(f"[MARS] Executing tool: {tool_name} with params: {params}")
        try:
            # Re-use V1 registry logic (which handles caching/validation)
            result = tool_registry.invoke_tool(tool_name, params)
            return result
        except Exception as e:
            return {"error": str(e)}