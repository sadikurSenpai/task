from pathlib import Path

DEFAULT_POLICY_PATH = Path(__file__).resolve().parent.parent / "policy" / "policy.md"


_cached_policy: str | None = None
_cached_mtime: float | None = None


def load_policy(path: str | Path = DEFAULT_POLICY_PATH) -> str:
    """Load policy markdown from disk at runtime.

    Checks mtime so file changes on disk are reflected immediately without
    needing a server restart. Raises FileNotFoundError if missing.
    """
    global _cached_policy, _cached_mtime
    policy_file = Path(path)
    if not policy_file.is_file():
        raise FileNotFoundError(f"Policy file not found at: {policy_file}")

    mtime = policy_file.stat().st_mtime
    if _cached_policy is None or _cached_mtime != mtime:
        _cached_policy = policy_file.read_text(encoding="utf-8")
        _cached_mtime = mtime

    return _cached_policy
