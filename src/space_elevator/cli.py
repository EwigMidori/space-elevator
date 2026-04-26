from __future__ import annotations

import argparse
import shutil
import sys
from importlib.resources import as_file, files
from pathlib import Path

from space_elevator import __version__


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="space-elevator",
        description="Install the portable `_pm` harness into another repository.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init",
        help="Copy the bundled `_pm` template into a target repository root.",
    )
    init_parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="Target repository root. Defaults to the current directory.",
    )
    init_parser.add_argument(
        "--pm-dir",
        default="_pm",
        help="Destination directory name inside the target repository. Defaults to `_pm`.",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing destination directory.",
    )

    return parser.parse_args()


def template_root(*parts: str) -> Path:
    resource = files("space_elevator").joinpath("template", *parts)
    with as_file(resource) as path:
        return path


def install_template(target_root: Path, pm_dir: str, force: bool) -> Path:
    source_root = template_root("_pm")
    destination = target_root / pm_dir

    if destination.exists():
        if not force:
            raise FileExistsError(
                f"destination already exists: {destination}. Use --force to replace it."
            )
        if destination.is_dir():
            shutil.rmtree(destination)
        else:
            destination.unlink()

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_root, destination)
    return destination


def install_progress_template(target_root: Path) -> Path:
    source_path = template_root("docs", "progress.json")
    docs_dir = target_root / "docs"
    destination = docs_dir / "progress.json"

    docs_dir.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        shutil.copy2(source_path, destination)

    return destination


def ensure_tmp_gitignore(target_root: Path) -> Path:
    tmp_dir = target_root / ".tmp"
    gitignore_path = tmp_dir / ".gitignore"

    tmp_dir.mkdir(parents=True, exist_ok=True)
    if not gitignore_path.exists():
        gitignore_path.write_text("*\n!.gitignore\n", encoding="utf-8")

    return gitignore_path


def cmd_init(args: argparse.Namespace) -> int:
    target_root = Path(args.target).resolve()
    if not target_root.exists():
        print(f"error: target path does not exist: {target_root}", file=sys.stderr)
        return 1
    if not target_root.is_dir():
        print(f"error: target path is not a directory: {target_root}", file=sys.stderr)
        return 1

    try:
        destination = install_template(target_root, args.pm_dir, args.force)
    except FileExistsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    progress_path = install_progress_template(target_root)
    gitignore_path = ensure_tmp_gitignore(target_root)
    print(f"installed `_pm` template to {destination}")
    print("next steps:")
    print(f"  1. inspect {progress_path}")
    print(f"  2. keep {destination / 'progress.json'} as a minimal starter template only")
    print(f"  3. adjust {destination / 'AGENTS.md'} to fit the repository")
    print(f"  4. review {gitignore_path} and keep `.tmp/` local-only")
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "init":
        return cmd_init(args)
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
