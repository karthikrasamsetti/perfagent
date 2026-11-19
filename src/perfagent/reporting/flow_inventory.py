"""Declared production flows per environment -> drives coverage reporting.

Config-owned so stakeholders can see which flows are *expected* to be
load-tested in each environment. Anything declared but never run shows
as 'uncovered' -- the direct answer to 'what needs to complete'.
Override via PERFAGENT_FLOW_INVENTORY (JSON file path).
"""
from __future__ import annotations

import json
import os

_DEFAULT: dict[str, list[str]] = {
    "prod": ["checkout", "login", "search", "product_browse", "order_history"],
    "staging": ["checkout", "login", "search"],
    "dev": ["login"],
}


def load_inventory() -> dict[str, list[str]]:
    """Load the declared flow inventory, from file if configured."""
    path = os.getenv("PERFAGENT_FLOW_INVENTORY")
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return _DEFAULT
