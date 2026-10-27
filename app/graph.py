import json
import uuid
from typing import Any, Callable

from langgraph.graph import END, START, StateGraph

from .confirmation import describe_action, is_explicit_confirmation
from .guards import build_policy_check_prompt, check_facts_first, parse_policy_verdict
from .llm import complete as default_complete
from .policy import load_policy
from .prompt import build_messages
from .state import AgentState

READ_TOOLS = {"get_user_details", "get_reservation_details", "get_flight_status"}
WRITE_TOOLS = {"cancel_reservation", "send_certificate"}
TRANSFER_TOOL = "transfer_to_human_agents"
TRANSFER_MESSAGE = "YOU ARE BEING TRANSFERRED TO A HUMAN AGENT. PLEASE HOLD ON."
MAX_LOOPS = 10


def _extract_facts_from_tool(name: str, args: dict[str, Any], result_str: str) -> list[str]:
    """Pure helper to extract verified entity IDs into session facts only on success."""
    new_facts: list[str] = []
    try:
        parsed = json.loads(result_str)
    except Exception:
        return new_facts

    if "result" not in parsed:
        # Tool returned error (e.g. unknown id); do NOT record any facts
        return new_facts

    res = parsed["result"]
    if isinstance(res, dict):
        if "user_id" in res and res["user_id"]:
            new_facts.append(f"user_id: {res['user_id']}")
        if "reservation_id" in res and res["reservation_id"]:
            new_facts.append(f"reservation_id: {res['reservation_id']}")
        if "reservations" in res and isinstance(res["reservations"], list):
            for rid in res["reservations"]:
                new_facts.append(f"reservation_id: {rid}")
        if "flights" in res and isinstance(res["flights"], list):
            for f in res["flights"]:
                if isinstance(f, dict) and "flight_number" in f:
                    fnum = f["flight_number"]
                    fdate = f.get("date")
                    new_facts.append(f"flight: {fnum} ({fdate})" if fdate else f"flight: {fnum}")
    elif isinstance(res, str) and name == "get_flight_status":
        fnum = args.get("flight_number")
        fdate = args.get("date")
        if fnum:
            new_facts.append(f"flight: {fnum} ({fdate})" if fdate else f"flight: {fnum}")

    return new_facts


def _merge_facts(existing: list[str], additions: list[str]) -> list[str]:
    """Merge facts preserving insertion order and eliminating duplicates."""
    seen = set(existing)
    merged = list(existing)
    for fact in additions:
        if fact not in seen:
            seen.add(fact)
            merged.append(fact)
    return merged


def create_route_turn_node() -> Callable[[AgentState], dict[str, Any]]:
    """Node at turn start: retains pending action only if confirmed, otherwise clears it."""

    def route_turn(state: AgentState) -> dict[str, Any]:
        pending = state.get("pending_action")
        messages = state.get("messages", [])
        user_msg = messages[-1].get("content", "") if messages and messages[-1].get("role") == "user" else ""

        if pending and is_explicit_confirmation(user_msg):
            return {}
        return {"pending_action": None}

    return route_turn


def route_after_turn(state: AgentState) -> str:
    """Conditional edge from route_turn: execute write if explicit yes, else call model."""
    pending = state.get("pending_action")
    messages = state.get("messages", [])
    user_msg = messages[-1].get("content", "") if messages and messages[-1].get("role") == "user" else ""

    if pending and is_explicit_confirmation(user_msg):
        return "execute_write"
    return "call_model"


def create_execute_write_node(toolbox: Any = None) -> Callable[[AgentState], dict[str, Any]]:
    """Node to execute the stored write action after explicit user confirmation (FR10)."""

    def execute_write(state: AgentState) -> dict[str, Any]:
        tb = state.get("toolbox") or toolbox
        messages = list(state.get("messages", []))
        facts = list(state.get("facts", []))
        action = state.get("pending_action") or {}

        tool_name = action.get("tool", "")
        args = action.get("args", {})
        call_id = f"exec_{uuid.uuid4().hex[:8]}"

        assistant_msg = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": json.dumps(args),
                    },
                }
            ],
        }

        result_str = tb.call(tool_name, args) if tb and hasattr(tb, "call") else json.dumps({"error": "No toolbox"})
        tool_msg = {
            "role": "tool",
            "tool_call_id": call_id,
            "content": result_str,
        }

        extracted = _extract_facts_from_tool(tool_name, args, result_str)
        updated_facts = _merge_facts(facts, extracted)

        return {
            "messages": messages + [assistant_msg, tool_msg],
            "facts": updated_facts,
            "pending_action": None,
        }

    return execute_write


