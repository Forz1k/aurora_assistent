"""Aurora Voice Studio: подготовка WAV-реплик и черновых транскрипций."""

import argparse
import csv
import html
import subprocess
import wave
from pathlib import Path
from tempfile import TemporaryDirectory

import imageio_ffmpeg
from faster_whisper.audio import decode_audio
from faster_whisper.vad import VadOptions, get_speech_timestamps

from aurora.audio.stt import load_model


def prepare(source: Path, destination: Path):
    source = source.resolve(strict=True)
    if destination.exists():
        raise FileExistsError(f"Выберите новую папку: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=destination.parent) as temp:
        project = Path(temp) / "project"
        clips = project / "clips"
        clips.mkdir(parents=True)
        master = project / "source.wav"
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-nostdin", "-v", "error",
                        "-i", str(source), "-map", "0:a:0", "-c:a", "pcm_s16le", str(master)],
                       check=True)
        audio = decode_audio(str(master), sampling_rate=16000)
        spans = get_speech_timestamps(audio, VadOptions(min_speech_duration_ms=150,
                                      min_silence_duration_ms=480, speech_pad_ms=150,
                                      max_speech_duration_s=18))
        if not spans:
            raise ValueError("Речь не обнаружена.")
        print(f"Фрагментов для транскрипции: {len(spans)}", flush=True)
        model = load_model()
        rows = []
        with wave.open(str(master)) as recording:
            rate = recording.getframerate()
            for number, span in enumerate(spans, 1):
                first, last = span["start"], span["end"]
                start = round(first * rate / 16000)
                end = min(round(last * rate / 16000), recording.getnframes())
                recording.setpos(start)
                filename = f"clips/{number:04d}.wav"
                with wave.open(str(project / filename), "wb") as clip:
                    clip.setparams(recording.getparams())
                    clip.writeframes(recording.readframes(end - start))
                segments, _ = model.transcribe(audio[first:last], language="ru", beam_size=1,
                                               condition_on_previous_text=False)
                text = " ".join(s.text.strip() for s in segments).strip()
                rows.append((filename, round(start/rate, 3), round(end/rate, 3), text, "не проверено"))
                if number % 25 == 0:
                    print(f"Обработано {number}/{len(spans)}", flush=True)
        with (project / "manifest.csv").open("w", newline="", encoding="utf-8-sig") as out:
            writer = csv.writer(out, delimiter=";")
            writer.writerow(("файл", "начало_с", "конец_с", "транскрипция", "статус"))
            writer.writerows(rows)
        with (project / "review.html").open("w", encoding="utf-8") as out:
            out.write('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Проверка реплик</title>'
                      '<h1>Проверка реплик</h1><p>Исправления текста и статус сохраните в manifest.csv.</p>')
            for file, start, end, text, _ in rows:
                out.write(f'<p><b>{file} · {start:.2f}–{end:.2f} с</b><br>{html.escape(text)}<br>'
                          f'<audio controls preload="none" src="{file}"></audio></p>')
            out.write('</html>')
        project.rename(destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    prepare(args.source, args.destination)
