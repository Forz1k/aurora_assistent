"""Локальный кеш завершённых PCM-фрагментов, по тексту и профилю голоса."""

import hashlib
import sqlite3
from pathlib import Path


class AudioCache:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=2)
        self.db.execute("CREATE TABLE IF NOT EXISTS audio "
                        "(id INTEGER PRIMARY KEY, key TEXT UNIQUE, pcm BLOB NOT NULL)")

    @staticmethod
    def key(profile, text):
        return hashlib.sha256(f"{profile}\0{text}".encode()).hexdigest()

    def get(self, profile, text):
        row = self.db.execute("SELECT pcm FROM audio WHERE key=?", (self.key(profile, text),)).fetchone()
        return row[0] if row else None

    def put(self, profile, text, pcm):
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO audio(key,pcm) VALUES (?,?)",
                            (self.key(profile, text), pcm))
            self.db.execute("DELETE FROM audio WHERE id IN (SELECT id FROM "
                            "(SELECT id, SUM(length(pcm)) OVER (ORDER BY id DESC) size FROM audio) "
                            "WHERE size > 67108864)")
