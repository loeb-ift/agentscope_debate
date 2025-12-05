from abc import ABC, abstractmethod
from typing import Dict, Any, List

class ToolResult:
    """
    工具調用的標準回傳格式。
    """
    def __init__(self, data: Any, raw: Any, used_cache: bool, cost: float, citations: List[Dict]):
        self.data = data
        self.raw = raw
        self.used_cache = used_cache
        self.cost = cost
        self.citations = citations

    def to_dict(self):
        return {
            "data": self.data,
            "raw": self.raw,
            "used_cache": self.used_cache,
            "cost": self.cost,
            "citations": self.citations
        }

class UpstreamError(Exception):
    """
    上游服務錯誤。
    """
    def __init__(self, code: str, http_status: int, message: str):
        self.code = code
        self.http_status = http_status
        self.message = message
        super().__init__(f"[{code}] {message}")

class BaseToolAdapter(ABC):
    """
    工具轉接器的抽象基礎類別，定義了所有工具轉接器應遵循的介面。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """工具的唯一名稱。"""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """工具的版本。"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """工具的描述。"""
        pass

    @property
    @abstractmethod
    def auth_config(self) -> Dict:
        """工具的授權設定。"""
        pass

    @property
    @abstractmethod
    def rate_limit_config(self) -> Dict:
        """工具的速率限制設定。"""
        pass

    @property
    @abstractmethod
    def cache_ttl(self) -> int:
        """快取的存活時間（秒）。"""
        pass

    @abstractmethod
    def describe(self) -> Dict:
        """回傳工具的 JSON Schema。"""
        pass

    @abstractmethod
    def validate(self, params: Dict) -> None:
        """驗證傳入的參數是否符合 JSON Schema。"""
        pass

    @abstractmethod
    def auth(self, req: Dict) -> Dict:
        """對請求進行授權。"""
        pass

    @abstractmethod
    def invoke(self, params: Dict) -> ToolResult:
        """執行工具並回傳結果。"""
        pass

    @abstractmethod
    def should_cache(self, params: Dict) -> bool:
        """判斷是否應該快取這次的調用。"""
        pass

    @abstractmethod
    def cache_key(self, params: Dict) -> str:
        """產生快取鍵。"""
        pass

    @abstractmethod
    def map_error(self, http_status: int, body: Any) -> Exception:
        """將上游錯誤映射為平台的標準錯誤。"""
        pass