def create_call_model_node(
    complete_fn: Callable[..., Any],
    policy: str | Callable[[], str],
    toolbox: Any = None,
) -> Callable[[AgentState], dict[str, Any]]:
    """Create the call_model node with injected LLM, policy, and tool schemas."""

    def call_model(state: AgentState) -> dict[str, Any]:
        loop_count = state.get("loop_count", 0)
        history = list(state.get("messages", []))
        facts = state.get("facts", [])
        pending = state.get("pending_action")

        if loop_count >= MAX_LOOPS:
            apology = "I apologize, but I am unable to process your request further. Please contact a human agent."
            return {
                "messages": history + [{"role": "assistant", "content": apology}],
                "final_response": apology,
                "loop_count": loop_count + 1,
            }

        current_policy = policy() if callable(policy) else policy
        full_messages = build_messages(
            policy=current_policy,
            facts=facts,
            pending=pending,
            history=history,
        )

        tb = state.get("toolbox") or toolbox
        schemas = tb.schemas() if tb and hasattr(tb, "schemas") else None

        response = complete_fn(messages=full_messages, tools=schemas)
        tool_calls = getattr(response, "tool_calls", None)

        if tool_calls and len(tool_calls) > 0:
            # FR6: Only the first tool call is kept; no reply text in the same step
            first_tc = tool_calls[0]
            call_id = getattr(first_tc, "id", None) or (first_tc.get("id") if isinstance(first_tc, dict) else str(uuid.uuid4()))
            fn = getattr(first_tc, "function", None) or (first_tc.get("function") if isinstance(first_tc, dict) else None)
            fn_name = getattr(fn, "name", None) or (fn.get("name") if isinstance(fn, dict) else "")
            fn_args = getattr(fn, "arguments", None) or (fn.get("arguments") if isinstance(fn, dict) else "{}")
            if not isinstance(fn_args, str):
                fn_args = json.dumps(fn_args)

            assistant_msg = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": fn_name,
                            "arguments": fn_args,
                        },
                    }
                ],
            }
            return {
                "messages": history + [assistant_msg],
                "loop_count": loop_count + 1,
            }

        content = getattr(response, "content", "") or ""
        assistant_msg = {"role": "assistant", "content": content}
        return {
            "messages": history + [assistant_msg],
            "final_response": content,
            "loop_count": loop_count + 1,
        }

    return call_model


def create_run_read_tool_node(toolbox: Any = None) -> Callable[[AgentState], dict[str, Any]]:
    """Create the run_read_tool node to execute read tools and record facts."""

    def run_read_tool(state: AgentState) -> dict[str, Any]:
        tb = state.get("toolbox") or toolbox
        messages = list(state.get("messages", []))
        facts = list(state.get("facts", []))

        last_msg = messages[-1] if messages else {}
        tc = last_msg.get("tool_calls", [{}])[0]
        call_id = tc.get("id", str(uuid.uuid4()))
        fn = tc.get("function", {})
        tool_name = fn.get("name", "")
        raw_args = fn.get("arguments", "{}")

        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
        except Exception:
            args = {}

        result_str = tb.call(tool_name, args) if tb and hasattr(tb, "call") else json.dumps({"error": "No toolbox"})

        tool_msg = {
            "role": "tool",
            "tool_call_id": call_id,
            "content": result_str,
        }

        extracted_facts = _extract_facts_from_tool(tool_name, args, result_str)
        updated_facts = _merge_facts(facts, extracted_facts)

        return {
            "messages": messages + [tool_msg],
            "facts": updated_facts,
        }

    return run_read_tool


