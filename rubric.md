# HAT Air AI Engineer Assessment: How You'll Be Evaluated

Thanks for taking the time to do this exercise. This page explains what we look at, so you can spend your 2.5 hours on what matters.

## What we value

We care more about a working agent you understand than a large one. Finishing every stage isn't the goal. A candidate who builds Stages 1–3 carefully and can explain every decision will usually do better than one who rushes to the stretch goal with code they can't walk through.

AI coding assistants are welcome. We'll ask you to explain any code you keep, and we'll ask how you used the assistant, so be ready to talk about both.

We'll score five areas from 1 (below expectations) to 4 (strong):

| Area | Weight |
|---|---|
| Spec-driven development | 20% |
| Context engineering and grounding | 25% |
| Agent safety and policy enforcement | 25% |
| Evaluation and testing | 15% |
| Documentation and communication | 15% |

## 1. Spec-driven development (20%)

We look at how you go from requirements to code. Strong work starts with reading the provided material (README, policy, toolbox, check script) and turning it into a clear, written plan of what the agent must do and where each rule will be enforced. You then build stage by stage, getting each one working before moving on.

If you use an AI assistant, we want to see you direct it with that plan and review what it produces, rather than accepting whatever comes back. If the docs are ambiguous or seem to conflict, ask us. Asking a good question is a positive signal, not a weakness.

## 2. Context engineering and grounding (25%)

We look at what goes into the model's context on each turn and why. That covers how you load the policy, how you structure the prompt, how you keep conversation history and tool results correct across turns, and how you stop the model from answering from general knowledge.

Strong work answers from the policy, names the section it used, says plainly when the policy doesn't cover something, and never invents data the tools didn't return. We'll ask you to justify your grounding approach, including why you did or didn't use retrieval, and what would make you change your mind.

## 3. Agent safety and policy enforcement (25%)

The write tools perform no rule checks, so whether an action is allowed is entirely your agent's responsibility. We look at how reliably your agent follows the policy when it's under pressure, not only when the conversation goes smoothly.

As the README states, an explicit confirmation before any write action must be enforced in your code, not only in the prompt. Strong work can point to exactly where each safeguard lives and explain what happens when a user, or the model itself, tries to get around it.

## 4. Evaluation and testing (15%)

We look at how you know your agent works. Passing `check.py` on the public scenarios is a starting point, not the finish line, because we'll run other conversations too.

Strong work tests beyond the provided scenarios, reads failing transcripts to understand why they failed, and keeps deterministic logic that can be tested without the LLM separate from behaviour that needs a model. Be ready to tell us what you tested, what you didn't, and what you'd add next.

## 5. Documentation and communication (15%)

We look at whether someone else could understand and pick up your work. Strong work includes a short write-up: how to run it, the key design decisions and their trade-offs, and known limitations or what you'd do with more time.

During the session, we value clear explanations, honesty about what you're unsure of or what the AI wrote, and keeping us informed as you work.

## Ground rules

These apply regardless of score:

- **You must be able to explain any code you keep.**
- **Write actions need a confirmation enforced in code.**
- **The agent must not make up answers for unknown IDs.**
- **Be honest about how you used AI tools.**

Good luck, and feel free to ask questions at any point during the session.