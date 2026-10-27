from typing import Any, Callable

from langgraph.graph import END, START, StateGraph

from .llm import complete as default_complete
from .policy import load_policy
from .prompt import build_messages
from .state import AgentState


def create_call_model_node(
    complete_fn: Callable[..., Any],
    policy: str,
) -> Callable[[AgentState], dict[str, Any]]:
    """Create the call_model node with injected LLM and policy."""

    def call_model(state: AgentState) -> dict[str, Any]:
        history = list(state.get("messages", []))
        facts = state.get("facts", [])
        pending = state.get("pending_action")

        full_messages = build_messages(
            policy=policy,
            facts=facts,
            pending=pending,
            history=history,
        )

        # Stage 1: pure grounded answers without tools
        response = complete_fn(messages=full_messages, tools=None)
        content = getattr(response, "content", "") or ""

        new_history = history + [{"role": "assistant", "content": content}]
        return {
            "messages": new_history,
            "final_response": content,
        }

    return call_model


def build_graph(
    complete_fn: Callable[..., Any] | None = None,
    toolbox: Any = None,
    policy: str | None = None,
) -> Any:
    """Build and compile the LangGraph StateGraph.

    All dependencies are injected with sensible defaults for production.
    """
    complete_callable = complete_fn or default_complete
    policy_text = policy if policy is not None else load_policy()

    builder = StateGraph(AgentState)
    builder.add_node("call_model", create_call_model_node(complete_callable, policy_text))

    builder.add_edge(START, "call_model")
    builder.add_edge("call_model", END)

    return builder.compile()
