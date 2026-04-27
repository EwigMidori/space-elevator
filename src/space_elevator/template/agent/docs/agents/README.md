# Agent Rule Documents

These documents are the binding rule set for agent-driven work under `.ci/agent`.

Use them together with:

- `.ci/agent/AGENTS.md`
- `docs/progress.json`
- the current batch spec under `<main_worktree_root>/.tmp/`

Rule documents:

- `.ci/agent/docs/agents/spec-review.md`
  Rules for reviewing a batch spec before any Worker Agent starts.
- `.ci/agent/docs/agents/architect-agent.md`
  Rules for Architect Agent planning, delegation, integration, and PR flow.
- `.ci/agent/docs/agents/worker-agent.md`
  Rules for Worker Agent implementation scope and behavior.
- `.ci/agent/docs/agents/test-agent.md`
  Rules for Test Agent test-planning and test-writing behavior.
- `.ci/agent/docs/agents/review-agent.md`
  Rules for Review Agent review behavior and completion authority.

Supporting handbooks:

- `.ci/agent/docs/review-scoring.md`
- `.ci/agent/docs/test-agent-handbook.md`

These documents exist to keep `.ci/agent/AGENTS.md` focused on repository-wide authority, workflow, and boundary rules while still giving each agent type a precise handbook.
