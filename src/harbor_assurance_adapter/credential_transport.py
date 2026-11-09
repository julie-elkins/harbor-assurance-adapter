"""Credential transport rules shared by the Harbor environment adapter.

The design rules are:

1. Provider credentials may cross the host/container boundary only through a
   protected temporary file.
2. Secret values must never be placed in a child-process argument list.
3. Unsupported multiline credentials are rejected instead of being rewritten.
"""

from __future__ import annotations

import shlex
from collections.abc import Mapping

_EXACT_SECRET_ENV_NAMES = frozenset(
    {
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "MSWEA_API_KEY",
    }
)


def is_secret_env_name(name: str) -> bool:
    """Return whether *name* should be transported as a secret."""

    return name in _EXACT_SECRET_ENV_NAMES or name.endswith(("_API_KEY", "_TOKEN", "_SECRET"))


def split_secret_environment(
    environment: Mapping[str, str],
) -> tuple[dict[str, str], dict[str, str]]:
    """Separate secret values from ordinary container environment values."""

    ordinary: dict[str, str] = {}
    secrets: dict[str, str] = {}
    for name, value in environment.items():
        if not is_secret_env_name(name):
            ordinary[name] = value
            continue
        if "\n" in value or "\r" in value:
            raise ValueError(
                f"{name} contains a newline; refusing to transport an ambiguous secret."
            )
        secrets[name] = value
    return ordinary, secrets


def secret_loader_command(
    secret_paths: Mapping[str, str],
    command: str,
) -> str:
    """Prefix *command* with shell exports loaded from secret files."""

    exports = [
        f"export {name}=\"$(cat {shlex.quote(path)})\""
        for name, path in secret_paths.items()
    ]
    if not exports:
        return command
    return "; ".join(exports + [command])
