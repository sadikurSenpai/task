import json
from types import SimpleNamespace
from app.graph import build_graph, TRANSFER_MESSAGE
from app.toolbox import ToolBox
from app.state import AgentState


def test_read_tool_lookup_and_facts():
    """Verify read tool execution, fact extraction from result, and multi-step tool completion."""
    tb = ToolBox()
    call_count = 0

    def fake_complete(messages: list[dict], tools=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Model decides to look up user details using valid user in db.json
            tc = SimpleNamespace(
                id="call_123",
                function=SimpleNamespace(
                    name="get_user_details",
                    arguments=json.dumps({"user_id": "yusuf_li_4428"}),
                ),
            )
            return SimpleNamespace(content=None, tool_calls=[tc])
        else:
            # Model replies after seeing tool output
            return SimpleNamespace(content="User yusuf_li_4428 is a gold member.", tool_calls=None)

    graph = build_graph(complete_fn=fake_complete, toolbox=tb, policy="Sample policy")
    state: AgentState = {
        "session_id": "s_read",
        "messages": [{"role": "user", "content": "What is yusuf_li_4428's membership?"}],
        "facts": [],
        "pending_action": None,
        "final_response": "",
        "toolbox": tb,
        "loop_count": 0,
    }

    result = graph.invoke(state)

    assert result["final_response"] == "User yusuf_li_4428 is a gold member."
    assert "user_id: yusuf_li_4428" in result["facts"]
    # Verify reservation from user's record was extracted into facts
    assert "reservation_id: FU5FSY" in result["facts"]
    assert any(c["tool"] == "get_user_details" and c["ok"] for c in tb.log)


def test_unknown_id_tool_error_handling_and_no_facts():
    """Verify tool errors for unknown IDs are passed to the model, reported, and record NO facts (FR5)."""
    tb = ToolBox()
    call_count = 0

    def fake_complete(messages: list[dict], tools=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            tc = SimpleNamespace(
                id="call_err",
                function=SimpleNamespace(
                    name="get_reservation_details",
                    arguments=json.dumps({"reservation_id": "INVALID_ID"}),
                ),
            )
            return SimpleNamespace(content=None, tool_calls=[tc])
        else:
            # Inspect last message to ensure error was delivered to model
            last_msg = messages[-1]
            assert last_msg["role"] == "tool"
            assert "error" in last_msg["content"]
            return SimpleNamespace(content="Reservation INVALID_ID was not found.", tool_calls=None)

    graph = build_graph(complete_fn=fake_complete, toolbox=tb, policy="Sample policy")
    state: AgentState = {
        "session_id": "s_err",
        "messages": [{"role": "user", "content": "Check reservation INVALID_ID"}],
        "facts": [],
        "pending_action": None,
        "final_response": "",
        "toolbox": tb,
        "loop_count": 0,
    }

    result = graph.invoke(state)

    assert result["final_response"] == "Reservation INVALID_ID was not found."
    # Crucial: unknown id must record NO facts
    assert result["facts"] == []
    assert any(c["tool"] == "get_reservation_details" and not c["ok"] for c in tb.log)


def test_transfer_to_human_agents():
    """Verify transfer_to_human_agents executes and sends the exact policy message (FR7)."""
    tb = ToolBox()

    def fake_complete(messages: list[dict], tools=None):
        tc = SimpleNamespace(
            id="call_transfer",
            function=SimpleNamespace(
                name="transfer_to_human_agents",
                arguments=json.dumps({"summary": "User wants to book a new flight"}),
            ),
        )
        return SimpleNamespace(content=None, tool_calls=[tc])

    graph = build_graph(complete_fn=fake_complete, toolbox=tb, policy="Sample policy")
    state: AgentState = {
        "session_id": "s_transfer",
        "messages": [{"role": "user", "content": "I want to book a flight to Paris"}],
        "facts": [],
        "pending_action": None,
        "final_response": "",
        "toolbox": tb,
        "loop_count": 0,
    }

    result = graph.invoke(state)

    assert result["final_response"] == TRANSFER_MESSAGE
    assert tb.transferred is True
    assert any(c["tool"] == "transfer_to_human_agents" and c["ok"] for c in tb.log)


def test_first_tool_call_only_enforced():
    """Verify that if model emits multiple tool calls, only the first is kept (FR6)."""
    tb = ToolBox()
    call_count = 0

    def fake_complete(messages: list[dict], tools=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            tc1 = SimpleNamespace(
                id="call_1",
                function=SimpleNamespace(
                    name="get_user_details",
                    arguments=json.dumps({"user_id": "yusuf_li_4428"}),
                ),
            )
            tc2 = SimpleNamespace(
                id="call_2",
                function=SimpleNamespace(
                    name="get_reservation_details",
                    arguments=json.dumps({"reservation_id": "FU5FSY"}),
                ),
            )
            # Returning multiple tool calls simultaneously
            return SimpleNamespace(content="Extraneous text", tool_calls=[tc1, tc2])
        else:
            return SimpleNamespace(content="Done", tool_calls=None)

    graph = build_graph(complete_fn=fake_complete, toolbox=tb, policy="Sample policy")
    state: AgentState = {
        "session_id": "s_multi",
        "messages": [{"role": "user", "content": "Look up my info"}],
        "facts": [],
        "pending_action": None,
        "final_response": "",
        "toolbox": tb,
        "loop_count": 0,
    }

    result = graph.invoke(state)

    assert len(tb.log) == 1
    assert tb.log[0]["tool"] == "get_user_details"


def _run_single_tool_attempt(tool_name: str, args: dict, final_text: str, tb: ToolBox):
    """Fake LLM calls one tool, then answers. Returns (result, tool_reply_content)."""
    seen = {}

    def fake_complete(messages: list[dict], tools=None):
        if "tool_reply" not in seen and messages[-1]["role"] != "tool":
            tc = SimpleNamespace(
                id="call_1",
                function=SimpleNamespace(name=tool_name, arguments=json.dumps(args)),
            )
            return SimpleNamespace(content=None, tool_calls=[tc])
        last_msg = messages[-1]
        assert last_msg["role"] == "tool"
        assert last_msg["tool_call_id"] == "call_1"
        seen["tool_reply"] = last_msg["content"]
        return SimpleNamespace(content=final_text, tool_calls=None)

    graph = build_graph(complete_fn=fake_complete, toolbox=tb, policy="Sample policy")
    state: AgentState = {
        "session_id": "s_single_tool",
        "messages": [{"role": "user", "content": "please do it"}],
        "facts": [],
        "pending_action": None,
        "final_response": "",
        "toolbox": tb,
        "loop_count": 0,
    }
    result = graph.invoke(state)
    return result, seen["tool_reply"]


def test_unknown_tool_call_gets_tool_reply_and_non_empty_answer():
    """A tool we don't support (e.g. booking) still gets a tool reply, so the history stays valid."""
    tb = ToolBox()
    result, tool_reply = _run_single_tool_attempt("book_flight", {}, "I can't book flights.", tb)

    assert "This action is not available yet" in tool_reply
    assert result["final_response"] == "I can't book flights."
    # OpenAI protocol: assistant tool_calls message is followed by a tool message
    assert [m["role"] for m in result["messages"]] == ["user", "assistant", "tool", "assistant"]


def test_write_tool_without_lookup_is_blocked_by_facts_first():
    """Stage 3: cancel_reservation on an id never looked up is blocked; nothing is cancelled."""
    tb = ToolBox()
    result, tool_reply = _run_single_tool_attempt(
        "cancel_reservation", {"reservation_id": "FU5FSY"}, "I need to look that up first.", tb
    )

    assert "Facts-first check failed" in tool_reply
    assert tb.cancelled() == []
    assert result["final_response"] == "I need to look that up first."
    assert [m["role"] for m in result["messages"]] == ["user", "assistant", "tool", "assistant"]
