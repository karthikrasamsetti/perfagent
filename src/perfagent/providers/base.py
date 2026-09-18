"""The provider interface — the single seam between our code and the LLM vendors.

Nothing outside this package imports `openai` or `anthropic`. Everything calls a
LLMProvider, so switching vendors (or falling back) is a one-line change and the
rest of the pipeline never knows which model produced a draft.

Every provider returns a *validated Pydantic object* (via Instructor). The model
drafts; the schema decides what is acceptable. That is the trust boundary.
"""

from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMProvider(Protocol):
    """Anything that can turn a prompt into a validated Pydantic object."""

    name: str

    def structured(
        self,
        *,
        response_model: type[T],
        system: str,
        user: str,
    ) -> T:
        """Return an instance of `response_model`, validated. Raises on failure."""
        ...
