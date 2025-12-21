"""
Push Notification Manager (Supports Consolidated Batch Push)

This module handles the delivery of final valuation reports.
It now supports 'Consolidated Push' to merge multiple ticker reports into one delivery.
"""

import structlog
import json
from typing import Dict, Any, Optional, List

logger = structlog.get_logger()

class PushNotifier:
    def __init__(self, target_config: Optional[Dict[str, Any]] = None):
        self.config = target_config or {}

    def push_consolidated_report(self, batch_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        將多個標的的估值報告合併為一則推送。
        """
        if not batch_data:
            return {"success": False, "error": "Empty batch data"}

        count = len(batch_data)
        summary_lines = []
        for item in batch_data:
            entity = item.get("entity", "Unknown")
            verdict = item.get("verdict", "N/A")
            conf = item.get("confidence", 0)
            summary_lines.append(f"- {entity}: {verdict} (信心: {conf}/10)")

        batch_summary = "\n".join(summary_lines)
        message = f"🚀 【MARS 投資組合估值合併推送】\n本次包含 {count} 個標的：\n{batch_summary}"
        
        logger.info("pushing_consolidated_report", ticker_count=count)
        
        # 模擬推送至 Slack/Email/LINE
        success = True
        
        return {
            "success": success,
            "count": count,
            "type": "consolidated",
            "message_preview": message[:200] + "..."
        }

    def push_valuation_report(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """單一報告推送"""
        entity = report_data.get("entity", "Unknown Entity")
        verdict = report_data.get("verdict", "N/A")
        confidence = report_data.get("confidence", 0)
        
        message = f"🔔 【MARS 估值推送】\n標的: {entity}\n最終裁決: {verdict}\n信心評分: {confidence}/10"
        
        return {
            "success": True,
            "entity": entity,
            "message_preview": message[:50] + "..."
        }

def trigger_report_push(report_json: str) -> Dict[str, Any]:
    """Agent 調用的入口點，支援單一 JSON 或 JSON List (合併推送)"""
    try:
        data = json.loads(report_json)
        notifier = PushNotifier()
        
        if isinstance(data, list):
            return notifier.push_consolidated_report(data)
        else:
            return notifier.push_valuation_report(data)
            
    except Exception as e:
        logger.error("push_failed", error=str(e))
        return {"success": False, "error": str(e)}
