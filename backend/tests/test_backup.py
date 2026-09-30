import sqlite3
from pathlib import Path

import pytest

from scripts.sqlite_copy import verified_copy


def test_live_wal_backup_and_isolated_restore(tmp_path: Path):
    database = tmp_path / "live.db"
    backup = tmp_path / "backup.db"
    restored = tmp_path / "restore.db"
    with sqlite3.connect(database) as live:
        live.execute("PRAGMA journal_mode=WAL")
        live.execute("CREATE TABLE alembic_version (version_num TEXT NOT NULL)")
        live.execute("INSERT INTO alembic_version VALUES ('004_review_events')")
        live.execute("CREATE TABLE review_events (note TEXT NOT NULL)")
        live.execute("INSERT INTO review_events VALUES ('saved decision')")
        live.commit()
        verified_copy(database, backup)
        live.execute("INSERT INTO review_events VALUES ('later decision')")
        live.commit()

    verified_copy(backup, restored)
    with sqlite3.connect(restored) as copy:
        assert copy.execute("SELECT note FROM review_events").fetchall() == [("saved decision",)]
        assert copy.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    with pytest.raises(ValueError, match="already exists"):
        verified_copy(backup, restored)
