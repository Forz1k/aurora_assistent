import sqlite3
from contextlib import closing
from pathlib import Path


class Facts:
    """Редактируемый пользователем список фактов для одной базы провайдера."""

    def __init__(self, path: Path):
        self.path = path

        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS memory "
                       "(id INTEGER PRIMARY KEY CHECK(id=1), facts TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO memory VALUES (1, '')")

    def read(self) -> str:
        with closing(sqlite3.connect(self.path)) as db:
            return db.execute("SELECT facts FROM memory WHERE id=1").fetchone()[0]

    def save(self, original: str, edited: str) -> None:
        facts = "\n".join(line.strip() for line in edited.splitlines() if line.strip())
        with closing(sqlite3.connect(self.path)) as db, db:
            changed = db.execute("UPDATE memory SET facts=? WHERE id=1 AND facts=?",
                                 (facts, original))
            if not changed.rowcount:
                raise ValueError("Память изменена в другом окне. Откройте её заново.")
