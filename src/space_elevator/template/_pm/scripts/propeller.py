#!/usr/bin/env python3
"""Watch a repository and auto-start a Codex architect when idle.

The watcher treats the repository as "active" whenever any of these change:
- any local branch tip commit metadata
- the tracked remote main ref SHA (after an optional fetch)
- any attached worktree's dirty file set or dirty-file timestamps

When two adjacent samples are identical, the watcher treats the repository as
idle for that sample interval and may launch a non-interactive `codex exec`
run with an Architect Agent prompt. It keeps watching until every monitored
progress file reports only `done` phase/task statuses.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import select
import shutil
import signal
import subprocess
import sys
import termios
import time
import tty
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_SAMPLE_SECONDS = 30 * 60
DEFAULT_FETCH_INTERVAL_SECONDS = 5 * 60
DEFAULT_CODEX_COOLDOWN_SECONDS = 5 * 60
DEFAULT_WAIT_TICK_SECONDS = 10
DEFAULT_REMOTE = "origin"
DEFAULT_MAIN_BRANCH = "main"
PM_DIR_NAME = "_pm"
PROGRESS_RELATIVE_PATH = Path("docs/progress.json")
STREAM_DISCONNECTED_MARKER = "error: reconnecting... 3/5"


STOP_REQUESTED = False
RUNTIME_STATE_KEYS = (
    "codex_pid",
    "last_command",
    "last_exited_pid",
    "last_launch_snapshot_hash",
    "last_launch_ts",
    "last_log_path",
    "last_message_path",
    "last_observed_codex_message",
    "prompt_path",
)


def handle_stop_signal(signum: int, _frame: object) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True
    print(f"[watcher] received signal {signum}, exiting after current cycle", flush=True)


def parse_args() -> argparse.Namespace:
    repo_default = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        description="Monitor git activity and launch a Codex architect after unchanged samples."
    )
    parser.add_argument("--repo", type=Path, default=repo_default, help="Repository root to monitor.")
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=repo_default / ".tmp" / "architect-watch-state",
        help="Directory for logs, pid files, and snapshot state.",
    )
    parser.add_argument(
        "--sample-seconds",
        type=int,
        default=DEFAULT_SAMPLE_SECONDS,
        help="Seconds between consecutive samples. If two adjacent samples match, Codex may launch.",
    )
    parser.add_argument(
        "--fetch-interval-seconds",
        type=int,
        default=DEFAULT_FETCH_INTERVAL_SECONDS,
        help="How often to refresh the remote main ref. Set to 0 to disable fetch.",
    )
    parser.add_argument(
        "--codex-cooldown-seconds",
        type=int,
        default=DEFAULT_CODEX_COOLDOWN_SECONDS,
        help="Minimum delay between Codex launches when the repo stays idle.",
    )
    parser.add_argument("--remote", default=DEFAULT_REMOTE, help="Git remote to refresh.")
    parser.add_argument(
        "--main-branch",
        default="",
        help="Default branch name. Auto-detected when omitted.",
    )
    parser.add_argument(
        "--codex-bin",
        default="codex",
        help="Codex executable to invoke when the repo is idle.",
    )
    parser.add_argument(
        "--codex-model",
        default="",
        help="Optional model override passed to `codex exec --model`.",
    )
    parser.add_argument(
        "--codex-profile",
        default="",
        help="Optional Codex profile passed to `codex exec --profile`.",
    )
    parser.add_argument(
        "--codex-extra-arg",
        action="append",
        default=[],
        help="Extra argument to append to `codex exec`. Repeatable.",
    )
    parser.add_argument(
        "--prompt-file",
        type=Path,
        help="Optional file whose contents replace the built-in Architect Agent prompt.",
    )
    parser.add_argument(
        "--progress-file",
        type=Path,
        action="append",
        default=[],
        help="Explicit progress.json path to monitor. Repeat to override auto-discovery.",
    )
    return parser.parse_args()


def run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def safe_read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def resolve_git_path(repo: Path, *parts: str) -> Path | None:
    result = run_git(repo, "rev-parse", "--git-path", str(Path(*parts)), check=False)
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    if not value:
        return None
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = repo / candidate
    return candidate


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def shorten_ref(refname: str) -> str:
    prefixes = (
        "refs/heads/",
        "refs/remotes/",
        "refs/tags/",
    )
    for prefix in prefixes:
        if refname.startswith(prefix):
            return refname[len(prefix) :]
    return refname


def parse_worktrees(repo: Path) -> list[dict[str, str]]:
    result = run_git(repo, "worktree", "list", "--porcelain")
    items: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for raw_line in result.stdout.splitlines():
        if not raw_line:
            if current:
                items.append(current)
                current = {}
            continue
        key, _, value = raw_line.partition(" ")
        current[key] = value
    if current:
        items.append(current)
    return items


def parse_branch_refs(repo: Path) -> dict[str, dict[str, object]]:
    result = run_git(
        repo,
        "for-each-ref",
        "--format=%(refname)\t%(objectname)\t%(committerdate:unix)",
        "refs/heads",
    )
    refs: dict[str, dict[str, object]] = {}
    for line in result.stdout.splitlines():
        refname, _, rest = line.partition("\t")
        sha, _, commit_ts = rest.partition("\t")
        refs[shorten_ref(refname)] = {
            "sha": sha,
            "commit_ts": int(commit_ts or "0"),
        }
    return refs


def get_ref_meta(repo: Path, refname: str) -> dict[str, object] | None:
    result = run_git(repo, "log", "-1", "--format=%H\t%ct", refname, check=False)
    if result.returncode != 0:
        return None
    output = result.stdout.strip()
    if not output:
        return None
    sha, _, commit_ts = output.partition("\t")
    return {
        "sha": sha,
        "commit_ts": int(commit_ts or "0"),
    }


def detect_default_branch(repo: Path, remote: str) -> str:
    candidates = [
        ("symbolic-ref", "--quiet", "--short", f"refs/remotes/{remote}/HEAD"),
        ("symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"),
    ]
    for command in candidates:
        result = run_git(repo, *command, check=False)
        if result.returncode != 0:
            continue
        value = result.stdout.strip()
        if value:
            return value.split("/", 1)[-1]

    for branch_name in ("main", "master"):
        result = run_git(repo, "show-ref", "--verify", f"refs/heads/{branch_name}", check=False)
        if result.returncode == 0:
            return branch_name

    result = run_git(repo, "branch", "--show-current", check=False)
    current_branch = result.stdout.strip()
    if current_branch:
        return current_branch
    return DEFAULT_MAIN_BRANCH


def detect_main_worktree_root(repo: Path) -> Path:
    result = run_git(repo, "worktree", "list", "--porcelain", check=False)
    if result.returncode != 0:
        return repo

    for raw_line in result.stdout.splitlines():
        if not raw_line.startswith("worktree "):
            continue
        _, _, value = raw_line.partition(" ")
        if value:
            return Path(value).resolve()
    return repo


def ensure_tmp_excluded(repo: Path, log) -> None:
    exclude_path = resolve_git_path(repo, "info", "exclude")
    if exclude_path is None or not exclude_path.exists():
        return

    try:
        existing = exclude_path.read_text(encoding="utf-8")
    except OSError as exc:
        log(f"failed to read {exclude_path}: {exc}")
        return

    rule = "/.tmp/"
    if rule in {line.strip() for line in existing.splitlines()}:
        return

    prefix = "" if not existing or existing.endswith("\n") else "\n"
    comment = "# Local PM scratch space\n"
    try:
        exclude_path.write_text(f"{existing}{prefix}{comment}{rule}\n", encoding="utf-8")
        log(f"added {rule} to {exclude_path}")
    except OSError as exc:
        log(f"failed to update {exclude_path}: {exc}")


def maybe_fetch_remote_main(args: argparse.Namespace, last_fetch_ts: float, now: float, log) -> float:
    if args.fetch_interval_seconds <= 0:
        return last_fetch_ts
    if last_fetch_ts and now - last_fetch_ts < args.fetch_interval_seconds:
        return last_fetch_ts
    try:
        result = run_git(args.repo, "fetch", "--prune", args.remote, args.main_branch, check=False)
    except FileNotFoundError:
        log("git executable is unavailable; skipping fetch")
        return now
    if result.returncode == 0:
        log(f"fetched {args.remote}/{args.main_branch}")
    else:
        stderr = result.stderr.strip() or "unknown fetch error"
        log(f"fetch failed for {args.remote}/{args.main_branch}: {stderr}")
    return now


def read_progress_paths(args: argparse.Namespace, worktrees: list[dict[str, str]]) -> list[Path]:
    if args.progress_file:
        return sorted({path.resolve() for path in args.progress_file})

    paths = {args.repo / PROGRESS_RELATIVE_PATH}
    for item in worktrees:
        worktree_path = Path(item["worktree"])
        candidate = worktree_path / PROGRESS_RELATIVE_PATH
        if candidate.exists():
            paths.add(candidate.resolve())
    return sorted(paths)


def progress_is_done(progress_path: Path) -> tuple[bool, list[str]]:
    try:
        payload = json.loads(safe_read_text(progress_path))
    except Exception as exc:  # noqa: BLE001
        return False, [f"failed to read {progress_path}: {exc}"]

    findings: list[str] = []
    phases = payload.get("phases", [])
    for phase in phases:
        phase_id = phase.get("id", "<unknown-phase>")
        phase_status = phase.get("status", "todo")
        if phase_status != "done":
            findings.append(f"{progress_path}: phase {phase_id} is {phase_status}")
        for task in phase.get("tasks", []):
            task_id = task.get("id", "<unknown-task>")
            task_status = task.get("status", "todo")
            if task_status != "done":
                findings.append(f"{progress_path}: task {task_id} is {task_status}")
    return not findings, findings


def relative_to_repo(repo: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo.resolve()))
    except ValueError:
        return str(path)


def parse_status_entries(output: bytes) -> list[tuple[str, str, str | None]]:
    parts = output.split(b"\0")
    entries: list[tuple[str, str, str | None]] = []
    index = 0
    while index < len(parts):
        raw = parts[index]
        index += 1
        if not raw:
            continue
        if len(raw) < 4:
            continue
        status = raw[:2].decode("utf-8", "replace")
        path = raw[3:].decode("utf-8", "surrogateescape")
        orig_path = None
        if "R" in status or "C" in status:
            if index < len(parts):
                orig_path = parts[index].decode("utf-8", "surrogateescape")
                index += 1
        entries.append((status, path, orig_path))
    return entries


def dirty_fingerprint(worktree: Path, repo_root: Path) -> dict[str, object]:
    result = subprocess.run(
        ["git", "-C", str(worktree), "status", "--porcelain=v1", "--untracked-files=all", "-z"],
        check=True,
        capture_output=True,
    )
    entries = parse_status_entries(result.stdout)

    file_digests: list[dict[str, object]] = []
    digest = hashlib.sha256()
    for status, path_text, orig_path_text in entries:
        path = worktree / path_text
        digest.update(status.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path_text.encode("utf-8", "surrogateescape"))
        digest.update(b"\0")
        if orig_path_text is not None:
            digest.update(orig_path_text.encode("utf-8", "surrogateescape"))
            digest.update(b"\0")
        if path.exists():
            stat_result = path.lstat()
            metadata = {
                "mtime_ns": stat_result.st_mtime_ns,
                "size": stat_result.st_size,
                "mode": stat_result.st_mode,
            }
            kind = "symlink" if path.is_symlink() else "present"
        else:
            metadata = None
            kind = "missing"
        digest.update(json.dumps(metadata, sort_keys=True).encode("utf-8"))
        digest.update(b"\0")
        file_digests.append(
            {
                "status": status,
                "path": relative_to_repo(repo_root, path),
                "orig_path": orig_path_text,
                "metadata": metadata,
                "kind": kind,
            }
        )

    return {
        "count": len(file_digests),
        "hash": digest.hexdigest(),
        "entries": file_digests,
    }


def snapshot_repository(args: argparse.Namespace, log) -> dict[str, object]:
    worktree_entries = parse_worktrees(args.repo)
    local_branches = parse_branch_refs(args.repo)
    remote_main_ref = f"refs/remotes/{args.remote}/{args.main_branch}"
    remote_main_meta = get_ref_meta(args.repo, remote_main_ref)
    main_meta = get_ref_meta(args.repo, f"refs/heads/{args.main_branch}")

    worktrees: list[dict[str, object]] = []
    for item in worktree_entries:
        worktree_path = Path(item["worktree"]).resolve()
        branch_ref = item.get("branch", "")
        branch_name = shorten_ref(branch_ref) if branch_ref else "(detached)"
        head_meta = get_ref_meta(worktree_path, item.get("HEAD", "HEAD"))
        try:
            dirty = dirty_fingerprint(worktree_path, args.repo)
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8", "replace").strip() if exc.stderr else "unknown error"
            log(f"failed to inspect dirty state for {worktree_path}: {stderr}")
            dirty = {"count": -1, "hash": f"error:{stderr}", "entries": []}
        worktrees.append(
            {
                "path": str(worktree_path),
                "branch": branch_name,
                "head": item.get("HEAD", ""),
                "head_commit_ts": None if head_meta is None else head_meta["commit_ts"],
                "dirty": dirty,
            }
        )

    progress_paths = read_progress_paths(args, worktree_entries)
    progress_status: list[dict[str, object]] = []
    all_progress_done = True
    for progress_path in progress_paths:
        done, findings = progress_is_done(progress_path)
        all_progress_done = all_progress_done and done
        progress_status.append(
            {
                "path": str(progress_path),
                "done": done,
                "findings": findings,
            }
        )

    snapshot = {
        "local_branches": local_branches,
        "main_branch": {
            "name": args.main_branch,
            "local": main_meta,
            "remote": remote_main_meta,
        },
        "worktrees": worktrees,
        "progress": progress_status,
        "all_progress_done": all_progress_done,
    }
    snapshot["fingerprint"] = sha256_bytes(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    return snapshot


def load_state(state_file: Path) -> dict[str, object]:
    if not state_file.exists():
        return {}
    try:
        return json.loads(safe_read_text(state_file))
    except Exception:  # noqa: BLE001
        return {}


def save_state(state_file: Path, state: dict[str, object]) -> None:
    state_file.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def process_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        waited_pid, _ = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        pass
    except OSError:
        return False
    else:
        if waited_pid == pid:
            return False
        if waited_pid == 0:
            return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def clear_runtime_state(state: dict[str, object]) -> dict[str, object]:
    for key in RUNTIME_STATE_KEYS:
        state.pop(key, None)
    return state


def stop_codex_process(pid: int | None, log, grace_seconds: float = 5.0) -> bool:
    if not pid:
        return True
    if not process_alive(pid):
        return True

    try:
        os.killpg(pid, signal.SIGTERM)
        log(f"sent SIGTERM to codex process group pid={pid}")
    except ProcessLookupError:
        return True
    except PermissionError as exc:
        log(f"failed to terminate codex pid={pid}: {exc}")
        return False

    deadline = time.time() + grace_seconds
    while time.time() < deadline:
        if not process_alive(pid):
            return True
        time.sleep(0.2)

    try:
        os.killpg(pid, signal.SIGKILL)
        log(f"sent SIGKILL to codex process group pid={pid}")
    except ProcessLookupError:
        return True
    except PermissionError as exc:
        log(f"failed to force-kill codex pid={pid}: {exc}")
        return False

    deadline = time.time() + grace_seconds
    while time.time() < deadline:
        if not process_alive(pid):
            return True
        time.sleep(0.2)
    return not process_alive(pid)


def log_has_stream_disconnect(log_path: Path | None) -> bool:
    if log_path is None or not log_path.exists():
        return False
    try:
        text = log_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return STREAM_DISCONNECTED_MARKER in text.lower()


def extract_latest_codex_message(log_path: Path | None, max_bytes: int = 256 * 1024) -> str | None:
    if log_path is None or not log_path.exists():
        return None
    try:
        with log_path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - max_bytes), os.SEEK_SET)
            text = handle.read().decode("utf-8", errors="ignore")
    except OSError:
        return None

    lines = text.splitlines()
    for index in range(len(lines) - 2, -1, -1):
        if lines[index] != "codex":
            continue
        message = lines[index + 1].strip()
        if message:
            return message
    return None


def refresh_latest_codex_message(state: dict[str, object], state_file: Path, log_path: Path | None, log) -> str | None:
    message = extract_latest_codex_message(log_path)
    if not message:
        return None
    if message == state.get("last_observed_codex_message"):
        return message
    state["last_observed_codex_message"] = message
    save_state(state_file, state)
    log(f"latest codex: {message}")
    return message


@dataclass
class LaunchResult:
    pid: int | None
    command: list[str]
    log_path: Path
    last_message_path: Path
    prompt_path: Path | None


def default_prompt(repo: Path) -> str:
    return f"""你现在在仓库 {repo} 中，必须严格作为 Architect Agent 工作。

