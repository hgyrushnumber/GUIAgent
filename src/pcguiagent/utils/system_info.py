# utils/system_info.py
import platform
import psutil
import socket


def get_system_info():
    return {
        "os": platform.platform(),
        "python_version": platform.python_version(),
        "hostname": socket.gethostname(),
        "cpu_count": psutil.cpu_count(),
        "memory_gb": round(psutil.virtual_memory().total / 1e9, 2),
    }
