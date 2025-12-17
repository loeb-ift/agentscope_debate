from enum import Enum

class TejErrorType(Enum):
    RECOVERABLE = "recoverable" # 參數錯誤、Rate Limit → 調整參數重試
    TERMINAL = "terminal"       # 資料不存在、權限不足 → 停止嘗試該路徑
    FATAL = "fatal"             # 系統崩潰、認證失效 → 立即中斷流程

class ToolError(Exception):
    def __init__(self, message: str, error_type: TejErrorType = TejErrorType.RECOVERABLE, metadata: dict = None):
        super().__init__(message)
        self.error_type = error_type
        self.metadata = metadata or {}

class ToolRecoverableError(ToolError):
    def __init__(self, message: str, metadata: dict = None):
        super().__init__(message, TejErrorType.RECOVERABLE, metadata)

class ToolTerminalError(ToolError):
    def __init__(self, message: str, metadata: dict = None):
        super().__init__(message, TejErrorType.TERMINAL, metadata)

class ToolFatalError(ToolError):
    def __init__(self, message: str, metadata: dict = None):
        super().__init__(message, TejErrorType.FATAL, metadata)