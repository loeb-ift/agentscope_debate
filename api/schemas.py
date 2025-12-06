
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import datetime

# --- Agent Schemas ---

class AgentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Agent 名稱")
    role: str = Field(default="debater", description="Agent 角色: debater, chairman, analyst")
    specialty: Optional[str] = Field(None, description="Agent 專長描述")
    system_prompt: str = Field(..., min_length=1, description="系統 Prompt")
    config_json: Dict[str, Any] = Field(default_factory=dict, description="其他配置")

class AgentCreate(AgentBase):
    """創建 Agent 的請求 Schema"""
    pass

class AgentUpdate(BaseModel):
    """更新 Agent 的請求 Schema（所有欄位都是可選的）"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    role: Optional[str] = None
    specialty: Optional[str] = None
    system_prompt: Optional[str] = Field(None, min_length=1)
    config_json: Optional[Dict[str, Any]] = None

class Agent(AgentBase):
    """Agent 回應 Schema"""
    id: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        orm_mode = True  # Pydantic v1 compatibility

# --- Debate Schemas ---

class DebateCreate(BaseModel):
    topic: str
    config: Dict[str, Any]

class TeamConfig(BaseModel):
    name: str
    side: str = Field(..., description="pro, con, or neutral")
    agent_ids: List[str]

class DebateConfigCreate(BaseModel):
    topic: str
    chairman_id: Optional[str] = None
    teams: List[TeamConfig]
    rounds: int = 3
    enable_cross_examination: bool = True

class DebateConfigResponse(DebateConfigCreate):
    id: str
    created_at: datetime.datetime
    
    class Config:
        orm_mode = True

class DebateArchive(BaseModel):
    id: int
    topic: str
    analysis_json: Dict[str, Any]
    rounds_json: List[Dict[str, Any]]
    logs_json: Any
    created_at: datetime.datetime

    class Config:
        orm_mode = True

# --- Tool Schemas ---

class ToolTest(BaseModel):
    name: str
    kwargs: Dict[str, Any]

class ToolBase(BaseModel):
    name: str
    type: str = "http"
    json_schema: Dict[str, Any]
    api_config: Optional[Dict[str, Any]] = None
    python_code: Optional[str] = None
    group: str = "basic"
    enabled: bool = True

class ToolCreate(ToolBase):
    pass

class Tool(ToolBase):
    id: int
    
    class Config:
        orm_mode = True

class ToolDescriptionGenerate(BaseModel):
    tool_type: str
    content: str # Code or Schema JSON

# --- Prompt Schemas ---

class PromptTemplateBase(BaseModel):
    key: str
    language: str = "zh-TW"
    content: str
    version: int = 1

class PromptTemplateCreate(PromptTemplateBase):
    pass

class PromptTemplateUpdate(BaseModel):
    content: Optional[str] = None
    version: Optional[int] = None

class PromptTemplate(PromptTemplateBase):
    id: int
    
    class Config:
        orm_mode = True
