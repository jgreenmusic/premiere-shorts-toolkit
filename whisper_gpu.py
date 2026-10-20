"""Whisper on the graphics card, for the transcription step.

faster-whisper only uses NVIDIA cards, so on AMD (and Intel) cards the GPU route is a
whisper.cpp build with Vulkan: a folder with whisper-cli(.exe) and a models\\ subfolder.
It is found at SHORTS_WHISPER_CPP, else ~/tools/whisper-vulkan; SHORTS_WHISPER_CPP=off
turns it off. Without it everything runs on the processor exactly as before.

Measured on an RX 9070 XT, 12 minutes of speech, model 'small': 25 s here against 74 s for
faster-whisper on a 16-core processor, and words cut from its times were heard right as
often (45 vs 41 of 60 in a re-listen test).

Speech is found with faster-whisper's own voice filter (Silero) and only that is sent to
whisper-cli, so every time maps back exactly: whisper-cli's own --vad maps line times back
but leaves word times in the shortened audio.
"""
import json
import os
import subprocess
import tempfile
import threading
import time
import urllib.request
import wave

import numpy as np

RATE = 16000
DEFAULT_DIR = os.path.join(os.path.expanduser("~"), "tools", "whisper-vulkan")
DTW_PRESETS = {"tiny": "tiny", "base": "base", "small": "small", "medium": "medium",
               "large-v3": "large.v3", "large-v3-turbo": "large.v3.turbo"}


class Stopped(Exception):
    """stop() said yes while whisper-cli was running."""


def find(model="small"):
    """whisper-cli to use for this model, or '' (then the processor is used)."""
    folder = os.environ.get("SHORTS_WHISPER_CPP", DEFAULT_DIR)
    if folder.lower() == "off" or model not in DTW_PRESETS:
        return ""
    exe = os.path.join(folder, "whisper-cli" + (".exe" if os.name == "nt" else ""))
    return exe if os.path.isfile(exe) else ""


def model_file(exe, model, log=print):
    path = os.path.join(os.path.dirname(exe), "models", "ggml-%s.bin" % model)
    if not os.path.isfile(path):
        log("  downloading Whisper '%s' for the graphics card (once)" % model)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        urllib.request.urlretrieve(
            "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-%s.bin" % model, path + ".part")
        os.replace(path + ".part", path)
    return path


def transcribe(exe, audio, model="small", vad=True, log=print, stop=None):
    """Words as [start, end, word, probability], like captions.transcribe on the processor."""
    from faster_whisper.transcribe import SpeechTimestampsMap
    from faster_whisper.vad import VadOptions, collect_chunks, get_speech_timestamps
    to_original = float
    if vad:
        chunks = get_speech_timestamps(audio, VadOptions())
        if not chunks:
            return []
        to_original = SpeechTimestampsMap(chunks, RATE).get_original_time
        audio = np.concatenate(collect_chunks(audio, chunks)[0])
    fd, wav = tempfile.mkstemp(suffix=".wav", prefix="shorts-whisper-")
    os.close(fd)
    out = wav[:-4]
    try:
        with wave.open(wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes((np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())
        # -mc 0 = condition_on_previous_text=False; word timing (DTW) needs flash attention off
        cmd = [exe, "-m", model_file(exe, model, log), "-f", wav, "-l", "en", "-ojf", "-of", out,
               "-np", "-sns", "-mc", "0", "-t", "4", "-dtw", DTW_PRESETS[model], "-nfa"]
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        err = []
        reader = threading.Thread(target=lambda: err.append(proc.stderr.read()), daemon=True)
        reader.start()
        while proc.poll() is None:
            if stop and stop():
                proc.kill()
                proc.wait()
                raise Stopped()
            time.sleep(0.3)
        reader.join(5)
        if proc.returncode != 0:
            tail = (err[0] if err else b"").decode("utf-8", "replace").strip().splitlines()[-3:]
            raise RuntimeError("whisper-cli exit %s: %s" % (proc.returncode, " | ".join(tail)))
        with open(out + ".json", encoding="utf-8", errors="replace") as f:
            segments = json.load(f)["transcription"]
    finally:
        for p in (wav, out + ".json"):
            try:
                os.remove(p)
            except OSError:
                pass
    return words_from(segments, to_original)


def words_from(segments, to_original=float):
    """Words from whisper-cli --output-json-full. Its DTW time marks where a token ENDS
    (measured: then each word's start matches faster-whisper to 0.00 s median), so a word runs
    from the previous word's end to its own last token. Probability = mean over its tokens,
    as faster-whisper does."""
    words = []
    for seg in segments:
        if not seg["text"].strip():
            continue
        prev = round(to_original(seg["offsets"]["from"] / 1000), 3)
        cur = None
        for t in seg["tokens"]:
            if t["text"].startswith("[_"):
                continue
            if cur is None or t["text"].startswith(" "):
                cur = dict(start=prev, end=prev, text=t["text"].strip(), p=[t.get("p", 0)])
                words.append(cur)
            else:
                cur["text"] += t["text"]
                cur["p"].append(t.get("p", 0))
            if t["t_dtw"] >= 0:
                cur["end"] = prev = round(to_original(t["t_dtw"] / 100), 3)
    return [[w["start"], w["end"], w["text"], round(sum(w["p"]) / len(w["p"]), 3)]
            for w in words if w["text"] and w["end"] > w["start"]]
