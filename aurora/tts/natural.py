"""Женский голос с интонацией из записанной русской реплики."""

from aurora.tts import design

SPEAKER = "aurora-live"
DIRECTORY = design.STUDIO / "qwen-natural"
REFERENCE = design.STUDIO / "hush/clips/0309.wav"
TRANSCRIPT = "Интересно, наши дубликаты ели на завтрак то же, что и мы? Надеюсь, да?"
PROFILE = f"qwen-base-1.7b:fd4b254:ru-0309:{TRANSCRIPT}:full-text:42:v1"
RATE = design.RATE


def installed():
    return design.weights_available(DIRECTORY) and REFERENCE.is_file()


def load_model():
    model = design.load_weights(DIRECTORY)
    prompt = model.create_voice_clone_prompt(ref_audio=str(REFERENCE), ref_text=TRANSCRIPT)
    return model, prompt


def synthesize(loaded, text):
    import torch

    model, prompt = loaded
    torch.manual_seed(42)
    waves, rate = model.generate_voice_clone(
        text=text, language="Russian", voice_clone_prompt=prompt, non_streaming_mode=True,
        max_new_tokens=max(192, len(text) * 4),
    )
    return design.pcm16(waves, rate)
