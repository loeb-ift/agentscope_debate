"""
ToolSet Schemas for API requests and responses.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
import datetime

# --- ToolSet Schemas ---

class ToolSetBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="工具集名稱")
    description: Optional[str] = Field(None, description="工具集描述")
    tool_names: List[str] = Field(..., description="工具名稱列表")
    is_global: bool = Field(default=False, description="是否為全局工具集")

class ToolSetCreate(ToolSetBase):
    """創建工具集的請求 Schema"""
    pass

class ToolSetUpdate(BaseModel):
    """更新工具集的請求 Schema（所有欄位都是可選的）"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    tool_names: Optional[List[str]] = None
    is_global: Optional[bool] = None

class ToolSet(ToolSetBase):
    """工具集回應 Schema"""
    id: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        orm_mode = True

# --- Agent-ToolSet Association Schemas ---

class AgentToolSetAssign(BaseModel):
    """分配工具集給 Agent 的請求 Schema"""
    agent_id: str = Field(..., description="Agent ID")
    toolset_id: str = Field(..., description="ToolSet ID")

class AgentToolSetResponse(BaseModel):
    """Agent-ToolSet 關聯回應 Schema"""
    id: str
    agent_id: str
    toolset_id: str
    created_at: datetime.datetime

    class Config:
        orm_mode = True

class AgentWithToolSets(BaseModel):
    """Agent 及其工具集的完整資訊"""
    agent_id: str
    agent_name: str
    toolsets: List[ToolSet]

class ToolSetWithTools(BaseModel):
    """工具集及其包含的工具詳情"""
    toolset: ToolSet
    tools: List[dict]  # Tool details from tool_registry