执行要求：
1. 先读 `_pm/AGENTS.md`、`docs/progress.json`、`_pm/docs/agents/README.md`，以及当前活跃批次对应的 `.tmp/` 规格。
2. 严格遵守 `_pm/AGENTS.md` 中的 PDCA 多代理流程、分支/工作树约束、进度状态约束和评审门槛。
3. 只推进 `docs/progress.json` 允许启动的下一个未完成阶段/任务；不要越过 phase gate。
4. 作为 Architect Agent，不要手改业务代码、测试代码、fixtures 或其他源码；需要实现时应先写/更新主仓库根目录 `.tmp/` 下的规格，再委派 Worker/Test/Review Agent，并在评审通过后集成。
5. 所有实现工作必须使用 dedicated non-default-branch worktree 和 batch branch；不要直接在默认分支所在 worktree 上做实现。
6. 只有在真实评审达到要求后，才允许把 `docs/progress.json` 里的 progress 项目标记为 done。
7. 禁止把任何已经是 done 的 phase 或 task 改回 todo、in_progress、blocked 或 ready_for_review。可以默认信任现有 done 状态是经过审核后成立的，除非你发现 `docs/progress.json` 本身损坏到无法解释，此时只能记录异常，不能自行回退这些 done 项。
8. 在启动任何 worker 之前，你必须先写出一份足够细的 `.tmp/` 实施规格，细到一个合格初级工程师无需猜测也能完成；如果规格缺少目标/非目标、作用范围与文件归属、冻结接口、任务切片、关键流程、错误路径、边界条件、验收标准、依赖前置条件、禁止擅自扩 scope 等信息，不得派工。
9. 写完规格后，不要自审了事。你必须先启动一个独立 Agent 对这份规格做 review，专门找缺失边界、模糊描述、未冻结接口、不可验证的验收标准和会导致 worker 猜测施工的空洞。只有这个 review 反馈被修完后，才允许启动 worker。
10. 给 worker 派工时，不能只甩一个 .tmp 文件路径；必须明确说明 owned scope、不能改的边界、完成标准和常见误区，避免 worker 自行补设计。
11. 你被明确授权在 `_pm/AGENTS.md` 允许的范围内执行 Architect Agent 的集成与 PR 推进职责，包括整理已评审通过的批次、准备/更新 PR 分支状态、创建 PR，以及**合并PR**。
12. 尽可能持续推进，直到监控中的 `docs/progress.json` 全部完成；如果遇到当前环境内无法自行解除的具体阻塞，清楚写明阻塞点后退出。
13. 注意你可能在任何阶段被唤醒，比如PR已经创建但未合并、工作已完成但PR未创建，或者工作完成了一半。你需要接受并开始工作直到全部完成。因为你处于无人值守的状态。持续运行长达12个小时。

