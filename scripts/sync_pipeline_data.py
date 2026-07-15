#!/usr/bin/env python3
"""Restore and publish pipeline-owned data on the dedicated data branch."""

from __future__ import annotations

import argparse
import datetime as dt
import shutil
import subprocess
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_BRANCH = "data"
DATA_FILES = (
    Path("data/feeds/social_feed_inbox.jsonl"),
    Path("data/feeds/social_candidates.jsonl"),
    Path("data/feeds/source_profiles.json"),
)


class DataSyncError(RuntimeError):
    pass


def git(*args: str, cwd: Path = PROJECT_ROOT, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def ref_exists(ref: str) -> bool:
    return git("rev-parse", "--verify", "--quiet", ref, check=False).returncode == 0


def resolve_data_ref(remote: str) -> str | None:
    remote_ref = f"refs/remotes/{remote}/{DATA_BRANCH}"
    local_ref = f"refs/heads/{DATA_BRANCH}"
    if ref_exists(remote_ref):
        return remote_ref
    if ref_exists(local_ref):
        return local_ref
    return None


def resolve_publish_ref(remote: str, *, push: bool) -> str | None:
    local_ref = f"refs/heads/{DATA_BRANCH}"
    if not push and ref_exists(local_ref):
        return local_ref
    return resolve_data_ref(remote)


def fetch_data_branch(remote: str) -> None:
    result = git("fetch", remote, f"{DATA_BRANCH}:refs/remotes/{remote}/{DATA_BRANCH}", check=False)
    if result.returncode and not resolve_data_ref(remote):
        raise DataSyncError(result.stderr.strip() or f"Could not fetch {remote}/{DATA_BRANCH}")


def restore(remote: str, *, fetch: bool) -> None:
    if fetch:
        fetch_data_branch(remote)
    ref = resolve_data_ref(remote)
    if ref is None:
        raise DataSyncError(f"Data branch not found: {remote}/{DATA_BRANCH}")

    for relative_path in DATA_FILES:
        result = git("show", f"{ref}:{relative_path.as_posix()}", check=False)
        if result.returncode:
            raise DataSyncError(f"Missing {relative_path} on {ref}")
        destination = PROJECT_ROOT / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(result.stdout, encoding="utf-8")
    print(f"Restored {len(DATA_FILES)} pipeline data files from {ref}.")


def publish(remote: str, *, push: bool) -> None:
    missing = [str(path) for path in DATA_FILES if not (PROJECT_ROOT / path).is_file()]
    if missing:
        raise DataSyncError(f"Cannot publish missing pipeline data: {', '.join(missing)}")

    fetch_data_branch(remote)
    ref = resolve_publish_ref(remote, push=push)
    if ref is None:
        raise DataSyncError(f"Data branch not found: {remote}/{DATA_BRANCH}")

    with tempfile.TemporaryDirectory(prefix="mayor2026-data-") as tmp:
        worktree = Path(tmp)
        git("worktree", "add", "--detach", str(worktree), ref)
        try:
            for relative_path in DATA_FILES:
                destination = worktree / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(PROJECT_ROOT / relative_path, destination)

            git("add", *[path.as_posix() for path in DATA_FILES], cwd=worktree)
            if git("diff", "--cached", "--quiet", cwd=worktree, check=False).returncode == 0:
                print("Pipeline data branch is already up to date.")
                return

            now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
            git("commit", "-m", f"Update pipeline data {now}", cwd=worktree)
            full_commit = git("rev-parse", "HEAD", cwd=worktree).stdout.strip()
            commit = full_commit[:7]
            if push:
                git("push", remote, f"HEAD:refs/heads/{DATA_BRANCH}", cwd=worktree)
            git("update-ref", f"refs/heads/{DATA_BRANCH}", full_commit, cwd=PROJECT_ROOT)
            print(f"Published pipeline data commit {commit} (pushed={push}).")
        finally:
            git("worktree", "remove", "--force", str(worktree), check=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("restore", "publish"))
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--no-fetch", action="store_true", help="Restore from the existing local data ref.")
    parser.add_argument("--no-push", action="store_true", help="Create/update only the local data branch.")
    args = parser.parse_args()

    try:
        if args.action == "restore":
            restore(args.remote, fetch=not args.no_fetch)
        else:
            publish(args.remote, push=not args.no_push)
    except (DataSyncError, subprocess.CalledProcessError) as exc:
        detail = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) and exc.stderr else str(exc)
        print(f"sync_pipeline_data.py: {detail}", file=__import__("sys").stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
