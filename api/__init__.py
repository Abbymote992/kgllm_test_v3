"""
API模块
"""

from .chat_api import router as chat_router
from .agent_api import router as agent_router
from .kg_api import router as kg_router

__all__ = ['chat_router', 'agent_router', 'kg_router']