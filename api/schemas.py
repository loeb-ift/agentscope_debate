
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

class AgentList(BaseModel):
    items: List[Agent]

# --- Team Schemas ---

class TeamBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    member_ids: List[str] = []

class TeamCreate(TeamBase):
    pass

class TeamUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    member_ids: Optional[List[str]] = None

class Team(TeamBase):
    id: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        orm_mode = True

class TeamList(BaseModel):
    items: List[Team]

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
    type: str = "api"  # "api", "python", "internal"
    json_schema: Dict[str, Any]
    
    # 舊字段（兼容性）
    api_config: Optional[Dict[str, Any]] = None
    python_code: Optional[str] = None
    group: str = "basic"
    enabled: bool = True
    
    # 新增：OpenAPI 規範支持
    version: str = "v1"
    description: Optional[str] = None
    provider: Optional[str] = None  # "tej", "yfinance", "custom"
    
    # OpenAPI 3.0 規範
    openapi_spec: Optional[Dict[str, Any]] = None
    
    # 認證配置
    auth_type: Optional[str] = None  # "api_key", "oauth2", "basic", "none"
    auth_config: Optional[Dict[str, Any]] = None
    
    # 速率限制
    rate_limit: Optional[Dict[str, Any]] = None
    
    # 緩存配置
    cache_ttl: int = 3600
    
    # 其他配置
    base_url: Optional[str] = None
    timeout: int = 15

class ToolCreate(ToolBase):
    pass

class ToolUpdate(BaseModel):
    """更新工具的請求 Schema（所有欄位都是可選的）"""
    name: Optional[str] = None
    type: Optional[str] = None
    json_schema: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None
    version: Optional[str] = None
    description: Optional[str] = None
    provider: Optional[str] = None
    openapi_spec: Optional[Dict[str, Any]] = None
    auth_type: Optional[str] = None
    auth_config: Optional[Dict[str, Any]] = None
    rate_limit: Optional[Dict[str, Any]] = None
    cache_ttl: Optional[int] = None
    base_url: Optional[str] = None
    timeout: Optional[int] = None

class Tool(ToolBase):
    id: int
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    
    class Config:
        orm_mode = True

class ToolDescriptionGenerate(BaseModel):
    tool_type: str
    content: str # Code or Schema JSON

# --- Financial Entity Schemas ---

class CompanyBase(BaseModel):
    company_id: str
    company_name: str
    ticker_symbol: Optional[str] = None
    industry_sector: Optional[str] = None
    market_cap: Optional[float] = None
    country_of_incorporation: Optional[str] = None

class CompanyCreate(CompanyBase):
    pass

class Company(CompanyBase):
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        orm_mode = True

class SecurityBase(BaseModel):
    security_id: str
    security_name: str
    security_type: str
    issuer_company_id: Optional[str] = None
    ticker: Optional[str] = None
    isin: Optional[str] = None
    market_cap: Optional[float] = None

class SecurityCreate(SecurityBase):
    pass

class Security(SecurityBase):
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        orm_mode = True

class FinancialTermBase(BaseModel):
    term_id: str
    term_name: str
    term_category: Optional[str] = None
    definition: Optional[str] = None

class FinancialTermCreate(FinancialTermBase):
    pass

class FinancialTermUpdate(BaseModel):
    term_name: Optional[str] = None
    term_category: Optional[str] = None
    definition: Optional[str] = None

class FinancialTerm(FinancialTermBase):
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        orm_mode = True

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
