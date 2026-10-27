from types import SimpleNamespace
from app.graph import build_graph
from app.state import AgentState, clear_session_store
from app.session import Session
from app.agent import respond


def test_graph_call_model_end_to_end():
    # Fake LLM response that mimics openai message object
    def fake_complete(messages: list[dict], tools=None):
        return SimpleNamespace(content="According to Section: Book flight, you need a user ID.", tool_calls=None)

    graph = build_graph(complete_fn=fake_complete, policy="Sample policy")
    initial_state: AgentState = {
        "session_id": "test_session",
        "messages": [{"role": "user", "content": "How do I book?"}],
        "facts": [],
        "pending_action": None,
        "final_response": "",
    }

    result = graph.invoke(initial_state)

    assert result["final_response"] == "According to Section: Book flight, you need a user ID."
    assert len(result["messages"]) == 2
    assert result["messages"][1]["role"] == "assistant"
    assert result["messages"][1]["content"] == "According to Section: Book flight, you need a user ID."


def test_agent_respond(monkeypatch):
    clear_session_store()

    def fake_complete(messages: list[dict], tools=None):
        return SimpleNamespace(content="the policy doesn't say", tool_calls=None)

    # Monkeypatch the module-level graph to use our fake LLM
    import app.agent
    test_graph = build_graph(complete_fn=fake_complete, policy="Sample policy")
    monkeypatch.setattr(app.agent, "_GRAPH", test_graph)

    session = Session(id="s1")
    reply = respond(session, "Can I bring my pet iguana?")

    assert reply == "the policy doesn't say"
    assert len(session.history) == 2
    assert session.history[0] == {"role": "user", "content": "Can I bring my pet iguana?"}
    assert session.history[1] == {"role": "assistant", "content": "the policy doesn't say"}
