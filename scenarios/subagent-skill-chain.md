Run an end-to-end capability test for subagent-to-skill chaining in this repository.

Requirements:
1. Explicitly invoke `/orchestration-tester`.
2. Inside that subagent run both skills:
   - `/capability-checklist`
   - `/capability-report`
3. Ensure a report artifact exists at `reports/cloud-agent-capability-report.md`.
4. Afterward, invoke `/artifact-verifier` to verify the generated artifact.
5. Final response must include all evidence marker lines returned by subagent and skills.

If any step fails, explain exactly what failed and why.
