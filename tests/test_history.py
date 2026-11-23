import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from aurora.memory.history import History


def test_independent_writers_and_restart(tmp_path):
    path = tmp_path / "chat.sqlite3"
    first = History(path)
    second = History(path)
    first.append("Первый вопрос\nс продолжением", "Ответ «Авроры»")
    with ThreadPoolExecutor(max_workers=2) as pool:
        writes = [pool.submit(history.append, f"Вопрос {i}", f"Ответ {i}")
                  for i, history in enumerate((first, second))]
        for write in writes:
            write.result()

    result = subprocess.run(
        [sys.executable, "-c",
         "import json, sys; from pathlib import Path; from aurora.memory.history import History; "
         "print(json.dumps(History(Path(sys.argv[1])).messages()))", str(path)],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, check=True,
    )
    messages = json.loads(result.stdout)
    assert [m["role"] for m in messages] == ["user", "assistant"] * 3
    assert messages[0]["content"] == "Первый вопрос\nс продолжением"
    assert messages[1]["content"] == "Ответ «Авроры»"
    assert {(messages[i]["content"], messages[i + 1]["content"]) for i in (2, 4)} == {
        ("Вопрос 0", "Ответ 0"), ("Вопрос 1", "Ответ 1")
    }
