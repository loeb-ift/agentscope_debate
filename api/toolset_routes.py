"""
ToolSet API 端點
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from api import models
from api.toolset_schemas import (
    ToolSetCreate, ToolSetUpdate, ToolSet,
    AgentToolSetAssign, AgentToolSetResponse,
    AgentWithToolSets, ToolSetWithTools
)
from api.toolset_service import ToolSetService
from api.database import SessionLocal
from api.schemas import (
    AgentToolDenyCreate, AgentToolDeny,
    RuntimeAttachmentRequest, RuntimeAttachmentApprove,
    RuntimeAttachment as RuntimeAttachmentSchema,
)

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- ToolSet CRUD API ---

@router.post("/api/v1/toolsets", response_model=ToolSet, status_code=201)
def create_toolset_endpoint(toolset: ToolSetCreate, db: Session = Depends(get_db)):
    """
    創建新的工具集。
    POST /api/v1/toolsets
    """
    db_toolset = models.ToolSet(
        name=toolset.name,
        description=toolset.description,
        tool_names=toolset.tool_names,
        is_global=toolset.is_global
    )
    
    db.add(db_toolset)
    db.commit()
    db.refresh(db_toolset)
    
    return db_toolset

@router.get("/api/v1/toolsets", response_model=List[ToolSet])
def list_toolsets_endpoint(
    skip: int = 0,
    limit: int = 100,
    is_global: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """
    列出所有工具集。
    GET /api/v1/toolsets
    GET /api/v1/toolsets?is_global=true
    """
    query = db.query(models.ToolSet)
    
    if is_global is not None:
        query = query.filter(models.ToolSet.is_global == is_global)
    
    toolsets = query.offset(skip).limit(limit).all()
    return toolsets

@router.get("/api/v1/toolsets/{toolset_id}")
def get_toolset_endpoint(toolset_id: str, db: Session = Depends(get_db)):
    """
    獲取工具集詳情（包含工具列表）。
    GET /api/v1/toolsets/{toolset_id}
    """
    toolset_details = ToolSetService.get_toolset_details(db, toolset_id)
    
    if not toolset_details:
        raise HTTPException(status_code=404, detail="ToolSet not found")
    
    return toolset_details

@router.put("/api/v1/toolsets/{toolset_id}", response_model=ToolSet)
def update_toolset_endpoint(
    toolset_id: str,
    toolset_update: ToolSetUpdate,
    db: Session = Depends(get_db)
):
    """
    更新工具集。
    PUT /api/v1/toolsets/{toolset_id}
    """
    db_toolset = db.query(models.ToolSet).filter(
        models.ToolSet.id == toolset_id
    ).first()
    
    if not db_toolset:
        raise HTTPException(status_code=404, detail="ToolSet not found")
    
    update_data = toolset_update.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(db_toolset, field, value)
    
    db.commit()
    db.refresh(db_toolset)
    
    return db_toolset

@router.delete("/api/v1/toolsets/{toolset_id}", status_code=204)
def delete_toolset_endpoint(toolset_id: str, db: Session = Depends(get_db)):
    """
    刪除工具集。
    DELETE /api/v1/toolsets/{toolset_id}
    """
    db_toolset = db.query(models.ToolSet).filter(
        models.ToolSet.id == toolset_id
    ).first()
    
    if not db_toolset:
        raise HTTPException(status_code=404, detail="ToolSet not found")
    
    # 檢查是否為全局工具集
    if db_toolset.is_global:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete global toolset"
        )
    
    # 刪除關聯
    db.query(models.AgentToolSet).filter(
        models.AgentToolSet.toolset_id == toolset_id
    ).delete()
    
    db.delete(db_toolset)
    db.commit()
    
    return None

# --- Agent-ToolSet Association API ---

@router.post("/api/v1/agents/{agent_id}/toolsets", response_model=AgentToolSetResponse, status_code=201)
def assign_toolset_to_agent_endpoint(
    agent_id: str,
    assignment: AgentToolSetAssign,
    db: Session = Depends(get_db)
):
    """
    分配工具集給 Agent。
    POST /api/v1/agents/{agent_id}/toolsets
    """
    # 驗證 Agent 存在
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # 驗證 ToolSet 存在
    toolset = db.query(models.ToolSet).filter(
        models.ToolSet.id == assignment.toolset_id
    ).first()
    if not toolset:
        raise HTTPException(status_code=404, detail="ToolSet not found")
    
    # 檢查是否已分配
    existing = db.query(models.AgentToolSet).filter(
        models.AgentToolSet.agent_id == agent_id,
        models.AgentToolSet.toolset_id == assignment.toolset_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail="ToolSet already assigned to this Agent"
        )
    
    # 創建關聯
    db_assignment = models.AgentToolSet(
        agent_id=agent_id,
        toolset_id=assignment.toolset_id
    )
    
    db.add(db_assignment)
    db.commit()
    db.refresh(db_assignment)
    
    return db_assignment

@router.get("/api/v1/agents/{agent_id}/toolsets")
def get_agent_toolsets_endpoint(agent_id: str, db: Session = Depends(get_db)):
    """
    獲取 Agent 的所有工具集。
    GET /api/v1/agents/{agent_id}/toolsets
    """
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # 獲取分配的工具集
    assigned_toolsets = []
    agent_toolsets = db.query(models.AgentToolSet).filter(
        models.AgentToolSet.agent_id == agent_id
    ).all()
    
    for ats in agent_toolsets:
        toolset = db.query(models.ToolSet).filter(
            models.ToolSet.id == ats.toolset_id
        ).first()
        if toolset:
            assigned_toolsets.append({
                "id": toolset.id,
                "name": toolset.name,
                "description": toolset.description,
                "tool_count": len(toolset.tool_names),
                "source": "assigned"
            })
    
    # 獲取全局工具集
    global_toolsets = db.query(models.ToolSet).filter(
        models.ToolSet.is_global == True
    ).all()
    
    for toolset in global_toolsets:
        assigned_toolsets.append({
            "id": toolset.id,
            "name": toolset.name,
            "description": toolset.description,
            "tool_count": len(toolset.tool_names),
            "source": "global"
        })
    
    return {
        "agent_id": agent_id,
        "agent_name": agent.name,
        "toolsets": assigned_toolsets
    }

@router.delete("/api/v1/agents/{agent_id}/toolsets/{toolset_id}", status_code=204)
def unassign_toolset_from_agent(agent_id: str, toolset_id: str, db: Session = Depends(get_db)):
    """
    取消分配工具集。
    DELETE /api/v1/agents/{agent_id}/toolsets/{toolset_id}
    """
    assignment = db.query(models.AgentToolSet).filter(
        models.AgentToolSet.agent_id == agent_id,
        models.AgentToolSet.toolset_id == toolset_id
    ).first()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
        
    db.delete(assignment)
    db.commit()
    return None

@router.get("/api/v1/agents/{agent_id}/available-tools")
def get_agent_available_tools_endpoint(agent_id: str, db: Session = Depends(get_db)):
    """
    獲取 Agent 可用的所有工具（assigned ∪ global）。
    GET /api/v1/agents/{agent_id}/available-tools
    """
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    tools = ToolSetService.get_agent_available_tools(db, agent_id)
    return tools

@router.get("/api/v1/agents/{agent_id}/tools/effective")
def get_agent_effective_tools_endpoint(
    agent_id: str,
    include_sources: bool = True,
    include_precedence: bool = False,
    include_denies: bool = False,
    db: Session = Depends(get_db)
):
    """
    最小可用版：獲取 Agent 的最終可用工具清單。
    目前等價於 available-tools（assigned ∪ global）。
    後續將納入 prompt 限制、runtime 附件與 deny/precedence 規則。
    Query:
    - include_sources: 是否保留來源與工具集標籤（source, toolset_name）。預設 True。
    GET /api/v1/agents/{agent_id}/tools/effective
    """
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    tools = ToolSetService.get_agent_effective_tools(db, agent_id, include_precedence=include_precedence, include_denies=include_denies)
    if include_denies:
        # when include_denies, service returns an object
        if not include_sources:
            # strip sources from tool entries
            tools['tools'] = [
                {k: v for k, v in t.items() if k not in ('source', 'toolset_name', 'precedence')}
                for t in tools['tools']
            ]
        return tools
    if include_sources:
        return tools
    # strip source annotations for minimal list
    sanitized = []
    for t in tools:
        t2 = dict(t)
        t2.pop('source', None)
        t2.pop('toolset_name', None)
        sanitized.append(t2)
    return sanitized

@router.delete("/api/v1/agents/{agent_id}/toolsets/{toolset_id}", status_code=204)
def remove_toolset_from_agent_endpoint(
    agent_id: str,
    toolset_id: str,
    db: Session = Depends(get_db)
):
    """
    移除 Agent 的工具集分配。
    DELETE /api/v1/agents/{agent_id}/toolsets/{toolset_id}
    """
    assignment = db.query(models.AgentToolSet).filter(
        models.AgentToolSet.agent_id == agent_id,
        models.AgentToolSet.toolset_id == toolset_id
    ).first()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    db.delete(assignment)
    db.commit()
    ToolSetService.invalidate_agent_cache(agent_id)
    return None

# --- Initialization ---

# --- Agent DENY tools (M2) ---

@router.post("/api/v1/agents/{agent_id}/tools/deny", response_model=AgentToolDeny, status_code=201)
def deny_tool_for_agent(agent_id: str, payload: AgentToolDenyCreate, db: Session = Depends(get_db)):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    row = models.AgentToolDeny(agent_id=agent_id, tool_name=payload.tool_name, reason=payload.reason)
    db.add(row); db.commit(); db.refresh(row)
    ToolSetService.invalidate_agent_cache(agent_id)
    return row

@router.get("/api/v1/agents/{agent_id}/tools/deny", response_model=List[AgentToolDeny])
def list_agent_denies(agent_id: str, db: Session = Depends(get_db)):
    rows = db.query(models.AgentToolDeny).filter(models.AgentToolDeny.agent_id == agent_id).all()
    return rows

@router.delete("/api/v1/agents/{agent_id}/tools/deny/{tool_name}", status_code=204)
def remove_agent_deny(agent_id: str, tool_name: str, db: Session = Depends(get_db)):
    row = db.query(models.AgentToolDeny).filter(
        models.AgentToolDeny.agent_id == agent_id,
        models.AgentToolDeny.tool_name == tool_name
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Deny not found")
    db.delete(row); db.commit(); ToolSetService.invalidate_agent_cache(agent_id); return None

# --- Runtime attachments (M2) ---

@router.post("/api/v1/agents/{agent_id}/runtime-tools/request", response_model=RuntimeAttachmentSchema, status_code=201)
def request_runtime_tool(agent_id: str, payload: RuntimeAttachmentRequest, db: Session = Depends(get_db)):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    row = models.RuntimeAttachment(
        agent_id=agent_id,
        tool_name=payload.tool_name,
        session_id=payload.session_id,
        status='pending',
        reason=payload.reason,
        expires_at=payload.expires_at
    )
    db.add(row); db.commit(); db.refresh(row)
    return row

@router.post("/api/v1/agents/{agent_id}/runtime-tools/{request_id}/approve", response_model=RuntimeAttachmentSchema)
def approve_runtime_tool(agent_id: str, request_id: str, payload: RuntimeAttachmentApprove, db: Session = Depends(get_db)):
    row = db.query(models.RuntimeAttachment).filter(
        models.RuntimeAttachment.id == request_id,
        models.RuntimeAttachment.agent_id == agent_id
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Request not found")
    row.status = 'approved'
    row.approved_by = payload.approved_by
    db.commit(); db.refresh(row)
    ToolSetService.invalidate_agent_cache(agent_id)
    return row

@router.post("/api/v1/agents/{agent_id}/runtime-tools/{request_id}/deny", response_model=RuntimeAttachmentSchema)
def deny_runtime_tool(agent_id: str, request_id: str, db: Session = Depends(get_db)):
    row = db.query(models.RuntimeAttachment).filter(
        models.RuntimeAttachment.id == request_id,
        models.RuntimeAttachment.agent_id == agent_id
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Request not found")
    row.status = 'denied'
    db.commit(); db.refresh(row)
    ToolSetService.invalidate_agent_cache(agent_id)
    return row

@router.get("/api/v1/agents/{agent_id}/runtime-tools/requests", response_model=List[RuntimeAttachmentSchema])
def list_runtime_tool_requests(agent_id: str, db: Session = Depends(get_db)):
    rows = db.query(models.RuntimeAttachment).filter(models.RuntimeAttachment.agent_id == agent_id).all()
    return rows

@router.post("/api/v1/toolsets/initialize-global")
def initialize_global_toolset_endpoint(db: Session = Depends(get_db)):
    """
    初始化全局工具集。
    POST /api/v1/toolsets/initialize-global
    """
    toolset = ToolSetService.create_global_toolset_if_not_exists(db)
    return toolset
