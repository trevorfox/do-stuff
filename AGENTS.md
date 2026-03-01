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
