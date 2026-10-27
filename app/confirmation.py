import re
from dataclasses import dataclass
from typing import Any


@dataclass
class PendingAction:
    tool: str
    args: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"tool": self.tool, "args": dict(self.args)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PendingAction":
        return cls(tool=data["tool"], args=dict(data.get("args", {})))


# Words indicating negation, hesitation, or conditionality
_NEGATIVE_WORDS = {
    "no", "not", "don't", "dont", "never", "cancel", "stop",
    "wait", "hold", "but", "unless", "why", "what", "how",
}

# Strict positive confirmation patterns
_CONFIRMATION_PATTERNS = [
    re.compile(r"^(?:yes|yep|yeah|sure|ok|okay)(?:,\s*|\s+)?(?:please\s+)?(?:go\s+ahead|proceed|do\s+it|confirm)?\.?$", re.IGNORECASE),
    re.compile(r"^(?:yes|i\s+confirm|confirm|please\s+proceed|please\s+go\s+ahead|go\s+ahead)\.?$", re.IGNORECASE),
    re.compile(r"^yes,\s*i\s+confirm\.?$", re.IGNORECASE),
    re.compile(r"^yes,\s*please\s+go\s+ahead\.?$", re.IGNORECASE),
]


def is_explicit_confirmation(text: str) -> bool:
    """Pure helper to evaluate whether the user's message is an unambiguous confirmation.

    Returns True ONLY if affirmative and free of negations or hesitation.
    """
    cleaned = text.strip().lower()
    if not cleaned:
        return False

    # Extract words to inspect for negative/hesitant tokens
    tokens = set(re.findall(r"\b[a-z']+\b", cleaned))

    # Reject if any negative token appears (e.g. "no", "don't", "wait", "yes but...")
    if tokens & _NEGATIVE_WORDS:
        # Special case: "i confirm" or "confirm" does not contain negative words,
        # but "cancel" is in _NEGATIVE_WORDS. If user says "yes, cancel it", check carefully:
        if "cancel" in tokens:
            # If the user says "yes, cancel it" or "yes, please cancel", that is confirmation to cancel!
            # Let's check if there is an explicit rejection word
            hard_negatives = {"no", "not", "don't", "dont", "never", "stop", "wait", "hold", "but"}
            if tokens & hard_negatives:
                return False
            # Check pattern like "yes, cancel it"
            if re.match(r"^(?:yes|please)(?:,\s*|\s+)?cancel(?:\s+it)?\.?$", cleaned):
                return True
            return False
        return False

    # Match against positive confirmation regexes
    for pattern in _CONFIRMATION_PATTERNS:
        if pattern.match(cleaned):
            return True

    return False


def describe_action(action: PendingAction | dict[str, Any]) -> str:
    """Format a human-readable description of the pending action."""
    act_dict = action.to_dict() if isinstance(action, PendingAction) else action
    tool = act_dict.get("tool", "")
    args = act_dict.get("args", {})

    if tool == "cancel_reservation":
        rid = args.get("reservation_id", "")
        if rid:
            return f"cancel_reservation for {rid} and refund payments according to policy"
        return "cancel_reservation"
    if tool == "send_certificate":
        uid = args.get("user_id", "")
        amount = args.get("amount", 0)
        if uid or amount:
            return f"send_certificate: issue a travel certificate of ${amount} to user {uid}"
        return "send_certificate"

    return f"execute {tool} with details: {args}"
