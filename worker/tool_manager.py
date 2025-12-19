import yaml
import os
import random
from typing import Dict, Optional, Any, List
from pydantic import BaseModel, Field, validator
from datetime import datetime, time as dtime, timedelta, timezone

# --- Pydantic Models for Validation ---

class ToolCost(BaseModel):
    api_cost_per_call: float = 0.0

class ToolPermissions(BaseModel):
    allow_ltm: bool = True
    allow_stale_on_error: bool = False
    max_stale_age: int = 3600
    requires_approval: bool = False

class ToolConfigModel(BaseModel):
    ttl: Optional[int] = None
    trading_hours_ttl: Optional[int] = None
    after_hours_ttl: Optional[str] = None
    jitter_percentage: Optional[int] = 0
    update_cycle: Optional[str] = None

class ToolDefinition(BaseModel):
    name: str
    lifecycle: str = Field(..., pattern=r'^(realtime|intraday|periodic|static|event_driven)$')
    config: ToolConfigModel
    permissions: ToolPermissions
    cost: ToolCost
    owner: Optional[str] = None

class RegistryConfig(BaseModel):
    version: str
    last_updated: str
    defaults: Dict[str, Any]
    tools: List[ToolDefinition]

# --- TTL Calculator ---

class TTLCalculator:
    def __init__(self):
        # UTC+8 for Taiwan Market
        self.tz_tw = timezone(timedelta(hours=8))
        
    def _is_trading_hours(self, dt: datetime) -> bool:
        if dt.weekday() >= 5: # Sat=5, Sun=6
            return False
        t = dt.time()
        # Market Hours: 09:00 - 13:30
        return dtime(9, 0) <= t <= dtime(13, 30)

    def _next_market_open(self, dt: datetime) -> datetime:
        """Find the next market open time (09:00)"""
        target = dt.replace(hour=9, minute=0, second=0, microsecond=0)
        
        # If already past 09:00 today, move to tomorrow
        if dt.time() >= dtime(9, 0):
             target += timedelta(days=1)
             
        # Skip weekends
        while target.weekday() >= 5:
             target += timedelta(days=1)
             
        return target

    def calculate(self, tool_def: ToolDefinition) -> int:
        """Calculate dynamic TTL based on lifecycle and current time"""
        now = datetime.now(self.tz_tw)
        
        # 1. Realtime (Market Aware)
        if tool_def.lifecycle == "realtime":
            if self._is_trading_hours(now):
                base = tool_def.config.trading_hours_ttl or 300
            else:
                # After hours
                if tool_def.config.after_hours_ttl == "dynamic":
                    next_open = self._next_market_open(now)
                    delta = (next_open - now).total_seconds()
                    base = max(int(delta), 60) # At least 1 min
                else:
                    base = 3600 # Fallback
        
        # 2. Intraday (Expires at midnight)
        elif tool_def.lifecycle == "intraday":
            end_of_day = now.replace(hour=23, minute=59, second=59)
            base = max(int((end_of_day - now).total_seconds()), 60)
            if tool_def.config.ttl: # Override if explicit static TTL provided
                 base = tool_def.config.ttl

        # 3. Periodic (Quarterly/Monthly)
        elif tool_def.lifecycle == "periodic":
            # Simplified Logic: Default to 7 days or explicit TTL if provided
            # Full implementation would calculate quarter end dates
            base = tool_def.config.ttl or 604800 # 7 days
            
        # 4. Static
        else:
            base = tool_def.config.ttl or 86400 # 24h default

        # Add Jitter
        jitter_pct = tool_def.config.jitter_percentage or 0
        if jitter_pct > 0:
            jitter_range = int(base * (jitter_pct / 100.0))
            if jitter_range > 0:
                base += random.randint(-jitter_range, jitter_range)
                
        return max(base, 1) # Ensure positive

# --- Tool Manager ---

class ToolManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ToolManager, cls).__new__(cls)
            cls._instance._load_registry()
        return cls._instance

    def _load_registry(self):
        config_path = os.path.join(os.path.dirname(__file__), "../config/tool_registry.yaml")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            self.registry = RegistryConfig(**data)
            self.tool_map = {t.name: t for t in self.registry.tools}
            self.defaults = self.registry.defaults
            self.ttl_calc = TTLCalculator()
            print(f"Loaded Tool Registry v{self.registry.version}")
        except Exception as e:
            print(f"ERROR: Failed to load tool registry: {e}")
            # Fallback empty registry
            self.tool_map = {}
            self.defaults = {}

    def get_tool_config(self, tool_name: str) -> ToolDefinition:
        """Get configuration for a tool. Returns default if not found."""
        if tool_name in self.tool_map:
            return self.tool_map[tool_name]
        
        # Construct default definition
        return ToolDefinition(
            name=tool_name,
            lifecycle=self.defaults.get("lifecycle", "static"),
            config=self.defaults.get("config", {}),
            permissions=self.defaults.get("permissions", {}),
            cost=self.defaults.get("cost", {})
        )

    def get_ttl(self, tool_name: str) -> int:
        tool_def = self.get_tool_config(tool_name)
        return self.ttl_calc.calculate(tool_def)
        
    def should_consolidate(self, tool_name: str) -> bool:
        tool_def = self.get_tool_config(tool_name)
        return tool_def.permissions.allow_ltm

# Global Instance
tool_manager = ToolManager()