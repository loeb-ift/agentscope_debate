from sqlalchemy import create_engine, Column, Integer, String, JSON, DateTime, Boolean, Text
from sqlalchemy.sql import func
import datetime
import uuid
from api.database import Base

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
    支持 OpenAPI 規範管理。
    """
    __tablename__ = 'tools'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)  # e.g., "tej.company_info"
    type = Column(String, nullable=False)  # "api", "python", "internal"
    json_schema = Column(JSON, nullable=False)
    enabled = Column(Boolean, default=True)
    
    # API 工具配置（舊字段，保留兼容性）
    api_config = Column(JSON, nullable=True)  # URL, method, headers for HTTP tools
    python_code = Column(Text, nullable=True)  # Python code for python tools
    group = Column(String, default="basic")
    
    # 新增：OpenAPI 規範支持
    version = Column(String, default="v1")
    description = Column(Text, nullable=True)
    provider = Column(String, nullable=True)  # "tej", "yfinance", "custom"
    
    # OpenAPI 3.0 規範（完整 spec）
    openapi_spec = Column(JSON, nullable=True)
    
    # 認證配置
    auth_type = Column(String, nullable=True)  # "api_key", "oauth2", "basic", "none"
    auth_config = Column(JSON, nullable=True)  # {"in": "query", "param": "api_key"}
    
    # 速率限制
    rate_limit = Column(JSON, nullable=True)  # {"tps": 5, "burst": 10}
    
    # 緩存配置
    cache_ttl = Column(Integer, default=3600)  # seconds
    
    # 其他配置
    base_url = Column(String, nullable=True)
    timeout = Column(Integer, default=15)
    
    # 元數據（可選，因為舊數據可能沒有這些字段）
    created_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)

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

class AgentToolDeny(Base):
    """
    Agent 級別的工具封鎖（顯式 DENY）。
    """
    __tablename__ = 'agent_tool_denies'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), nullable=False, index=True)
    tool_name = Column(String(200), nullable=False, index=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class RuntimeAttachment(Base):
    """
    智能體在運行期間請求附加的工具（需審批）。
    status: pending/approved/denied
    """
    __tablename__ = 'runtime_attachments'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), nullable=False, index=True)
    tool_name = Column(String(200), nullable=False)
    session_id = Column(String(100), nullable=True)
    status = Column(String(20), default='pending')
    reason = Column(Text, nullable=True)
    approved_by = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    removed_at = Column(DateTime(timezone=True), nullable=True)

class Team(Base):
    """
    Persistent Team Model (團隊模型).
    """
    __tablename__ = 'teams'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    member_ids = Column(JSON, nullable=False) # List of Agent IDs
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class EvidenceDoc(Base):
    """
    EvidenceDoc: The atomic unit of fact in the Evidence Lifecycle.
    Tracks provenance, status, and verification history.
    """
    __tablename__ = 'evidence_docs'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    debate_id = Column(String(36), nullable=False, index=True)
    
    # Core Data
    agent_id = Column(String(100), nullable=False)
    tool_name = Column(String(100), nullable=False)
    params = Column(JSON, nullable=False) # Normalized params
    content = Column(JSON, nullable=True) # The actual tool result
    
    # Metadata & Provenance
    inputs_hash = Column(String(64), nullable=False, index=True) # For de-duplication
    provenance = Column(JSON, nullable=True) # {provider, model_family, run_id, etc.}
    
    # Lifecycle Status
    # DRAFT, QUARANTINE, VERIFIED, STALE, ARCHIVED, DELETED
    status = Column(String(20), default="DRAFT", index=True) 
    
    # Trust & Verification
    trust_score = Column(Integer, default=50) # 0-100
    verification_log = Column(JSON, default=list) # List of verification events
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    ttl_expiry = Column(DateTime(timezone=True), nullable=True) # When this evidence becomes STALE
    
    # EDA Artifact Support (NEW)
    artifact_type = Column(String(20), nullable=True)  # "report", "plot", "table", or None for regular evidence
    file_path = Column(String(500), nullable=True)     # Absolute path to artifact file (for EDA reports/plots/tables)
    
    # Missing columns for check_sqlite_schema compatibility
    title = Column(Text, nullable=True)
    source = Column(Text, nullable=True)
    snippet = Column(Text, nullable=True)
    fulltext_ref = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=True)
    tool = Column(Text, nullable=True)
    citations = Column(JSON, nullable=True)

class Checkpoint(Base):
    """
    Checkpoint: Represents a context snapshot for Handoff/Continuation.
    """
    __tablename__ = 'checkpoints'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    debate_id = Column(String(36), nullable=False, index=True)
    step_name = Column(String(100), nullable=True) # e.g. "pre_debate_analysis", "round_1"
    
    # Snapshot Content
    context_snapshot = Column(JSON, nullable=False) # Key-Value pairs of current context
    cited_evidence_ids = Column(JSON, default=list) # List of EvidenceDoc IDs referenced here
    
    # Next Actions
    next_actions = Column(JSON, nullable=True) # Suggested next tools/steps
    
    # Lease / Token
    lease_token = Column(String(64), nullable=True)
    lease_expiry = Column(DateTime(timezone=True), nullable=True)
    
    # Missing columns for check_sqlite_schema compatibility
    plan_node_id = Column(String(100), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
