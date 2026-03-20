from typing import Any, Dict, Optional

class AdaptIQException(Exception):
    """Base exception for the AdaptIQ application."""
    def __init__(self, message: str, status_code: int = 500, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}

class FlowExecutionError(AdaptIQException):
    """Raised when an orchestration flow (employer or employee) fails."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=500, details=details)

class ClientConnectionError(AdaptIQException):
    """Raised when an external client (LLM, Vector DB, Graph DB) cannot be reached."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=503, details=details)

class ValidationErorr(AdaptIQException):
    """Raised when input validation fails."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=400, details=details)

