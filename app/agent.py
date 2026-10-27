"""Agent response implementation using LangGraph."""
from .graph import build_graph
from .policy import load_policy
from .session import Session
from .state import AgentState, get_session_state

# Validate policy file exists and is readable at startup (FR1)
load_policy()

# Initialize the LangGraph with dynamic mtime-aware policy loader
_GRAPH = build_graph(policy=load_policy)


def respond(session: Session, user_message: str) -> str:
    """Handle one user message turn and return the reply."""
    session.history.append({"role": "user", "content": user_message})

    session_state = get_session_state(session.id)
    initial_state: AgentState = {
        "session_id": session.id,
        "messages": list(session.history),
        "facts": list(session_state.facts),
        "pending_action": session_state.pending_action,
        "final_response": "",
        "toolbox": session.toolbox,
        "loop_count": 0,
    }

    result = _GRAPH.invoke(initial_state)

    session.history = result.get("messages", session.history)
    session_state.facts = result.get("facts", session_state.facts)
    session_state.pending_action = result.get("pending_action", session_state.pending_action)

    return result.get("final_response", "")
