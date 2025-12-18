from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from api import schemas, models
from api.database import SessionLocal
from api.config import Config
import os
import glob
from fastapi.responses import FileResponse
from worker.celery_app import app as celery_app
from api.redis_client import get_redis_client

router = APIRouter()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Redis Connection
redis_client = get_redis_client()

@router.post("/api/v1/debates/config", response_model=schemas.DebateConfigResponse, status_code=201)
def create_debate_config(config: schemas.DebateConfigCreate, db: Session = Depends(get_db)):
    """
    創建辯論配置。
    """
    # 0. 驗證規則
    # 0. 驗證規則
    # 規則 1: 每場辯論最多三團 (Configurable via .env)
    max_teams = Config.MAX_TEAMS_PER_DEBATE
    if len(config.teams) > max_teams:
        raise HTTPException(status_code=400, detail=f"每場辯論最多只能有 {max_teams} 個辯論團")
    
    # 規則 2: 辯論團由 1-{max_members} 個代理組成
    max_members = Config.MAX_MEMBERS_PER_TEAM
    all_debater_ids = set()
    for team in config.teams:
        if not (1 <= len(team.agent_ids) <= max_members):
            raise HTTPException(status_code=400, detail=f"團隊 '{team.name}' 的代理人數必須為 1 到 {max_members} 人")
        
        for agent_id in team.agent_ids:
            all_debater_ids.add(agent_id)

    # 規則 3: 主席不可以參與辯論團
    if config.chairman_id and config.chairman_id in all_debater_ids:
        raise HTTPException(status_code=400, detail="主席不能同時是辯論團成員")

    # 1. 創建 DebateConfig
    db_config = models.DebateConfig(
        topic=config.topic,
        chairman_id=config.chairman_id,
        rounds=config.rounds,
        enable_cross_examination=config.enable_cross_examination
    )
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    
    # 2. 創建 DebateTeams
    for team in config.teams:
        db_team = models.DebateTeam(
            debate_id=db_config.id,
            team_name=team.name,
            team_side=team.side,
            agent_ids=team.agent_ids
        )
        db.add(db_team)
    
    db.commit()
    
    # 建構回應
    response = schemas.DebateConfigResponse(
        id=db_config.id,
        topic=db_config.topic,
        chairman_id=db_config.chairman_id,
        rounds=db_config.rounds,
        enable_cross_examination=db_config.enable_cross_examination,
        teams=config.teams,
        created_at=db_config.created_at
    )
    
    return response

@router.post("/api/v1/debates/launch", status_code=201)
def launch_debate(config_id: str, db: Session = Depends(get_db)):
    """
    根據配置 ID 啟動辯論。
    """
    # 1. 獲取配置
    db_config = db.query(models.DebateConfig).filter(models.DebateConfig.id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=404, detail="Debate configuration not found")
    
    # 2. 獲取團隊
    db_teams = db.query(models.DebateTeam).filter(models.DebateTeam.debate_id == config_id).all()
    
    teams_config = []
    
    for team in db_teams:
        # 獲取 Agent 詳細資訊
        agents = []
        for agent_id in team.agent_ids:
            agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
            if agent:
                agents.append({
                    "name": agent.name,
                    "id": agent.id,
                    "role": agent.role,
                    "specialty": agent.specialty,
                    "system_prompt": agent.system_prompt,
                    "config": agent.config_json
                })
        
        teams_config.append({
            "name": team.team_name,
            "side": team.team_side,
            "agents": agents
        })
    
    # 3. 觸發 Celery 任務
    task = celery_app.send_task(
        'worker.tasks.run_debate_cycle',
        args=[
            db_config.topic,
            teams_config,
            db_config.rounds,
            db_config.enable_cross_examination
        ]
    )
    
    # 將任務 ID 存儲到 Redis
    redis_client.set(f"debate:{task.id}:topic", db_config.topic)
    redis_client.set(f"debate:{task.id}:config_id", config_id)
    # 基礎觀測/TTL 提示（可選）
    redis_client.set(f"debate:{task.id}:created_at", str(db_config.created_at))
    redis_client.set(f"debate:{task.id}:ttl_hint", os.getenv("DEBATE_TTL_HINT", ""))
    
    return {
        "task_id": task.id,
        "status": "Debate launched",
        "config_id": config_id,
        "topic": db_config.topic,
        "rounds": db_config.rounds,
        "enable_cross_examination": db_config.enable_cross_examination,
        "sse_channel": f"debate:{task.id}:log_stream",
    }


