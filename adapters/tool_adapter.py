from abc import ABC, abstractmethod
from typing import Dict, Any

class ToolAdapter(ABC):
    """
    工具適配器的抽象基礎類別。
    """
    @property
    @abstractmethod
    def name(self) -> str:
        """工具的名稱。"""
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
    def schema(self) -> Dict[str, Any]:
        """工具的 JSON Schema。"""
        pass

    @abstractmethod
    def describe(self) -> Dict[str, Any]:
        """回傳工具的詳細描述，包含 JSON Schema。"""
        pass

    @abstractmethod
    def invoke(self, **kwargs: Any) -> Dict[str, Any]:
        """調用工具。"""
        pass
