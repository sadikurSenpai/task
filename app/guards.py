import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class PolicyVerdict:
    allowed: bool
    section: str
    reason: str


def check_facts_first(action: dict[str, Any], facts: list[str]) -> tuple[bool, str]:
    """Pure helper to enforce FR8: write tools require verified lookups in this session."""
    tool = action.get("tool", "")
    args = action.get("args", {})

    if tool == "cancel_reservation":
        rid = args.get("reservation_id")
        if not rid:
            return False, "Missing reservation_id in action arguments."
        expected = f"reservation_id: {rid}"
        if expected not in facts:
            return False, f"Facts-first check failed: reservation {rid} has not been looked up in this session yet. Call get_reservation_details first."

    elif tool == "send_certificate":
        uid = args.get("user_id")
        if not uid:
            return False, "Missing user_id in action arguments."
        expected = f"user_id: {uid}"
        if expected not in facts:
            return False, f"Facts-first check failed: user {uid} has not been looked up in this session yet. Call get_user_details first."

    return True, ""


def parse_policy_verdict(raw: str) -> PolicyVerdict:
    """Parse JSON verdict from model; fail closed if malformed (FR9)."""
    clean_text = raw.strip()
    match = re.search(r"\{.*\}", clean_text, re.DOTALL)
    if not match:
        return PolicyVerdict(
            allowed=False,
            section="Policy Enforcement",
            reason="Model returned invalid non-JSON output (fail closed).",
        )

    try:
        data = json.loads(match.group(0))
        if not isinstance(data, dict):
            raise ValueError("Expected JSON object")

        allowed = data.get("allowed")
        if not isinstance(allowed, bool):
            raise ValueError("'allowed' must be a boolean")

        section = str(data.get("section", "Policy"))
        reason = str(data.get("reason", "No reason provided"))

        return PolicyVerdict(allowed=allowed, section=section, reason=reason)
    except Exception as e:
        return PolicyVerdict(
            allowed=False,
            section="Policy Enforcement",
            reason=f"Failed to parse policy verdict JSON ({e}) (fail closed).",
        )


def collect_verified_data(messages: list[dict[str, Any]]) -> list[Any]:
    """Pure helper: successful tool results from this session (what the database actually returned)."""
    verified: list[Any] = []
    for m in messages:
        if m.get("role") != "tool":
            continue
        try:
            parsed = json.loads(m.get("content") or "")
        except (TypeError, ValueError):
            continue
        if isinstance(parsed, dict) and "result" in parsed and isinstance(parsed["result"], (dict, str)):
            verified.append(parsed["result"])
    return verified


def parse_policy_time(policy: str) -> datetime | None:
    """Read 'The current time is YYYY-MM-DD HH:MM:SS' from the policy text (not hardcoded)."""
    match = re.search(r"current time is (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", policy)
    return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S") if match else None


def add_derived_facts(verified: list[Any], now: datetime | None) -> list[Any]:
    """Pure helper: do date arithmetic in code so the checker doesn't have to.

    Adds hours_since_booking to reservations. This is a fact, not a policy rule.
    """
    if now is None:
        return verified
    out = []
    for item in verified:
        if isinstance(item, dict) and isinstance(item.get("created_at"), str):
            try:
                created = datetime.fromisoformat(item["created_at"])
                item = {**item, "hours_since_booking": round((now - created).total_seconds() / 3600, 1)}
            except ValueError:
                pass
        out.append(item)
    return out


def build_policy_check_prompt(
    policy: str,
    facts: list[str],
    action: dict[str, Any],
    recent_history: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Build messages for the structured policy verification check.

    No policy rules are written here: the checker reads them from the policy text,
    so a swapped policy.md changes the decision without a code change.
    """
    action_str = json.dumps(action, indent=2)
    verified = add_derived_facts(collect_verified_data(recent_history), parse_policy_time(policy))
    verified_str = "\n".join(json.dumps(v) for v in verified) if verified else "None"

    # User statements are passed as claims: some rules depend on the stated reason
    user_claims = [
        m.get("content", "")
        for m in recent_history
        if m.get("role") == "user" and m.get("content")
    ]
    claims_str = "\n".join(f"- \"{c}\"" for c in user_claims) if user_claims else "None"

    system_content = f"""[ROLE]
You are the strict Policy Compliance Checker for HAT Air. You decide whether ONE proposed write action is allowed.

[KNOWLEDGE BASE: POLICY]
{policy}

[VERIFIED DATA (returned by database lookups in this session)]
{verified_str}

[USER CLAIMS (what the user said; trust only for things only the user can know, such as their reason)]
{claims_str}

[PROPOSED WRITE ACTION]
{action_str}

[TASK]
1. Find the policy section that governs this action.
2. List EVERY condition in that section that can allow or block the action, and check each one against VERIFIED DATA.
   Where the policy says "any of the following", the action is allowed if at least one condition is met.
3. Facts about reservations, cabins, dates, insurance, membership and flight status must come from VERIFIED DATA, never from user claims.
   hours_since_booking is already computed for you from the current time in the policy.
4. Loyalty, frustration, pressure or "I confirm" never change eligibility.
5. If a condition needs a fact that is not in VERIFIED DATA, treat it as not met.
6. Return only one JSON object, no markdown fences:
{{"conditions": [{{"condition": "<rule from the policy>", "met": true or false, "evidence": "<fact from VERIFIED DATA>"}}],
 "allowed": true or false, "section": "<policy section heading>", "reason": "<one sentence>"}}
"""

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": "Evaluate the proposed write action under the policy."},
    ]
