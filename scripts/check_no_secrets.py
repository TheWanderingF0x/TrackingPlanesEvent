#!/usr/bin/env python3
"""
Fail if likely secrets or forbidden files would be published.

Run before the first push / in CI:
  python scripts/check_no_secrets.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Paths that must never appear in a public tree (relative to repo root)
FORBIDDEN_NAMES = {
    ".env",
    "credentials.json",
    "settings.conf",
    "secrets.toml",
}

FORBIDDEN_SUFFIXES = (".pem", ".key", ".p12", ".pfx")

# Placeholder-only patterns allowed in .env.example
PLACEHOLDER_SECRET = re.compile(
    r"(?i)(your_|changeme|example|xxx|todo|placeholder|<.*>|_here$)"
)

# Lines that look like assigned OpenSky secrets with non-placeholder values
ASSIGNED_SECRET = re.compile(
    r"(?i)^\s*(?:OPENSKY_CLIENT_(?:ID|SECRET)|GOOGLE_MAPS_API_KEY)\s*=\s*(?P<value>.+?)\s*$"
)

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "node_modules",
    ".idea",
    ".vscode",
    "data",
    "spark-warehouse",
    "metastore_db",
}


def _is_skipped(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def check_forbidden_files() -> list[str]:
    errors: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or _is_skipped(path.relative_to(ROOT)):
            continue
        rel = path.relative_to(ROOT).as_posix()
        name = path.name
        if name in FORBIDDEN_NAMES and name != ".env.example":
            # .env at repo root is local-only; flag if present so authors double-check gitignore
            if name == ".env":
                # Existence is OK locally; only error if somehow not ignored when using git
                continue
            errors.append(f"Forbidden file present: {rel}")
        if name.endswith(FORBIDDEN_SUFFIXES):
            errors.append(f"Key/cert file present: {rel}")
    return errors


def check_tracked_env_via_git() -> list[str]:
    errors: list[str] = []
    git_dir = ROOT / ".git"
    if not git_dir.exists():
        return errors
    try:
        import subprocess

        result = subprocess.run(
            ["git", "ls-files"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return errors
        tracked = result.stdout.splitlines()
        for rel in tracked:
            base = Path(rel).name
            if base == ".env" or rel.endswith("/.env"):
                errors.append(f"SECRET LEAK RISK: git is tracking {rel}")
            if base in FORBIDDEN_NAMES and base != ".env.example":
                errors.append(f"SECRET LEAK RISK: git is tracking {rel}")
            if base.endswith(FORBIDDEN_SUFFIXES):
                errors.append(f"SECRET LEAK RISK: git is tracking {rel}")
            if rel == ".env.example" or rel.endswith(".env.example"):
                errors.extend(_check_env_example_values(ROOT / rel))
    except OSError:
        pass
    return errors


def _check_env_example_values(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return errors
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        m = ASSIGNED_SECRET.match(line)
        if not m:
            continue
        value = m.group("value").strip().strip('"').strip("'")
        if not value:
            continue
        if not PLACEHOLDER_SECRET.search(value):
            errors.append(
                f"{path.relative_to(ROOT).as_posix()}:{i} looks like a real secret value "
                f"(use a clear placeholder like your_client_id_here)"
            )
    return errors


def check_source_hardcoded_secrets() -> list[str]:
    """Scan project source (not .venv) for suspicious assignments."""
    errors: list[str] = []
    pattern = re.compile(
        r"""(?i)(OPENSKY_CLIENT_SECRET|client_secret)\s*=\s*['\"]([A-Za-z0-9_\-]{16,})['\"]"""
    )
    for path in list(ROOT.joinpath("src").rglob("*.py")) + list(
        ROOT.joinpath("scripts").rglob("*.py")
    ):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line) and "os.getenv" not in line and "environ" not in line:
                errors.append(
                    f"{path.relative_to(ROOT).as_posix()}:{i} possible hardcoded secret"
                )
    # Always validate .env.example placeholders
    errors.extend(_check_env_example_values(ROOT / ".env.example"))
    return errors


def main() -> int:
    errors: list[str] = []
    errors.extend(check_forbidden_files())
    errors.extend(check_tracked_env_via_git())
    errors.extend(check_source_hardcoded_secrets())

    if errors:
        print("Secret / publish safety check FAILED:\n", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        print(
            "\nFix these before pushing. Rotate any credential that may have been exposed.",
            file=sys.stderr,
        )
        return 1

    print("OK: no obvious secrets found for public GitHub publish.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
