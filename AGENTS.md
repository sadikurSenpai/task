# AGENTS.md: How we work

## Layout
- Our code: `app/agent.py`, new modules under `app/`, new tests under `tests/`.
- Provided files: don't edit `app/toolbox.py`, `app/main.py`, `app/session.py`, `app/llm.py`,
  `check.py`, `cli.py`, `data/`, `policy/`, `scenarios/public.json`, or existing tests.
  If one seems to need a change, ask first.
- `PLAN.md` is the spec. Follow it. If code and plan disagree, say so before going on.

## Working style
- Go stage by stage. Don't start the next stage until I say so.
- Small, simple changes I can explain line by line.
- Logic that doesn't need the LLM goes in pure functions with unit tests.
- Don't add dependencies without asking.
- If the docs are unclear, ask me instead of guessing.

## After every change
1. Run `pytest -q` and show the result.
2. Add an entry to `CHANGELOG.md`.
3. Give me a 2-3 bullet summary.

## CHANGELOG.md rules
- Newest entry on top.
- Each entry: time, stage, what changed, why, and author (AI or me).
- One entry per meaningful change, not per file.

## Commands
- Server: `uvicorn app.main:app --reload`
- Tests: `pytest -q`
- Scenarios: `python check.py scenarios/public.json -v`
