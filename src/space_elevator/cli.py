from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass
from importlib.resources import as_file, files
from pathlib import Path
from datetime import datetime, timezone

from space_elevator import __version__

INSTALL_MANIFEST_NAME = "space-elevator.json"
PRESERVED_UPGRADE_PATHS = {
    Path("AGENTS.md"),
    Path("progress.json"),
}


@dataclass(frozen=True)
class TmpExcludeResult:
    path: Path | None
    status: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="space-elevator",
        description="Install the portable `.ci/agent` harness into another repository.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init",
        help="Copy the bundled `.ci/agent` template into a target repository root.",
    )
    init_parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="Target repository root. Defaults to the current directory.",
    )
    init_parser.add_argument(
        "--pm-dir",
        default=".ci/agent",
        help="Destination directory path inside the target repository. Defaults to `.ci/agent`.",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing destination directory.",
    )

    upgrade_parser = subparsers.add_parser(
        "upgrade",
        help="Refresh an existing installed harness in-place without overwriting docs/progress.json.",
    )
    upgrade_parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="Target repository root. Defaults to the current directory.",
    )
    upgrade_parser.add_argument(
        "--pm-dir",
        default=".ci/agent",
        help="Installed harness directory path inside the target repository. Defaults to `.ci/agent`.",
    )

    return parser.parse_args()


def template_root(*parts: str) -> Path:
    resource = files("space_elevator").joinpath("template", *parts)
    with as_file(resource) as path:
        return path


def iter_relative_files(root: Path) -> set[Path]:
    return {
        path.relative_to(root)
        for path in root.rglob("*")
        if path.is_file()
    }


def copy_relative_file(source_root: Path, destination_root: Path, relative_path: Path) -> None:
    source_path = source_root / relative_path
    destination_path = destination_root / relative_path
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, destination_path)


def merge_upgrade_tree(source_root: Path, existing_root: Path, staging_root: Path) -> None:
    shutil.copytree(source_root, staging_root)
    shipped_files = iter_relative_files(source_root)

    for relative_path in iter_relative_files(existing_root):
        if relative_path == Path(INSTALL_MANIFEST_NAME):
            continue
        if relative_path in PRESERVED_UPGRADE_PATHS or relative_path not in shipped_files:
            copy_relative_file(existing_root, staging_root, relative_path)


def install_template(target_root: Path, pm_dir: str, force: bool, preserve_existing: bool = False) -> Path:
    source_root = template_root("agent")
    destination = target_root / pm_dir

    if destination.exists():
        if not force:
            raise FileExistsError(
                f"destination already exists: {destination}. Use --force to replace it."
            )
        if preserve_existing and destination.is_dir():
            with tempfile.TemporaryDirectory(dir=target_root) as tmp_dir:
                staging_root = Path(tmp_dir) / destination.name
                merge_upgrade_tree(source_root, destination, staging_root)
                shutil.rmtree(destination)
                shutil.move(str(staging_root), destination)
            return destination
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


def resolve_git_exclude_path(target_root: Path) -> Path | None:
    git_dir = target_root / ".git"
    if not git_dir.exists():
        return None
    if git_dir.is_dir():
        return git_dir / "info" / "exclude"

    try:
        payload = git_dir.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    prefix = "gitdir: "
    if not payload.startswith(prefix):
        return None

    git_metadata_dir = (target_root / payload[len(prefix):]).resolve()
    return git_metadata_dir / "info" / "exclude"


def ensure_tmp_excluded(target_root: Path) -> TmpExcludeResult:
    exclude_path = resolve_git_exclude_path(target_root)
    if exclude_path is None:
        return TmpExcludeResult(path=None, status="missing_git_metadata")

    try:
        exclude_path.parent.mkdir(parents=True, exist_ok=True)
        existing = ""
        if exclude_path.exists():
            existing = exclude_path.read_text(encoding="utf-8")

        rule = "/.tmp/"
        if rule not in {line.strip() for line in existing.splitlines()}:
            prefix = "" if not existing or existing.endswith("\n") else "\n"
            comment = "# Local space-elevator scratch space\n"
            exclude_path.write_text(
                f"{existing}{prefix}{comment}{rule}\n",
                encoding="utf-8",
            )
    except OSError:
        return TmpExcludeResult(path=exclude_path, status="exclude_unwritable")

    return TmpExcludeResult(path=exclude_path, status="ok")


