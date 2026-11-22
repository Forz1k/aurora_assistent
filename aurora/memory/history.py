import sqlite3
from contextlib import closing
from pathlib import Path


class History:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS turns "
                       "(id INTEGER PRIMARY KEY, question TEXT NOT NULL, answer TEXT NOT NULL)")

    def messages(self):
        messages = []
        with closing(sqlite3.connect(self.path)) as db:
            for question, answer in db.execute("SELECT question, answer FROM turns ORDER BY id"):
                messages.extend(({"role": "user", "content": question},
                                 {"role": "assistant", "content": answer}))
        return messages

    def append(self, question, answer):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO turns(question, answer) VALUES (?, ?)", (question, answer))
