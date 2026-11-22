"""Изолированный процесс голосового ввода. В stdout пишутся события JSON."""

import json
import sys


def emit(kind, value=""):
    print(json.dumps([kind, value]), flush=True)


def main():
    try:
        from aurora.audio.input import select_device
        from aurora.audio.wake import listen

        device = select_device(None, sys.argv[1] or None)
        text = listen(device, 5, lambda state: emit("state", state))
        emit("text", text)
        return 0
    except Exception as error:
        emit("error", str(error))
        return 1


if __name__ == "__main__":
    sys.exit(main())
