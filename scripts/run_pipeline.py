#!/usr/bin/env python3
"""Run the standalone public data pipeline.

Lock handling and runtime-status reporting are ported from
Harmonica-in-Taiwan's run_pipeline.py: a stale-aware lock file keeps
overlapping scheduled ticks from colliding, and every step's state is
written to site/api/pipeline-runtime.json so the /status/ page (and anyone
curl-ing the API) can see what the pipeline is doing right now.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
DEFAULT_LOCK_FILE = PROJECT_ROOT / "state" / "run_pipeline.lock"
DEFAULT_RUNTIME_STATUS = PROJECT_ROOT / "site" / "api" / "pipeline-runtime.json"


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def parse_time(value: object) -> dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def write_json_atomic(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def process_is_running(pid: object) -> bool:
    try:
        value = int(pid)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    if value <= 0:
        return False
    try:
        os.kill(value, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def load_lock(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def lock_is_stale(info: dict[str, object], *, stale_after: dt.timedelta, now: dt.datetime) -> bool:
    if not process_is_running(info.get("pid")):
        return True
    started_at = parse_time(info.get("started_at"))
    return started_at is None or now - started_at > stale_after


def acquire_lock(path: Path, *, stale_after_minutes: float) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    now = utc_now()
    stale_after = dt.timedelta(minutes=max(1.0, stale_after_minutes))
    lock_info = {"pid": os.getpid(), "started_at": now.isoformat()}

    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            existing = load_lock(path)
            if lock_is_stale(existing, stale_after=stale_after, now=now):
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
                continue
            print(
                "Pipeline already running; skipping this scheduled tick "
                f"(lock={path}, pid={existing.get('pid')}, started_at={existing.get('started_at')})."
            )
            return False
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(lock_info, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        return True


def release_lock(path: Path) -> None:
    existing = load_lock(path)
    if existing.get("pid") == os.getpid():
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-watch", action="store_true", help="Skip fetching new posts; rebuild site from existing data only.")
    parser.add_argument("--skip-youtube", action="store_true")
    parser.add_argument("--skip-facebook-apify", action="store_true")
    parser.add_argument("--skip-official-site", action="store_true")
    parser.add_argument("--full-refresh", action="store_true", help="Ignore per-source fetch intervals.")
    parser.add_argument("--max-post-age-days", type=int, default=30)
    parser.add_argument("--publish-pages", action="store_true")
    parser.add_argument("--pages-no-push", action="store_true")
    parser.add_argument("--skip-data-restore", action="store_true", help="Use existing local pipeline data without restoring the data branch first.")
    parser.add_argument("--data-no-push", action="store_true", help="Commit pipeline data only to the local data branch.")
    parser.add_argument("--lock-file", type=Path, default=DEFAULT_LOCK_FILE)
    parser.add_argument("--lock-stale-minutes", type=float, default=240.0)
    parser.add_argument("--runtime-status", type=Path, default=DEFAULT_RUNTIME_STATUS)
    parser.add_argument("--no-lock", action="store_true")
    args = parser.parse_args()

    lock_path = args.lock_file if args.lock_file.is_absolute() else PROJECT_ROOT / args.lock_file
    runtime_status_path = args.runtime_status if args.runtime_status.is_absolute() else PROJECT_ROOT / args.runtime_status
    started_at = utc_now()
    step_states: dict[str, dict[str, object]] = {}
    current_step_label = ""

    def publish_runtime_status(status: str, *, current_step: str = "", message: str = "", returncode: int | None = None) -> None:
        payload: dict[str, object] = {
            "version": 1,
            "status": status,
            "pid": os.getpid(),
            "startedAt": started_at.isoformat(),
            "heartbeatAt": utc_now().isoformat(),
            "currentStep": current_step,
            "message": message,
            "maxPostAgeDays": int(args.max_post_age_days),
            "steps": list(step_states.values()),
        }
        if returncode is not None:
            payload["returnCode"] = returncode
        write_json_atomic(runtime_status_path, payload)

    def mark_step(label: str, status: str, *, command: list[str], returncode: int | None = None) -> None:
        nonlocal current_step_label
        current_step_label = label
        now_iso = utc_now().isoformat()
        entry = step_states.setdefault(
            label,
            {"name": label, "command": command, "status": "pending", "startedAt": "", "finishedAt": "", "returnCode": None},
        )
        if status == "running":
            if entry["status"] != "running":
                entry["startedAt"] = now_iso
            entry["status"] = "running"
            entry["finishedAt"] = ""
            entry["returnCode"] = None
            publish_runtime_status("running", current_step=label)
            return
        entry["status"] = status
        entry["finishedAt"] = now_iso
        entry["returnCode"] = returncode
        if status == "failed":
            publish_runtime_status("failed", current_step=label, message=f"{label} failed", returncode=returncode)
        else:
            publish_runtime_status("running", current_step=label, returncode=returncode)

    def run(command: list[str], *, step: str, optional: bool = False) -> None:
        mark_step(step, "running", command=command)
        result = subprocess.run(command, cwd=PROJECT_ROOT)
        if result.returncode:
            mark_step(step, "optional_failed" if optional else "failed", command=command, returncode=result.returncode)
            if optional:
                print(f"Optional pipeline step failed with exit code {result.returncode}: {' '.join(command)}", file=sys.stderr)
            else:
                raise subprocess.CalledProcessError(result.returncode, command)
        else:
            mark_step(step, "ok", command=command, returncode=0)

    locked = args.no_lock or acquire_lock(lock_path, stale_after_minutes=args.lock_stale_minutes)
    if not locked:
        return 0

    publish_runtime_status("running", message="Pipeline started")
    completed = False
    try:
        if not args.skip_data_restore:
            run([PYTHON, "scripts/sync_pipeline_data.py", "restore"], step="restore pipeline data")
        run([PYTHON, "scripts/build_social_sources.py"], step="build social sources")

        if not args.skip_watch:
            rsshub_args = [PYTHON, "scripts/rsshub_fetcher.py"]
            if args.full_refresh:
                rsshub_args.append("--full-refresh")
            run(rsshub_args, step="fetch rsshub", optional=True)
            if not args.skip_youtube:
                run([PYTHON, "scripts/youtube_ytdlp_fetcher.py"], step="fetch youtube", optional=True)
            if not args.skip_facebook_apify:
                run([PYTHON, "scripts/apify_facebook_fetcher.py"], step="fetch facebook apify", optional=True)
            if not args.skip_official_site:
                run([PYTHON, "scripts/official_site_fetcher.py"], step="fetch official sites", optional=True)
            run(
                [PYTHON, "scripts/social_feed_watchdog.py", "--max-post-age-days", str(args.max_post_age_days)],
                step="watch social feeds",
            )

        run([PYTHON, "scripts/fetch_media_cache.py"], step="cache media", optional=True)
        run([PYTHON, "scripts/classify_topics.py"], step="classify topics")
        run([PYTHON, "scripts/classify_context.py"], step="classify post context")
        run([PYTHON, "scripts/build_public_data.py"], step="build public data")
        run([PYTHON, "scripts/build_spectrum.py"], step="build spectrum")
        run([PYTHON, "scripts/build_qualitative.py"], step="build qualitative comparisons")
        run([PYTHON, "scripts/generate_rss_feeds.py"], step="generate rss feeds")
        run([PYTHON, "scripts/build_status_page.py"], step="build status page")
        run([PYTHON, "scripts/generate_site_pages.py"], step="generate site pages")
        run([PYTHON, "scripts/generate_seo_pages.py"], step="generate SEO pages")
        run([PYTHON, "scripts/check_source_coverage.py"], step="check source coverage")
        run([PYTHON, "scripts/validate_public_outputs.py"], step="validate public outputs")

        data_args = [PYTHON, "scripts/sync_pipeline_data.py", "publish"]
        if args.data_no_push:
            data_args.append("--no-push")
        run(data_args, step="publish pipeline data")

        if args.publish_pages:
            pages_args = [PYTHON, "scripts/publish_github_pages.py"]
            if args.pages_no_push:
                pages_args.append("--no-push")
            publish_runtime_status("ok", message="Pipeline completed; publishing snapshot")
            run(pages_args, step="publish github pages")
        completed = True
        publish_runtime_status("ok", message="Pipeline completed")
    finally:
        if not args.no_lock:
            release_lock(lock_path)
        if not completed:
            publish_runtime_status("failed", current_step=current_step_label, message="Pipeline stopped before completion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
