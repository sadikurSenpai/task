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
