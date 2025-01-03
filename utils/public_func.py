__all__ = [
    "get_system",
    "generate_uuid",
    "generate_timestamp",
    "get_local_ip",
    "generate_ftp_passwd",
    "exists_port",
    "generate_http_port",
    "generate_project_path",
    "get_config_from_toml",
    "generate_product_version",
]

import time
import socket
import random
import os
import sys
import platform
import uuid
import json
from typing import Dict, Any

import toml


def get_system() -> str:
    """
    获取系统类型

    Returns:
        str: 系统类型
    """
    return platform.system()


def generate_uuid() -> str:
    """
    生成uuid

    Returns:
        str: 生成的uuid
    """
    return str(uuid.uuid1()).replace("-", "")


def generate_timestamp() -> int:
    """
    获取毫秒

    Returns:
        int: 毫秒
    """
    return int(time.time() * 1000)


def get_local_ip() -> str:
    """
    获取本地可通讯IP地址

    Returns:
        str: 本地可通讯IP地址
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except:
            return ""
    finally:
        s.close()

    return ip


def generate_ftp_passwd() -> str:
    """
    生成FTP密码

    Returns:
        str: FTP密码
    """
    base_str = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"

    return "".join(random.sample(base_str, 5))


def exists_port(port: int) -> bool:
    """
    判断端口是否被占用

    Args:
        port: 被判断端口号

    Returns:
        bool: 是否被占用
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.2)
        sock.connect((get_local_ip(), port))
        sock.close()
        return True
    except:
        return False


def generate_http_port(start_port: int) -> int:
    """
    生成HTTP可用端口

    Args:
        start_port: 起始端口

    Returns:
        int: HTTP可用端口
    """
    if start_port <= 1024:
        start_port = 8080

    if exists_port(start_port):
        start_port += 1
        return generate_http_port(start_port)
    else:
        return start_port


def generate_project_path() -> str:
    """
    生成项目主目录路径

    Returns:
        str: 项目主目录路径
    """
    if getattr(sys, "frozen", False):
        # MacOS的静态文件均放在Resources路径下
        if get_system() == "Darwin":
            return os.path.join(
                os.path.dirname(os.path.dirname(sys.executable)), "Resources"
            )
        else:
            return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_config_from_toml(is_customize: bool = True) -> Dict[str, Any]:
    """
    配置文件转字典

    Args:
        is_customize: 是否为用户配置

    Returns:
        Dict[str, Any]: 转成的字典
    """
    project_path = generate_project_path()
    tool_config = {}
    if is_customize:
        settings_file = os.path.join(project_path, "customize.toml")
        if not os.path.exists(settings_file):
            settings_file = os.path.join(project_path, "pyproject.toml")
    else:
        settings_file = os.path.join(project_path, "pyproject.toml")
    if not os.path.exists(settings_file):
        return tool_config

    try:
        tool_config = toml.load(settings_file)
    except Exception:
        pass

    return tool_config


def generate_product_version() -> str:
    """
    生成项目版本号

    Returns:
        str: 项目版本号
    """
    tool_config = get_config_from_toml(False)

    return tool_config.get("file-sharer", {}).get("version", "0.1.0")


def generate_color_card_map() -> Dict[str, str]:
    """
    生成配置的颜色表(色卡)

    Returns:
        Dict[str, str]: 配置的颜色表
    """
    project_path = generate_project_path()
    color_card_json_path = os.path.join(
        project_path, "static", "themes", "color_card.json"
    )
    if not os.path.exists(color_card_json_path):
        color_card_json_path = os.path.join(project_path, "color_card.json")
    if not os.path.exists(color_card_json_path):
        return {}

    with open(color_card_json_path, encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return {}
