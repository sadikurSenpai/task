# Changelog

## 2026-10-27 14:15 · Stage 3 (safe actions and explicit confirmation) · AI
- **What:** Implemented `app/confirmation.py` (`PendingAction`, `is_explicit_confirmation`, `describe_action`), `app/guards.py` (`check_facts_first`, `parse_policy_verdict` with fail-closed parsing, `build_policy_check_prompt`), and updated `app/graph.py` with complete Stage 3 nodes (`route_turn`, `facts_check`, `policy_check`, `ask_confirmation`, `execute_write`). Added comprehensive unit tests in `tests/test_stage3_safeguards.py`.
- **Why:** Enforces FR8 (facts-first lookup check before write tool proposal), FR9 (code-gated structured LLM policy compliance check), FR10 (explicit confirmation listing exact action before execution), and FR11 (user pressure resistance). Write tools cannot execute on the first turn and require policy approval plus an explicit "yes" in the subsequent turn.

## 2026-10-27 14:08 · Stage 2 (bug fixes and robustness) · AI
- **What:** Added `run_unhandled_tool` node in `app/graph.py` to reply to unsupported/write tools with `{"error": "This action is not available yet"}` and loop back to the model; fixed `_extract_facts_from_tool` to only record facts on successful lookups and read `"reservations"` (aligning with `db.json`); updated system prompt in `app/prompt.py` with tool scope and exact values preservation; eagerly called `load_policy()` at import in `app/agent.py`; and updated `tests/test_stage2_tools.py` with `yusuf_li_4428`, unknown ID fact suppression test, and unhandled tool recovery test.
- **Why:** Prevent OpenAI 400 errors on unhandled tool calls, prevent recording facts from failed lookups, ensure missing policy crashes at server startup, and keep unit test suite green against actual database fixtures.

## 2026-10-27 14:00 · Stage 2 (tools and human transfer) · AI
- **What:** Implemented tool calling and read/transfer workflow in `app/graph.py`, updated `AgentState` in `app/state.py` to hold session tools and loop count, expanded system prompt guidelines in `app/prompt.py` (single-tool execution, accurate tool error reporting for unknown IDs, transfer for out-of-scope requests), wired `session.toolbox` in `app/agent.py`, and added unit tests in `tests/test_stage2_tools.py`.
- **Why:** Satisfies Stage 2 requirements (FR4: lookup tools, FR5: honest reporting of missing IDs without hallucination, FR6: first-tool-only enforcement and no simultaneous text reply, FR7: transfer to human agents with exact policy message).

## 2026-10-27 13:49 · Stage 1 (prompt refinement) · AI
- **What:** Refined system prompt in `app/prompt.py` to provide concrete citation examples without angle brackets (`Section: Cancel flight`, `Section: Book flight > Checked bag allowance`) and instructed the agent to briefly offer help with supported topics (reservations, cancellations, compensation) when the policy does not cover a question.
- **Why:** Prevent the model from outputting literal `<...>` placeholder brackets in citations and improve user experience on uncovered questions.

## 2026-10-27 13:46 · Stage 1 (test configuration) · AI
- **What:** Created `pytest.ini` with `pythonpath = .`.
- **Why:** Allows running plain `pytest -q` directly from the repo root without needing `python -m`.

## 2026-10-27 13:36 · Stage 1 (grounded answers boilerplate) · AI
- **What:** Implemented `app/policy.py` (runtime file loader), `app/state.py` (LangGraph state and session store), `app/prompt.py` (prompt builder with citation and unmentioned rules), `app/graph.py` (LangGraph StateGraph `START -> call_model -> END`), `app/agent.py` (`respond()` pipeline), and unit tests (`tests/test_policy.py`, `tests/test_prompt.py`, `tests/test_stage1_graph.py`).
- **Why:** Establish the grounded answer baseline for Stage 1 per `PLAN.md` with dependency-injected LLM and policy for pure unit testability.

## 2026-10-27 13:16 · Stage 0 (planning) · AI (decisions by me)
- **What:** Added `PLAN.md`: functional requirements, prompt layout, LangGraph graph (nodes and edges), modules, stage "done when" criteria.
- **Why:** Records the agreed architecture (custom LangGraph `StateGraph`, policy loaded at runtime, facts-first + policy-check + explicit-"yes" safeguards) as the spec before any code.

## 2026-10-27 12:50 · Stage 0 (setup) · AI
- **What:** Added `AGENTS.md` (workflow rules) and this `CHANGELOG.md`.
- **Why:** Agree how we work before building.