def create_run_transfer_node(toolbox: Any = None) -> Callable[[AgentState], dict[str, Any]]:
    """Create the run_transfer node to execute transfer and send exact policy message."""

    def run_transfer(state: AgentState) -> dict[str, Any]:
        tb = state.get("toolbox") or toolbox
        messages = list(state.get("messages", []))

        last_msg = messages[-1] if messages else {}
        tc = last_msg.get("tool_calls", [{}])[0]
        call_id = tc.get("id", str(uuid.uuid4()))
        fn = tc.get("function", {})
        raw_args = fn.get("arguments", "{}")

        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
        except Exception:
            args = {}

        if tb and hasattr(tb, "call"):
            tb.call(TRANSFER_TOOL, args)

        tool_msg = {
            "role": "tool",
            "tool_call_id": call_id,
            "content": json.dumps({"result": "Transfer successful"}),
        }
        assistant_msg = {
            "role": "assistant",
            "content": TRANSFER_MESSAGE,
        }

        return {
            "messages": messages + [tool_msg, assistant_msg],
            "final_response": TRANSFER_MESSAGE,
        }

    return run_transfer


def create_run_unhandled_tool_node() -> Callable[[AgentState], dict[str, Any]]:
    """Node to safely reply to unhandled tool calls with a tool error message."""

    def run_unhandled_tool(state: AgentState) -> dict[str, Any]:
        messages = list(state.get("messages", []))
        last_msg = messages[-1] if messages else {}
        tc = last_msg.get("tool_calls", [{}])[0]
        call_id = tc.get("id", str(uuid.uuid4()))

        tool_msg = {
            "role": "tool",
            "tool_call_id": call_id,
            "content": json.dumps({"error": "This action is not available yet"}),
        }
        return {
            "messages": messages + [tool_msg],
        }

    return run_unhandled_tool


def create_facts_check_node() -> Callable[[AgentState], dict[str, Any]]:
    """Node enforcing FR8 (facts-first check before write tool execution)."""

    def facts_check(state: AgentState) -> dict[str, Any]:
        messages = list(state.get("messages", []))
        facts = list(state.get("facts", []))

        last_msg = messages[-1] if messages else {}
        tc = last_msg.get("tool_calls", [{}])[0]
        call_id = tc.get("id", str(uuid.uuid4()))
        fn = tc.get("function", {})
        tool_name = fn.get("name", "")
        raw_args = fn.get("arguments", "{}")

        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
        except Exception:
            args = {}

        action = {"tool": tool_name, "args": args}
        ok, error_msg = check_facts_first(action, facts)

        if not ok:
            tool_msg = {
                "role": "tool",
                "tool_call_id": call_id,
                "content": json.dumps({"error": error_msg}),
            }
            return {
                "messages": messages + [tool_msg],
                "facts_ok": False,
                "proposed_action": None,
            }

        return {
            "facts_ok": True,
            "proposed_action": action,
        }

    return facts_check


def create_policy_check_node(
    complete_fn: Callable[..., Any],
    policy: str | Callable[[], str],
) -> Callable[[AgentState], dict[str, Any]]:
    """Node enforcing FR9 (LLM compliance check before write tool execution)."""

    def policy_check(state: AgentState) -> dict[str, Any]:
        messages = list(state.get("messages", []))
        facts = list(state.get("facts", []))
        action = state.get("proposed_action") or {}

        last_msg = messages[-1] if messages else {}
        tc = last_msg.get("tool_calls", [{}])[0]
        call_id = tc.get("id", str(uuid.uuid4()))

        current_policy = policy() if callable(policy) else policy
        check_messages = build_policy_check_prompt(
            policy=current_policy,
            facts=facts,
            action=action,
            recent_history=messages,
        )

        response = complete_fn(messages=check_messages, tools=None)
        raw_verdict = getattr(response, "content", "") or ""
        verdict = parse_policy_verdict(raw_verdict)

        if not verdict.allowed:
            tool_msg = {
                "role": "tool",
                "tool_call_id": call_id,
                "content": json.dumps({
                    "error": f"Policy check denied: {verdict.reason} (Section: {verdict.section})"
                }),
            }
            return {
                "messages": messages + [tool_msg],
                "policy_ok": False,
            }

        return {
            "policy_ok": True,
        }

    return policy_check


