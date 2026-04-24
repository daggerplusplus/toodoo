#!/usr/bin/env python3
"""
PreToolUse secret scanner for Claude Code.
Reads hook JSON from stdin, inspects the content about to be written,
and outputs allow/deny JSON.
"""

import json
import re
import sys

PLACEHOLDER = re.compile(
    r"(your[-_]?(?:api[-_]?)?key|<[A-Z_]+>|changeme|example|xxx+|placeholder|todo|secret_here|token_here)",
    re.IGNORECASE,
)

PATTERNS = [
    # Private keys / certs
    (re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"), "private key"),
    # AWS access key ID
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key ID"),
    # AWS secret access key assignment
    (re.compile(r'(?i)aws_secret_access_key\s*=\s*["\']?[A-Za-z0-9/+]{40}["\']?'), "AWS secret access key"),
    # Generic high-entropy token assignments (key=, token=, secret=, password=, passwd=, pwd=, auth=)
    (
        re.compile(
            r'(?i)(?:api_?key|token|secret|password|passwd|pwd|auth(?:_token)?)\s*[=:]\s*["\']?([A-Za-z0-9+/\-_\.]{20,})["\']?'
        ),
        "credential assignment",
    ),
    # Connection strings with embedded credentials
    (
        re.compile(r'(?i)(?:postgresql|mysql|mongodb(?:\+srv)?|redis)://[^:]+:[^@]{6,}@'),
        "connection string with credentials",
    ),
    # JWT tokens (three base64url segments)
    (re.compile(r'\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b'), "JWT token"),
    # GitHub / GitLab / npm / PyPI tokens
    (re.compile(r'\bghp_[A-Za-z0-9]{36}\b'), "GitHub personal access token"),
    (re.compile(r'\bgho_[A-Za-z0-9]{36}\b'), "GitHub OAuth token"),
    (re.compile(r'\bglpat-[A-Za-z0-9\-_]{20}\b'), "GitLab personal access token"),
    (re.compile(r'\bnpm_[A-Za-z0-9]{36}\b'), "npm token"),
    (re.compile(r'\bpypi-[A-Za-z0-9\-_]{40,}\b'), "PyPI token"),
    # Anthropic / OpenAI keys
    (re.compile(r'\bsk-ant-[A-Za-z0-9\-_]{20,}\b'), "Anthropic API key"),
    (re.compile(r'\bsk-[A-Za-z0-9]{40,}\b'), "OpenAI API key"),
    # Stripe keys
    (re.compile(r'\bsk_(?:live|test)_[A-Za-z0-9]{24,}\b'), "Stripe secret key"),
]


def is_placeholder(value: str) -> bool:
    return bool(PLACEHOLDER.search(value))


def scan(content: str) -> list[tuple[int, str]]:
    hits = []
    for lineno, line in enumerate(content.splitlines(), 1):
        for pattern, label in PATTERNS:
            m = pattern.search(line)
            if m and not is_placeholder(m.group(0)):
                hits.append((lineno, label))
                break
    return hits


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        # Can't parse input — allow and let the tool proceed
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}}))
        return

    tool_input = hook_input.get("tool_input", {})
    # Write tool uses "content"; Edit tool uses "new_string"
    content = tool_input.get("content") or tool_input.get("new_string") or ""

    hits = scan(content)
    if hits:
        descriptions = "; ".join(f"line {ln}: {label}" for ln, label in hits[:5])
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"SECRET DETECTED: {descriptions}",
            }
        }))
    else:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}}))


if __name__ == "__main__":
    main()
