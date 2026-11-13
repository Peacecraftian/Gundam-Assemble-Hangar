import json
import os
import sqlite3
from pathlib import Path

from .match import Match


UNDO_LIMIT = 20
LOCAL_SCENARIO_PREFIX = "local-"


def default_save_path():
    directory = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    return directory / "Gundam Assemble Companion" / "match.sqlite3"


class SaveConflict(ValueError):
    """The save changed since this window last loaded it."""


class MatchStore:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        try:
            with self.db:
                version = self.db.execute("PRAGMA user_version").fetchone()[0]
                if version not in (0, 1):
                    raise ValueError("This save was made by a newer version of the companion.")
                self.db.execute("""
                    CREATE TABLE IF NOT EXISTS current_match (
                        id INTEGER PRIMARY KEY CHECK (id = 1),
                        revision INTEGER NOT NULL,
                        payload TEXT NOT NULL
                    )
                """)
                self.db.execute("""
                    CREATE TABLE IF NOT EXISTS undo (
                        id INTEGER PRIMARY KEY,
                        payload TEXT NOT NULL
                    )
                """)
                self.db.execute("""
                    CREATE TABLE IF NOT EXISTS scenarios (
                        id TEXT PRIMARY KEY NOT NULL,
                        revision INTEGER NOT NULL,
                        payload TEXT NOT NULL
                    )
                """)
                self.db.execute("PRAGMA user_version = 1")
        except Exception:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def _current(self):
        return self.db.execute("SELECT revision, payload FROM current_match WHERE id = 1").fetchone()

    def load(self):
        row = self._current()
        return (Match.from_json(row[1]), row[0]) if row else (None, 0)

    def load_scenarios(self):
        rows = self.db.execute("SELECT payload, revision FROM scenarios ORDER BY rowid").fetchall()
        return [(json.loads(payload), revision) for payload, revision in rows]

    def save_scenario(self, scenario, expected_revision):
        payload = json.dumps(scenario, ensure_ascii=False)
        with self.db:
            if expected_revision == 0:
                self.db.execute(
                    "INSERT INTO scenarios (id, revision, payload) VALUES (?, 1, ?)", (scenario["id"], payload),
                )
            else:
                updated = self.db.execute("""
                    UPDATE scenarios SET payload = ?, revision = revision + 1
                    WHERE id = ? AND revision = ?
                """, (payload, scenario["id"], expected_revision))
                if not updated.rowcount:
                    raise SaveConflict("This scenario changed in another window. Cancel and reopen it to see the latest version.")

    def delete_scenario(self, scenario_id, expected_revision):
        if expected_revision <= 0 or not scenario_id.startswith(LOCAL_SCENARIO_PREFIX):
            raise ValueError("Only saved local scenarios can be deleted.")
        with self.db:
            deleted = self.db.execute(
                "DELETE FROM scenarios WHERE id = ? AND revision = ?", (scenario_id, expected_revision),
            )
            if not deleted.rowcount:
                raise SaveConflict("This scenario changed in another window. Cancel and reopen it to see the latest version.")

    def can_undo(self):
        return self.db.execute("SELECT 1 FROM undo LIMIT 1").fetchone() is not None

    def _require_revision(self, expected_revision):
        current = self._current()
        revision = current[0] if current else 0
        if revision != expected_revision:
            raise SaveConflict("The match changed in another window. The latest save has been reloaded.")
        return current

    def _write(self, revision, payload):
        self.db.execute("""
            INSERT INTO current_match (id, revision, payload) VALUES (1, ?, ?)
            ON CONFLICT (id) DO UPDATE SET revision = excluded.revision, payload = excluded.payload
        """, (revision, payload))

    def save(self, match, expected_revision, *, replace=False):
        payload = match.to_json()
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            current = self._require_revision(expected_revision)
            if replace:
                self.db.execute("DELETE FROM undo")
            elif current:
                if current[1] == payload:
                    return expected_revision
                self.db.execute("INSERT INTO undo (payload) VALUES (?)", (current[1],))
                self.db.execute("""
                    DELETE FROM undo WHERE id NOT IN (SELECT id FROM undo ORDER BY id DESC LIMIT ?)
                """, (UNDO_LIMIT,))
            revision = expected_revision + 1
            self._write(revision, payload)
        return revision

    def undo(self, expected_revision):
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            self._require_revision(expected_revision)
            previous = self.db.execute("SELECT id, payload FROM undo ORDER BY id DESC LIMIT 1").fetchone()
            if previous is None:
                return self.load()
            match = Match.from_json(previous[1])
            revision = expected_revision + 1
            self._write(revision, previous[1])
            self.db.execute("DELETE FROM undo WHERE id = ?", (previous[0],))
        return match, revision
