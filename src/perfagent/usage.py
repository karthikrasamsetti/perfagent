"""Token usage tracking for LLM calls.

Each provider records the tokens used by its most recent call in `last_usage`. The
GuardedProvider passes it through, and the API surfaces it per action (plan, chat,
dynamize, narrate) and in the audit trail, so users see what each AI step cost.

Pricing is approximate and configurable; it's only for a rough cost estimate, never
billing. Costs change, so these are ballpark figures per 1M tokens (USD).
"""

from __future__ import annotations

from dataclasses import dataclass

# Rough prices per 1,000,000 tokens (input, output), USD. Update as needed.
# Only used for a ballpark "~$X" estimate in the UI.
_PRICES = {
    # OpenAI
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    # Anthropic
    "claude-sonnet-4": (3.00, 15.00),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-5-haiku": (0.80, 4.00),
    "claude-3-opus": (15.00, 75.00),
}
_DEFAULT_PRICE = (2.00, 8.00)


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def cost_usd(self) -> float:
        """Rough cost estimate from the model's price (ballpark only)."""
        in_price, out_price = _price_for(self.model)
        return (self.prompt_tokens / 1_000_000) * in_price + \
               (self.completion_tokens / 1_000_000) * out_price

    def summary(self) -> dict:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "model": self.model,
            "cost_usd": round(self.cost_usd(), 5),
        }


def _price_for(model: str) -> tuple[float, float]:
    m = (model or "").lower()
    for key, price in _PRICES.items():
        if key in m:
            return price
    return _DEFAULT_PRICE


def extract_usage(response, model: str = "") -> Usage:
    """Pull token usage out of an OpenAI/Anthropic/Instructor response, best-effort.

    Instructor exposes the raw completion on `._raw_response`; OpenAI puts usage on
    `.usage` (prompt_tokens/completion_tokens); Anthropic uses input_tokens/
    output_tokens. We handle all shapes and fall back to zeros.
    """
    raw = getattr(response, "_raw_response", response)
    usage = getattr(raw, "usage", None)
    if usage is None:
        return Usage(model=model)

    # OpenAI style
    p = getattr(usage, "prompt_tokens", None)
    c = getattr(usage, "completion_tokens", None)
    # Anthropic style
    if p is None:
        p = getattr(usage, "input_tokens", 0)
    if c is None:
        c = getattr(usage, "output_tokens", 0)
    return Usage(prompt_tokens=int(p or 0), completion_tokens=int(c or 0), model=model)
