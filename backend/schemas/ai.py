"""
AI Request and Response Schemas for Agent KitKat.
"""

from typing import Optional
from pydantic import BaseModel, Field


class AITestRequest(BaseModel):
    prompt: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User prompt or question to send to Qwen2.5 1.5B"
    )
    system_prompt: Optional[str] = Field(
        default="You are Agent KitKat, a helpful and sharp career assistant.",
        description="Optional system prompt to guide response style"
    )
    temperature: Optional[float] = Field(
        default=0.7,
        ge=0.0,
        le=1.5,
        description="Sampling temperature"
    )


class AITestResponse(BaseModel):
    success: bool
    model: str
    prompt: str
    response: str
    duration_ms: float
    prompt_eval_count: Optional[int] = None
    eval_count: Optional[int] = None
    error: Optional[str] = None
