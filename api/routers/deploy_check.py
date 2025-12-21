from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict
import os
import hashlib
import glob

from api.database import get_db
from api import models
from api.toolset_service import ToolSetService
import itertools
router = APIRouter(prefix="/health", tags=["health"]) 


def _prompts_checksum() -> str:
    h = hashlib.sha256()
    for path in sorted(glob.glob("prompts/**/*.yaml", recursive=True)):
        try:
            with open(path, "rb") as f:
                h.update(f.read())
        except Exception:
            continue
    return h.hexdigest()

def _toolsets_fingerprint(db: Session) -> str:
    """Compute a stable fingerprint of toolsets and their tool names."""
    h = hashlib.sha256()
    rows = db.query(models.ToolSet).all()
    # collect pairs (toolset_name, [tool_names...])
    for ts in sorted(rows, key=lambda x: (not x.is_global, x.name)):
        h.update((ts.name or "").encode())
        tools = [att.tool.name for att in sorted(ts.tools, key=lambda a: a.tool.name)] if hasattr(ts, 'tools') else []
        for t in tools:
            h.update(t.encode())
    return h.hexdigest()

@router.get("/deploy-check")
def deploy_check(db: Session = Depends(get_db)) -> Dict:
    # cache backend info
    cache_backend = os.getenv("EFFECTIVE_TOOLS_CACHE", "memory").lower()

    # agents count
    agents = db.query(models.Agent).count()

    # toolsets
    toolsets = db.query(models.ToolSet).count()
    global_exists = db.query(models.ToolSet).filter(models.ToolSet.is_global == True).count() > 0

    # prompts checksum
    prompts_hash = _prompts_checksum()

    toolsets_fp = _toolsets_fingerprint(db)

    resp = {
        "cache_backend": cache_backend,
        "agents": agents,
        "toolsets": toolsets,
        "global_toolset": global_exists,
        "prompts_checksum": prompts_hash,
        "toolsets_fingerprint": toolsets_fp,
    }
    return resp
