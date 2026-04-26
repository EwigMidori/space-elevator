# space-elevator

`space-elevator` is a portable PM harness for multi-agent PDCA execution in any repository.

The package ships a vendorable `_pm/` template and a small CLI that installs that template into another repository root.

## What It Contains

- A copyable `_pm/` directory template under `src/space_elevator/template/_pm/`
- A roadmap schema checker
- A local roadmap viewer
- `propeller.py`, an unattended architect watcher for Codex-driven execution
- Agent rulebooks, scoring rules, and the default Playdex roadmap snapshot used during development

## Install Or Run With `uv`

From this repository:

```bash
PYTHONPATH=src python3 -m space_elevator.cli init /path/to/your/repo
```

After publishing:

```bash
uv tool run --from git+https://github.com/ewigmidori/space-elevator space-elevator init /path/to/your/repo
```

## CLI

Install the template into a repository root:

```bash
PYTHONPATH=src python3 -m space_elevator.cli init .
```

Overwrite an existing `_pm/` directory:

```bash
PYTHONPATH=src python3 -m space_elevator.cli init . --force
```

Choose another destination directory name:

```bash
PYTHONPATH=src python3 -m space_elevator.cli init . --pm-dir ops-pm
```

## Consuming The Template

The installed template expects:

- the copied directory to live at `<repo-root>/_pm/`
- active batch specs to live at `<main_worktree_root>/.tmp/`
- local git ignore rules to permit `/.tmp/` scratch state

Useful commands after vendoring:

```bash
python3 _pm/scripts/check_progress_schema.py
python3 _pm/scripts/view_progress.py
python3 _pm/scripts/propeller.py
```

## Repository Layout

- `src/space_elevator/cli.py`
  Initialization CLI.
- `src/space_elevator/template/_pm/`
  The vendorable harness template.

## Publish Notes

This repository is prepared for GitHub publication as `ewigmidori/space-elevator`.

The local environment used to build this extraction has no outbound network access, so the actual GitHub repo creation and first push still need to happen from a network-enabled shell.
That same restriction also prevents validating `uv run space-elevator ...` here, because the isolated build environment cannot fetch `hatchling` from PyPI. The package metadata is ready for a normal network-enabled `uv` workflow.