产出要求：
- 优先完成可以闭环的当前批次。
- 说明你创建或更新了哪些 `.tmp/` 规格、使用了哪些 worktree/branch、以及当前推进到了哪个 progress 任务。
"""


def next_codex_run_id(state_dir: Path) -> int:
    max_index = 0
    for path in state_dir.glob("codex-*.log"):
        suffix = path.stem.removeprefix("codex-")
        if suffix.isdigit():
            max_index = max(max_index, int(suffix))
    for path in state_dir.glob("codex-last-message-*.txt"):
        suffix = path.stem.removeprefix("codex-last-message-")
        if suffix.isdigit():
            max_index = max(max_index, int(suffix))
    return max_index + 1


def find_previous_last_message_path(state_dir: Path, next_run_id: int) -> Path | None:
    for run_id in range(next_run_id - 1, 0, -1):
        candidate = state_dir / f"codex-last-message-{run_id:04d}.txt"
        if candidate.exists():
            return candidate
    return None


def build_launch_prompt(
    args: argparse.Namespace,
    state_dir: Path,
    next_run_id: int,
    prompt_path: Path | None,
) -> str:
    if args.prompt_file:
        prompt = safe_read_text(args.prompt_file)
    else:
        prompt = default_prompt(args.repo)

    previous_last_message_path = find_previous_last_message_path(state_dir, next_run_id)
    if previous_last_message_path is None:
        return prompt

    try:
        previous_last_message = safe_read_text(previous_last_message_path).strip()
    except Exception as exc:  # noqa: BLE001
        previous_last_message = f"<failed to read previous last message: {exc}>"

    previous_last_message = previous_last_message or "<previous codex run did not write a final message>"
    return (
        f"{prompt}\n\n"
        "上一轮 codex 退出时留下了一份最后消息。把它当作低置信线索，而不是事实或优先级来源。"
        " 这类遗言经常只反映中断前最后一件鸡毛蒜皮的小事，容易把你带偏。"
        " 你必须先重新检查仓库真实状态，再决定是否采纳其中任何建议。\n"
        f"上一轮最后消息文件: {previous_last_message_path}\n"
        "上一轮最后消息内容如下：\n"
        f"{previous_last_message}\n"
    )


def launch_codex(args: argparse.Namespace, state_dir: Path, log) -> LaunchResult:
    codex_path = shutil.which(args.codex_bin)
    if not codex_path:
        raise FileNotFoundError(f"cannot find codex binary: {args.codex_bin}")

    prompt_path: Path | None = None
    if args.prompt_file:
        prompt_path = args.prompt_file.resolve()

    run_id = next_codex_run_id(state_dir)
    prompt = build_launch_prompt(args, state_dir, run_id, prompt_path)

    prompt_cache = state_dir / "last_prompt.txt"
    prompt_cache.write_text(prompt, encoding="utf-8")

    command = [
        codex_path,
        "exec",
        "--cd",
        str(args.repo),
        "--dangerously-bypass-approvals-and-sandbox",
    ]
    if args.codex_model:
        command.extend(["--model", args.codex_model])
    if args.codex_profile:
        command.extend(["--profile", args.codex_profile])
    command.extend(args.codex_extra_arg)
    command.append(prompt)

    log_path = state_dir / f"codex-{run_id:04d}.log"
    last_message_path = state_dir / f"codex-last-message-{run_id:04d}.txt"
    command.extend(["--output-last-message", str(last_message_path)])

    log_handle = log_path.open("ab", buffering=0)
    process = subprocess.Popen(
        command,
        cwd=args.repo,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    return LaunchResult(
        pid=process.pid,
        command=command,
        log_path=log_path,
        last_message_path=last_message_path,
        prompt_path=prompt_path,
    )


def make_logger(log_path: Path):
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(message: str) -> None:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {message}"
        try:
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            pass
        print(line, flush=True)

    return log


def enable_cbreak_stdin(log):
    if not sys.stdin.isatty():
        return None
    fd = sys.stdin.fileno()
    old_attrs = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    log("stdin hotkey enabled; press 's' to force an immediate sample")
    return fd, old_attrs


def restore_stdin(terminal_state) -> None:
    if terminal_state is None:
        return
    fd, old_attrs = terminal_state
    termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)


def wait_for_next_cycle(
    sample_seconds: int,
    codex_pid: int | None,
    last_message_path: Path | None,
    active_log_path: Path | None,
    state: dict[str, object],
    state_file: Path,
    log,
) -> str:
    if sample_seconds <= 0:
        return "timeout"

    deadline = time.time() + sample_seconds
    while time.time() < deadline and not STOP_REQUESTED:
        refresh_latest_codex_message(state, state_file, active_log_path, log)
        if codex_pid and not process_alive(codex_pid):
            log(f"codex pid={codex_pid} exited during sample wait")
            return "codex_exit"
        if last_message_path and last_message_path.exists():
            log(f"detected last-message output during sample wait: {last_message_path}")
            return "last_message"
        timeout = min(DEFAULT_WAIT_TICK_SECONDS, max(0.0, deadline - time.time()))
        if sys.stdin.isatty():
            ready, _, _ = select.select([sys.stdin], [], [], timeout)
            if not ready:
                continue
            chars = os.read(sys.stdin.fileno(), 32).decode("utf-8", "ignore")
            if "s" in chars.lower():
                log("manual sample requested from stdin")
                return "manual_sample"
            continue
        time.sleep(timeout)
    if STOP_REQUESTED:
        return "stop_requested"
    return "timeout"


def acquire_lock(lock_path: Path) -> object:
    handle = lock_path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        raise SystemExit(f"another watcher instance already holds {lock_path}") from exc
    return handle


def summarize_progress(progress_items: Iterable[dict[str, object]]) -> str:
    incomplete: list[str] = []
    for item in progress_items:
        if item.get("done"):
            continue
        findings = item.get("findings", [])
        if findings:
            incomplete.append(str(findings[0]))
    if not incomplete:
        return "all monitored progress files are done"
    return "; ".join(incomplete[:3])


def main() -> int:
    args = parse_args()
    args.repo = args.repo.resolve()
    default_state_dir = (args.repo / ".tmp" / "architect-watch-state").resolve()
    main_worktree_root = detect_main_worktree_root(args.repo)
    if args.state_dir.resolve() == default_state_dir:
        args.state_dir = main_worktree_root / ".tmp" / "architect-watch-state"
    args.repo = main_worktree_root
    args.state_dir = args.state_dir.resolve()
    if not args.main_branch:
        args.main_branch = detect_default_branch(args.repo, args.remote)
    args.state_dir.mkdir(parents=True, exist_ok=True)

    log = make_logger(args.state_dir / "watcher.log")
    _lock_handle = acquire_lock(args.state_dir / "watcher.lock")
    terminal_state = None

    signal.signal(signal.SIGINT, handle_stop_signal)
    signal.signal(signal.SIGTERM, handle_stop_signal)

    state_file = args.state_dir / "state.json"
    state = load_state(state_file)
    stale_pid = state.get("codex_pid")
    if stale_pid and not process_alive(int(stale_pid)):
        clear_runtime_state(state)
        save_state(state_file, state)

    try:
        terminal_state = enable_cbreak_stdin(log)
        ensure_tmp_excluded(args.repo, log)
        log(f"watching repo {args.repo}")
        log(
            "watch config: "
            f"sample={args.sample_seconds}s "
            f"fetch_interval={args.fetch_interval_seconds}s codex_cooldown={args.codex_cooldown_seconds}s "
            f"default_branch={args.main_branch}"
        )
        log(f"codex stdout/stderr logs: {args.state_dir / 'codex-XXXX.log'}")

        last_fetch_ts = float(state.get("last_fetch_ts", 0.0) or 0.0)

        while not STOP_REQUESTED:
            now = time.time()
            last_fetch_ts = maybe_fetch_remote_main(args, last_fetch_ts, now, log)

            snapshot = snapshot_repository(args, log)
            snapshot_hash = str(snapshot["fingerprint"])
            previous_snapshot_hash = state.get("last_snapshot_hash")
            changed = snapshot_hash != previous_snapshot_hash
            if changed:
                state["last_snapshot_hash"] = snapshot_hash
                state["last_snapshot"] = snapshot
                log("sample changed since previous sample")
            else:
                log("sample unchanged since previous sample")

            save_state(state_file, {**state, "last_fetch_ts": last_fetch_ts})

            if snapshot["all_progress_done"]:
                log("all monitored progress files are done; watcher exiting")
                return 0

            codex_pid = state.get("codex_pid")
            codex_running = process_alive(int(codex_pid)) if codex_pid else False
            codex_exited = bool(codex_pid) and not codex_running
            active_log_path = Path(state["last_log_path"]) if state.get("last_log_path") else None
            latest_codex_message = refresh_latest_codex_message(state, state_file, active_log_path, log)
            stream_disconnected = codex_running and log_has_stream_disconnect(active_log_path)
            if codex_exited and state.get("last_exited_pid") != codex_pid:
                log(f"detected codex exit pid={codex_pid}; will relaunch on this sample if progress is not done")
                state["last_exited_pid"] = codex_pid
            if stream_disconnected:
                log(
                    "detected codex stream disconnect marker in log; "
                    f"pid={codex_pid} log={active_log_path}"
                )
                stop_codex_process(int(codex_pid), log)
                codex_running = False
                codex_exited = True
            sample_window = max(0, args.sample_seconds)
            log(
                "sample "
                f"window={sample_window}s changed={changed} "
                f"codex_pid={codex_pid or '-'} codex_running={codex_running} "
                f"stream_disconnected={stream_disconnected} "
                f"progress={summarize_progress(snapshot['progress'])} "
                f"latest_codex={latest_codex_message or '-'}"
            )

            last_launch_ts = float(state.get("last_launch_ts", 0.0) or 0.0)
            cooldown_ready = now - last_launch_ts >= args.codex_cooldown_seconds

            should_launch = codex_exited or (not changed and not codex_running and cooldown_ready)
            if should_launch:
                try:
                    launch = launch_codex(args, args.state_dir, log)
                except Exception as exc:  # noqa: BLE001
                    log(f"failed to launch codex: {exc}")
                else:
                    state.pop("last_observed_codex_message", None)
                    state["codex_pid"] = launch.pid
                    state["last_launch_ts"] = now
                    state["last_launch_snapshot_hash"] = snapshot_hash
                    state["last_command"] = launch.command
                    state["last_log_path"] = str(launch.log_path)
                    state["last_message_path"] = str(launch.last_message_path)
                    if launch.prompt_path:
                        state["prompt_path"] = str(launch.prompt_path)
                    save_state(state_file, {**state, "last_fetch_ts": last_fetch_ts})
                    if stream_disconnected:
                        log(
                            "relaunched codex architect after stream disconnect "
                            f"pid={launch.pid} log={launch.log_path} last_message={launch.last_message_path}"
                        )
                    elif codex_exited:
                        log(
                            "relaunched codex architect after exit "
                            f"pid={launch.pid} log={launch.log_path} last_message={launch.last_message_path}"
                        )
                    else:
                        log(
                            f"launched codex architect pid={launch.pid} "
                            f"log={launch.log_path} last_message={launch.last_message_path}"
                        )

            wake_reason = wait_for_next_cycle(
                args.sample_seconds,
                int(state["codex_pid"]) if state.get("codex_pid") else None,
                Path(state["last_message_path"]) if state.get("last_message_path") else None,
                Path(state["last_log_path"]) if state.get("last_log_path") else None,
                state,
                state_file,
                log,
            )
            if wake_reason in {"codex_exit", "last_message", "manual_sample"}:
                log(f"waking early for next sample: reason={wake_reason}")

        log("stop requested; watcher exiting")
        return 0
    finally:
        if STOP_REQUESTED:
            active_pid = state.get("codex_pid")
            if active_pid:
                stop_codex_process(int(active_pid), log)
            clear_runtime_state(state)
            save_state(state_file, state)
        restore_stdin(terminal_state)


if __name__ == "__main__":
    sys.exit(main())
