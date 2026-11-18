"""Base Tool Class and Execution Result Models (📘 Lesson 2)."""

from typing import Any, Callable, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class ToolResult(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    recovery_suggestion: Optional[str] = None

    def to_observation(self) -> str:
        """Serialize tool execution result into an informative observation string for the LLM."""
        if self.success:
            return f"Observation [SUCCESS]: {self.data}"
        else:
            obs = f"Observation [ERROR]: {self.error}"
            if self.recovery_suggestion:
                obs += f"\nSelf-Correction Hint: {self.recovery_suggestion}"
            return obs


class SupermarketTool(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    parameters: Dict[str, Any]
    func: Callable[..., ToolResult]

    def run(self, **kwargs) -> ToolResult:
        try:
            return self.func(**kwargs)
        except TypeError as te:
            return ToolResult(
                success=False,
                error=f"Invalid arguments provided: {te}",
                recovery_suggestion=f"Verify required arguments against schema: {list(self.parameters.get('properties', {}).keys())}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Unexpected error executing {self.name}: {str(e)}",
                recovery_suggestion="Verify parameters or fall back to checking store policies / escalating to staff.",
            )
