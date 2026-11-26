"""模型适配：只写挂卖文案与砍价应对话术。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

PROMPT = Path(__file__).resolve().parents[2] / "prompts" / "listing.md"


class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def write(self, facts: str) -> str:
        system = PROMPT.read_text(encoding="utf-8") if PROMPT.exists() else "写二手挂卖文案。"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": facts}],
            "temperature": 0.5,
            "max_tokens": 700,
        }
        with httpx.Client(timeout=self.timeout) as c:
            r = c.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
        return ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "").strip()