@router.post("/api/v1/debates/new", status_code=201)
def create_and_launch_debate(config: schemas.DebateConfigCreate, db: Session = Depends(get_db)):
    """
    一鍵：建立新的辯論設定並立即啟動，回傳 new debate_id 與 SSE channel。
    """
    # --- 建立設定（重用 create_debate_config 的核心邏輯） ---
    max_teams = Config.MAX_TEAMS_PER_DEBATE
    if len(config.teams) > max_teams:
        raise HTTPException(status_code=400, detail=f"每場辯論最多只能有 {max_teams} 個辯論團")
    max_members = Config.MAX_MEMBERS_PER_TEAM
    all_debater_ids = set()
    for team in config.teams:
        if not (1 <= len(team.agent_ids) <= max_members):
            raise HTTPException(status_code=400, detail=f"團隊 '{team.name}' 的代理人數必須為 1 到 {max_members} 人")
        for agent_id in team.agent_ids:
            all_debater_ids.add(agent_id)
    if config.chairman_id and config.chairman_id in all_debater_ids:
        raise HTTPException(status_code=400, detail="主席不能同時是辯論團成員")

    db_config = models.DebateConfig(
        topic=config.topic,
        chairman_id=config.chairman_id,
        rounds=config.rounds,
        enable_cross_examination=config.enable_cross_examination
    )
    db.add(db_config)
    db.commit()
    db.refresh(db_config)

    for team in config.teams:
        db_team = models.DebateTeam(
            debate_id=db_config.id,
            team_name=team.name,
            team_side=team.side,
            agent_ids=team.agent_ids
        )
        db.add(db_team)
    db.commit()

    # --- 立即啟動（重用 launch_debate 的核心邏輯） ---
    db_teams = db.query(models.DebateTeam).filter(models.DebateTeam.debate_id == db_config.id).all()
    teams_config = []
    for team in db_teams:
        agents = []
        for agent_id in team.agent_ids:
            agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
            if agent:
                agents.append({
                    "name": agent.name,
                    "id": agent.id,
                    "role": agent.role,
                    "specialty": agent.specialty,
                    "system_prompt": agent.system_prompt,
                    "config": agent.config_json
                })
        teams_config.append({"name": team.team_name, "side": team.team_side, "agents": agents})

    task = celery_app.send_task(
        'worker.tasks.run_debate_cycle',
        args=[
            db_config.topic,
            teams_config,
            db_config.rounds,
            db_config.enable_cross_examination
        ]
    )

    redis_client.set(f"debate:{task.id}:topic", db_config.topic)
    redis_client.set(f"debate:{task.id}:config_id", db_config.id)
    redis_client.set(f"debate:{task.id}:created_at", str(db_config.created_at))
    redis_client.set(f"debate:{task.id}:ttl_hint", os.getenv("DEBATE_TTL_HINT", ""))

    return {
        "debate_id": task.id,
        "config_id": db_config.id,
        "topic": db_config.topic,
        "rounds": db_config.rounds,
        "enable_cross_examination": db_config.enable_cross_examination,
        "sse_channel": f"debate:{task.id}:log_stream",
        "status": "launched",
    }

@router.get("/api/v1/replays")
async def list_replays(limit: int = 50):
    """列出所有 Markdown 辯論報告 (按檔名時間戳排序)"""
    import asyncio
    report_dir = "data/replays"
    if not os.path.exists(report_dir):
        return []
    
    # Run I/O in thread pool to avoid blocking event loop
    loop = asyncio.get_running_loop()
    
    def _scan_files():
        files = glob.glob(os.path.join(report_dir, "*.md"))
        
        def get_sort_key(filepath):
            try:
                filename = os.path.basename(filepath)
                # Format: topic_YYYYMMDD_HHMMSS.md
                ts_part = filename.rsplit('.', 1)[0].rsplit('_', 2)[-2:]
                return "_".join(ts_part)
            except:
                return str(os.path.getmtime(filepath))
                
        files.sort(key=get_sort_key, reverse=True)
        return files[:limit] # Limit results

    files = await loop.run_in_executor(None, _scan_files)
    
    replays = []
    for f in files:
        replays.append({
            "filename": os.path.basename(f),
            "path": f
        })
    return replays

@router.get("/api/v1/replays/{filename}")
def get_replay_content(filename: str):
    """獲取指定報告的內容"""
    report_dir = "data/replays"
    filepath = os.path.join(report_dir, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Replay not found")
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    return {"content": content}

@router.get("/api/v1/replays/{filename}/download")
def download_replay(filename: str):
    """下載指定報告"""
    report_dir = "data/replays"
    filepath = os.path.join(report_dir, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Replay not found")
    
    return FileResponse(filepath, filename=filename)