def write_install_manifest(destination: Path) -> Path:
    manifest_path = destination / INSTALL_MANIFEST_NAME
    payload = {
        "name": "space-elevator",
        "version": __version__,
        "installed_at_utc": datetime.now(timezone.utc).isoformat(),
        "install_root": destination.as_posix(),
    }
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path


def load_install_manifest(destination: Path) -> dict[str, object] | None:
    manifest_path = destination / INSTALL_MANIFEST_NAME
    if not manifest_path.exists():
        return None

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None
    return payload


def is_space_elevator_install(destination: Path) -> bool:
    manifest = load_install_manifest(destination)
    return bool(manifest and manifest.get("name") == "space-elevator")


def resolve_target_root(path_text: str) -> Path:
    target_root = Path(path_text).resolve()
    if not target_root.exists():
        raise FileNotFoundError(f"target path does not exist: {target_root}")
    if not target_root.is_dir():
        raise NotADirectoryError(f"target path is not a directory: {target_root}")
    return target_root


def cmd_init(args: argparse.Namespace) -> int:
    try:
        target_root = resolve_target_root(args.target)
    except (FileNotFoundError, NotADirectoryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    try:
        destination = install_template(target_root, args.pm_dir, args.force)
    except FileExistsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    progress_path = install_progress_template(target_root)
    exclude_result = ensure_tmp_excluded(target_root)
    manifest_path = write_install_manifest(destination)
    print(f"installed agent harness to {destination}")
    print("next steps:")
    print(f"  1. inspect {progress_path}")
    print(f"  2. keep {destination / 'progress.json'} as a minimal starter template only")
    print(f"  3. adjust {destination / 'AGENTS.md'} to fit the repository")
    if exclude_result.status == "ok" and exclude_result.path is not None:
        print(f"  4. review {exclude_result.path} and keep `.tmp/` local-only")
    elif exclude_result.status == "exclude_unwritable" and exclude_result.path is not None:
        print(
            f"  4. add `/.tmp/` to local ignore rules manually because {exclude_result.path} was not writable"
        )
    else:
        print("  4. ensure `/.tmp/` is ignored locally because no git metadata was detected")
    print(f"  5. recorded install metadata in {manifest_path}")
    return 0


def cmd_upgrade(args: argparse.Namespace) -> int:
    try:
        target_root = resolve_target_root(args.target)
    except (FileNotFoundError, NotADirectoryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    destination = target_root / args.pm_dir
    if not destination.exists():
        print(
            f"error: installed harness path does not exist: {destination}. Run `space-elevator init` first.",
            file=sys.stderr,
        )
        return 1
    if not destination.is_dir():
        print(f"error: installed harness path is not a directory: {destination}", file=sys.stderr)
        return 1
    if not is_space_elevator_install(destination):
        print(
            f"error: {destination} is not a recognized space-elevator install. Refusing to upgrade it in-place.",
            file=sys.stderr,
        )
        return 1

    try:
        install_template(target_root, args.pm_dir, force=True, preserve_existing=True)
    except FileExistsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    progress_path = install_progress_template(target_root)
    exclude_result = ensure_tmp_excluded(target_root)
    manifest_path = write_install_manifest(destination)
    print(f"installed agent harness to {destination}")
    print("next steps:")
    print(f"  1. inspect {progress_path}")
    print(f"  2. keep {destination / 'progress.json'} as a minimal starter template only")
    print(f"  3. review upgraded files; repo-local {destination / 'AGENTS.md'} was preserved")
    if exclude_result.status == "ok" and exclude_result.path is not None:
        print(f"  4. review {exclude_result.path} and keep `.tmp/` local-only")
    elif exclude_result.status == "exclude_unwritable" and exclude_result.path is not None:
        print(
            f"  4. add `/.tmp/` to local ignore rules manually because {exclude_result.path} was not writable"
        )
    else:
        print("  4. ensure `/.tmp/` is ignored locally because no git metadata was detected")
    print(f"  5. recorded install metadata in {manifest_path}")
    print(f"upgraded installed harness at {destination}")
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "init":
        return cmd_init(args)
    if args.command == "upgrade":
        return cmd_upgrade(args)
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
