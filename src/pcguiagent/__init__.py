"""
PC GUI Agent Package
"""

__version__ = "0.1.0"
__all__ = ["PCGuiAgent"]


def __getattr__(name):
    if name == "PCGuiAgent":
        from pcguiagent.agent import PCGuiAgent
        return PCGuiAgent
    raise AttributeError(f"module 'pcguiagent' has no attribute {name!r}")
