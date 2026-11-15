"""
Health Check Schemas for Agent KitKat.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class OllamaModelInfo(BaseModel):
    name: str
    size_bytes: Optional[int] = None
    modified_at: Optional[str] = None


class OllamaHealthStatus(BaseModel):
    status: str = Field(..., description="Status: 'connected' or 'disconnected'")
    endpoint: str = Field(..., description="Ollama API base endpoint")
    target_model: str = Field(..., description="Model configured for Agent KitKat")
    model_available: bool = Field(..., description="Whether target model is present in Ollama")
    available_models: List[str] = Field(default_factory=list, description="List of all installed models")
    latency_ms: Optional[float] = Field(None, description="Round-trip latency to Ollama in milliseconds")
    error: Optional[str] = Field(None, description="Error message if connection failed")


class HealthCheckResponse(BaseModel):
    status: str = Field(..., description="Overall health: 'healthy', 'degraded', or 'unhealthy'")
    app_name: str
    version: str
    environment: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ollama: OllamaHealthStatus
