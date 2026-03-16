"""
结构化日志模块
功能：统一的日志记录，支持文件输出、轮转、错误追踪
"""
import sys
import os
import json
from datetime import datetime
from pathlib import Path
from loguru import logger
import traceback

# 确保日志目录存在
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

# 移除默认的 handler
logger.remove()

# 添加控制台输出（带颜色）
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="DEBUG",
    colorize=True
)

# 添加文件输出 - 所有日志
logger.add(
    log_dir / "app_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG",
    rotation="100 MB",  # 每个文件最大100MB
    retention="30 days",  # 保留30天
    compression="zip",  # 压缩旧日志
    encoding="utf-8"
)

# 添加文件输出 - 错误日志单独存放
logger.add(
    log_dir / "error_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}\n{traceback}",
    level="ERROR",
    rotation="100 MB",
    retention="30 days",
    compression="zip",
    encoding="utf-8"
)

# 添加文件输出 - JSON 格式（便于后续分析）
logger.add(
    log_dir / "json_{time:YYYY-MM-DD}.log",
    format=lambda record: json.dumps({
        "time": record["time"].strftime("%Y-%m-%d %H:%M:%S.%f"),
        "level": record["level"].name,
        "module": record["name"],
        "function": record["function"],
        "line": record["line"],
        "message": record["message"],
        "extra": record["extra"]
    }, ensure_ascii=False) + "\n",
    level="INFO",
    rotation="100 MB",
    retention="30 days",
    compression="zip",
    encoding="utf-8"
)


# ========== 性能监控装饰器 ==========
def log_performance(log_level="INFO"):
    """
    性能监控装饰器
    记录函数执行时间、参数、返回值
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            try:
                result = func(*args, **kwargs)
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()

                # 记录性能信息
                logger.bind(
                    performance=True,
                    duration=duration,
                    function=func.__name__
                ).log(
                    log_level,
                    f"函数 {func.__name__} 执行完成，耗时: {duration:.3f}秒"
                )
                return result
            except Exception as e:
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                logger.bind(
                    performance=True,
                    duration=duration,
                    function=func.__name__,
                    error=str(e)
                ).error(
                    f"函数 {func.__name__} 执行失败，耗时: {duration:.3f}秒，错误: {e}"
                )
                raise

        return wrapper

    return decorator


# ========== 用户行为追踪 ==========
def log_user_action(username, action, details=None):
    """
    记录用户行为
    """
    extra = {
        "user": username,
        "action": action,
        "timestamp": datetime.now().isoformat()
    }
    if details:
        extra["details"] = details

    logger.bind(**extra).info(f"用户行为: {username} - {action}")


# ========== 问答日志 ==========
def log_qa_interaction(username, question, answer, context_docs=None, duration=None):
    """
    记录问答交互
    """
    extra = {
        "user": username,
        "question": question,
        "answer": answer[:200] + "..." if len(answer) > 200 else answer,
        "duration": duration
    }
    if context_docs:
        extra["context_count"] = len(context_docs)
        extra["context_sources"] = list(set([doc.metadata.get('source', 'unknown') for doc in context_docs]))

    logger.bind(**extra).info(f"问答: {username} - {question[:50]}...")


# 导出 logger 实例
__all__ = ['logger', 'log_performance', 'log_user_action', 'log_qa_interaction']