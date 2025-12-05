
# --- Agent Management API ---

@app.get("/api/v1/agents", response_model=List[schemas.Agent])
def list_agents(
    skip: int = 0,
    limit: int = 100,
    role: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    列出所有 Agent。
    可選參數：
    - skip: 跳過的數量（分頁）
    - limit: 返回的最大數量
    - role: 篩選角色（debater, chairman, analyst）
    """
    query = db.query(models.Agent)
    
    if role:
        query = query.filter(models.Agent.role == role)
    
    agents = query.offset(skip).limit(limit).all()
    return agents

@app.post("/api/v1/agents", response_model=schemas.Agent, status_code=201)
def create_agent(agent: schemas.AgentCreate, db: Session = Depends(get_db)):
    """
    創建新的 Agent。
    """
    # 驗證角色
    valid_roles = ['debater', 'chairman', 'analyst']
    if agent.role not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}"
        )
    
    # 創建 Agent
    db_agent = models.Agent(
        name=agent.name,
        role=agent.role,
        specialty=agent.specialty,
        system_prompt=agent.system_prompt,
        config_json=agent.config_json
    )
    
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    
    return db_agent

@app.get("/api/v1/agents/{agent_id}", response_model=schemas.Agent)
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    """
    獲取特定 Agent 的詳細資訊。
    """
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return agent

@app.put("/api/v1/agents/{agent_id}", response_model=schemas.Agent)
def update_agent(
    agent_id: str,
    agent_update: schemas.AgentUpdate,
    db: Session = Depends(get_db)
):
    """
    更新 Agent 的資訊。
    只更新提供的欄位（部分更新）。
    """
    db_agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    
    if not db_agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # 更新提供的欄位
    update_data = agent_update.dict(exclude_unset=True)
    
    # 驗證角色（如果提供）
    if 'role' in update_data:
        valid_roles = ['debater', 'chairman', 'analyst']
        if update_data['role'] not in valid_roles:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}"
            )
    
    for field, value in update_data.items():
        setattr(db_agent, field, value)
    
    db.commit()
    db.refresh(db_agent)
    
    return db_agent

@app.delete("/api/v1/agents/{agent_id}", status_code=204)
def delete_agent(agent_id: str, db: Session = Depends(get_db)):
    """
    刪除 Agent。
    注意：如果 Agent 正在被使用中的辯論引用，應該先檢查。
    """
    db_agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    
    if not db_agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # TODO: 檢查是否有正在進行的辯論使用此 Agent
    # 這需要查詢辯論配置或團隊配置
    
    db.delete(db_agent)
    db.commit()
    
    return None

@app.get("/api/v1/agents/roles/available")
def get_available_roles():
    """
    獲取可用的 Agent 角色列表。
    """
    return {
        "roles": [
            {
                "value": "debater",
                "label": "辯士",
                "description": "參與辯論的 Agent"
            },
            {
                "value": "chairman",
                "label": "主席",
                "description": "主持辯論、進行分析和總結的 Agent"
            },
            {
                "value": "analyst",
                "label": "分析師",
                "description": "專門進行數據分析的 Agent"
            }
        ]
    }
