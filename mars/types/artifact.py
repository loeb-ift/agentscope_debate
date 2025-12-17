from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from enum import Enum
from datetime import datetime

class ArtifactType(str, Enum):
    EVIDENCE = "evidence"
    CLAIM = "claim"
    REPORT_SECTION = "report_section"
    PLAN = "plan"

class ArtifactBase(BaseModel):
    id: str
    type: ArtifactType
    content: Any
    created_at: datetime = Field(default_factory=datetime.now)
    source_agent: str
    metadata: Dict[str, Any] = {}

class Evidence(ArtifactBase):
    type: ArtifactType = ArtifactType.EVIDENCE
    content: str  # Raw text or JSON string
    source_url: Optional[str] = None
    confidence: float = 1.0

class Claim(ArtifactBase):
    type: ArtifactType = ArtifactType.CLAIM
    content: str  # The claim statement
    supporting_evidence_ids: List[str] = []
    counter_evidence_ids: List[str] = []
    status: str = "draft"  # draft, verified, rejected

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"

class Task(BaseModel):
    id: str
    description: str
    assigned_role: str
    status: TaskStatus = TaskStatus.PENDING
    dependencies: List[str] = []
    output_artifact_ids: List[str] = []

class ResearchPlan(ArtifactBase):
    type: ArtifactType = ArtifactType.PLAN
    content: str # High level goal
    tasks: List[Task] = []