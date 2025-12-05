"""
ToolSet Service - 管理工具集和 Agent 的工具權限
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from api import models
from api.tool_registry import tool_registry

class ToolSetService:
    """
    工具集服務，負責：
    1. 管理工具集的 CRUD
    2. 管理 Agent 和工具集的關聯
    3. 獲取 Agent 可用的工具列表
    """
    
    @staticmethod
    def get_agent_available_tools(db: Session, agent_id: str) -> List[Dict[str, Any]]:
        """
        獲取 Agent 可用的所有工具。
        包括：
        1. 分配給該 Agent 的工具集中的工具
        2. 全局工具集中的工具
        
        返回格式：
        [
            {
                "name": "tej.stock_price",
                "version": "v1",
                "description": "...",
                "schema": {...},
                "source": "assigned" | "global"
            }
        ]
        """
        tools = []
        tool_names_seen = set()
        
        # 1. 獲取分配給該 Agent 的工具集
        agent_toolsets = db.query(models.AgentToolSet).filter(
            models.AgentToolSet.agent_id == agent_id
        ).all()
        
        for ats in agent_toolsets:
            toolset = db.query(models.ToolSet).filter(
                models.ToolSet.id == ats.toolset_id
            ).first()
            
            if toolset:
                for tool_name_with_version in toolset.tool_names:
                    if tool_name_with_version not in tool_names_seen:
                        # 解析工具名稱和版本
                        if ':' in tool_name_with_version:
                            tool_name, version = tool_name_with_version.split(':', 1)
                        else:
                            tool_name = tool_name_with_version
                            version = 'v1'
                        
                        tool_info = tool_registry.get_tool_info(tool_name, version)
                        if tool_info:
                            tool_info['source'] = 'assigned'
                            tool_info['toolset_name'] = toolset.name
                            tools.append(tool_info)
                            tool_names_seen.add(tool_name_with_version)
        
        # 2. 獲取全局工具集
        global_toolsets = db.query(models.ToolSet).filter(
            models.ToolSet.is_global == True
        ).all()
        
        for toolset in global_toolsets:
            for tool_name_with_version in toolset.tool_names:
                if tool_name_with_version not in tool_names_seen:
                    # 解析工具名稱和版本
                    if ':' in tool_name_with_version:
                        tool_name, version = tool_name_with_version.split(':', 1)
                    else:
                        tool_name = tool_name_with_version
                        version = 'v1'
                    
                    tool_info = tool_registry.get_tool_info(tool_name, version)
                    if tool_info:
                        tool_info['source'] = 'global'
                        tool_info['toolset_name'] = toolset.name
                        tools.append(tool_info)
                        tool_names_seen.add(tool_name_with_version)
        
        return tools
    
    @staticmethod
    def get_toolset_details(db: Session, toolset_id: str) -> Optional[Dict[str, Any]]:
        """
        獲取工具集的詳細資訊，包括工具列表。
        """
        toolset = db.query(models.ToolSet).filter(
            models.ToolSet.id == toolset_id
        ).first()
        
        if not toolset:
            return None
        
        tools = []
        for tool_name in toolset.tool_names:
            tool_info = tool_registry.get_tool_info(tool_name)
            if tool_info:
                tools.append(tool_info)
        
        return {
            "toolset": {
                "id": toolset.id,
                "name": toolset.name,
                "description": toolset.description,
                "tool_names": toolset.tool_names,
                "is_global": toolset.is_global,
                "created_at": toolset.created_at,
                "updated_at": toolset.updated_at
            },
            "tools": tools
        }
    
    @staticmethod
    def create_global_toolset_if_not_exists(db: Session):
        """
        創建全局工具集（如果不存在）。
        包含所有已註冊的工具。
        """
        # 檢查是否已存在全局工具集
        existing = db.query(models.ToolSet).filter(
            models.ToolSet.name == "全局工具集",
            models.ToolSet.is_global == True
        ).first()
        
        if existing:
            # 更新工具列表
            all_tools = tool_registry.list_tools()
            existing.tool_names = list(all_tools.keys())
            db.commit()
            return existing
        
        # 創建新的全局工具集
        all_tools = tool_registry.list_tools()
        global_toolset = models.ToolSet(
            name="全局工具集",
            description="包含所有已註冊的工具，自動分配給所有 Agent",
            tool_names=list(all_tools.keys()),
            is_global=True
        )
        
        db.add(global_toolset)
        db.commit()
        db.refresh(global_toolset)
        
        return global_toolset
    
    @staticmethod
    def format_tools_for_prompt(tools: List[Dict[str, Any]]) -> str:
        """
        將工具列表格式化為 Prompt 字串。
        
        返回格式：
        **可用工具**：
        1. tej.stock_price (v1) - 查詢台股股價數據
           參數: coid, start_date, end_date, limit
        2. searxng.search (v1) - 網頁搜尋
           參數: q, engines
        """
        if not tools:
            return "**可用工具**：無"
        
        lines = ["**可用工具**："]
        
        for i, tool in enumerate(tools, 1):
            name = tool.get('name', 'unknown')
            version = tool.get('version', 'v1')
            description = tool.get('description', '無描述')
            schema = tool.get('schema', {})
            
            # 提取參數
            params = []
            if 'properties' in schema:
                params = list(schema['properties'].keys())
            
            params_str = ', '.join(params) if params else '無參數'
            
            lines.append(f"{i}. {name} ({version}) - {description}")
            lines.append(f"   參數: {params_str}")
        
        return '\n'.join(lines)
