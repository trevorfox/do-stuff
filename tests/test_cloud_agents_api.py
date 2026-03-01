"""Unit tests for scripts/cloud_agents_api.py."""

from __future__ import annotations

import argparse
import base64
import unittest

from scripts import cloud_agents_api as api


def _launch_args(**overrides: object) -> argparse.Namespace:
    defaults = {
        "repository": "https://github.com/example-org/example-repo",
        "infer_repository": False,
        "remote_name": "origin",
        "ref": "main",
        "pr_url": None,
        "model": None,
        "auto_create_pr": False,
        "open_as_cursor_github_app": False,
        "skip_reviewer_request": False,
        "branch_name": None,
        "auto_branch": None,
        "webhook_url": None,
        "webhook_secret": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class TestRepositoryUrlSanitization(unittest.TestCase):
    def test_sanitizes_https_url_with_credentials(self) -> None:
        raw = "https://x-access-token:abc123@github.com/trevorfox/do-stuff.git"
        sanitized = api._sanitize_repository_url(raw)  # pylint: disable=protected-access
        self.assertEqual(sanitized, "https://github.com/trevorfox/do-stuff")

    def test_sanitizes_ssh_url(self) -> None:
        raw = "git@github.com:trevorfox/do-stuff.git"
        sanitized = api._sanitize_repository_url(raw)  # pylint: disable=protected-access
        self.assertEqual(sanitized, "https://github.com/trevorfox/do-stuff")


class TestAuthHeaders(unittest.TestCase):
    def test_basic_auth_header(self) -> None:
        expected = "Basic " + base64.b64encode(b"my-key:").decode("ascii")
        actual = api._encode_auth_header("my-key", "basic")  # pylint: disable=protected-access
        self.assertEqual(actual, expected)

    def test_bearer_auth_header(self) -> None:
        actual = api._encode_auth_header("my-key", "bearer")  # pylint: disable=protected-access
        self.assertEqual(actual, "Bearer my-key")


class TestLaunchPayload(unittest.TestCase):
    def test_build_payload_for_repository_source(self) -> None:
        args = _launch_args(
            model="claude-4-sonnet-thinking",
            branch_name="cursor-api/test-branch",
            auto_create_pr=True,
        )
        payload = api._build_launch_payload(  # pylint: disable=protected-access
            args,
            "hello from test",
        )

        self.assertEqual(payload["prompt"]["text"], "hello from test")
        self.assertEqual(
            payload["source"],
            {
                "repository": "https://github.com/example-org/example-repo",
                "ref": "main",
            },
        )
        self.assertEqual(payload["target"]["branchName"], "cursor-api/test-branch")
        self.assertTrue(payload["target"]["autoCreatePr"])

    def test_build_payload_for_pr_source(self) -> None:
        args = _launch_args(
            pr_url="https://github.com/example-org/example-repo/pull/123",
            repository=None,
            ref=None,
            auto_branch="false",
        )
        payload = api._build_launch_payload(  # pylint: disable=protected-access
            args,
            "follow the PR",
        )

        self.assertEqual(
            payload["source"],
            {"prUrl": "https://github.com/example-org/example-repo/pull/123"},
        )
        self.assertFalse(payload["target"]["autoBranch"])


class TestScenarios(unittest.TestCase):
    def test_scenario_prompts_exist(self) -> None:
        for scenario in api.SCENARIOS.values():
            self.assertTrue(scenario.prompt_path.exists(), msg=scenario.name)


if __name__ == "__main__":
    unittest.main()
