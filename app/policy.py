from pathlib import Path

DEFAULT_POLICY_PATH = Path(__file__).resolve().parent.parent / "policy" / "policy.md"


def load_policy(path: str | Path = DEFAULT_POLICY_PATH) -> str:
    """Load policy markdown from disk at runtime.

    Raises FileNotFoundError if the policy file does not exist.
    """
    policy_file = Path(path)
    if not policy_file.is_file():
        raise FileNotFoundError(f"Policy file not found at: {policy_file}")
    return policy_file.read_text(encoding="utf-8")
