# HAT Air support agent: 2.5-hour assessment

You are building the brain of a customer-support chat agent for **HAT Air**, a fictional airline.
The server skeleton, tools, data and a self-check script are provided. The agent is yours to build.

**Time:** about 2.5 hours, on site. An interviewer is in the room and will ask questions along the way.
**Allowed:** documentation, web search, AI coding assistants. You will be asked to explain any code you
keep, so don't keep what you can't explain. Prioritise a working, understood agent over a big one.

How you will be evaluated is in [rubric.md](rubric.md). Read it first.

## The goal

Users chat with the agent about their reservations. The agent must:

1. answer from the HAT Air policy (`policy/policy.md`) and say so when the policy doesn't cover something,
2. use tools to look things up and to act,
3. follow the policy when deciding whether an action is allowed,
4. know when to hand over to a human.

## Stages (do them in order; each one is useful on its own)

| # | Stage | Done when |
|---|-------|-----------|
| 1 | **Grounded answers** | Asked a policy question, the agent answers from the policy, points to the section it used, and says "the policy doesn't say" when it doesn't. |
| 2 | **Tools** | Given a user id or reservation id, it looks the data up. Unknown ids don't lead to made-up answers. |
| 3 | **Safe actions** | Cancellations and compensation follow the policy. The agent lists what it is about to do and gets an explicit "yes" first. That rule is enforced **in your code**, not only in the prompt. |
| 4 | **Stretch (pick one)** | Handoff polish, multi-turn memory limits, a Bangla/Banglish message, or streaming replies. |

You decide how to ground the answers. The policy is short; whether you retrieve sections or put the
whole thing in the prompt is your call, and you should be ready to explain the trade-off.

## What's here

```
app/main.py       FastAPI server: POST /chat, GET /debug/<session> (provided)
app/agent.py      respond(): the function you build
app/toolbox.py    tools + OpenAI-style schemas (provided; read it before you start)
app/llm.py        one-call wrapper for an OpenAI-compatible endpoint
policy/policy.md  the HAT Air policy
data/db.json      users, reservations and flights (fictional)
scenarios/        sample chats for check.py
check.py          runs scripted chats against your server and checks the outcome
cli.py            chat with your server from the terminal
```

Things to know about the tools:

- `cancel_reservation` and `send_certificate` change data and **do no rule checking**. Whether the
  action is allowed is decided by your agent, using the policy.
- Changes are per chat session and are never written to `data/db.json`.
- The current time for this airline is the one stated in the policy.

**Policy file:** your agent must read `policy/policy.md` from disk when the server starts. The
interviewer may replace that file during the session, so don't paste policy text into your code.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in the values the interviewer gives you
uvicorn app.main:app --reload
```

In a second terminal:

```bash
python cli.py                              # chat by hand
python check.py scenarios/public.json -v   # scripted chats, -v prints transcripts
pytest -q                                  # tests for the provided tools
```

`check.py` passing on the public scenarios is **not** the finish line. The interviewer scores your agent
on other chats, and also on how you work and how well you can explain what you built.

## Out of scope

UI, authentication, deployment, database changes, fine-tuning, booking or changing flights (there are no
tools for them; the policy covers them, but the right move in this exercise is a handoff).

## Credit

Data, tools and policy are adapted from the airline domain of
[tau2-bench](https://github.com/sierra-research/tau2-bench) by Sierra Research (MIT, see
`LICENSE-tau2-bench`). The policy has been edited, so don't rely on published benchmark results.
