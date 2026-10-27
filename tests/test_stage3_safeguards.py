import json
from types import SimpleNamespace
from app.confirmation import is_explicit_confirmation, describe_action
from app.guards import check_facts_first, parse_policy_verdict
from app.graph import build_graph
from app.state import AgentState
from app.toolbox import ToolBox


def test_is_explicit_confirmation():
    # Strict affirmatives
    assert is_explicit_confirmation("yes") is True
    assert is_explicit_confirmation("Yes.") is True
    assert is_explicit_confirmation("YES, please go ahead.") is True
    assert is_explicit_confirmation("Yes, I confirm.") is True
    assert is_explicit_confirmation("I confirm.") is True
    assert is_explicit_confirmation("please proceed") is True
    assert is_explicit_confirmation("yes, cancel it") is True

    # Negatives, questions, or conditional statements
    assert is_explicit_confirmation("no") is False
    assert is_explicit_confirmation("No, don't do that.") is False
    assert is_explicit_confirmation("Yes, but wait a second.") is False
    assert is_explicit_confirmation("Why would you cancel it?") is False
    assert is_explicit_confirmation("That's not fair. Please cancel it anyway.") is False
    assert is_explicit_confirmation("") is False


def test_describe_action():
    desc_cancel = describe_action({"tool": "cancel_reservation", "args": {"reservation_id": "FU5FSY"}})
    assert "FU5FSY" in desc_cancel
    assert "cancel_reservation" in desc_cancel

    desc_cert = describe_action({"tool": "send_certificate", "args": {"user_id": "yusuf_li_4428", "amount": 120}})
    assert "yusuf_li_4428" in desc_cert
    assert "120" in desc_cert


def test_check_facts_first():
    # Reservation cancel requires reservation_id looked up
    action_cancel = {"tool": "cancel_reservation", "args": {"reservation_id": "FU5FSY"}}
    ok, err = check_facts_first(action_cancel, ["reservation_id: FU5FSY"])
    assert ok is True
    assert err == ""

    ok, err = check_facts_first(action_cancel, ["reservation_id: OTHER"])
    assert ok is False
    assert "not been looked up" in err

    # Certificate requires user_id looked up
    action_cert = {"tool": "send_certificate", "args": {"user_id": "user_1", "amount": 50}}
    ok, err = check_facts_first(action_cert, ["user_id: user_1"])
    assert ok is True

    ok, err = check_facts_first(action_cert, [])
    assert ok is False


def test_parse_policy_verdict_fail_closed():
    # Valid allowed
    v1 = parse_policy_verdict('{"allowed": true, "section": "Cancel flight", "reason": "Business cabin"}')
    assert v1.allowed is True
    assert v1.section == "Cancel flight"

    # Valid denied
    v2 = parse_policy_verdict('{"allowed": false, "section": "Cancel flight", "reason": "Basic economy > 48h"}')
    assert v2.allowed is False
    assert "Basic economy" in v2.reason

    # Malformed JSON (fail closed)
    v3 = parse_policy_verdict("This is not JSON")
    assert v3.allowed is False

    # Missing allowed boolean
    v4 = parse_policy_verdict('{"allowed": "yes", "section": "Cancel"}')
    assert v4.allowed is False


