"""OpenAI provider — wraps the OpenAI client with Instructor for validated output."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str, max_tokens: int = 4096) -> None:
        # Imported lazily so the package (and tests) don't require the SDK unless used.
        import instructor
        from openai import OpenAI

        self._model = model
        self._max_tokens = max_tokens
        self._client = instructor.from_openai(OpenAI(api_key=api_key))

    def structured(self, *, response_model: type[T], system: str, user: str) -> T:
        return self._client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            response_model=response_model,
            max_retries=2,  # Instructor re-asks the model if validation fails
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
