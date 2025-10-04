#!/usr/bin/env python3
"""
Simple pre-commit redaction helper.

What it does:
- Scans staged files (added/modified) for common secret patterns.
- Auto-redacts detected secret values (replaces with "<REDACTED>") in the working tree
  and re-stages the file so the commit contains the redacted value.
- Prints a summary of redactions.

Notes:
- If you prefer to block commits instead of auto-redacting, set the environment variable
  BLOCK_ON_SECRET=1 when committing (e.g. `BLOCK_ON_SECRET=1 git commit ...` or on
  Windows PowerShell: `$env:BLOCK_ON_SECRET=1; git commit ...`).
- This script operates on text files only and will skip binary files.
- Patterns are heuristic and conservative; review any redactions before pushing.
"""

from __future__ import annotations
import subprocess
import sys
import os
import re
from typing import List

GIT = "git"

# Regex patterns to find secrets. Each pattern should have a capture group for the
# "prefix" (the left-hand side and assignment operator) and the secret value as
# a following group.
PATTERNS = [
    # JSON / JS / PY style: "clientSecret": "<REDACTED>"  or client_secret = '<REDACTED>'
    re.compile(r'(?im)("?(?:client[_\-]?secret|clientSecret|client_secret|clientSecretValue|client-secret|secret|api[_\-]?key|apiKey|access[_\-]?token|auth[_\-]?token|password|pwd)"?\s*[:=]\s*)(["\'])([^"\']{4,})(["\'])'),
    # ENV style: SECRET_KEY=abc123
    re.compile(r'(?im)(^\s*(?:AWS_SECRET_ACCESS_KEY|AWS_SECRET|SECRET_KEY|SECRET|TOKEN|ACCESS_TOKEN|API_KEY|PRIVATE_KEY)\s*[:=]\s*)(["\']?)([^#\n\r]+)(["\']?)'),
]


def run(cmd: List[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def list_staged_files() -> List[str]:
    try:
        out = run([GIT, "diff", "--cached", "--name-only", "--diff-filter=ACM"])
        return [line for line in out.splitlines() if line]
    except subprocess.CalledProcessError:
        return []


def list_worktree_files() -> List[str]:
    """Return modified and untracked files in the working tree.

    This is used when SCAN_WORKTREE=1 is set. We include modified tracked files
    and untracked files (excluding ignored files) so users can run the script
    manually to clean secrets before staging.
    """
    files = []
    try:
        # modified tracked files
        out = run([GIT, "ls-files", "-m"])
        files.extend([line for line in out.splitlines() if line])
    except subprocess.CalledProcessError:
        pass
    try:
        # untracked files (not ignored)
        out = run([GIT, "ls-files", "--others", "--exclude-standard"])
        files.extend([line for line in out.splitlines() if line])
    except subprocess.CalledProcessError:
        pass
    # dedupe while preserving order
    seen = set()
    res = []
    for f in files:
        if f not in seen:
            seen.add(f)
            res.append(f)
    return res


def is_binary(content: bytes) -> bool:
    # Heuristic: if it contains a NUL byte or a long sequence of non-text bytes
    if b"\x00" in content:
        return True
    # Try decode as utf-8
    try:
        content.decode("utf-8")
        return False
    except UnicodeDecodeError:
        return True


def redact_content(text: str) -> tuple[str, int]:
    total = 0

    def make_repl(prefix_group_index: int = 1):
        def repl(m: re.Match) -> str:
            nonlocal total
            # rebuild: prefix + "<REDACTED>" (keep surrounding quotes if present)
            groups = m.groups()
            # groups: (prefix, quote1, secret, quote2) or similar
            # We'll preserve the quote characters when present.
            prefix = m.group(1)
            # find the quote char if any at group 2; if it's a quote, keep it
            quote = ""
            try:
                quote = m.group(2) if m.group(2) is not None else ""
            except IndexError:
                quote = ""
            total += 1
            return f"{prefix}{quote}<REDACTED>{quote}"

        return repl

    new_text = text
    for pat in PATTERNS:
        new_text, count = pat.subn(make_repl(), new_text)
        total += 0  # count accounted in repl
    return new_text, total


def main() -> int:
    # By default we operate on staged files. Set SCAN_WORKTREE=1 to instead
    # scan modified/untracked files in the working tree (useful if you forgot
    # to stage files and want to clean them before committing).
    if os.getenv("SCAN_WORKTREE", "0") == "1":
        files = list_worktree_files()
    else:
        files = list_staged_files()
    if not files:
        # nothing staged
        return 0

    redacted_files = []

    for path in files:
        # Only operate on files that exist in the working tree (skip deleted files)
        if not os.path.exists(path):
            continue
        # Get the staged content; fallback to working tree if show fails
        try:
            blob = subprocess.check_output([GIT, "show", f":{path}"], text=False)
        except subprocess.CalledProcessError:
            # file might be new and not yet in index; read from disk
            with open(path, "rb") as f:
                blob = f.read()

        if is_binary(blob):
            continue

        try:
            text = blob.decode("utf-8")
        except UnicodeDecodeError:
            # Skip files we can't decode
            continue

        new_text, total = redact_content(text)
        if total > 0 and new_text != text:
            # Write redacted content to working tree
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_text)
            # Stage updated file
            try:
                subprocess.check_call([GIT, "add", path])
            except subprocess.CalledProcessError:
                print(f"Failed to git add {path}")
                return 1
            redacted_files.append((path, total))

    if redacted_files:
        print("Pre-commit redaction applied to staged files:")
        for p, c in redacted_files:
            print(f" - {p}: {c} secrets redacted")

        # Optionally block the commit if user wants
        if os.getenv("BLOCK_ON_SECRET", "0") == "1":
            print("Commits blocked because secrets were found (BLOCK_ON_SECRET=1). Fix and commit again.")
            return 1
        else:
            print("Files were redacted and re-staged. Please review changes and re-run commit if necessary.")
            # Allow commit to continue with redacted files
            return 0

    # no secrets found
    return 0


if __name__ == "__main__":
    code = main()
    sys.exit(code)
