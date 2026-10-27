from dataclasses import dataclass, field
from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """LangGraph state passed across graph nodes."""
    session_id: str
    messages: list[dict[str, Any]]
    facts: list[str]
    pending_action: dict[str, Any] | None
    final_response: str


@dataclass
class SessionState:
    """Per-session metadata not stored in the provided Session class."""
    facts: list[str] = field(default_factory=list)
    pending_action: dict[str, Any] | None = None


_SESSION_STORE: dict[str, SessionState] = {}


def get_session_state(session_id: str) -> SessionState:
    """Retrieve or create session state for a given session ID."""
    if session_id not in _SESSION_STORE:
        _SESSION_STORE[session_id] = SessionState()
    return _SESSION_STORE[session_id]


def clear_session_store() -> None:
    """Clear in-memory session store (useful for testing)."""
    _SESSION_STORE.clear()
