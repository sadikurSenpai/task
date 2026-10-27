from app.prompt import build_messages, build_system_prompt


def test_build_system_prompt_structure():
    policy = "# Sample Policy\nSome text."
    facts = ["user_id: 123"]
    pending = {"tool": "cancel_reservation"}

    prompt = build_system_prompt(policy=policy, facts=facts, pending=pending)

    assert "[SYSTEM]" in prompt
    assert "[KNOWLEDGE BASE]" in prompt
    assert "# Sample Policy" in prompt
    assert "[SESSION FACTS]" in prompt
    assert "user_id: 123" in prompt
    assert "[PENDING ACTION]" in prompt
    assert "cancel_reservation" in prompt
    assert "Section: Cancel flight" in prompt
    assert "Section: Book flight > Checked bag allowance" in prompt
    assert "the policy doesn't say" in prompt


def test_build_messages_with_history():
    policy = "Policy text"
    history = [
        {"role": "user", "content": "What is the policy?"},
        {"role": "assistant", "content": "Section: Intro..."},
    ]

    messages = build_messages(policy=policy, history=history)

    assert len(messages) == 3
    assert messages[0]["role"] == "system"
    assert "Policy text" in messages[0]["content"]
    assert messages[1] == history[0]
    assert messages[2] == history[1]
