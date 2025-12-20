"""
ToolSet Service - 管理工具集和 Agent 的工具權限
"""

from typing import List, Dict, Any, Optional, Tuple
import os
from sqlalchemy.orm import Session
from api import models
from api.tool_registry import tool_registry

class ToolSetService:
    # pluggable cache backend
    _CACHE_BACKEND = None  # will be set via configure_cache_backend
    _EFFECTIVE_CACHE_VER: Dict[str, int] = {}
    _DEFAULT_TTL: int = int(os.getenv("EFFECTIVE_TOOLS_TTL", "60"))

    @staticmethod
    def configure_cache_backend(backend):
        """backend must implement get(key), set(key, value, ttl=None), delete(key)"""
        ToolSetService._CACHE_BACKEND = backend

    @staticmethod
    def _cache_get(key: str):
        if ToolSetService._CACHE_BACKEND is None:
            return None
        try:
            return ToolSetService._CACHE_BACKEND.get(key)
        except Exception:
            return None

    @staticmethod
    def _cache_set(key: str, value, ttl: Optional[int] = None):
        if ToolSetService._CACHE_BACKEND is None:
            return
        try:
            ToolSetService._CACHE_BACKEND.set(key, value, ttl=ttl)
        except Exception:
            pass

    @staticmethod
    def _cache_delete(key: str):
        if ToolSetService._CACHE_BACKEND is None:
            return
        try:
            ToolSetService._CACHE_BACKEND.delete(key)
        except Exception:
            pass

    @staticmethod
    def invalidate_agent_cache(agent_id: str):
        ToolSetService._EFFECTIVE_CACHE_VER[agent_id] = ToolSetService._EFFECTIVE_CACHE_VER.get(agent_id, 0) + 1
        ToolSetService._cache_delete(f"effective:{agent_id}")
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
    def _get_agent_denies(db: Session, agent_id: str) -> set:
        rows = db.query(models.AgentToolDeny).filter(models.AgentToolDeny.agent_id == agent_id).all()
        return {r.tool_name for r in rows}

    def _get_agent_runtime_approved(db: Session, agent_id: str) -> set:
        rows = db.query(models.RuntimeAttachment).filter(
            models.RuntimeAttachment.agent_id == agent_id,
            models.RuntimeAttachment.status == 'approved'
        ).all()
        return {r.tool_name for r in rows}

    def _get_prompt_rules(agent: models.Agent) -> Tuple[set, set]:
        """Extract allow/deny tool rules from agent.config_json (prompt-derived).
        Expected structure: {"tools": {"allow": [..], "deny": [..]}}
        """
        try:
            tools_cfg = (agent.config_json or {}).get("tools", {})
            allow = set(tools_cfg.get("allow", []) or [])
            deny = set(tools_cfg.get("deny", []) or [])
            return allow, deny
        except Exception:
            return set(), set()

    def get_agent_effective_tools(db: Session, agent_id: str, include_precedence: bool = False, include_denies: bool = False) -> List[Dict[str, Any]] | Dict[str, Any]:
        """
        M1 minimal effective tools computation.
        Currently equals assigned toolsets ∪ global toolsets, with de-dup.
        Future extensions (M2+):
        - prompt allowlist/deny
        - runtime attachments
        - precedence resolution
        """
        # cache check (only for default variant)
        ver = ToolSetService._EFFECTIVE_CACHE_VER.get(agent_id, 0)
        if not include_precedence and not include_denies:
            cached = ToolSetService._cache_get(f"effective:{agent_id}")
            if cached and cached.get('ver') == ver:
                return cached['data']

        agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
        prompt_allow, prompt_deny = ToolSetService._get_prompt_rules(agent) if agent else (set(), set())

        denies = ToolSetService._get_agent_denies(db, agent_id) | prompt_deny
        runtime_tools = ToolSetService._get_agent_runtime_approved(db, agent_id)

        base = ToolSetService.get_agent_available_tools(db, agent_id)

        # precedence ranking
        def rank_of(src: str) -> int:
            # lower number is higher precedence
            order = {
                'deny': 0,
                'runtime': 1,
                'prompt': 2,
                'agent_toolset': 3,
                'global': 4,
            }
            return order.get(src, 9)

        index: Dict[str, Dict[str, Any]] = {}
        source_rank: Dict[str, int] = {}

        # Seed with base tools
        for t in base:
            name = t.get('name') or t.get('tool_name')
            src = t.get('source') or ('global' if t.get('toolset_name') == 'GLOBAL' or t.get('toolset_name') is None and t.get('is_global', False) else 'agent_toolset')
            index[name] = dict(t)
            source_rank[name] = rank_of(src)
            index[name]['precedence'] = src if include_precedence else index[name].get('source')

        # Overlay runtime attachments (higher precedence)
        for name in runtime_tools:
            if name in denies:
                continue
            r = rank_of('runtime')
            if name in source_rank and source_rank[name] <= r:
                # existing has higher or equal precedence, just mark source
                index[name]['source'] = 'runtime'
                if include_precedence:
                    index[name]['precedence'] = 'runtime'
            else:
                tool_row = db.query(models.Tool).filter(models.Tool.name == name).first()
                if tool_row:
                    index[name] = {
                        'id': tool_row.id,
                        'name': tool_row.name,
                        'type': tool_row.type,
                        'json_schema': tool_row.json_schema,
                        'enabled': tool_row.enabled,
                        'source': 'runtime',
                    }
                    if include_precedence:
                        index[name]['precedence'] = 'runtime'
                source_rank[name] = r

        # Prompt allow can add new tools or upgrade precedence below runtime
        for name in prompt_allow:
            if name in denies:
                continue
            r = rank_of('prompt')
            if name in source_rank and source_rank[name] <= r:
                # keep existing higher precedence
                continue
            tool_row = db.query(models.Tool).filter(models.Tool.name == name).first()
            if tool_row:
                index[name] = {
                    'id': tool_row.id,
                    'name': tool_row.name,
                    'type': tool_row.type,
                    'json_schema': tool_row.json_schema,
                    'enabled': tool_row.enabled,
                    'source': 'prompt',
                }
                if include_precedence:
                    index[name]['precedence'] = 'prompt'
                source_rank[name] = r

        # Apply denies at the end
        denied_list: List[Dict[str, Any]] = []
        for dn in list(index.keys()):
            if dn in denies:
                denied_list.append({'name': dn, 'source': 'deny'})
                index.pop(dn, None)

        result = list(index.values())

        # cache store for default variant
        if not include_precedence and not include_denies:
            # default TTL: 60s (can be tuned)
            ToolSetService._cache_set(f"effective:{agent_id}", {"ver": ver, "data": result}, ttl=60)
        if include_denies:
            return {'tools': result, 'denies': denied_list}
        return result

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
