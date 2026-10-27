"""Base tool classes and data models for the Orbit AI tool registry."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    """Definition of a single tool parameter."""

    name: str = Field(..., description="Parameter name.")
    type: str = Field(..., description="Parameter type: string, integer, boolean, object, array.")
    description: str = Field(..., description="Human-readable description of the parameter.")
    required: bool = Field(default=True, description="Whether the parameter is required.")
    default: Optional[Any] = Field(default=None, description="Default value if not provided.")


class ToolExecutionResult(BaseModel):
    """Standardized outcome from any tool execution."""

    success: bool = Field(..., description="Whether the tool action succeeded.")
    output: Any = Field(default=None, description="Result output data (text, dict, list, etc.).")
    error: Optional[str] = Field(default=None, description="Error message if execution failed.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic metadata.")


class BaseTool(ABC):
    """Abstract base class for all registered computer task tools."""

    name: str
    description: str
    supported_actions: List[str]

    @abstractmethod
    def get_parameters_schema(self, action: Optional[str] = None) -> Dict[str, Any]:
        """Returns the JSON Schema or parameter specification for the tool."""
        pass

    @abstractmethod
    def execute(self, action: str, params: Dict[str, Any]) -> ToolExecutionResult:
        """Executes the requested tool action with validated parameters."""
        pass

    def validate_action(self, action: str) -> None:
        """Validates that the requested action is supported."""
        if action not in self.supported_actions:
            raise ValueError(
                f"Action '{action}' is not supported by tool '{self.name}'. "
                f"Supported actions: {self.supported_actions}"
            )
