# `.ci/agent` Harness

This directory is a small project-management harness intended to be copied into a repository root as-is.

## Layout

- `.ci/agent/AGENTS.md`
  Repository-wide PM and delegation rules.
- `.ci/agent/progress.json`
  Minimal starter template only.
- `.ci/agent/docs/`
  Agent handbooks and scoring rules.
- `.ci/agent/scripts/`
  Local helper scripts for schema validation, roadmap viewing, and unattended watcher mode.

## Runtime Assumptions

- `.ci/agent` lives directly under the repository root.
- The live roadmap lives at `<repo-root>/docs/progress.json`.
- Active batch specs live under `<main_worktree_root>/.tmp/`, not inside ephemeral worktrees.
- `.tmp/` should be locally ignored. `propeller.py` will try to add `/.tmp/` to `.git/info/exclude` automatically.

## Useful Commands

```bash
python3 .ci/agent/scripts/check_progress_schema.py
python3 .ci/agent/scripts/view_progress.py
python3 .ci/agent/scripts/propeller.py
```

## First-Use Checklist

1. Copy or adapt the starter roadmap into `docs/progress.json`.
2. Replace the template phases in `docs/progress.json` with repository-specific work.
3. Review `.ci/agent/AGENTS.md` and remove any rules that do not fit this repository's actual workflow.
4. Confirm `<main_worktree_root>/.tmp/` is locally ignored and available for specs.
