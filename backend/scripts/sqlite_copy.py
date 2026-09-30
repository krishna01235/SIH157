"""Create or restore a consistent SQLite database copy, including live WAL data."""

import argparse
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path


def verified_copy(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise ValueError(f"Source database does not exist: {source}")
    if destination.exists():
        raise ValueError(f"Destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        prefix=f".{destination.name}.", suffix=".partial", dir=destination.parent, delete=False,
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        source_connection = sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro", uri=True)
        target_connection = sqlite3.connect(temporary_path)
        with closing(source_connection) as original, closing(target_connection) as copy:
            original.backup(copy)
            copy.execute("PRAGMA journal_mode=DELETE")
            if copy.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise ValueError("Copied database failed its integrity check")
            if copy.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise ValueError("Copied database has broken references")
            if copy.execute("SELECT version_num FROM alembic_version").fetchone() is None:
                raise ValueError("Copied database has no migration revision")
        temporary_path.rename(destination)
    finally:
        temporary_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("backup", "restore"))
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    verified_copy(args.source, args.destination)
    print(f"{args.mode} verified: {args.destination}")


if __name__ == "__main__":
    main()
