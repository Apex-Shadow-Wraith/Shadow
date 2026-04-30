"""Tests for main.py wrappers — narrow scope, only the parts exercised
by the daemon-coupled boot path.

B3: _check_training_backup_freshness is now a thin reader over
data/void_latest.json. The Void daemon owns the freshness probe.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import pytest


def _write_void_state(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def test_backup_check_silent_when_fresh(tmp_path, monkeypatch, caplog):
    """status='fresh' produces no warnings."""
    monkeypatch.chdir(tmp_path)
    _write_void_state(
        tmp_path / "data" / "void_latest.json",
        {"backup_status": "fresh", "backup_age_hours": 4.5,
         "backup_target": "snap-1", "backup_error": None},
    )
    from main import _check_training_backup_freshness

    logger = logging.getLogger("test.boot")
    with caplog.at_level(logging.WARNING):
        _check_training_backup_freshness(logger)
    assert not any("backup" in r.getMessage().lower() for r in caplog.records)


def test_backup_check_silent_when_not_configured(tmp_path, monkeypatch, caplog):
    """status='not_configured' is intentional silence (backup mount absent)."""
    monkeypatch.chdir(tmp_path)
    _write_void_state(
        tmp_path / "data" / "void_latest.json",
        {"backup_status": "not_configured", "backup_age_hours": None,
         "backup_target": None, "backup_error": None},
    )
    from main import _check_training_backup_freshness

    with caplog.at_level(logging.WARNING):
        _check_training_backup_freshness(logging.getLogger("test.boot"))
    assert not any("backup" in r.getMessage().lower() for r in caplog.records)


def test_backup_check_warns_on_stale(tmp_path, monkeypatch, caplog):
    """status='stale' emits the >48h warning the old inline check produced."""
    monkeypatch.chdir(tmp_path)
    _write_void_state(
        tmp_path / "data" / "void_latest.json",
        {"backup_status": "stale", "backup_age_hours": 72.5,
         "backup_target": "snap-old", "backup_error": None},
    )
    from main import _check_training_backup_freshness

    with caplog.at_level(logging.WARNING):
        _check_training_backup_freshness(logging.getLogger("test.boot"))
    msgs = [r.getMessage() for r in caplog.records]
    assert any("STALE" in m and "72.5" in m for m in msgs), msgs


def test_backup_check_warns_on_missing_symlink(tmp_path, monkeypatch, caplog):
    """status='missing' (symlink absent) warns to investigate timer."""
    monkeypatch.chdir(tmp_path)
    _write_void_state(
        tmp_path / "data" / "void_latest.json",
        {"backup_status": "missing", "backup_age_hours": None,
         "backup_target": None, "backup_error": None},
    )
    from main import _check_training_backup_freshness

    with caplog.at_level(logging.WARNING):
        _check_training_backup_freshness(logging.getLogger("test.boot"))
    assert any(
        "symlink missing" in r.getMessage()
        for r in caplog.records
    )


def test_backup_check_skips_when_state_file_missing(tmp_path, monkeypatch, caplog):
    """No void_latest.json → log skip + return cleanly (Void might be down)."""
    monkeypatch.chdir(tmp_path)
    # No state file written.
    from main import _check_training_backup_freshness

    with caplog.at_level(logging.WARNING):
        _check_training_backup_freshness(logging.getLogger("test.boot"))
    assert any(
        "Void daemon" in r.getMessage() for r in caplog.records
    )


def test_backup_check_skips_when_state_file_stale(tmp_path, monkeypatch, caplog):
    """State file older than 2× tick interval → log skip + return."""
    monkeypatch.chdir(tmp_path)
    state = tmp_path / "data" / "void_latest.json"
    _write_void_state(state, {
        "backup_status": "fresh",  # would normally be silent, but file is stale
        "backup_age_hours": 1.0,
        "backup_target": "snap-x",
        "backup_error": None,
    })
    # Backdate file mtime to 5 minutes ago (> 120s threshold).
    old = state.stat().st_mtime - 300
    os.utime(state, (old, old))

    from main import _check_training_backup_freshness

    with caplog.at_level(logging.WARNING):
        _check_training_backup_freshness(logging.getLogger("test.boot"))
    assert any(
        "Void daemon may be stopped" in r.getMessage()
        for r in caplog.records
    )
