"""Base classes for the agent skill system."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
import uuid


class SkillCategory(StrEnum):
    """Categories of skills."""

    ANALYSIS = "analysis"
    VERSION_MANAGEMENT = "version_management"
    CODE_TRANSFORMATION = "code_transformation"
    INFORMATION = "information"
    REPOSITORY = "repository"
    UTILITY = "utility"


class ParameterType(StrEnum):
    """Types of skill parameters."""

    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    UUID = "uuid"


@dataclass
class SkillParameter:
    """Definition of a skill parameter."""

    name: str
    description: str
    type: ParameterType
    required: bool = True
    default: Any = None
    enum: list[str] | None = None
    items_type: ParameterType | None = None  # For array types

    def to_json_schema(self) -> dict:
        """Convert to JSON Schema format for LLM tool calling."""
        schema: dict[str, Any] = {
            "type": self.type.value,
            "description": self.description,
        }

        if self.enum:
            schema["enum"] = self.enum

        if self.type == ParameterType.ARRAY and self.items_type:
            schema["items"] = {"type": self.items_type.value}

        if self.default is not None:
            schema["default"] = self.default

        return schema


@dataclass
class SkillContext:
    """Context passed to skill execution."""

    user_id: uuid.UUID
    repository_id: uuid.UUID | None = None
    analysis_id: uuid.UUID | None = None
    session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillResult:
    """Result from skill execution."""

    success: bool
    data: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
        }


class Skill(ABC):
    """Base class for all agent skills."""

    # Skill metadata (override in subclasses)
    name: str = "base_skill"
    description: str = "Base skill"
    category: SkillCategory = SkillCategory.UTILITY
    version: str = "1.0.0"

    @property
    @abstractmethod
    def parameters(self) -> list[SkillParameter]:
        """Define the parameters this skill accepts."""
        ...

    @abstractmethod
    async def execute(self, context: SkillContext, **kwargs) -> SkillResult:
        """Execute the skill with the given parameters."""
        ...

    def get_tool_definition(self) -> dict:
        """Get the tool definition for LLM function calling."""
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = param.to_json_schema()
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    def validate_parameters(self, **kwargs) -> tuple[bool, str | None]:
        """Validate the provided parameters."""
        for param in self.parameters:
            if param.required and param.name not in kwargs:
                return False, f"Missing required parameter: {param.name}"

            if param.name in kwargs:
                value = kwargs[param.name]
                # Basic type validation
                if param.type == ParameterType.STRING and not isinstance(value, str):
                    return False, f"Parameter {param.name} must be a string"
                if param.type == ParameterType.INTEGER and not isinstance(value, int):
                    return False, f"Parameter {param.name} must be an integer"
                if param.type == ParameterType.BOOLEAN and not isinstance(value, bool):
                    return False, f"Parameter {param.name} must be a boolean"
                if param.type == ParameterType.ARRAY and not isinstance(value, list):
                    return False, f"Parameter {param.name} must be an array"
                if param.enum and value not in param.enum:
                    return False, f"Parameter {param.name} must be one of: {param.enum}"

        return True, None
