"""
Agent KitKat - Ollama Local AI Service
Handles communication with local Ollama runtime hosting qwen2.5:1.5b.
Strictly local: 100% offline, ₹0 cost.
"""

import time
import logging
from typing import Optional, Dict, Any, List
import httpx
from fastapi import HTTPException, status

from backend.config import Settings, get_settings
from backend.schemas.health import OllamaHealthStatus
from backend.schemas.ai import AITestResponse

logger = logging.getLogger("agent_kitkat.ollama")


class OllamaService:
    """Service wrapper for interacting with the local Ollama daemon."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.base_url = self.settings.OLLAMA_BASE_URL.rstrip("/")
        self.default_model = self.settings.OLLAMA_MODEL
        self.timeout = self.settings.OLLAMA_REQUEST_TIMEOUT_SECONDS

    async def check_health(self) -> OllamaHealthStatus:
        """
        Check if Ollama is running and if the required model is loaded.
        Measures round-trip latency.
        """
        start_time = time.perf_counter()
        tags_url = f"{self.base_url}/api/tags"

        try:
            async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
                response = await client.get(tags_url)
                latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

                if response.status_code != 200:
                    return OllamaHealthStatus(
                        status="disconnected",
                        endpoint=self.base_url,
                        target_model=self.default_model,
                        model_available=False,
                        available_models=[],
                        latency_ms=latency_ms,
                        error=f"Ollama returned HTTP status {response.status_code}"
                    )

                data = response.json()
                raw_models: List[Dict[str, Any]] = data.get("models", [])
                model_names = [m.get("name", "") for m in raw_models]

                # Check if target model matches either "qwen2.5:1.5b" or "qwen2.5:1.5b:latest"
                target_base = self.default_model.split(":")[0]
                model_available = any(
                    self.default_model in name or (target_base in name and "1.5b" in name)
                    for name in model_names
                )

                return OllamaHealthStatus(
                    status="connected",
                    endpoint=self.base_url,
                    target_model=self.default_model,
                    model_available=model_available,
                    available_models=model_names,
                    latency_ms=latency_ms,
                    error=None if model_available else f"Model '{self.default_model}' not found in Ollama. Available: {model_names}"
                )

        except httpx.ConnectError:
            return OllamaHealthStatus(
                status="disconnected",
                endpoint=self.base_url,
                target_model=self.default_model,
                model_available=False,
                available_models=[],
                latency_ms=None,
                error=(
                    f"Cannot connect to Ollama at {self.base_url}. "
                    "Please ensure Ollama is installed and running (`ollama serve`)."
                )
            )
        except httpx.TimeoutException:
            return OllamaHealthStatus(
                status="disconnected",
                endpoint=self.base_url,
                target_model=self.default_model,
                model_available=False,
                available_models=[],
                latency_ms=None,
                error=f"Connection timed out while reaching Ollama at {self.base_url}."
            )
        except Exception as e:
            logger.exception("Unexpected error during Ollama health check: %s", str(e))
            return OllamaHealthStatus(
                status="disconnected",
                endpoint=self.base_url,
                target_model=self.default_model,
                model_available=False,
                available_models=[],
                latency_ms=None,
                error=f"Unexpected error: {str(e)}"
            )

    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        model: Optional[str] = None
    ) -> AITestResponse:
        """
        Send a generation request to Ollama and return structured response.
        """
        target_model = model or self.default_model
        generate_url = f"{self.base_url}/api/generate"

        payload: Dict[str, Any] = {
            "model": target_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        if system_prompt:
            payload["system"] = system_prompt

        start_time = time.perf_counter()

        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                response = await client.post(generate_url, json=payload)
                duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

                if response.status_code != 200:
                    error_msg = f"Ollama generation failed with HTTP {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=error_msg
                    )

                data = response.json()
                generated_text = data.get("response", "").strip()

                return AITestResponse(
                    success=True,
                    model=data.get("model", target_model),
                    prompt=prompt,
                    response=generated_text,
                    duration_ms=duration_ms,
                    prompt_eval_count=data.get("prompt_eval_count"),
                    eval_count=data.get("eval_count"),
                    error=None
                )

        except httpx.ConnectError:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Ollama service is unreachable at {self.base_url}. Is Ollama running?"
            )
        except httpx.TimeoutException:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Ollama generation timed out after {self.timeout} seconds."
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Unexpected error in Ollama generation: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal error processing AI request: {str(e)}"
            )


# Singleton instance
ollama_service = OllamaService()
