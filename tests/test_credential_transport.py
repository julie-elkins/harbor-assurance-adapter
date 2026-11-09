from __future__ import annotations

import unittest

from harbor_assurance_adapter.credential_transport import (
    secret_loader_command,
    split_secret_environment,
)


class CredentialTransportTests(unittest.TestCase):
    def test_secret_values_are_separated_from_ordinary_environment(self) -> None:
        ordinary, secrets = split_secret_environment(
            {
                "MSWEA_CONFIGURED": "true",
                "ANTHROPIC_API_KEY": "synthetic-anthropic-key",
            }
        )

        self.assertEqual(ordinary, {"MSWEA_CONFIGURED": "true"})
        self.assertEqual(secrets, {"ANTHROPIC_API_KEY": "synthetic-anthropic-key"})

    def test_loader_command_contains_path_and_name_but_not_secret_value(self) -> None:
        secret = "synthetic-secret-value"

        command = secret_loader_command(
            {"ANTHROPIC_API_KEY": "/tmp/credential-file"},
            "mini-swe-agent --help",
        )

        self.assertIn("ANTHROPIC_API_KEY", command)
        self.assertIn("/tmp/credential-file", command)
        self.assertNotIn(secret, command)

    def test_multiline_secret_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "contains a newline"):
            split_secret_environment(
                {"OPENAI_API_KEY": "synthetic-secret\ninjected"}
            )

    def test_provider_token_names_are_also_secret_transport(self) -> None:
        ordinary, secrets = split_secret_environment(
            {
                "GITHUB_TOKEN": "synthetic-token",
                "SAFE_SETTING": "ordinary",
            }
        )

        self.assertEqual(ordinary, {"SAFE_SETTING": "ordinary"})
        self.assertEqual(secrets, {"GITHUB_TOKEN": "synthetic-token"})


if __name__ == "__main__":
    unittest.main()
