import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from api.models import EvidenceDoc, Checkpoint
from api.database import SessionLocal
from worker.tool_config import get_tool_ttl_config, tool_manager

class EvidenceLifecycle:
    """
    Manages the lifecycle of EvidenceDocs:
    Draft -> Verified -> Stale -> Archived
          -> Quarantine
    """
    
    def __init__(self, debate_id: str):
        self.debate_id = debate_id

    def ingest(self, agent_id: str, tool_name: str, params: Dict, result: Any) -> EvidenceDoc:
        """
        Ingest a tool result as a DRAFT EvidenceDoc.
        Performs basic sanity checks immediately.
        """
        db = SessionLocal()
        try:
            # 1. Normalize Params & Hash
            # Simple normalization: sort keys
            param_str = json.dumps(params, sort_keys=True)
            inputs_hash = hashlib.md5(f"{tool_name}:{param_str}".encode()).hexdigest()
            
            # 2. Check for Existing Doc (De-duplication)
            # If a valid (Verified/Draft) doc exists with same hash within TTL, return it?
            # Or always create new Draft and let verification dedup?
            # Let's create new Draft for this run, but link it?
            # For simplicity, we create a new Draft. Verification step can consolidate.
            
            doc = EvidenceDoc(
                debate_id=self.debate_id,
                agent_id=agent_id,
                tool_name=tool_name,
                params=params,
                content=result,
                inputs_hash=inputs_hash,
                status="DRAFT",
                trust_score=50,
                verification_log=[{
                    "event": "ingest",
                    "timestamp": datetime.now().isoformat(),
                    "note": "Initial ingestion"
                }]
            )
            
            db.add(doc)
            db.commit()
            db.refresh(doc)
            return doc
        finally:
            db.close()

    def verify(self, doc_id: str) -> EvidenceDoc:
        """
        Run verification checks on a DRAFT doc.
        Transitions to VERIFIED or QUARANTINE.
        """
        db = SessionLocal()
        try:
            doc = db.query(EvidenceDoc).filter(EvidenceDoc.id == doc_id).first()
            if not doc:
                raise ValueError(f"Doc {doc_id} not found")
                
            if doc.status != "DRAFT":
                return doc # Already processed
            
            checks_passed = True
            rejection_reason = ""
            
            # Check 1: Empty Data Sanity
            content = doc.content
            if isinstance(content, dict):
                # TEJ specific check
                if "data" in content and isinstance(content["data"], list) and len(content["data"]) == 0:
                    checks_passed = False
                    rejection_reason = "Empty data returned"
                if "error" in content:
                    checks_passed = False
                    rejection_reason = f"Tool returned error: {content['error']}"
            elif not content:
                checks_passed = False
                rejection_reason = "Empty content"
                
            # Check 2: Schema / Format (Simplified)
            # If passes Sanity, we assume format is okay for now.
            
            if checks_passed:
                doc.status = "VERIFIED"
                
                # Set TTL
                ttl_seconds = tool_manager.get_ttl(doc.tool_name)
                doc.ttl_expiry = datetime.now() + timedelta(seconds=ttl_seconds)
                doc.trust_score = 80 # Boost score
                
                doc.verification_log = doc.verification_log + [{
                    "event": "verify",
                    "status": "PASS",
                    "timestamp": datetime.now().isoformat()
                }]
            else:
                doc.status = "QUARANTINE"
                doc.trust_score = 10
                doc.verification_log = doc.verification_log + [{
                    "event": "verify",
                    "status": "FAIL",
                    "reason": rejection_reason,
                    "timestamp": datetime.now().isoformat()
                }]
                
            db.commit()
            db.refresh(doc)
            return doc
        finally:
            db.close()

    def check_aging(self):
        """
        Cron-like task to marks VERIFIED docs as STALE if TTL expired.
        """
        db = SessionLocal()
        try:
            now = datetime.now()
            stale_candidates = db.query(EvidenceDoc).filter(
                EvidenceDoc.status == "VERIFIED",
                EvidenceDoc.ttl_expiry < now
            ).all()
            
            for doc in stale_candidates:
                doc.status = "STALE"
                doc.verification_log = doc.verification_log + [{
                    "event": "aging",
                    "note": "TTL Expired",
                    "timestamp": datetime.now().isoformat()
                }]
                
            if stale_candidates:
                db.commit()
                print(f"EvidenceLifecycle: Marked {len(stale_candidates)} docs as STALE.")
        finally:
            db.close()
            
    def get_verified_evidence(self, limit=10) -> List[EvidenceDoc]:
        db = SessionLocal()
        try:
            return db.query(EvidenceDoc).filter(
                EvidenceDoc.debate_id == self.debate_id,
                EvidenceDoc.status == "VERIFIED"
            ).order_by(EvidenceDoc.created_at.desc()).limit(limit).all()
        finally:
            db.close()

    def create_checkpoint(self, step_name: str, context: Dict, next_actions: Dict = None) -> Checkpoint:
        """
        Create a Handoff Checkpoint.
        """
        db = SessionLocal()
        try:
            # Find Verified Evidence to link
            verified_docs = self.get_verified_evidence(limit=50) # Link recent ones
            doc_ids = [d.id for d in verified_docs]
            
            cp = Checkpoint(
                debate_id=self.debate_id,
                step_name=step_name,
                context_snapshot=context,
                cited_evidence_ids=doc_ids,
                next_actions=next_actions,
                lease_token=hashlib.sha256(f"{datetime.now}".encode()).hexdigest()[:16]
            )
            db.add(cp)
            db.commit()
            db.refresh(cp)
            return cp
        finally:
            db.close()
