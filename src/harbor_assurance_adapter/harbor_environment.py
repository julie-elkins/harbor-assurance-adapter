"""Harbor Docker environment with argv-safe provider credential transport.

The design rules are:

1. Inherited and per-command provider credentials are removed before Harbor
   constructs Docker Compose arguments.
2. Each credential is uploaded through a path-only Docker Compose copy and is
   loaded inside the container by name.
3. Secret files are removed before the environment stops; the inherited
   Finch shim remains a second, downstream protection.
"""

from __future__ import annotations

import asyncio
import os
import shlex
import tempfile
import uuid
from pathlib import Path

from harbor.environments.docker.docker import DockerEnvironment

from .credential_transport import (
    secret_loader_command,
    split_secret_environment,
)


class CredentialSafeDockerEnvironment(DockerEnvironment):
    """Docker environment that keeps provider values out of Docker argv."""

    _secret_target_prefix = "/tmp/.harbor-assurance-credential-"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._credential_targets: dict[str, str] = {}

    async def _install_secret_file(self, name: str, value: str) -> str:
        target = self._credential_targets.get(name)
        if target is None:
            target = f"{self._secret_target_prefix}{uuid.uuid4().hex}"
            self._credential_targets[name] = target

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix="harbor-assurance-credential-",
            delete=True,
        ) as secret_file:
            os.chmod(secret_file.name, 0o600)
            secret_file.write(value)
            secret_file.flush()
            await super().upload_file(secret_file.name, target)

        # Docker Compose copies the file with host-oriented ownership. Give
        # ownership to Harbor's resolved agent user and keep the file private
        # inside the container trust boundary.
        owner = self._resolve_user(None) or "root"
        await super().exec(
            f"chown {shlex.quote(str(owner))} {shlex.quote(target)} && "
            f"chmod 600 {shlex.quote(target)}",
            user="root",
        )
        return target

    async def exec(
        self,
        command: str,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_sec: int | None = None,
        user: str | int | None = None,
    ):
        merged_environment = self._merge_env(env) or {}
        ordinary, secrets = split_secret_environment(merged_environment)
        if not secrets:
            return await super().exec(
                command,
                cwd=cwd,
                env=ordinary or None,
                timeout_sec=timeout_sec,
                user=user,
            )

        if any(
            name in self._persistent_env
            for name in secrets
        ):
            raise RuntimeError(
                "Provider credentials must be supplied per command so the "
                "argv-safe transport can remove their values before Docker."
            )

        secret_paths = {
            name: await self._install_secret_file(name, value)
            for name, value in secrets.items()
        }
        safe_command = secret_loader_command(secret_paths, command)
        return await super().exec(
            safe_command,
            cwd=cwd,
            env=ordinary or None,
            timeout_sec=timeout_sec,
            user=user,
        )

    async def stop(self, delete: bool):
        base_exec = super().exec
        cleanup_tasks = [
            base_exec(f"rm -f {shlex.quote(target)}", user="root")
            for target in self._credential_targets.values()
        ]
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        await super().stop(delete)
