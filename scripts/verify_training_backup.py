#!/usr/bin/env python3
"""Verify Shadow training-data backup health across both paths.

Checks:
    1. GitHub remote is configured on ~/dev/shadow-training-data and
       local `main` is in sync with `origin/main` after a fetch.
    2. /mnt/storage/backup/training-data/current symlink exists and
       points at a snapshot newer than 25 hours.
    3. Latest snapshot file count is within 10% of the live repo
       (catches rsync truncation bugs).
    4. Latest snapshot total size is within 10% of the live repo.

Exit codes:
    0 — all checks passed
    1 — one or more checks failed

Standalone: no Shadow imports, stdlib only, safe to run from cron/manual.
"""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

LIVE_REPO = Path.home() / "dev" / "shadow-training-data"
BACKUP_ROOT = Path("/mnt/storage/backup/training-data")
CURRENT_LINK = BACKUP_ROOT / "current"
EXPECTED_REMOTE_SUFFIX = "Apex-Shadow-Wraith/shadow-training-data"
STALENESS_HOURS = 25
TOLERANCE = 0.10  # 10%


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


def _run_git(args: list[str]) -> tuple[int, str, str]:
    """Run a git command in the live repo. Returns (rc, stdout, stderr)."""
    proc = subprocess.run(
        ["git", "-C", str(LIVE_REPO), *args],
        capture_output=True, text=True, timeout=30,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def check_github_sync() -> CheckResult:
    """Verify origin is set correctly and main matches origin/main after fetch."""
    if not LIVE_REPO.exists():
        return CheckResult(
            "GitHub sync", False,
            f"Live repo not found at {LIVE_REPO}",
        )

    rc, stdout, _ = _run_git(["remote", "get-url", "origin"])
    if rc != 0:
        return CheckResult(
            "GitHub sync", False,
            "No 'origin' remote configured.",
        )
    origin_url = stdout
    if EXPECTED_REMOTE_SUFFIX not in origin_url:
        return CheckResult(
            "GitHub sync", False,
            f"origin points at unexpected repo: {origin_url}",
        )

    rc, _, stderr = _run_git(["fetch", "--quiet", "origin", "main"])
    if rc != 0:
        return CheckResult(
            "GitHub sync", False,
            f"git fetch origin main failed: {stderr or 'unknown'}",
        )

    rc, local_sha, _ = _run_git(["rev-parse", "main"])
    if rc != 0:
        return CheckResult(
            "GitHub sync", False, "Local branch 'main' not found.",
        )
    rc, remote_sha, _ = _run_git(["rev-parse", "origin/main"])
    if rc != 0:
        return CheckResult(
            "GitHub sync", False, "origin/main not resolvable after fetch.",
        )

    if local_sha != remote_sha:
        rc, ahead_behind, _ = _run_git([
            "rev-list", "--left-right", "--count", "main...origin/main",
        ])
        return CheckResult(
            "GitHub sync", False,
            f"main out of sync with origin/main (ahead/behind: {ahead_behind or 'unknown'}).",
        )

    return CheckResult(
        "GitHub sync", True,
        f"origin={origin_url}, main@{local_sha[:8]} in sync with origin/main.",
    )


def check_snapshot_freshness() -> CheckResult:
    """Verify `current` symlink exists, resolves, and target is <25h old."""
    if not CURRENT_LINK.is_symlink():
        return CheckResult(
            "Snapshot freshness", False,
            f"{CURRENT_LINK} is not a symlink (or missing).",
        )

    target = CURRENT_LINK.resolve()
    if not target.exists() or not target.is_dir():
        return CheckResult(
            "Snapshot freshness", False,
            f"current -> {target} does not resolve to an existing directory.",
        )

    # Use the target dir's mtime (rsync updates it on every write).
    mtime = datetime.fromtimestamp(target.stat().st_mtime, tz=timezone.utc)
    age = datetime.now(timezone.utc) - mtime
    age_hours = age.total_seconds() / 3600

    if age_hours > STALENESS_HOURS:
        return CheckResult(
            "Snapshot freshness", False,
            f"Latest snapshot {target.name} is {age_hours:.1f}h old "
            f"(threshold {STALENESS_HOURS}h).",
        )

    return CheckResult(
        "Snapshot freshness", True,
        f"current -> {target.name} ({age_hours:.1f}h old).",
    )


def _count_files_and_bytes(root: Path) -> tuple[int, int]:
    """Count regular files and sum their sizes under root. Follows no symlinks."""
    count = 0
    total_bytes = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # Skip nothing — rsync preserves .git too, so we compare like-for-like.
        for fname in filenames:
            fpath = Path(dirpath) / fname
            try:
                st = fpath.lstat()
            except OSError:
                continue
            # Skip symlinks themselves (rsync -a preserves them, but we
            # count regular files only for consistent comparison).
            import stat as _stat
            if _stat.S_ISREG(st.st_mode):
                count += 1
                total_bytes += st.st_size
    return count, total_bytes


def check_snapshot_completeness() -> CheckResult:
    """Verify latest snapshot's file count and total size are within 10% of live."""
    if not CURRENT_LINK.is_symlink():
        return CheckResult(
            "Snapshot completeness", False,
            "current symlink missing — cannot compare.",
        )
    target = CURRENT_LINK.resolve()
    if not target.is_dir():
        return CheckResult(
            "Snapshot completeness", False,
            f"Snapshot target {target} is not a directory.",
        )

    if not LIVE_REPO.is_dir():
        return CheckResult(
            "Snapshot completeness", False,
            f"Live repo {LIVE_REPO} not found.",
        )

    live_count, live_bytes = _count_files_and_bytes(LIVE_REPO)
    snap_count, snap_bytes = _count_files_and_bytes(target)

    if live_count == 0:
        return CheckResult(
            "Snapshot completeness", False,
            "Live repo has 0 files — something is wrong upstream.",
        )

    count_delta = abs(snap_count - live_count) / live_count
    bytes_delta = (
        abs(snap_bytes - live_bytes) / live_bytes if live_bytes > 0 else 0.0
    )

    count_ok = count_delta <= TOLERANCE
    bytes_ok = bytes_delta <= TOLERANCE

    detail = (
        f"files: snap={snap_count} live={live_count} "
        f"(Δ {count_delta:.1%}); "
        f"bytes: snap={snap_bytes:,} live={live_bytes:,} "
        f"(Δ {bytes_delta:.1%})."
    )

    if count_ok and bytes_ok:
        return CheckResult("Snapshot completeness", True, detail)

    failures = []
    if not count_ok:
        failures.append(f"file count off by {count_delta:.1%}")
    if not bytes_ok:
        failures.append(f"byte size off by {bytes_delta:.1%}")
    return CheckResult(
        "Snapshot completeness", False,
        f"{'; '.join(failures)} (tolerance {TOLERANCE:.0%}). {detail}",
    )


def main() -> int:
    checks = [
        check_github_sync(),
        check_snapshot_freshness(),
        check_snapshot_completeness(),
    ]

    print("=" * 68)
    print("Shadow training-data backup verification")
    print(f"Run at: {datetime.now().isoformat(timespec='seconds')}")
    print("=" * 68)

    width = max(len(c.name) for c in checks)
    for c in checks:
        status = "PASS" if c.passed else "FAIL"
        print(f"  [{status}]  {c.name.ljust(width)}  {c.detail}")

    print("-" * 68)
    passed = sum(1 for c in checks if c.passed)
    total = len(checks)
    all_ok = passed == total
    verdict = "ALL CHECKS PASSED" if all_ok else f"{total - passed} CHECK(S) FAILED"
    print(f"Result: {passed}/{total}  —  {verdict}")
    print("=" * 68)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
