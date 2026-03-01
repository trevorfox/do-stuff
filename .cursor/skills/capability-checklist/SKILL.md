---
name: capability-checklist
description: Build a concise checklist for validating Cloud Agent API runs that involve subagents and skill chaining.
metadata:
  purpose: cloud-agent-capability-testing
  version: 1
---

# Capability Checklist

Use this skill to create a short, auditable checklist for Cloud Agent API test runs.

## When to use

- A task asks to verify Cursor Cloud Agent behavior through the API.
- The task needs evidence that subagents and skills were both exercised.

## Instructions

1. Summarize the requested test objective in one sentence.
2. Produce a checklist with at least these items:
   - Agent launched through Cloud Agents API.
   - A named subagent was explicitly invoked.
   - At least one named skill was explicitly invoked by the subagent.
   - Output contains verifiable evidence markers.
3. Mark each item as PASS, FAIL, or UNKNOWN with a one-line rationale.
4. End your response with this marker:
   - `SKILL_USED: capability-checklist`

## Output format

Use this structure:

```text
Objective: ...

Checklist:
- [PASS|FAIL|UNKNOWN] ...
- [PASS|FAIL|UNKNOWN] ...

Notes:
- ...

SKILL_USED: capability-checklist
```
