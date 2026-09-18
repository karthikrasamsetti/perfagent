"""Anthropic (Claude) provider — wraps the Anthropic client with Instructor."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str, max_tokens: int = 4096) -> None:
        import instructor
        from anthropic import Anthropic

        self._model = model
        self._max_tokens = max_tokens
        self._client = instructor.from_anthropic(Anthropic(api_key=api_key))

    def structured(self, *, response_model: type[T], system: str, user: str) -> T:
        return self._client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            response_model=response_model,
            max_retries=2,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
