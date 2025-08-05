#常用工具方法

import sys
import os
import importlib

#常用日志记录器
from loguru import logger
def setup_logging():
    logger.remove()
    logger.add(
        #输出日志到控制台，格式是：时间 | 日志等级 | 进程名 | 线程名 | 日志消息
        sink=sys.stdout,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {process.name:<15} | {thread.name:<15} | {message}",
        level="DEBUG",
        filter=lambda record:'coroutine' not in record
        )
    logger.add(
        #输出日志到文件toolbox.log，格式是：时间 | 日志等级 | 进程名 | 线程名 | 日志消息
        sink="toolbox.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {process.name:<15} | {thread.name:<15} | {message}",
        level="DEBUG",
        filter=lambda record:'coroutine' not in record
        )
    logger.add(
        #输出日志到控制台，并能记录协程信息，格式是：时间 | 日志等级 | 进程名 | 线程名 | 协程名 | 日志消息
        sink=sys.stdout,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {process.name:<15} | {thread.name:<15} | {coroutine.name:15} | {message}",
        level="DEBUG",
        filter=lambda record:'coroutine' in record
        )
    logger.add(
        #输出日志到文件toolbox.log，并能记录协程信息，格式是：时间 | 日志等级 | 进程名 | 线程名 | 协程名 | 日志消息
        sink="toolbox.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {process.name:<15} | {thread.name:<15} | {coroutine.name:15} | {message}",
        level="DEBUG",
        filter=lambda record:'coroutine' in record
        )
    return logger
logger = setup_logging()

#将项目根目录和工具目录添加到系统路径中，主要给工具模块导入使用
from pathlib import Path
def setup_sys_path():
    current_file = Path(__file__).resolve()# #当前文件的绝对路径
    current_dir = current_file.parent #当前工具的父目录
    project_root_dir = current_dir.parent #项目根目录
    if current_dir not in sys.path:
        sys.path.append(str(current_dir))
        logger.debug(f"添加当前工具目录到系统路径：{current_dir}")
    if project_root_dir not in sys.path:
        sys.path.append(str(project_root_dir))
        logger.debug(f"添加项目根目录到系统路径：{project_root_dir}")
    logger.debug(f"当前系统路径：{sys.path}")


#IP地址检查工具
import ipaddress
def ipAddressCheck(user_input_ip):
    """
    检查用户输入的IP地址或CIDR块是否有效，并返回有效的主机列表
    :param user_input_ip: 用户输入的IP地址或CIDR块
    :return: 有效的主机列表，如果输入无效则返回None
    """
    hosts = []
    try:
        ip = ipaddress.ip_address(user_input_ip)
        if isinstance(ip, ipaddress.IPv4Address):
            hosts.append(ip)
        elif isinstance(ip, ipaddress.IPv6Address):
            hosts.append(ip)
        return hosts
    except ValueError:
        try:
            cidr = ipaddress.ip_network(user_input_ip, strict=False)
            if isinstance(cidr, ipaddress.IPv4Network):
                hosts.extend(cidr.hosts())
            elif isinstance(cidr, ipaddress.IPv6Network):
                hosts.extend(cidr.hosts())
            return hosts
        except ValueError:
            return None