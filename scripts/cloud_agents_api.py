#!/usr/bin/env python3
"""CLI for Cursor Cloud Agents API and capability test scenarios."""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any
from urllib import error, parse, request


DEFAULT_BASE_URL = "https://api.cursor.com"
DEFAULT_AUTH_MODE = "basic"
TERMINAL_STATUSES = {"FINISHED", "ERROR", "EXPIRED"}

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent


@dataclass(frozen=True)
class Scenario:
    name: str
    prompt_path: Path
    expected_markers: tuple[str, ...]
    description: str


SCENARIOS: dict[str, Scenario] = {
    "subagent-smoke": Scenario(
        name="subagent-smoke",
        prompt_path=REPO_ROOT / "scenarios" / "subagent-smoke.md",
        expected_markers=("SUBAGENT_USED: orchestration-tester",),
        description="Smoke test explicit subagent invocation.",
    ),
    "subagent-skill-chain": Scenario(
        name="subagent-skill-chain",
        prompt_path=REPO_ROOT / "scenarios" / "subagent-skill-chain.md",
        expected_markers=(
            "SUBAGENT_USED: orchestration-tester",
            "SKILL_USED: capability-checklist",
            "SKILL_USED: capability-report",
        ),
        description="Test subagent invocation and subagent-driven skill chaining.",
    ),
}


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class ApiError(RuntimeError):
    """Error returned by the Cloud Agents API."""

    def __init__(
        self,
        status_code: int,
        message: str,
        payload: dict[str, Any] | list[Any] | str | None = None,
    ) -> None:
        self.status_code = status_code
        self.payload = payload
        super().__init__(message)


def _encode_auth_header(api_key: str, auth_mode: str) -> str:
    if auth_mode == "basic":
        token = base64.b64encode(f"{api_key}:".encode("utf-8")).decode("ascii")
        return f"Basic {token}"
    if auth_mode == "bearer":
        return f"Bearer {api_key}"
    raise ValueError(f"Unsupported auth mode: {auth_mode}")


def _load_json(data: bytes) -> Any:
    if not data:
        return {}
    return json.loads(data.decode("utf-8"))


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _read_text_file(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return path.read_text(encoding="utf-8")


def _bool_from_cli(raw: str) -> bool:
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"Expected boolean-like value, got: {raw}")


def _sanitize_repository_url(remote_url: str) -> str:
    remote_url = remote_url.strip()
    if not remote_url:
        raise ValueError("Repository URL cannot be empty")

    ssh_match = re.match(r"^git@github\.com:(?P<repo>[\w.\-]+/[\w.\-]+?)(?:\.git)?$", remote_url)
    if ssh_match:
        return f"https://github.com/{ssh_match.group('repo')}"

    if remote_url.startswith("ssh://"):
        parsed = parse.urlparse(remote_url)
        if parsed.hostname and parsed.path:
            repo_path = parsed.path.lstrip("/")
            if repo_path.endswith(".git"):
                repo_path = repo_path[:-4]
            return f"https://{parsed.hostname}/{repo_path}"

    parsed = parse.urlparse(remote_url)
    if parsed.scheme in {"http", "https"} and parsed.hostname and parsed.path:
        repo_path = parsed.path.lstrip("/")
        if repo_path.endswith(".git"):
            repo_path = repo_path[:-4]
        return f"https://{parsed.hostname}/{repo_path}"

    raise ValueError(f"Unsupported remote URL format: {remote_url}")


def _run_git_command(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def infer_repository_from_git(remote: str = "origin") -> str:
    return _sanitize_repository_url(_run_git_command(["remote", "get-url", remote]))


def infer_ref_from_git(default_ref: str = "main") -> str:
    try:
        ref = _run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])
        if ref and ref != "HEAD":
            return ref
    except subprocess.CalledProcessError:
        pass
    return default_ref


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


class CursorCloudAgentsClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        auth_mode: str = DEFAULT_AUTH_MODE,
        timeout_seconds: int = 60,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.auth_header = _encode_auth_header(api_key, auth_mode)

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        if query:
            filtered = {k: v for k, v in query.items() if v is not None}
            if filtered:
                url = f"{url}?{parse.urlencode(filtered)}"

        data_bytes = None
        headers = {
            "Accept": "application/json",
            "Authorization": self.auth_header,
            "User-Agent": "cursor-cloud-agents-api-cli/1.0",
        }

        if payload is not None:
            data_bytes = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = request.Request(
            url=url,
            data=data_bytes,
            headers=headers,
            method=method.upper(),
        )

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                return _load_json(resp.read())
        except error.HTTPError as exc:
            body = exc.read()
            parsed_body: Any
            try:
                parsed_body = _load_json(body)
            except Exception:
                parsed_body = body.decode("utf-8", errors="replace")

            if isinstance(parsed_body, dict):
                message = (
                    parsed_body.get("error", {}).get("message")
                    if isinstance(parsed_body.get("error"), dict)
                    else parsed_body.get("message")
                ) or f"HTTP {exc.code}"
            else:
                message = f"HTTP {exc.code}: {parsed_body}"
            raise ApiError(exc.code, message, parsed_body) from exc
        except error.URLError as exc:
            raise RuntimeError(f"Network error while contacting {url}: {exc}") from exc

    def create_agent(self, payload: dict[str, Any]) -> Any:
        return self._request("POST", "/v0/agents", payload=payload)

    def list_agents(
        self,
        *,
        limit: int | None = None,
        cursor: str | None = None,
        pr_url: str | None = None,
    ) -> Any:
        return self._request(
            "GET",
            "/v0/agents",
            query={"limit": limit, "cursor": cursor, "prUrl": pr_url},
        )

    def get_agent(self, agent_id: str) -> Any:
        return self._request("GET", f"/v0/agents/{agent_id}")

    def delete_agent(self, agent_id: str) -> Any:
        return self._request("DELETE", f"/v0/agents/{agent_id}")

    def add_followup(self, agent_id: str, prompt_text: str) -> Any:
        return self._request(
            "POST",
            f"/v0/agents/{agent_id}/followup",
            payload={"prompt": {"text": prompt_text}},
        )

    def stop_agent(self, agent_id: str) -> Any:
        return self._request("POST", f"/v0/agents/{agent_id}/stop")

    def get_conversation(self, agent_id: str) -> Any:
        return self._request("GET", f"/v0/agents/{agent_id}/conversation")

    def get_me(self) -> Any:
        return self._request("GET", "/v0/me")

    def list_models(self) -> Any:
        return self._request("GET", "/v0/models")

    def list_repositories(self) -> Any:
        return self._request("GET", "/v0/repositories")


def _build_launch_payload(args: argparse.Namespace, prompt_text: str) -> dict[str, Any]:
    source: dict[str, Any]
    if args.pr_url:
        source = {"prUrl": args.pr_url}
    else:
        repository = args.repository
        if not repository and args.infer_repository:
            repository = infer_repository_from_git(args.remote_name)
        if not repository:
            raise ValueError(
                "Repository is required unless --pr-url is provided. "
                "Set --repository or use --infer-repository."
            )
        repository = _sanitize_repository_url(repository)
        source = {"repository": repository, "ref": args.ref or infer_ref_from_git()}

    payload: dict[str, Any] = {
        "prompt": {"text": prompt_text},
        "source": source,
    }

    if args.model:
        payload["model"] = args.model

    target: dict[str, Any] = {}
    if args.auto_create_pr:
        target["autoCreatePr"] = True
    if args.open_as_cursor_github_app:
        target["openAsCursorGithubApp"] = True
    if args.skip_reviewer_request:
        target["skipReviewerRequest"] = True
    if args.branch_name:
        target["branchName"] = args.branch_name
    if args.auto_branch is not None:
        target["autoBranch"] = _bool_from_cli(args.auto_branch)
    if target:
        payload["target"] = target

    if args.webhook_url:
        webhook: dict[str, Any] = {"url": args.webhook_url}
        if args.webhook_secret:
            webhook["secret"] = args.webhook_secret
        payload["webhook"] = webhook

    return payload


