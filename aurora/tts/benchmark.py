"""Измерение одного прогона TTS в отдельном процессе Windows."""

import argparse
import json
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDIO = ROOT / "data/voice-studio"
PHRASE = "Аврора на связи. Проверка микрофона завершена."


def benchmark(engine, output, reference, transcript):
    start = time.perf_counter()
    if engine == "piper":
        import win32api
        import win32process
        from piper import PiperVoice
        piper_model = ROOT / "data/voices/ru_RU-irina-medium.onnx"

        model = PiperVoice.load(piper_model, use_cuda=False)
        loaded = time.perf_counter()
        with wave.open(str(output), "wb") as wav:
            model.synthesize_wav(PHRASE, wav)
        peak = win32process.GetProcessMemoryInfo(win32api.GetCurrentProcess())["PeakWorkingSetSize"]
    else:
        import psutil
        import soundfile as sf
        import torch
        from qwen_tts import Qwen3TTSModel

        torch.set_num_threads(8)
        torch.manual_seed(42)
        model = Qwen3TTSModel.from_pretrained(str(STUDIO / "qwen-base"), device_map="cpu",
                                              dtype=torch.float32, attn_implementation="eager")
        loaded = time.perf_counter()
        wavs, rate = model.generate_voice_clone(text=PHRASE, language="Russian",
                                               ref_audio=str(reference), ref_text=transcript,
                                               x_vector_only_mode=engine == "qwen-vector",
                                               max_new_tokens=160)
        sf.write(output, wavs[0], rate, subtype="PCM_16")
        peak = psutil.Process().memory_info().peak_wset
    end = time.perf_counter()
    with wave.open(str(output)) as wav:
        duration = wav.getnframes() / wav.getframerate()
    return dict(engine=engine, phrase=PHRASE, device="cpu", reference=str(reference) if reference else None,
                reference_text=transcript, load_s=round(loaded-start, 3), synthesis_s=round(end-loaded, 3),
                audio_s=round(duration, 3), rtf=round((end-loaded)/duration, 3),
                peak_working_set_mib=round(peak/1024**2, 1))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", choices=["piper", "qwen-vector", "qwen-icl"])
    parser.add_argument("output", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--transcript")
    args = parser.parse_args()
    if args.engine.startswith("qwen") and not args.reference:
        parser.error("Укажите --reference.")
    if args.engine == "qwen-icl" and not args.transcript:
        parser.error("Укажите --transcript.")
    if args.output.exists() or args.output.with_suffix(".json").exists():
        parser.error("Выберите новый путь результата.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = benchmark(args.engine, args.output, args.reference, args.transcript)
    report = json.dumps(result, ensure_ascii=False, indent=2)
    args.output.with_suffix(".json").write_text(report, encoding="utf-8")
    print(report)
