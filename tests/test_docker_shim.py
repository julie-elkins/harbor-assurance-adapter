from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
import base64
from pathlib import Path


class DockerShimTests(unittest.TestCase):
    def test_provider_keys_are_not_reintroduced_into_finch_exec_args(self) -> None:
        repository = Path(__file__).parents[1]
        shim = repository / "bin" / "docker"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            captured_args = root / "finch-args"
            fake_finch = fake_bin / "finch"
            fake_finch.write_text(
                "#!/bin/sh\n"
                'printf "%s\\n" "$@" > "$FAKE_FINCH_ARGS"\n',
                encoding="utf-8",
            )
            fake_finch.chmod(0o700)

            for environment_flag in ("-e", "--env"):
                for secret_name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
                    with self.subTest(
                        environment_flag=environment_flag,
                        secret_name=secret_name,
                    ):
                        if captured_args.exists():
                            captured_args.unlink()
                        secret = f"synthetic-{secret_name.lower()}"
                        environment = os.environ.copy()
                        environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
                        environment["FAKE_FINCH_ARGS"] = str(captured_args)
                        result = subprocess.run(
                            (
                                str(shim),
                                "compose",
                                "-p",
                                "harbor",
                                "exec",
                                "-T",
                                environment_flag,
                                f"{secret_name}={secret}",
                                "main",
                                "true",
                            ),
                            env=environment,
                            capture_output=True,
                            text=True,
                            check=False,
                        )

                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertTrue(captured_args.exists())
                        self.assertNotIn(
                            secret,
                            captured_args.read_text(encoding="utf-8"),
                        )

    def test_direct_exec_and_run_keep_provider_keys_out_of_finch_args(self) -> None:
        repository = Path(__file__).parents[1]
        shim = repository / "bin" / "docker"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            captured_args = root / "finch-args"
            fake_finch = fake_bin / "finch"
            fake_finch.write_text(
                "#!/bin/sh\n"
                'printf "%s\\n" "$@" > "$FAKE_FINCH_ARGS"\n',
                encoding="utf-8",
            )
            fake_finch.chmod(0o700)
            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
            environment["FAKE_FINCH_ARGS"] = str(captured_args)

            for subcommand in ("exec", "run"):
                with self.subTest(subcommand=subcommand):
                    secret = f"synthetic-{subcommand}-secret"
                    result = subprocess.run(
                        (
                            str(shim),
                            subcommand,
                            "-e",
                            f"OPENAI_API_KEY={secret}",
                            "main",
                            "true",
                        ),
                        env=environment,
                        capture_output=True,
                        text=True,
                        check=False,
                    )

                    self.assertEqual(result.returncode, 0, result.stderr)
                    captured = captured_args.read_text(encoding="utf-8")
                    self.assertNotIn(secret, captured)
                    self.assertIn("--env-file", captured)

    def test_secret_env_file_is_removed_after_finch_returns(self) -> None:
        repository = Path(__file__).parents[1]
        shim = repository / "bin" / "docker"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            captured_env_file = root / "env-file-path"
            fake_finch = fake_bin / "finch"
            fake_finch.write_text(
                "#!/bin/sh\n"
                'for arg in "$@"; do\n'
                '  case "$arg" in\n'
                '    /private/tmp/harbor-finch-secrets.*) printf "%s\\n" "$arg" > "$CAPTURED_ENV_FILE"; cp "$arg" "$COPIED_ENV_FILE" ;;\n'
                '  esac\n'
                "done\n",
                encoding="utf-8",
            )
            fake_finch.chmod(0o700)
            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
            environment["CAPTURED_ENV_FILE"] = str(captured_env_file)
            copied_env_file = root / "copied-env-file"
            environment["COPIED_ENV_FILE"] = str(copied_env_file)

            result = subprocess.run(
                (
                    str(shim),
                    "exec",
                    "-e",
                    "ANTHROPIC_API_KEY=synthetic-cleanup-secret",
                    "main",
                    "true",
                ),
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(captured_env_file.exists())
            self.assertFalse(Path(captured_env_file.read_text(encoding="utf-8").strip()).exists())
            self.assertEqual(
                copied_env_file.read_text(encoding="utf-8"),
                "ANTHROPIC_API_KEY=synthetic-cleanup-secret\n",
            )

    def test_mini_swe_uv_install_gets_bounded_download_retries(self) -> None:
        repository = Path(__file__).parents[1]
        shim = repository / "bin" / "docker"
        secret = "synthetic-test-token"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            captured_args = root / "finch-args"
            fake_finch = fake_bin / "finch"
            fake_finch.write_text(
                "#!/bin/sh\n"
                'printf "%s\\n" "$@" > "$FAKE_FINCH_ARGS"\n',
                encoding="utf-8",
            )
            fake_finch.chmod(0o700)
            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
            environment["FAKE_FINCH_ARGS"] = str(captured_args)
            command = (
                "curl -LsSf https://astral.sh/uv/0.7.13/install.sh | sh && "
                "uv tool install mini-swe-agent && mini-swe-agent --help"
            )

            result = subprocess.run(
                (
                    str(shim),
                    "compose",
                    "-p",
                    "harbor",
                    "exec",
                    "-T",
                    "--env",
                    f"ANTHROPIC_API_KEY={secret}",
                    "main",
                    "sh",
                    "-c",
                    command,
                ),
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            encoded_command = next(
                line
                for line in captured_args.read_text(encoding="utf-8").splitlines()
                if line.startswith("echo ") and line.endswith(" | base64 -d | bash")
            )
            encoded = encoded_command.removeprefix("echo ").removesuffix(
                " | base64 -d | bash"
            )
            rewritten = base64.b64decode(encoded).decode("utf-8")
            self.assertIn(
                "export INSTALLER_DOWNLOAD_URL=https://releases.astral.sh/github/uv/releases/download/0.7.13",
                rewritten,
            )
            self.assertIn("--retry 5 --retry-delay 5 --retry-max-time 180", rewritten)
            self.assertIn(
                "UV_PYTHON_INSTALL_MIRROR=https://releases.astral.sh/github/"
                "python-build-standalone/releases/download "
                "uv tool install --managed-python "
                "--with 'mcp>=2.2,<3' mini-swe-agent",
                rewritten,
            )

    def test_terminal_bench_verifier_uses_uv_release_mirror(self) -> None:
        repository = Path(__file__).parents[1]
        shim = repository / "bin" / "docker"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            captured_args = root / "finch-args"
            fake_finch = fake_bin / "finch"
            fake_finch.write_text(
                "#!/bin/sh\n"
                'printf "%s\\n" "$@" > "$FAKE_FINCH_ARGS"\n',
                encoding="utf-8",
            )
            fake_finch.chmod(0o700)
            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
            environment["FAKE_FINCH_ARGS"] = str(captured_args)

            result = subprocess.run(
                (
                    str(shim),
                    "compose",
                    "-p",
                    "harbor",
                    "exec",
                    "-T",
                    "main",
                    "sh",
                    "-c",
                    "bash /tests/test.sh",
                ),
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            encoded_command = next(
                line
                for line in captured_args.read_text(encoding="utf-8").splitlines()
                if line.startswith("echo ") and line.endswith(" | base64 -d | bash")
            )
            encoded = encoded_command.removeprefix("echo ").removesuffix(
                " | base64 -d | bash"
            )
            rewritten = base64.b64decode(encoded).decode("utf-8")
            self.assertTrue(
                rewritten.startswith(
                    "export INSTALLER_DOWNLOAD_URL=https://releases.astral.sh/"
                    "github/uv/releases/download/0.9.5; "
                )
            )
            self.assertIn("bash /tests/test.sh", rewritten)

    def test_known_apt_setups_use_bullseye_archive_fallback(self) -> None:
        repository = Path(__file__).parents[1]
        shim = repository / "bin" / "docker"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            captured_args = root / "finch-args"
            fake_finch = fake_bin / "finch"
            fake_finch.write_text(
                "#!/bin/sh\n"
                'printf "%s\\n" "$@" > "$FAKE_FINCH_ARGS"\n',
                encoding="utf-8",
            )
            fake_finch.chmod(0o700)
            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
            environment["FAKE_FINCH_ARGS"] = str(captured_args)

            for package_set in ("curl ripgrep", "curl build-essential git"):
                with self.subTest(package_set=package_set):
                    if captured_args.exists():
                        captured_args.unlink()
                    command = (
                        "apt-get update && "
                        f"apt-get install -y {package_set};"
                    )
                    result = subprocess.run(
                        (
                            str(shim),
                            "compose",
                            "-p",
                            "harbor",
                            "exec",
                            "-T",
                            "main",
                            "sh",
                            "-c",
                            command,
                        ),
                        env=environment,
                        capture_output=True,
                        text=True,
                        check=False,
                    )

                    self.assertEqual(result.returncode, 0, result.stderr)
                    encoded_command = next(
                        line
                        for line in captured_args.read_text(
                            encoding="utf-8"
                        ).splitlines()
                        if line.startswith("echo ")
                        and line.endswith(" | base64 -d | bash")
                    )
                    encoded = encoded_command.removeprefix("echo ").removesuffix(
                        " | base64 -d | bash"
                    )
                    rewritten = base64.b64decode(encoded).decode("utf-8")
                    self.assertIn(
                        "grep -Rqs bullseye-security /etc/apt/sources.list",
                        rewritten,
                    )
                    self.assertIn(
                        "http://archive.debian.org/debian-security",
                        rewritten,
                    )
                    self.assertIn(
                        "Acquire::Check-Valid-Until=false",
                        rewritten,
                    )
                    self.assertIn(
                        f'HARBOR_APT_PACKAGES="{package_set}"',
                        rewritten,
                    )
                    self.assertIn(
                        "install -y $HARBOR_APT_PACKAGES",
                        rewritten,
                    )
                    self.assertIn(
                        "else\n        apt-get -o Acquire::Retries=5 update",
                        rewritten,
                    )
                    self.assertIn(
                        "apt-get -o Acquire::Retries=5 update",
                        rewritten,
                    )

            result = subprocess.run(
                (
                    str(shim),
                    "compose",
                    "-p",
                    "harbor",
                    "exec",
                    "-T",
                    "main",
                    "sh",
                    "-c",
                    "apt-get update && apt-get install -y curl git;",
                ),
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            encoded_command = next(
                line
                for line in captured_args.read_text(encoding="utf-8").splitlines()
                if line.startswith("echo ") and line.endswith(" | base64 -d | bash")
            )
            encoded = encoded_command.removeprefix("echo ").removesuffix(
                " | base64 -d | bash"
            )
            unchanged = base64.b64decode(encoded).decode("utf-8")
            self.assertNotIn("archive.debian.org", unchanged)
            self.assertEqual(
                unchanged,
                "apt-get update && apt-get install -y curl git;",
            )


if __name__ == "__main__":
    unittest.main()
