# Changelog

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
