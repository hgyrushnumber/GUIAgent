# utils/logger.py
import logging
from logging import Logger, Formatter, FileHandler
from typing import Optional
import sys
import threading
from pathlib import Path
from datetime import datetime

# 模块级变量：用于管理独立的文件日志 handler
_file_handler_initialized: bool = False
_file_handler: Optional[FileHandler] = None
_file_handler_lock = threading.Lock()


def configure_global_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    auto_generate_log_file: bool = True,
    log_dir: Optional[str] = None
):
    """
    配置全局日志系统
    
    Args:
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
        log_file: 日志文件路径（如果为 None 且 auto_generate_log_file=True，则自动生成）
        auto_generate_log_file: 如果 log_file 为 None，是否自动生成日志文件
        log_dir: 日志目录（默认：logs/ 相对于工作目录）
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Create formatter with more details
    formatter = Formatter(
        "[%(asctime)s][%(levelname)s][%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    handlers = []
    
    # Console handler with colored output support
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    handlers.append(console_handler)

    # File handler
    final_log_file = log_file
    if not final_log_file and auto_generate_log_file:
        # 自动生成日志文件名：logs/agent_YYYYMMDD_HHMMSS.log
        if log_dir is None:
            log_dir = "logs"
        
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_log_file = str(log_path / f"agent_{timestamp}.log")
    
    if final_log_file:
        # 确保日志文件目录存在
        log_file_path = Path(final_log_file)
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = FileHandler(final_log_file, encoding="utf-8", mode='w')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)  # 文件日志使用相同的级别
        handlers.append(file_handler)
        
        # 记录日志文件位置
        console_handler_temp = logging.StreamHandler(sys.stdout)
        console_handler_temp.setFormatter(Formatter("%(message)s"))
        temp_logger = logging.getLogger("LoggerConfig")
        temp_logger.addHandler(console_handler_temp)
        temp_logger.setLevel(logging.INFO)
        temp_logger.info(f"Log file: {final_log_file}")
        temp_logger.removeHandler(console_handler_temp)

    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=True  # Override any existing configuration
    )
    
    return final_log_file  # 返回实际使用的日志文件路径


def _ensure_file_handler() -> None:
    """
    确保文件 handler 已创建并初始化。
    该函数是线程安全的，只会创建一次文件 handler。
    """
    global _file_handler_initialized, _file_handler
    
    # 如果已初始化，直接返回
    if _file_handler_initialized:
        return
    
    # 使用锁保护初始化过程（线程安全）
    with _file_handler_lock:
        # 双重检查，避免多线程环境下重复初始化
        if _file_handler_initialized:
            return
        
        # 创建 logs 目录
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 使用时间戳创建日志文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"pcguiagent_{timestamp}.log"
        
        # 创建文件 handler（写入模式，每次运行创建新文件）
        file_handler = FileHandler(
            str(log_file),
            encoding="utf-8",
            mode='w'  # 写入模式，每次运行创建新文件
        )
        
        # 设置文件 handler 级别为 DEBUG
        file_handler.setLevel(logging.DEBUG)
        
        # 创建格式化器
        formatter = Formatter(
            "[%(asctime)s][%(levelname)s][%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        
        # 保存文件 handler 实例
        _file_handler = file_handler
        _file_handler_initialized = True


def get_logger(name: str) -> Logger:
    """
    获取 logger 实例，并自动为其添加文件 handler（如果尚未添加）。
    
    该函数确保所有通过 get_logger() 创建的 logger 都会自动将日志写入
    logs/pcguiagent.log 文件（DEBUG 级别及以上），同时不影响 stdout 输出。
    
    Args:
        name: Logger 名称
        
    Returns:
        Logger 实例
    """
    # 确保文件 handler 已创建
    _ensure_file_handler()
    
    # 获取 logger
    logger = logging.getLogger(name)
    
    # 检查 logger 是否已有该文件 handler（避免重复添加）
    # 通过检查 handler 的类型和文件路径来识别
    if _file_handler is not None:
        # 检查是否已添加该 handler
        handler_exists = False
        for handler in logger.handlers:
            # 检查是否是同一个文件 handler 实例，或者是否是相同路径的 FileHandler
            if handler is _file_handler:
                handler_exists = True
                break
            elif isinstance(handler, FileHandler):
                # 检查文件路径是否相同
                try:
                    if hasattr(handler, 'baseFilename') and handler.baseFilename == _file_handler.baseFilename:
                        handler_exists = True
                        break
                except AttributeError:
                    pass
        
        # 如果没有添加，则添加文件 handler
        if not handler_exists:
            logger.addHandler(_file_handler)
            # 注意：不修改 logger 的级别，让它保持默认或继承自 root logger
            # 这样可以确保 stdout 输出不受影响（由 stdout handler 的级别控制）
            # 文件 handler 的级别是 DEBUG，所以会记录所有 DEBUG 及以上的日志
    
    return logger
