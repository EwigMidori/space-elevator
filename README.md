# space-elevator

[![CI](https://github.com/EwigMidori/space-elevator/actions/workflows/ci.yml/badge.svg)](https://github.com/EwigMidori/space-elevator/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

`space-elevator` is a portable PM harness for multi-agent PDCA execution in any repository.

The package ships a vendorable `_pm/` template and a small CLI that installs that template into another repository root.

It is designed for repositories that want a durable local source of truth for roadmap state, agent rulebooks, spec-review gates, and unattended architect wakeups.

## What It Contains

- A copyable `_pm/` directory template under `src/space_elevator/template/_pm/`
- A roadmap schema checker
- A local roadmap viewer
- `propeller.py`, an unattended architect watcher for Codex-driven execution
- Agent rulebooks and scoring rules under `_pm/`
- A minimal live-roadmap starter for `docs/progress.json`

## Install Or Run With `uv`

From this repository:

```bash
PYTHONPATH=src python3 -m space_elevator --version
PYTHONPATH=src python3 -m space_elevator.cli init /path/to/your/repo
```

After publishing:

```bash
uv tool run --from git+https://github.com/ewigmidori/space-elevator space-elevator init /path/to/your/repo
```

Or install the tool persistently:

```bash
uv tool install git+https://github.com/ewigmidori/space-elevator
space-elevator init /path/to/your/repo
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

The installer also creates `<repo-root>/.tmp/.gitignore` when it is missing.
If `docs/progress.json` is missing, the installer also creates it from the bundled starter template.

## Consuming The Template

The installed template expects:

- the copied directory to live at `<repo-root>/_pm/`
- the live mutable roadmap to live at `<repo-root>/docs/progress.json`
- active batch specs to live at `<main_worktree_root>/.tmp/`
- local git ignore rules to permit `/.tmp/` scratch state

Useful commands after vendoring:

```bash
python3 _pm/scripts/check_progress_schema.py
python3 _pm/scripts/view_progress.py
python3 _pm/scripts/propeller.py
```

Inside the vendored harness:

- `_pm/progress.json` is only a minimal starter template kept with the harness.
- `docs/progress.json` is the real mutable roadmap that agents should read and update.

## Repository Layout

- `src/space_elevator/cli.py`
  Initialization CLI.
- `src/space_elevator/__main__.py`
  `python -m space_elevator` entrypoint.
- `src/space_elevator/template/_pm/`
  The vendorable harness template.
- `tests/`
  Basic offline validation for the CLI installer.

## Development

Offline validation used in this repository:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m py_compile src/space_elevator/*.py
```

## Publish Notes

This repository is prepared for GitHub publication as `ewigmidori/space-elevator`.

The local environment used to harden this extraction had no outbound PyPI access, so `uv run space-elevator ...` could not be validated through an isolated build backend here because `hatchling` could not be fetched. The package metadata is still prepared for a normal network-enabled `uv` workflow.
