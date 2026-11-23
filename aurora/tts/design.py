"""Русский разговорный профиль Qwen VoiceDesign для автономного CPU-синтеза."""

import os
from pathlib import Path

STUDIO = Path(__file__).resolve().parents[2] / "data/voice-studio"
DIRECTORY = STUDIO / "qwen-design"
PYTHON = STUDIO / "qwen-env/Scripts/python.exe"
SPEAKER = "aurora-design"
RATE = 24000
STYLE = (
    "A warm adult female voice speaking native standard Russian, in a relaxed "
    "one-to-one conversation. A clear, soft mid-range timbre with gentle resonance. "
    "Let the meaning guide the emphasis, vary the rhythm naturally, and leave small "
    "pauses between thoughts. Questions sound genuinely curious. Calm and friendly."
)
PROFILE = f"qwen3-tts-1.7b-voicedesign:{RATE}:42:{STYLE}"


def installed():
    return PYTHON.is_file() and (DIRECTORY / "model.safetensors").is_file() and (
        DIRECTORY / "speech_tokenizer/model.safetensors").is_file()


def load_model():
    os.environ["HF_HUB_OFFLINE"] = "1"
    import torch
    from qwen_tts import Qwen3TTSModel

    torch.set_num_threads(8)
    return Qwen3TTSModel.from_pretrained(
        str(DIRECTORY), local_files_only=True, device_map="cpu",
        dtype=torch.float32, attn_implementation="eager",
    )


def synthesize(model, text):
    import numpy as np
    import torch

    torch.manual_seed(42)
    waves, rate = model.generate_voice_design(
        text=text, language="Russian", instruct=STYLE,
        max_new_tokens=max(192, len(text) * 4),
    )
    if rate != RATE or not waves or not waves[0].size or not np.isfinite(waves[0]).all():
        raise ValueError("Модель вернула некорректный звук.")
    return (np.clip(waves[0], -1, 1) * 32767).astype("<i2").tobytes()
