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
        return {k: getattr(cls, k) for k in dir(cls) if k.isupper() and not k.startswith("_")}

# Backward compatibility proxies (but mutable if accessed via Config)
# Note: If modules import these directly, they get the initial value.
# We should refactor to use Config.VAR
MAX_TEAMS_PER_DEBATE = Config.MAX_TEAMS_PER_DEBATE
MAX_MEMBERS_PER_TEAM = Config.MAX_MEMBERS_PER_TEAM
DATABASE_URL = Config.DATABASE_URL
REDIS_URL = Config.REDIS_URL