# Agent Rule Documents

These documents are the binding rule set for agent-driven work under `_pm`.

Use them together with:

- `_pm/AGENTS.md`
- `_pm/progress.json`
- the current batch spec under `<main_worktree_root>/.tmp/`

Rule documents:

- `_pm/docs/agents/spec-review.md`
  Rules for reviewing a batch spec before any Worker Agent starts.
- `_pm/docs/agents/architect-agent.md`
  Rules for Architect Agent planning, delegation, integration, and PR flow.
- `_pm/docs/agents/worker-agent.md`
  Rules for Worker Agent implementation scope and behavior.
- `_pm/docs/agents/test-agent.md`
  Rules for Test Agent test-planning and test-writing behavior.
- `_pm/docs/agents/review-agent.md`
  Rules for Review Agent review behavior and completion authority.

Supporting handbooks:

- `_pm/docs/review-scoring.md`
- `_pm/docs/test-agent-handbook.md`

These documents exist to keep `_pm/AGENTS.md` focused on repository-wide authority, workflow, and boundary rules while still giving each agent type a precise handbook.
