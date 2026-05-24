"""Ollama HTTP client (Step 8)."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from config.settings import get_settings

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model
        self.timeout = settings.ollama_timeout

    def is_available(self) -> bool:
        try:
            with httpx.Client(timeout=5.0) as client:
                r = client.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    def generate(self, prompt: str, system: Optional[str] = None) -> Optional[str]:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return data.get("response", "")
        except Exception as exc:
            logger.error("Ollama request failed: %s", exc)
            return None
