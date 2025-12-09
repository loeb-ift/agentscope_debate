import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Debate Configuration
    MAX_TEAMS_PER_DEBATE = int(os.getenv("MAX_TEAMS_PER_DEBATE", 3))
    MAX_MEMBERS_PER_TEAM = int(os.getenv("MAX_MEMBERS_PER_TEAM", 2))
    
    # System Configuration
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/debate.db")
    REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

    # Metadata for UI
    CONFIG_DESCRIPTIONS = {
        "OLLAMA_HOST": "LLM 服務器地址 (例如 http://10.x.x.x:11434)",
        "OLLAMA_MODEL": "使用的 LLM 模型名稱 (例如 gpt-oss:20b)",
        "MAX_TEAMS_PER_DEBATE": "每場辯論的最大團隊數",
        "MAX_MEMBERS_PER_TEAM": "每個團隊的最大成員數",
        "GOOGLE_SEARCH_API_KEY": "Google Custom Search API Key",
        "GOOGLE_CSE_ID": "Google Custom Search Engine ID",
        "BRAVE_SEARCH_API_KEY": "Brave Search API Key",
        "TEJ_API_KEY": "TEJ 台灣經濟新報 API Key",
        "LOG_LEVEL": "系統日誌級別 (INFO, DEBUG)",
        "DEFAULT_LANGUAGE": "預設語言 (zh-TW)",
        "REDIS_HOST": "Redis 主機地址",
        "REDIS_URL": "Redis 連接 URL",
        "DATABASE_URL": "資料庫連接 URL"
    }

    @classmethod
    def update(cls, key, value):
        """Update config in memory and save to .env"""
        # 1. Update Memory
        if hasattr(cls, key):
            # Simple type casting
            current_val = getattr(cls, key)
            if isinstance(current_val, int):
                try:
                    value = int(value)
                except:
                    pass
            setattr(cls, key, value)
        
        # 2. Update File (.env)
        env_path = ".env"
        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                lines = f.readlines()
        
        new_lines = []
        found = False
        for line in lines:
            if line.strip().startswith(f"{key}="):
                new_lines.append(f"{key}={value}\n")
                found = True
            else:
                new_lines.append(line)
        
        if not found:
            if new_lines and not new_lines[-1].endswith('\n'):
                new_lines.append('\n')
            new_lines.append(f"{key}={value}\n")
        
        with open(env_path, "w") as f:
            f.writelines(new_lines)
            
    @classmethod
    def get_all(cls):
        """Get all configs, merging class attrs and .env file content"""
        configs = {k: getattr(cls, k) for k in dir(cls) if k.isupper() and not k.startswith("_")}
        
        # Read from .env to capture keys not in class attrs
        env_path = ".env"
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"): continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip()
                        if key not in configs:
                            configs[key] = val
        return configs

# Backward compatibility proxies (but mutable if accessed via Config)
# Note: If modules import these directly, they get the initial value.
# We should refactor to use Config.VAR
MAX_TEAMS_PER_DEBATE = Config.MAX_TEAMS_PER_DEBATE
MAX_MEMBERS_PER_TEAM = Config.MAX_MEMBERS_PER_TEAM
DATABASE_URL = Config.DATABASE_URL
REDIS_URL = Config.REDIS_URL