import pytest
from pathlib import Path
from app.policy import load_policy


def test_load_policy_success():
    content = load_policy()
    assert isinstance(content, str)
    assert len(content) > 100
    assert "HAT Air Agent Policy" in content


def test_load_policy_file_not_found(tmp_path: Path):
    non_existent = tmp_path / "does_not_exist.md"
    with pytest.raises(FileNotFoundError):
        load_policy(non_existent)


def test_load_policy_reloads_on_file_change(tmp_path: Path):
    temp_policy = tmp_path / "policy.md"
    temp_policy.write_text("Version 1 content", encoding="utf-8")

    assert load_policy(temp_policy) == "Version 1 content"

    # Simulate interviewer replacing policy file
    temp_policy.write_text("Version 2 updated content", encoding="utf-8")
    assert load_policy(temp_policy) == "Version 2 updated content"
