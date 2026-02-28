"""
应用检测模块（Windows 版本）
检测当前活动窗口的应用
"""
import platform
from typing import Optional, Dict, Any
from pcguiagent.utils.logger import get_logger

logger = get_logger("AppDetector")


class AppDetector:
    """检测当前活动应用（Windows）"""
    
    def __init__(self):
        self.platform = platform.system().lower()
    
    def get_current_app(self) -> Optional[Dict[str, Any]]:
        """
        获取当前活动应用
        
        Returns:
            {
                "app_name": "chrome",
                "window_title": "Google Chrome",
                "window_id": "..."
            }
        """
        if self.platform == "windows":
            return self._get_windows_app()
        else:
            logger.warning(f"App detection not implemented for {self.platform}")
            return None
    
    def _get_windows_app(self) -> Optional[Dict[str, Any]]:
        """Windows 平台应用检测"""
        try:
            import pygetwindow as gw
            
            # 首先尝试获取活动窗口
            active_window = gw.getActiveWindow()
            if active_window:
                window_title = active_window.title.lower()
                app_name = self._infer_app_name(window_title, active_window)
                
                # 如果活动窗口能识别出应用，直接返回
                if app_name != "unknown":
                    return {
                        "app_name": app_name,
                        "window_title": active_window.title,
                        "window_id": str(active_window._hWnd) if hasattr(active_window, '_hWnd') else None
                    }
            
            # 如果活动窗口无法识别，搜索所有打开的窗口
            # 优先搜索特定应用（按优先级）
            priority_apps = ["code", "chrome", "excel", "vlc"]
            
            # 获取所有窗口（通过搜索空标题会返回所有窗口，但更高效的方式是按应用名搜索）
            all_windows = gw.getAllWindows()
            
            for app_name in priority_apps:
                # 搜索关键词
                search_keywords = {
                    "code": ["code", "visual studio code", "vscode"],
                    "chrome": ["chrome", "google", "edge", "browser"],
                    "excel": ["excel", "spreadsheet"],
                    "vlc": ["vlc", "media player"]
                }
                
                keywords = search_keywords.get(app_name, [app_name])
                
                for window in all_windows:
                    if not window or not window.title:
                        continue
                    
                    window_title = window.title.lower()
                    inferred_name = self._infer_app_name(window_title, window)
                    
                    # 检查是否匹配目标应用
                    if inferred_name == app_name:
                        logger.debug(f"[AppDetector] Found {app_name} window (not active): {window.title}")
                        return {
                            "app_name": app_name,
                            "window_title": window.title,
                            "window_id": str(window._hWnd) if hasattr(window, '_hWnd') else None
                        }
            
            # 如果活动窗口存在但无法识别，返回活动窗口信息
            if active_window:
                window_title = active_window.title.lower()
                app_name = self._infer_app_name(window_title, active_window)
                return {
                    "app_name": app_name,
                    "window_title": active_window.title,
                    "window_id": str(active_window._hWnd) if hasattr(active_window, '_hWnd') else None
                }
            
            return None
        except ImportError:
            logger.warning("pygetwindow not available, app detection disabled")
            return None
        except Exception as e:
            logger.error(f"Failed to detect Windows app: {e}")
            return None
    
    def _infer_app_name(self, window_title: str, window) -> str:
        """
        从窗口标题推断应用名称
        
        Args:
            window_title: 窗口标题（小写）
            window: pygetwindow 窗口对象
            
        Returns:
            应用名称（如 "chrome", "code", "excel"）
        """
        # 尝试从窗口对象获取进程名
        try:
            if hasattr(window, 'process') and window.process:
                process_name = window.process.lower()
                # 提取进程名（去掉 .exe）
                if process_name.endswith('.exe'):
                    process_name = process_name[:-4]
                
                # 映射进程名到应用名
                process_mapping = {
                    "chrome": "chrome",
                    "msedge": "chrome",  # Edge 也使用 chrome 工具
                    "code": "code",
                    "devenv": "code",  # Visual Studio 也使用 code 工具
                    "excel": "excel",
                    "winword": "word",
                    "powerpnt": "ppt",
                    "vlc": "vlc",
                    "firefox": "chrome",  # Firefox 也使用浏览器工具
                }
                
                if process_name in process_mapping:
                    return process_mapping[process_name]
        except Exception:
            pass
        
        # 基于窗口标题推断
        if "chrome" in window_title or "google" in window_title or "edge" in window_title:
            return "chrome"
        elif ("code" in window_title or 
              "visual studio code" in window_title or 
              "vscode" in window_title or
              window_title.startswith("visual studio") or
              "- visual studio code" in window_title):
            return "code"
        elif "excel" in window_title:
            return "excel"
        elif "word" in window_title:
            return "word"
        elif "powerpoint" in window_title or "ppt" in window_title:
            return "ppt"
        elif "vlc" in window_title:
            return "vlc"
        else:
            return "unknown"

