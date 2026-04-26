# Contributing

## Development Setup

If you have network access and want a fully managed environment:

```bash
UV_CACHE_DIR=$PWD/.uv-cache uv lock
```

For offline local edits, the repository can also be exercised directly:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m py_compile src/space_elevator/*.py
```

## Contribution Expectations

- Keep the vendored `_pm` template portable across repositories.
- Avoid introducing assumptions tied to one product codebase unless they are clearly template examples.
- Preserve offline usability for basic validation where practical.
- Update `CHANGELOG.md` for user-visible changes.

## Pull Request Checklist

- Add or update tests when behavior changes.
- Update docs if CLI flags, template behavior, or installation expectations change.
- Keep release metadata and packaged template contents in sync.

