# Cloud agent test instructions

This repository is a testbed for Cursor Cloud Agent API orchestration.

When a task references Cloud Agent API capability tests:

1. Delegate to `/orchestration-tester`.
2. Ensure `/capability-checklist` is used.
3. Ensure `/capability-report` is used and `reports/cloud-agent-capability-report.md` is updated.
4. Delegate to `/artifact-verifier` for a verification pass.

Prefer producing evidence markers in assistant responses:

- `SUBAGENT_USED: orchestration-tester`
- `SUBAGENT_USED: artifact-verifier`
- `SKILL_USED: capability-checklist`
- `SKILL_USED: capability-report`

## Cursor Cloud specific instructions

### Overview

Pure Python 3 CLI testbed (stdlib only, zero third-party dependencies). No web server, database, or frontend to run. The CLI at `scripts/cloud_agents_api.py` drives the remote Cursor Cloud Agents API.

### Running tests

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```

Unit tests run fully offline with no API key required.

### Running the CLI (requires `CURSOR_API_KEY`)

Auth sanity check: `python3 scripts/cloud_agents_api.py me`

Dry-run payload build (no API call): `python3 scripts/cloud_agents_api.py launch --print-payload-only --infer-repository --ref main --prompt "test"`

See `README.md` for the full command reference and scenario runner usage.

### Linting

No linter configuration is present in this repo. Python source uses only stdlib imports and type annotations compatible with Python 3.10+.

### Key caveats

- The `CURSOR_API_KEY` env var must be set for any live API commands (`me`, `models`, `repositories`, `list-agents`, `launch`, `run-scenario`, etc.). Unit tests do **not** need it.
- `--infer-repository` reads the git remote URL; ensure the working directory is the repo root.
- The `reports/` and `artifacts/` directories are gitignored.
