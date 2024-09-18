from __future__ import annotations
import logging
import os
import socket
import traceback
from datetime import datetime
from typing import List

from aiohttp import web

from . import constants, judger


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('localhost', 0))  # Bind to any available port on localhost
        return s.getsockname()[1]  # Return the port number


def get_logger():
    # 获取当前脚本的所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # 创建日志文件夹路径
    log_dir = os.path.join(current_dir, 'log')

    # 如果日志文件夹不存在，则创建它
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 创建日志文件的完整路径
    log_filename = os.path.join(log_dir, datetime.now().strftime('%Y-%m-%d') + '.log')

    # 创建一个日志记录器
    logger = logging.getLogger('my_logger')
    logger.setLevel(logging.DEBUG)

    # 创建一个日志格式化器
    formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')

    # 创建一个控制台处理器并设置其格式
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # 创建一个文件处理器并设置其格式
    file_handler = logging.FileHandler(log_filename)
    file_handler.setFormatter(formatter)

    # 将处理器添加到记录器中
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


def get_exception_details(exception, target: judger.Judger) -> str:
    """
    获取异常的详细信息，包括异常类型、异常信息和堆栈跟踪信息，
    并返回一个包含这些信息的字符串。

    :param exception: 异常实例
    :param target: 发生异常的judger实体
    :return: 包含异常详情的字符串
    """
    # 获取异常类型和异常信息
    exception_type = type(exception).__name__
    exception_message = str(exception)

    # 获取堆栈跟踪信息
    stack_trace = ''.join(traceback.format_tb(exception.__traceback__))

    # 将所有信息格式化为一个字符串
    details = f"来自 Judger 的内部错误\n"
    details += f"JID: {target.jid}\n"
    details += f"Exception Type: {exception_type}\n"
    details += f"Exception Message: {exception_message}\n"
    details += f"Stack Trace:\n{stack_trace}"

    return details


def response_ok(data=None):
    if data is None:
        return web.json_response({"code": constants.ResponseCode.OK})
    else:
        return web.json_response({"code": constants.ResponseCode.OK, "data": data})


def response_code(code: int):
    return web.json_response({"code": code})


def response_error(message: str):
    return web.json_response({"code": constants.ResponseCode.ERROR, "message": message})


def response_message(message: str):
    return web.json_response({"code": constants.ResponseCode.MSG, "message": message})


def array_to_text(arr: List[int]) -> str:
    flag = False
    res = ''
    for i in arr:
        if not flag:
            res += str(i)
            flag = True
        else:
            res += ", " + str(i)
    return res