def test_stage3_confirmation_cycle():
    """Verify that a write tool is proposed, gated behind confirmation, and executed only upon explicit 'yes'."""
    tb = ToolBox()
    call_count = 0

    def fake_complete(messages: list[dict], tools=None):
        nonlocal call_count
        call_count += 1

        # Check if this is the policy compliance check call
        if tools is None and any("strict Policy Compliance Checker" in m.get("content", "") for m in messages):
            return SimpleNamespace(
                content=json.dumps({"allowed": True, "section": "Cancel flight", "reason": "Business class eligible"}),
                tool_calls=None,
            )

        if call_count == 1:
            # Turn 1 Step 1: Model looks up reservation
            tc = SimpleNamespace(
                id="call_read",
                function=SimpleNamespace(
                    name="get_reservation_details",
                    arguments=json.dumps({"reservation_id": "FU5FSY"}),
                ),
            )
            return SimpleNamespace(content=None, tool_calls=[tc])
        elif call_count == 2:
            # Turn 1 Step 2: Model sees lookup and proposes cancel_reservation
            tc = SimpleNamespace(
                id="call_write",
                function=SimpleNamespace(
                    name="cancel_reservation",
                    arguments=json.dumps({"reservation_id": "FU5FSY"}),
                ),
            )
            return SimpleNamespace(content=None, tool_calls=[tc])
        else:
            # Turn 2: After write executed, model replies with confirmation
            return SimpleNamespace(content="Reservation FU5FSY has been cancelled.", tool_calls=None)

    graph = build_graph(complete_fn=fake_complete, toolbox=tb, policy="Sample policy")

    # Turn 1: User asks to cancel
    state_turn1: AgentState = {
        "session_id": "s_stage3",
        "messages": [{"role": "user", "content": "Please cancel my reservation FU5FSY"}],
        "facts": [],
        "pending_action": None,
        "final_response": "",
        "toolbox": tb,
        "loop_count": 0,
    }

    result1 = graph.invoke(state_turn1)

    # In turn 1, write tool must NOT have run yet
    assert tb.cancelled() == []
    assert result1["pending_action"] == {"tool": "cancel_reservation", "args": {"reservation_id": "FU5FSY"}}
    assert "reply with 'yes' to confirm" in result1["final_response"]

    # Turn 2: User says "Yes, please go ahead."
    state_turn2: AgentState = {
        "session_id": "s_stage3",
        "messages": result1["messages"] + [{"role": "user", "content": "Yes, please go ahead."}],
        "facts": result1["facts"],
        "pending_action": result1["pending_action"],
        "final_response": "",
        "toolbox": tb,
        "loop_count": 0,
    }

    result2 = graph.invoke(state_turn2)

    # In turn 2, write tool MUST have executed
    assert tb.cancelled() == ["FU5FSY"]
    assert result2["pending_action"] is None
    assert result2["final_response"] == "Reservation FU5FSY has been cancelled."


def test_stage3_policy_denial_prevents_action():
    """Verify that when policy_check denies an action, it is blocked and pending_action is not set."""
    tb = ToolBox()
    call_count = 0

    def fake_complete(messages: list[dict], tools=None):
        nonlocal call_count
        call_count += 1

        # Policy checker denies
        if tools is None and any("strict Policy Compliance Checker" in m.get("content", "") for m in messages):
            return SimpleNamespace(
                content=json.dumps({"allowed": False, "section": "Cancel flight", "reason": "Basic economy > 48 hours"}),
                tool_calls=None,
            )

        if call_count == 1:
            # Model proposes cancel_reservation directly (with facts seeded)
            tc = SimpleNamespace(
                id="call_cancel",
                function=SimpleNamespace(
                    name="cancel_reservation",
                    arguments=json.dumps({"reservation_id": "6NSXQU"}),
                ),
            )
            return SimpleNamespace(content=None, tool_calls=[tc])
        else:
            # Model receives policy denial tool error and explains to user
            last_msg = messages[-1]
            assert last_msg["role"] == "tool"
            assert "Policy check denied" in last_msg["content"]
            return SimpleNamespace(content="Cancellation denied under Section: Cancel flight.", tool_calls=None)

    graph = build_graph(complete_fn=fake_complete, toolbox=tb, policy="Sample policy")

    state: AgentState = {
        "session_id": "s_deny",
        "messages": [{"role": "user", "content": "Cancel reservation 6NSXQU"}],
        "facts": ["reservation_id: 6NSXQU"],
        "pending_action": None,
        "final_response": "",
        "toolbox": tb,
        "loop_count": 0,
    }

    result = graph.invoke(state)

    assert tb.cancelled() == []
    assert result["pending_action"] is None
    assert "Cancellation denied" in result["final_response"]
