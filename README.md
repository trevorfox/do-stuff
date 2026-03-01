# Cursor Cloud Agent API integration testbed

This repository is configured to test **Cursor Cloud Agents** behavior through the **Cloud Agents API**, including:

- custom subagents
- custom skills
- explicit subagent invocation
- subagents invoking skills

## What is included

### Subagents (`.cursor/agents/`)

- `orchestration-tester`: focused on delegation and explicit skill usage evidence
- `artifact-verifier`: validates generated artifacts and reports pass/fail

### Skills (`.cursor/skills/`)

- `capability-checklist`: generates auditable PASS/FAIL/UNKNOWN test checklist output
- `capability-report`: creates/updates `reports/cloud-agent-capability-report.md`
  - includes helper script:
    - `.cursor/skills/capability-report/scripts/render_report_template.py`

### API harness

- `scripts/cloud_agents_api.py`
  - supports common API operations:
    - `launch`
    - `list-agents`
    - `status`
    - `wait`
    - `conversation`
    - `followup`
    - `stop`
    - `delete`
    - `me`
    - `models`
    - `repositories`
  - includes scenario runner:
    - `run-scenario subagent-smoke`
    - `run-scenario subagent-skill-chain`

### Scenarios (`scenarios/`)

- `subagent-smoke.md`: explicit subagent invocation smoke test
- `subagent-skill-chain.md`: tests subagent invocation + subagent-driven skill invocation

## Docs references used

- Cloud Agents API overview: https://cursor.com/docs/cloud-agent/api/overview
- Cloud Agents OpenAPI spec: https://cursor.com/docs-static/cloud-agents-openapi.yaml
- Subagents: https://cursor.com/docs/context/subagents
- Skills: https://cursor.com/docs/context/skills

## Prerequisites

1. A Cursor API key (`CURSOR_API_KEY`)
2. Repo accessible by your Cursor account in GitHub
3. Python 3
4. Cursor GitHub integration enabled for the repo/org

## What you need to set up on your end

### 1) Cursor account + API key

- Create/find your API key in Cursor Dashboard:
  - https://cursor.com/settings
- Make sure the account tied to that key can access the target GitHub repo.

### 2) GitHub access for Cloud Agents

- Confirm Cursor has GitHub access for the repository (and org, if private).
- The Cloud Agent must be able to clone and push a branch in that repo.

### 3) Environment variables

You can set these manually or via `.env`.

Required:

- `CURSOR_API_KEY`: your Cursor API key

Optional (recommended):

- `CURSOR_API_AUTH_MODE` (default: `basic`)
- `CURSOR_API_BASE_URL` (default: `https://api.cursor.com`)
- `CURSOR_API_REQUEST_TIMEOUT_SECONDS` (default: `60`)
- `CURSOR_REPOSITORY` (default repository URL for commands)
- `CURSOR_SOURCE_REF` (default source branch/ref, e.g. `main`)
- `CURSOR_REMOTE_NAME` (default: `origin`, used with `--infer-repository`)
- `CURSOR_MODEL` (default model for launch/scenario commands)
- `CURSOR_API_POLL_INTERVAL_SECONDS` (default: `15`)
- `CURSOR_API_WAIT_TIMEOUT_SECONDS` (default: `1800`)

Use the template:

```bash
cp .env.example .env
```

Then load it in your shell:

```bash
set -a && source .env && set +a
```

## Quick start

```bash
export CURSOR_API_KEY="<your-cursor-api-key>"
```

Or, if using `.env`:

```bash
set -a && source .env && set +a
```

### 1) Sanity check auth and visibility

```bash
python3 scripts/cloud_agents_api.py me
python3 scripts/cloud_agents_api.py models
python3 scripts/cloud_agents_api.py repositories
```

### 2) Run subagent smoke scenario remotely

```bash
python3 scripts/cloud_agents_api.py run-scenario subagent-smoke \
  --infer-repository \
  --ref main \
  --save-conversation artifacts/subagent-smoke-conversation.json
```

### 3) Run subagent + skill-chain scenario remotely

```bash
python3 scripts/cloud_agents_api.py run-scenario subagent-skill-chain \
  --infer-repository \
  --ref main \
  --save-conversation artifacts/subagent-skill-chain-conversation.json
```

## Manual launch example

```bash
python3 scripts/cloud_agents_api.py launch \
  --infer-repository \
  --ref main \
  --branch-name "cursor-api/manual-$(date +%Y%m%d-%H%M%S)" \
  --prompt-file scenarios/subagent-skill-chain.md
```

Then poll status and inspect conversation:

```bash
python3 scripts/cloud_agents_api.py status <agent-id>
python3 scripts/cloud_agents_api.py wait <agent-id>
python3 scripts/cloud_agents_api.py conversation <agent-id>
```

## Auth mode

Default auth mode is `basic` (matching docs examples). You can switch if needed:

```bash
export CURSOR_API_AUTH_MODE=bearer
```

or pass `--auth-mode bearer` on each command.

## Scenario validation markers

`run-scenario` checks assistant-side conversation output for required markers:

- `SUBAGENT_USED: orchestration-tester`
- `SKILL_USED: capability-checklist`
- `SKILL_USED: capability-report` (for skill-chain scenario)

If markers are missing, the command exits non-zero.

## Local tests

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

## Notes

- The Cloud Agents API docs currently call out Basic Authentication and link to the OpenAPI spec.
- API docs note that MCP is not yet supported via Cloud Agents API.
