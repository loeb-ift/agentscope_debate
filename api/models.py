from sqlalchemy import create_engine, Column, Integer, String, JSON, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import datetime
import uuid

Base = declarative_base()

class Agent(Base):
    """
    智能體模型，對應 SDD 6.1 L1 持久化層的 Agent 表。
    擴展支持角色、專長和更詳細的配置。
    """
    __tablename__ = 'agents'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    role = Column(String(50), nullable=False, default='debater')  # 'debater', 'chairman', 'analyst'
    specialty = Column(Text, nullable=True)  # 專長描述
    system_prompt = Column(Text, nullable=False)
    config_json = Column(JSON, nullable=False, default=dict)  # 其他配置（如溫度、max_tokens等）
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Tool(Base):
    """
    工具模型，對應 SDD 6.1 L1 持久化層的 Tool 表。
    """
    __tablename__ = 'tools'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    json_schema = Column(JSON, nullable=False)
    enabled = Column(Boolean, default=True)
    api_config = Column(JSON, nullable=True) # URL, method, headers for HTTP tools
    python_code = Column(Text, nullable=True) # Python code for python tools
    group = Column(String, default="basic")

class ToolSet(Base):
    """
    工具集模型。
    工具集是工具的集合，可以分配給 Agent。
    """
    __tablename__ = 'toolsets'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    tool_names = Column(JSON, nullable=False)  # List of tool names, e.g., ["tej.stock_price", "searxng.search"]
    is_global = Column(Boolean, default=False)  # 是否為全局工具集
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class AgentToolSet(Base):
    """
    Agent 和 ToolSet 的關聯表（多對多關係）。
    一個 Agent 可以有多個 ToolSet，一個 ToolSet 可以分配給多個 Agent。
    """
    __tablename__ = 'agent_toolsets'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), nullable=False)  # Foreign key to agents.id
    toolset_id = Column(String(36), nullable=False)  # Foreign key to toolsets.id
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class PromptTemplate(Base):
    """
    提示詞範本模型，對應 SDD 6.1 L1 持久化層的 PromptTemplate 表。
    """
    __tablename__ = 'prompt_templates'
    id = Column(Integer, primary_key=True)
    key = Column(String, nullable=False)
    language = Column(String, nullable=False)
    content = Column(String, nullable=False)
    version = Column(Integer, nullable=False)

class DebateArchive(Base):
    """
    辯論存檔模型，對應 SDD 6.1 L1 持久化層的 DebateArchive 表。
    """
    __tablename__ = 'debate_archives'
    id = Column(Integer, primary_key=True)
    topic = Column(String, nullable=False)
    analysis_json = Column(JSON, nullable=False)
    rounds_json = Column(JSON, nullable=False)
    logs_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class DebateConfig(Base):
    """
    辯論配置模型。
    """
    __tablename__ = 'debate_configs'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    topic = Column(Text, nullable=False)
    chairman_id = Column(String(36), nullable=True)  # Agent ID
    rounds = Column(Integer, default=3)
    enable_cross_examination = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class DebateTeam(Base):
    """
    辯論隊伍模型。
    """
    __tablename__ = 'debate_teams'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    debate_id = Column(String(36), nullable=False) # 關聯到 DebateConfig.id
    team_name = Column(String(100), nullable=False)
    team_side = Column(String(20), nullable=False)  # 'pro', 'con', 'neutral'
    agent_ids = Column(JSON, nullable=False) # List of Agent IDs
    created_at = Column(DateTime(timezone=True), server_default=func.now())
