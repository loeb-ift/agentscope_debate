import os
import json
import logging
from typing import Dict, Any, List, Optional
from api.redis_client import get_redis_client

class ChairmanFacilitationMixin:
    """
    Mixin for Chairman to facilitate debate flow without making conclusions.
    Enabled via CHAIRMAN_FACILITATION=1 environment variable.
    """
    
    def _is_facilitation_enabled(self) -> bool:
        return os.getenv("CHAIRMAN_FACILITATION", "0") == "1"

    def _publish_event(self, debate_id: str, event_type: str, payload: Dict[str, Any]):
        """
        Emit event using Redis Pub/Sub to merge with existing SSE stream.
        """
        try:
            # If debate_id is missing, we cannot publish to specific stream
            if not debate_id:
                print(f"[Facilitation] Event {event_type} dropped (no debate_id)")
                return

            redis_client = get_redis_client()
            channel = f"debate:{debate_id}:log_stream"
            history_key = f"debate:{debate_id}:log_history"
            
            # Construct SSE compatible message
            # Existing frontend expects 'role' and 'content' for logging
            # We add 'type' and 'payload' for specialized handling if needed
            event = {
                "type": event_type,
                "payload": payload,
                "role": "Chairman (System)", # Distinct role
                "content": f"⚡ [Event: {event_type}] {json.dumps(payload, ensure_ascii=False)[:100]}..." # Human readable fallback
            }
            
            message = json.dumps(event, ensure_ascii=False)
            
            # Publish and Append to History
            redis_client.publish(channel, message)
            redis_client.rpush(history_key, message)
            
            print(f"[Facilitation] Published {event_type} to {channel}")
            
        except Exception as e:
            print(f"[Facilitation] Failed to publish event {event_type}: {e}")

    async def generate_plan_nodes(self, debate_id: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate execution plan nodes.
        Event: ChairmanRequestsPublished
        """
        if not self._is_facilitation_enabled():
            return []

        # TODO: Implement actual planning logic
        plan_nodes = [
            {"id": "node_init", "type": "initial_scan", "status": "pending"},
            {"id": "node_deep", "type": "deep_research", "status": "pending"}
        ]
        
        self._publish_event(debate_id, "ChairmanRequestsPublished", {
            "plan_nodes": plan_nodes,
            "context_summary": str(context)[:50],
            "trace_id": context.get("trace_id")
        })
        return plan_nodes

    async def publish_requests(self, debate_id: str, requests: List[Dict[str, Any]]):
        """
        Publish requests to agents.
        Event: ChairmanRequestsPublished
        """
        if not self._is_facilitation_enabled():
            return

        self._publish_event(debate_id, "ChairmanRequestsPublished", {
            "requests": requests,
            "request_count": len(requests)
        })

    async def detect_mode_switch(self, debate_id: str, current_state: Dict[str, Any]) -> str:
        """
        Detect if mode should switch (e.g. to ranking_debate).
        Event: ChairmanModeSwitch
        """
        if not self._is_facilitation_enabled():
            return "normal"

        # Mock Logic: Switch if 'ranking_triggered' is in state
        mode = "normal"
        if current_state.get("ranking_triggered"):
            mode = "ranking_debate"
            self._publish_event(debate_id, "ChairmanModeSwitch", {
                "from_mode": "normal",
                "to_mode": "ranking_debate",
                "rationale": "Ranking trigger detected in state"
            })
        
        return mode

    async def summarize_without_conclusion(self, debate_id: str, process_data: Dict[str, Any]):
        """
        Provide a procedural summary without a final verdict.
        Event: ChairmanDecisionLog
        """
        if not self._is_facilitation_enabled():
            return

        self._publish_event(debate_id, "ChairmanDecisionLog", {
            "summary_type": "procedural_summary",
            "coverage": process_data.get("coverage", 0),
            "issues": process_data.get("issues", [])
        })
