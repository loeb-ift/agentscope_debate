from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
import uuid

# Import V1 dependencies for compatibility
from api.redis_client import get_redis_client
# We will need to import the Celery task (to be created)
# from worker.tasks import run_mars_task 

router = APIRouter()
redis_client = get_redis_client()

class ResearchRequest(BaseModel):
    topic: str
    context: Optional[str] = None

class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str

@router.post("/research", response_model=TaskResponse)
async def start_research(request: ResearchRequest):
    """
    Start a new MARS research task.
    """
    task_id = str(uuid.uuid4())
    
    # Store initial status
    redis_client.set(f"mars:task:{task_id}:status", "initialized")
    redis_client.set(f"mars:task:{task_id}:topic", request.topic)
    
    # Dispatch to Celery (Import lazily to avoid circular imports if any)
    from worker.tasks import run_mars_task
    run_mars_task.delay(task_id, request.topic)
    
    return TaskResponse(
        task_id=task_id,
        status="submitted",
        message="Research task submitted successfully."
    )

@router.get("/research/{task_id}")
async def get_research_status(task_id: str):
    """
    Get the status and artifacts of a research task.
    """
    status = redis_client.get(f"mars:task:{task_id}:status")
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
        
    # In a real impl, we would fetch artifacts from DB/Redis
    import json
    artifacts_json = redis_client.get(f"mars:task:{task_id}:artifacts")
    artifacts = json.loads(artifacts_json) if artifacts_json else []
    
    response_data = {
        "task_id": task_id,
        "status": status,
        "topic": redis_client.get(f"mars:task:{task_id}:topic"),
        "artifacts": artifacts
    }
    
    if status == "failed":
        response_data["error"] = redis_client.get(f"mars:task:{task_id}:error")
        
    return response_data