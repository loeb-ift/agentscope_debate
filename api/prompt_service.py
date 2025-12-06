from sqlalchemy.orm import Session
from api import models
import yaml
import os

PROMPT_FILE_PATH = "prompts/system_prompts.yaml"

class PromptService:
    _file_cache = {}

    @classmethod
    def load_defaults_from_file(cls):
        """從 YAML 文件加載預設 Prompt"""
        if os.path.exists(PROMPT_FILE_PATH):
            try:
                with open(PROMPT_FILE_PATH, "r", encoding="utf-8") as f:
                    cls._file_cache = yaml.safe_load(f) or {}
                print(f"Loaded {len(cls._file_cache)} prompts from file.")
            except Exception as e:
                print(f"Error loading prompts file: {e}")
        else:
            print(f"Warning: Prompt file not found at {PROMPT_FILE_PATH}")

    @classmethod
    def initialize_db_from_file(cls, db: Session):
        """初始化資料庫中的 Prompt (若不存在)"""
        if not cls._file_cache:
            cls.load_defaults_from_file()
            
        for key, content in cls._file_cache.items():
            existing = db.query(models.PromptTemplate).filter(models.PromptTemplate.key == key).first()
            if not existing:
                print(f"Initializing prompt: {key}")
                new_prompt = models.PromptTemplate(
                    key=key,
                    language="zh-TW", # Default language
                    content=content,
                    version=1
                )
                db.add(new_prompt)
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