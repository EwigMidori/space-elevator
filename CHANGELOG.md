# Changelog

## 0.1.0 - 2026-04-26

- Bootstrap the `space-elevator` package.
- Ship the vendorable `.ci/agent` template as packaged data.
- Add `space-elevator init` for copying the template into another repository.
- Add `space-elevator upgrade` for refreshing an existing installation in place.
- Make `upgrade` refuse unknown directories and preserve repo-local harness customizations.
- Include the `propeller.py` watcher, roadmap schema checker, and local roadmap viewer.
- Move live mutable roadmap state to `docs/progress.json` and keep harness-local `progress.json` as a starter template.
- Store `/.tmp/` ignore rules in local git exclude state instead of tracked files.
- Add basic offline tests and CI validation.
