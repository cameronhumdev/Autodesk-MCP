"""Windows client agent — resolve/download MCP + outbound gateway session."""

from .agent import AgentResult, ClientAgent
from .config import ClientConfig, load_config
from .paths import McpPaths

__all__ = ["AgentResult", "ClientAgent", "ClientConfig", "McpPaths", "load_config"]
