from sqlalchemy.orm import Session
from api import models
import yaml
import os
import glob

PROMPTS_SYSTEM_DIR = "prompts/system"

class PromptService:
    _file_cache = {}
    _base_contract = None

    @classmethod
    def load_base_contract(cls):
        """加載 Base Contract"""
        contract_path = os.path.join(PROMPTS_SYSTEM_DIR, "base_contract.yaml")
        if os.path.exists(contract_path):
            try:
                with open(contract_path, "r", encoding="utf-8") as f:
                    cls._base_contract = yaml.safe_load(f)
                print(f"Loaded Base Contract from {contract_path}")
            except Exception as e:
                print(f"Error loading Base Contract: {e}")

    @classmethod
    def load_defaults_from_file(cls):
        """從 YAML 文件加載預設 Prompt (掃描目錄)"""
        cls._file_cache = {}
        cls.load_base_contract()
        
        if not os.path.exists(PROMPTS_SYSTEM_DIR):
            print(f"Warning: Prompts directory not found at {PROMPTS_SYSTEM_DIR}")
            return

        yaml_files = glob.glob(os.path.join(PROMPTS_SYSTEM_DIR, "*.yaml"))
        
        for file_path in yaml_files:
            if os.path.basename(file_path) == "base_contract.yaml":
                continue
                
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if data and isinstance(data, dict):
                        cls._file_cache.update(data)
            except Exception as e:
                print(f"Error loading prompt file {file_path}: {e}")
        
        print(f"Loaded {len(cls._file_cache)} prompts from {len(yaml_files)} files.")

    @classmethod
    def initialize_db_from_file(cls, db: Session):
        """初始化資料庫中的 Prompt (若不存在)"""
        if not cls._file_cache:
            cls.load_defaults_from_file()
            
        for key, content in cls._file_cache.items():
            # Check specifically for zh-TW version
            existing = db.query(models.PromptTemplate).filter(
                models.PromptTemplate.key == key,
                models.PromptTemplate.language == "zh-TW"
            ).first()
            
            if not existing:
                print(f"Initializing prompt: {key} (zh-TW)")
                new_prompt = models.PromptTemplate(
                    key=key,
                    language="zh-TW", # Default language
                    content=content,
                    version=1
                )
                db.add(new_prompt)
            else:
                # Update existing prompt if content changed (Force sync from file)
                if existing.content != content:
                    print(f"Updating prompt content: {key}")
                    existing.content = content
                    # existing.version += 1 # Optional: increment version
        try:
            db.commit()
        except Exception as e:
            print(f"Error initializing prompts in DB: {e}")
            db.rollback()

    @staticmethod
    def get_prompt(db: Session, key: str, language: str = "zh-TW", default: str = None) -> str:
        """
        獲取 Prompt 內容。
        優先級: 資料庫 -> 文件快取 -> 代碼傳入的 default -> 空字串
        """
        # 1. Check Database
        prompt = db.query(models.PromptTemplate).filter(
            models.PromptTemplate.key == key,
            models.PromptTemplate.language == language
        ).first()
        
        if prompt:
            return prompt.content
        
        # 2. Check File Cache (System Defaults)
        if key in PromptService._file_cache:
            return PromptService._file_cache[key]
            
        # 3. Fallback
        if default:
            return default
            
        # 4. Reload cache just in case
        PromptService.load_defaults_from_file()
        if key in PromptService._file_cache:
            return PromptService._file_cache[key]

        return ""

    @classmethod
    def compose_system_prompt(cls, db: Session, agent_key: str = None, override_content: str = None) -> str:
        """
        組合最終的 System Prompt (Base Contract + Agent Persona)。
        
        Args:
            db: 資料庫 Session
            agent_key: Agent 的 Prompt Key (e.g., 'agents.risk_officer')，若無則只返回 Contract
            override_content: 直接傳入的 Agent Persona 內容 (可選)
            
        Returns:
            str: 完整的 System Prompt
        """
        # 1. Load Base Contract
        if not cls._base_contract:
            cls.load_base_contract()
            
        contract_text = ""
        if cls._base_contract:
            c = cls._base_contract
            rules = c.get('rules', {})
            
            rule_texts = []
            for rule_name, content in rules.items():
                instruction = content.get('instruction', '')
                rule_texts.append(f"### {rule_name.upper()}\n{instruction}")
            
            contract_body = "\n\n".join(rule_texts)
            
            contract_text = f"""
# System Base Contract (MUST FOLLOW)
The following rules are non-negotiable and override any persona instructions.

{contract_body}
"""

        # 2. Load Agent Persona
        persona_text = ""
        if override_content:
            persona_text = override_content
        elif agent_key:
            persona_text = cls.get_prompt(db, agent_key, default="")

        # 3. Combine
        full_prompt = f"{contract_text}\n\n# Agent Role & Specific Instructions\n{persona_text}"
        return full_prompt.strip()