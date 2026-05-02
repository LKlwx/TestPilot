import logging
import os
from logging.handlers import RotatingFileHandler
from logging import Formatter


def setup_logger(app):
    """配置项目日志系统"""
    # 日志目录
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 日志格式
    log_format = Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. 常规日志（INFO及以上） - 每天切割，保留7天
    info_handler = RotatingFileHandler(
        os.path.join(log_dir, "app.log"),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=7,
        encoding="utf-8"
    )
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(log_format)

    # 2. 错误日志（ERROR及以上） - 单独文件，保留30天
    error_handler = RotatingFileHandler(
        os.path.join(log_dir, "error.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=30,
        encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(log_format)

    # 3. 调试日志（DEBUG） - 开发环境用
    debug_handler = RotatingFileHandler(
        os.path.join(log_dir, "debug.log"),
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding="utf-8"
    )
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(log_format)

    # 注册到Flask应用
    app.logger.addHandler(info_handler)
    app.logger.addHandler(error_handler)

    # 同时设置root logger，让其他模块的日志也能写入
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(info_handler)
    root_logger.addHandler(error_handler)

    # 开发环境加debug日志
    if app.debug:
        root_logger.addHandler(debug_handler)

    return app.logger


def get_logger(name):
    """获取业务日志记录器"""
    return logging.getLogger(name)


def log_request(request, response=None):
    """记录请求日志"""
    logger = logging.getLogger("request")
    msg = f"{request.method} {request.path} - {request.remote_addr}"
    if response:
        msg += f" - {response.status_code}"
    logger.info(msg)


def log_error(error, context=""):
    """记录错误日志"""
    logger = logging.getLogger("error")
    logger.error(f"{context}: {str(error)}", exc_info=True)