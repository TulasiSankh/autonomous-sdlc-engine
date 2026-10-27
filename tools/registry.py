"""Tool Registry module managing registration, discovery, and execution of local tools."""

from typing import Any, Dict, List, Optional

from tools.app_launcher_tool import AppLauncherTool
from tools.base import BaseTool, ToolExecutionResult
from tools.browser_tool import BrowserTool
from tools.command_tool import CommandTool
from tools.filesystem_tool import FilesystemTool
from tools.verification_tool import VerificationTool


class ToolRegistry:
    """Registry coordinating available computer tools for task execution."""

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register_tool(self, tool: BaseTool) -> None:
        """Registers a tool instance in the registry."""
        self._tools[tool.name] = tool

    def register(self, tool: BaseTool) -> None:
        """Alias for register_tool."""
        self.register_tool(tool)

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Retrieves a registered tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        """Lists metadata and capabilities for all registered tools."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "supported_actions": tool.supported_actions,
            }
            for tool in self._tools.values()
        ]

    def execute(self, tool_name: str, action: str, params: Dict[str, Any]) -> ToolExecutionResult:
        """Finds and executes the requested tool action."""
        tool = self.get_tool(tool_name)
        if tool is None:
            return ToolExecutionResult(
                success=False,
                error=f"Tool '{tool_name}' is not registered in the system.",
                metadata={"tool_name": tool_name, "available_tools": list(self._tools.keys())},
            )

        return tool.execute(action, params)


_default_registry: Optional[ToolRegistry] = None


def get_default_registry() -> ToolRegistry:
    """Returns the singleton ToolRegistry initialized with standard tools."""
    global _default_registry
    if _default_registry is None:
        registry = ToolRegistry()
        registry.register_tool(BrowserTool())
        registry.register_tool(FilesystemTool())
        registry.register_tool(AppLauncherTool())
        registry.register_tool(CommandTool())
        registry.register_tool(VerificationTool())
        _default_registry = registry
    return _default_registry