def _wait_for_terminal(
    client: CursorCloudAgentsClient,
    agent_id: str,
    *,
    poll_interval: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    start = time.time()
    last_status: str | None = None
    while True:
        response = client.get_agent(agent_id)
        status = response.get("status")
        if status != last_status:
            print(f"[wait] status={status}")
            last_status = status
        if status in TERMINAL_STATUSES:
            return response
        if time.time() - start > timeout_seconds:
            raise TimeoutError(
                f"Timed out waiting for agent {agent_id} after {timeout_seconds}s"
            )
        time.sleep(poll_interval)


def _messages_to_text(messages: list[dict[str, Any]], message_type: str) -> str:
    lines: list[str] = []
    for message in messages:
        if message.get("type") == message_type:
            lines.append(str(message.get("text", "")))
    return "\n".join(lines)


def _resolve_prompt_from_args(args: argparse.Namespace) -> str:
    if args.prompt and args.prompt_file:
        raise ValueError("Use either --prompt or --prompt-file, not both.")
    if args.prompt:
        return args.prompt
    if args.prompt_file:
        return _read_text_file(Path(args.prompt_file))
    raise ValueError("A prompt is required. Use --prompt or --prompt-file.")


def _get_client(args: argparse.Namespace) -> CursorCloudAgentsClient:
    api_key = args.api_key or os.getenv("CURSOR_API_KEY")
    if not api_key:
        raise ValueError(
            "Missing API key. Set --api-key or the CURSOR_API_KEY environment variable."
        )
    return CursorCloudAgentsClient(
        api_key,
        base_url=args.base_url,
        auth_mode=args.auth_mode,
        timeout_seconds=args.request_timeout_seconds,
    )


def _cmd_launch(args: argparse.Namespace) -> int:
    prompt_text = _resolve_prompt_from_args(args)
    payload = _build_launch_payload(args, prompt_text)
    if args.print_payload_only:
        _print_json(payload)
        return 0
    client = _get_client(args)
    response = client.create_agent(payload)
    _print_json(response)
    return 0


def _cmd_wait(args: argparse.Namespace) -> int:
    client = _get_client(args)
    terminal = _wait_for_terminal(
        client,
        args.agent_id,
        poll_interval=args.poll_interval_seconds,
        timeout_seconds=args.wait_timeout_seconds,
    )
    _print_json(terminal)
    return 0


def _cmd_followup(args: argparse.Namespace) -> int:
    client = _get_client(args)
    prompt_text = _resolve_prompt_from_args(args)
    response = client.add_followup(args.agent_id, prompt_text)
    _print_json(response)
    return 0


def _cmd_run_scenario(args: argparse.Namespace) -> int:
    scenario = SCENARIOS[args.scenario]
    client = _get_client(args)

    prompt_text = _read_text_file(scenario.prompt_path)
    branch_name = args.branch_name or f"cursor-api/{scenario.name}-{_timestamp_slug()}"

    launch_ns = argparse.Namespace(
        repository=args.repository,
        infer_repository=args.infer_repository,
        remote_name=args.remote_name,
        ref=args.ref,
        pr_url=None,
        model=args.model,
        auto_create_pr=args.auto_create_pr,
        open_as_cursor_github_app=args.open_as_cursor_github_app,
        skip_reviewer_request=args.skip_reviewer_request,
        branch_name=branch_name,
        auto_branch=None,
        webhook_url=None,
        webhook_secret=None,
    )

    payload = _build_launch_payload(launch_ns, prompt_text)
    launch_response = client.create_agent(payload)
    agent_id = launch_response.get("id")
    if not agent_id:
        raise RuntimeError(f"Agent launch response did not include id: {launch_response}")

    print(f"[scenario] launched {scenario.name}: {agent_id}")
    print(f"[scenario] web url: {launch_response.get('target', {}).get('url', 'n/a')}")
    _print_json({"launch": launch_response})

    if args.no_wait:
        return 0

    terminal = _wait_for_terminal(
        client,
        agent_id,
        poll_interval=args.poll_interval_seconds,
        timeout_seconds=args.wait_timeout_seconds,
    )
    conversation = client.get_conversation(agent_id)
    messages = conversation.get("messages", []) if isinstance(conversation, dict) else []

    assistant_text = _messages_to_text(messages, "assistant_message")
    missing_markers = [m for m in scenario.expected_markers if m not in assistant_text]

    if args.save_conversation:
        save_path = Path(args.save_conversation)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(json.dumps(conversation, indent=2, sort_keys=True), encoding="utf-8")
        print(f"[scenario] conversation saved: {save_path}")

    summary = {
        "scenario": scenario.name,
        "description": scenario.description,
        "agentId": agent_id,
        "status": terminal.get("status"),
        "targetUrl": terminal.get("target", {}).get("url"),
        "branchName": terminal.get("target", {}).get("branchName"),
        "missingMarkers": missing_markers,
    }
    _print_json({"terminal": terminal, "summary": summary})

    if terminal.get("status") != "FINISHED":
        return 2
    if missing_markers:
        return 3
    return 0


def _add_global_auth_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--api-key",
        default=os.getenv("CURSOR_API_KEY"),
        help="Cursor API key. Defaults to CURSOR_API_KEY.",
    )
    parser.add_argument(
        "--auth-mode",
        choices=["basic", "bearer"],
        default=os.getenv("CURSOR_API_AUTH_MODE", DEFAULT_AUTH_MODE),
        help="Auth mode. Docs currently show Basic auth; bearer is also supported by OpenAPI spec.",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("CURSOR_API_BASE_URL", DEFAULT_BASE_URL),
        help="Cursor API base URL.",
    )
    parser.add_argument(
        "--request-timeout-seconds",
        type=int,
        default=_int_env("CURSOR_API_REQUEST_TIMEOUT_SECONDS", 60),
        help="HTTP request timeout in seconds. Defaults to CURSOR_API_REQUEST_TIMEOUT_SECONDS or 60.",
    )


