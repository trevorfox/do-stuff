---
name: capability-report
description: Create or update a structured report for Cloud Agent API capability runs, including subagent and skill invocation evidence.
disable-model-invocation: true
compatibility:
  runtime:
    - python3
metadata:
  purpose: cloud-agent-capability-testing
  output: reports/cloud-agent-capability-report.md
---

# Capability Report

Use this skill to generate a durable artifact for Cloud Agent API capability validation.

## When to use

- You need a report file summarizing a remote agent test run.
- The run includes subagents and skill invocation checks.

## Instructions

1. Ensure `reports/cloud-agent-capability-report.md` exists.
2. If the file does not exist, initialize it with:
   - `python3 .cursor/skills/capability-report/scripts/render_report_template.py --output reports/cloud-agent-capability-report.md`
3. Fill in or update sections with concrete evidence from the current run:
   - Agent ID
   - Branch name
   - Subagent(s) used
   - Skill(s) used
   - Pass/fail assessment
4. Keep entries factual and include exact marker lines where available.
5. End your response with:
   - `SKILL_USED: capability-report`

## Reference

- Report template guidance: `references/REPORT_TEMPLATE.md`
