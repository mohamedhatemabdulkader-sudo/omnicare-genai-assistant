from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    model_config = {"extra": "forbid", "str_strip_whitespace": True}

    user_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$", examples=["usr_123"])
    message: str = Field(min_length=1, max_length=2000, examples=["Is a burst pipe covered?"])


class ToolCallRecord(BaseModel):
    name: str
    args: dict[str, Any]
    output: str | None = None
    status: Literal["success", "error"] | None = None


class ChatResponse(BaseModel):
    response: str
    sources: list[str]
    tool_calls: list[ToolCallRecord]


class HealthResponse(BaseModel):
    status: Literal["healthy"] = "healthy"
