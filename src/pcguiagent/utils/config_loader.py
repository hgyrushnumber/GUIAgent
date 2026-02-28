"""
统一配置文件查找工具

提供统一的配置文件查找逻辑，避免代码重复。
"""
from pathlib import Path
import os
from typing import Optional


def find_config_file(config_path: str, module_dir: Optional[Path] = None) -> Path:
    """
    统一的配置文件查找逻辑
    
    支持多种路径风格：
    1. 绝对路径
    2. 相对当前工作目录
    3. 相对模块目录（pcguiagent/）
    
    Args:
        config_path: 配置文件路径
        module_dir: 模块目录（可选，默认使用调用者的模块目录）
    
    Returns:
        配置文件的 Path 对象
    
    Raises:
        FileNotFoundError: 如果配置文件无法找到
    """
    config_file = Path(config_path)
    
    # 如果是绝对路径且存在，直接返回
    if config_file.is_absolute() and config_file.exists():
        return config_file
    
    # 尝试相对当前工作目录
    if config_file.exists():
        return config_file.resolve()
    
    # 尝试相对模块目录
    if module_dir is None:
        # 尝试从调用栈获取模块目录
        import inspect
        frame = inspect.currentframe()
        try:
            caller_file = frame.f_back.f_globals.get('__file__')
            if caller_file:
                module_dir = Path(caller_file).parent
            else:
                # 回退到默认位置
                module_dir = Path(__file__).parent.parent
        finally:
            del frame
    else:
        module_dir = Path(module_dir)
    
    module_config = module_dir / config_path
    if module_config.exists():
        return module_config.resolve()
    
    # 如果只提供了文件名，尝试模块目录
    if config_path == Path(config_path).name:
        module_config = module_dir / config_path
        if module_config.exists():
            return module_config.resolve()
    
    # 所有尝试都失败，抛出错误
    raise FileNotFoundError(
        f"Config file not found: {config_path}\n"
        f"Tried paths:\n"
        f"  1. {config_file.resolve() if config_file.is_absolute() else 'N/A (not absolute)'}\n"
        f"  2. {Path.cwd() / config_path}\n"
        f"  3. {module_dir / config_path}\n"
        f"Current working directory: {os.getcwd()}\n"
        f"Module directory: {module_dir}"
    )

