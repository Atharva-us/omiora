"""Request-size estimation shared by the agents.

Providers such as Groq's Developer tier count the prompt plus the requested completion budget
against a per-minute token limit, so a request that does not fit is rejected outright. Agents estimate
the prompt before sending and shrink, compact, or refuse the request instead of sending one that
cannot succeed.
"""

from __future__ import annotations

# Characters per token. Against Groq's measured prompt counts for the evaluation fixtures this
# over-estimates by roughly 15-20%, which is the safety margin for the per-request budget.
TOKEN_ESTIMATE_DIVISOR = 3.5


def estimate_tokens(text: str) -> int:
    return int(len(text) / TOKEN_ESTIMATE_DIVISOR) + 1