def create_ask_confirmation_node() -> Callable[[AgentState], dict[str, Any]]:
    """Node enforcing FR10 (listing exact action and asking for explicit 'yes')."""

    def ask_confirmation(state: AgentState) -> dict[str, Any]:
        messages = list(state.get("messages", []))
        action = state.get("proposed_action") or {}

        last_msg = messages[-1] if messages else {}
        tc = last_msg.get("tool_calls", [{}])[0]
        call_id = tc.get("id", str(uuid.uuid4()))

        desc = describe_action(action)
        confirmation_msg = f"I am ready to {desc}. Please reply with 'yes' to confirm and proceed."

        # Complete the tool call in conversation history so OpenAI format is preserved
        tool_msg = {
            "role": "tool",
            "tool_call_id": call_id,
            "content": json.dumps({"status": "confirmation_required", "action": desc}),
        }
        assistant_msg = {
            "role": "assistant",
            "content": confirmation_msg,
        }

        return {
            "messages": messages + [tool_msg, assistant_msg],
            "pending_action": action,
            "final_response": confirmation_msg,
        }

    return ask_confirmation


def route_after_model(state: AgentState) -> str:
    """Route based on whether model produced text, transfer, read tool, write tool, or unhandled tool."""
    if state.get("final_response"):
        return END

    messages = state.get("messages", [])
    if not messages:
        return END

    last_msg = messages[-1]
    tool_calls = last_msg.get("tool_calls")
    if not tool_calls:
        return END

    first_call = tool_calls[0]
    tool_name = first_call.get("function", {}).get("name", "")

    if tool_name == TRANSFER_TOOL:
        return "run_transfer"
    if tool_name in WRITE_TOOLS:
        return "facts_check"
    if tool_name in READ_TOOLS:
        return "run_read_tool"

    return "run_unhandled_tool"


def build_graph(
    complete_fn: Callable[..., Any] | None = None,
    toolbox: Any = None,
    policy: str | Callable[[], str] | None = None,
) -> Any:
    """Build and compile the LangGraph StateGraph with Stage 3 safeguards."""
    complete_callable = complete_fn or default_complete
    policy_source = policy if policy is not None else load_policy

    builder = StateGraph(AgentState)
    builder.add_node("route_turn", create_route_turn_node())
    builder.add_node("execute_write", create_execute_write_node(toolbox))
    builder.add_node("call_model", create_call_model_node(complete_callable, policy_source, toolbox))
    builder.add_node("run_read_tool", create_run_read_tool_node(toolbox))
    builder.add_node("run_transfer", create_run_transfer_node(toolbox))
    builder.add_node("run_unhandled_tool", create_run_unhandled_tool_node())
    builder.add_node("facts_check", create_facts_check_node())
    builder.add_node("policy_check", create_policy_check_node(complete_callable, policy_source))
    builder.add_node("ask_confirmation", create_ask_confirmation_node())

    builder.add_edge(START, "route_turn")
    builder.add_conditional_edges(
        "route_turn",
        route_after_turn,
        {
            "execute_write": "execute_write",
            "call_model": "call_model",
        },
    )
    builder.add_edge("execute_write", "call_model")

    builder.add_conditional_edges(
        "call_model",
        route_after_model,
        {
            "run_read_tool": "run_read_tool",
            "run_transfer": "run_transfer",
            "run_unhandled_tool": "run_unhandled_tool",
            "facts_check": "facts_check",
            END: END,
        },
    )
    builder.add_edge("run_read_tool", "call_model")
    builder.add_edge("run_unhandled_tool", "call_model")
    builder.add_edge("run_transfer", END)

    builder.add_conditional_edges(
        "facts_check",
        lambda state: "policy_check" if state.get("facts_ok") else "call_model",
        {
            "policy_check": "policy_check",
            "call_model": "call_model",
        },
    )
    builder.add_conditional_edges(
        "policy_check",
        lambda state: "ask_confirmation" if state.get("policy_ok") else "call_model",
        {
            "ask_confirmation": "ask_confirmation",
            "call_model": "call_model",
        },
    )
    builder.add_edge("ask_confirmation", END)

    return builder.compile()
