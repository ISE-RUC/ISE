"""
统一API响应工具模块
提供标准化的JSON响应格式
"""
from typing import Any, Optional


def api_response(data: Any = None, msg: str = "success", code: int = 0) -> dict:
    """
    统一API响应格式

    :param data: 响应数据
    :param msg: 响应消息
    :param code: 业务状态码 (0表示成功，非0表示失败)
    :return: 标准响应字典
    """
    return {
        "code": code,
        "msg": msg,
        "data": data
    }


def success(data: Any = None, msg: str = "success") -> dict:
    """
    成功响应

    :param data: 响应数据
    :param msg: 响应消息
    :return: 标准响应字典
    """
    return api_response(data=data, msg=msg, code=0)


def error(msg: str = "error", code: int = 1, data: Any = None) -> dict:
    """
    错误响应

    :param msg: 错误消息
    :param code: 业务错误码
    :param data: 可选的错误详情数据
    :return: 标准响应字典
    """
    return api_response(data=data, msg=msg, code=code)
