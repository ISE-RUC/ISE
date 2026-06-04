"""
Shared API response helpers.
"""
from typing import Any


def api_response(data: Any = None, msg: str = "success", code: int = 0) -> dict:
    """Return the standard business response shape."""
    return {
        "code": code,
        "msg": msg,
        "data": data,
    }


def success(data: Any = None, msg: str = "success") -> dict:
    """Successful response."""
    return api_response(data=data, msg=msg, code=0)


def error(msg: str = "error", code: int = 1, data: Any = None) -> dict:
    """Error response."""
    return api_response(data=data, msg=msg, code=code)