def _add_launch_payload_args(parser: argparse.ArgumentParser) -> None:
    prompt_group = parser.add_mutually_exclusive_group(required=False)
    prompt_group.add_argument("--prompt", help="Prompt text to send.")
    prompt_group.add_argument("--prompt-file", help="Path to a file containing prompt text.")

    source_group = parser.add_argument_group("source")
    source_group.add_argument(
        "--repository",
        default=os.getenv("CURSOR_REPOSITORY"),
        help="GitHub repository URL. Defaults to CURSOR_REPOSITORY when set.",
    )
    source_group.add_argument(
        "--infer-repository",
        action="store_true",
        help="Infer repository URL from git remote.",
    )
    source_group.add_argument(
        "--remote-name",
        default=os.getenv("CURSOR_REMOTE_NAME", "origin"),
        help="Git remote name used when --infer-repository is set. Defaults to CURSOR_REMOTE_NAME or origin.",
    )
    source_group.add_argument(
        "--ref",
        default=os.getenv("CURSOR_SOURCE_REF"),
        help="Source branch or tag. Defaults to CURSOR_SOURCE_REF or current git branch.",
    )
    source_group.add_argument("--pr-url", help="GitHub pull request URL.")

    target_group = parser.add_argument_group("target")
    target_group.add_argument("--branch-name", help="Custom target branch name.")
    target_group.add_argument(
        "--auto-create-pr",
        action="store_true",
        help="Set target.autoCreatePr=true.",
    )
    target_group.add_argument(
        "--open-as-cursor-github-app",
        action="store_true",
        help="Set target.openAsCursorGithubApp=true (only relevant when auto-creating PRs).",
    )
    target_group.add_argument(
        "--skip-reviewer-request",
        action="store_true",
        help="Set target.skipReviewerRequest=true (only relevant when auto-creating PRs).",
    )
    target_group.add_argument(
        "--auto-branch",
        help="Boolean-like value for target.autoBranch (used when source.prUrl is set).",
    )

    parser.add_argument(
        "--model",
        default=os.getenv("CURSOR_MODEL"),
        help="Model name, e.g. claude-4-sonnet-thinking. Defaults to CURSOR_MODEL when set.",
    )
    parser.add_argument("--webhook-url", help="Webhook URL.")
    parser.add_argument("--webhook-secret", help="Webhook secret.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Cursor Cloud Agents API CLI with scenario runner.",
    )
    _add_global_auth_args(parser)

    subparsers = parser.add_subparsers(dest="command", required=True)

    launch_parser = subparsers.add_parser("launch", help="Launch a cloud agent.")
    _add_launch_payload_args(launch_parser)
    launch_parser.add_argument(
        "--print-payload-only",
        action="store_true",
        help="Print the launch payload without calling the API.",
    )
    launch_parser.set_defaults(func=_cmd_launch)

    list_parser = subparsers.add_parser("list-agents", help="List cloud agents.")
    list_parser.add_argument("--limit", type=int, default=20)
    list_parser.add_argument("--cursor")
    list_parser.add_argument("--pr-url")
    list_parser.set_defaults(
        func=lambda args: (_print_json(_get_client(args).list_agents(
            limit=args.limit,
            cursor=args.cursor,
            pr_url=args.pr_url,
        )) or 0)
    )

    status_parser = subparsers.add_parser("status", help="Get cloud agent status.")
    status_parser.add_argument("agent_id")
    status_parser.set_defaults(
        func=lambda args: (_print_json(_get_client(args).get_agent(args.agent_id)) or 0)
    )

    wait_parser = subparsers.add_parser("wait", help="Poll until an agent reaches terminal state.")
    wait_parser.add_argument("agent_id")
    wait_parser.add_argument("--poll-interval-seconds", type=int, default=15)
    wait_parser.add_argument("--wait-timeout-seconds", type=int, default=1800)
    wait_parser.set_defaults(func=_cmd_wait)

    conversation_parser = subparsers.add_parser(
        "conversation",
        help="Fetch conversation history for an agent.",
    )
    conversation_parser.add_argument("agent_id")
    conversation_parser.set_defaults(
        func=lambda args: (
            _print_json(_get_client(args).get_conversation(args.agent_id)) or 0
        )
    )

    followup_parser = subparsers.add_parser("followup", help="Add followup instruction.")
    followup_parser.add_argument("agent_id")
    prompt_group = followup_parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt")
    prompt_group.add_argument("--prompt-file")
    followup_parser.set_defaults(func=_cmd_followup)

    stop_parser = subparsers.add_parser("stop", help="Stop a running cloud agent.")
    stop_parser.add_argument("agent_id")
    stop_parser.set_defaults(
        func=lambda args: (_print_json(_get_client(args).stop_agent(args.agent_id)) or 0)
    )

    delete_parser = subparsers.add_parser("delete", help="Delete a cloud agent.")
    delete_parser.add_argument("agent_id")
    delete_parser.set_defaults(
        func=lambda args: (_print_json(_get_client(args).delete_agent(args.agent_id)) or 0)
    )

    me_parser = subparsers.add_parser("me", help="Show API key metadata.")
    me_parser.set_defaults(func=lambda args: (_print_json(_get_client(args).get_me()) or 0))

    models_parser = subparsers.add_parser("models", help="List available models.")
    models_parser.set_defaults(
        func=lambda args: (_print_json(_get_client(args).list_models()) or 0)
    )

    repos_parser = subparsers.add_parser(
        "repositories",
        help="List repositories available to authenticated account.",
    )
    repos_parser.set_defaults(
        func=lambda args: (_print_json(_get_client(args).list_repositories()) or 0)
    )

    scenario_parser = subparsers.add_parser(
        "run-scenario",
        help="Launch and validate one of the predefined capability scenarios.",
    )
    scenario_parser.add_argument("scenario", choices=sorted(SCENARIOS.keys()))
    scenario_parser.add_argument(
        "--repository",
        default=os.getenv("CURSOR_REPOSITORY"),
        help="GitHub repository URL. Defaults to CURSOR_REPOSITORY when set.",
    )
    scenario_parser.add_argument("--infer-repository", action="store_true")
    scenario_parser.add_argument(
        "--remote-name",
        default=os.getenv("CURSOR_REMOTE_NAME", "origin"),
        help="Git remote name used with --infer-repository. Defaults to CURSOR_REMOTE_NAME or origin.",
    )
    scenario_parser.add_argument(
        "--ref",
        default=os.getenv("CURSOR_SOURCE_REF"),
        help="Source ref. Defaults to CURSOR_SOURCE_REF or current git branch.",
    )
    scenario_parser.add_argument(
        "--model",
        default=os.getenv("CURSOR_MODEL"),
        help="Model name. Defaults to CURSOR_MODEL when set.",
    )
    scenario_parser.add_argument("--branch-name")
    scenario_parser.add_argument("--auto-create-pr", action="store_true")
    scenario_parser.add_argument("--open-as-cursor-github-app", action="store_true")
    scenario_parser.add_argument("--skip-reviewer-request", action="store_true")
    scenario_parser.add_argument("--no-wait", action="store_true")
    scenario_parser.add_argument(
        "--poll-interval-seconds",
        type=int,
        default=_int_env("CURSOR_API_POLL_INTERVAL_SECONDS", 15),
        help="Polling interval. Defaults to CURSOR_API_POLL_INTERVAL_SECONDS or 15.",
    )
    scenario_parser.add_argument(
        "--wait-timeout-seconds",
        type=int,
        default=_int_env("CURSOR_API_WAIT_TIMEOUT_SECONDS", 1800),
        help="Overall wait timeout. Defaults to CURSOR_API_WAIT_TIMEOUT_SECONDS or 1800.",
    )
    scenario_parser.add_argument(
        "--save-conversation",
        help="Optional path to save conversation JSON.",
    )
    scenario_parser.set_defaults(func=_cmd_run_scenario)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return int(args.func(args))
    except ApiError as exc:
        error_payload = {
            "error": {
                "status": exc.status_code,
                "message": str(exc),
                "payload": exc.payload,
            }
        }
        _print_json(error_payload)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
