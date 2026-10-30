"""Who is talking: every caption gets a speaker, every speaker a name and a colour.

The toolkit can know who talks in three ways, best first:
    mic       the recording has your mic on its own track (tracks.py, OBS track 2): where that
              track has speech, it's you. Exact - no guessing.
    albert    voice analysis on this PC with sherpa-onnx: pyannote segmentation 3.0 (MIT) finds
              where voices change, WeSpeaker ResNet34 (Apache-2.0) makes a voice print of each
              stretch, and the prints are grouped into voices. Free models, ~33 MB, downloaded
              once to ~/tools/speaker-models. You then say who each voice is (play its samples).
    premiere  Premiere's own transcript, made with Speaker labeling on (Text panel). Name the
              speakers there; the toolkit reads the names through the Speech panel.
With a mic track, "albert" analyses only the rest (on the Discord track if there is one).

<outdir>/speakers.json   {"source", "made", "people_asked",
                          "voices": {id: {"label", "secs", "samples": [[s, e]], "print": [...]}},
                          "turns": [[start, end, id]]}                     timeline seconds
toolkit.json "speakers"  {"on": bool, "who": {voice id: person name}}
~/.shorts-toolkit.json "people"  {name: {"colour": "RRGGBB", "me": bool, "print": [...], "n": int}}
    shared by every project, so a friend keeps their colour and is recognised by voice next time.
"""
import json
import os
import time
import urllib.request

import numpy as np

RATE = 16000
MODELS = os.environ.get("SHORTS_SPEAKER_MODELS") or os.path.join(os.path.expanduser("~"), "tools", "speaker-models")
SEG_URL = ("https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-segmentation-models/"
           "sherpa-onnx-pyannote-segmentation-3-0.tar.bz2")
EMB_NAME = "wespeaker_en_voxceleb_resnet34_LM.onnx"
EMB_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/" + EMB_NAME
SETTINGS = os.path.join(os.path.expanduser("~"), ".shorts-toolkit.json")

ME = "me"                     # the voice id of the mic track's speaker
ME_COLOUR = "7B5CFF"          # purple
# Friends' colours: they sit with the purple above and the orange of loud lines and screams
# (FF8A3C / FF5A3C) - teal is the third corner of that triangle, the rest fill in between.
# None is close to purple or orange, so a friend never looks like you or like a shout.
PALETTE = [("Teal", "14B8A6"), ("Pink", "FF4F9A"), ("Lime", "A3E635"), ("Sky", "38BDF8"),
           ("Gold", "FACC15"), ("Mint", "34D399"), ("Red", "F43F5E"), ("Blue", "4F7BFF")]
# Voice print likeness (cosine) that counts as "the same person". Measured on a mixed 3-person
# Discord + game recording: halves of one person's talk scored 0.93-0.94, different voices
# 0.65-0.90 - so only a close match that is clearly ahead of the next best names anyone.
SAME_VOICE = 0.92
CLEAR_LEAD = 0.04


# -- colours --------------------------------------------------------------------------------
def text_on(rgb):
    """White or near-black text, whichever reads better on this colour (for highlight boxes)."""
    r, g, b = (int(rgb[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lin = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    lum = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
    dark = 0.0070                                # luminance of 141414
    return "FFFFFF" if 1.05 / (lum + 0.05) >= (lum + 0.05) / (dark + 0.05) else "141414"


def set_who(outdir, who, on=None):
    """Replace the project's whole voice -> person map (config.update would merge old names in)."""
    import config
    cfg = config.load(outdir)
    sp = dict(cfg.get("speakers") or {})
    sp["who"] = who
    if on is not None:
        sp["on"] = bool(on)
    cfg["speakers"] = sp
    config.save(outdir, cfg)
    return sp


# -- people (every project) -----------------------------------------------------------------
def _settings():
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def people():
    return _settings().get("people") or {}


def save_people(ppl):
    s = _settings()
    s["people"] = ppl
    tmp = SETTINGS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)
    os.replace(tmp, SETTINGS)


def next_colour(ppl, taken=()):
    used = {p.get("colour", "").upper() for p in ppl.values()} | {c.upper() for c in taken}
    for _, c in PALETTE:
        if c not in used:
            return c
    return PALETTE[len(used) % len(PALETTE)][1]


def name_voice(outdir, voice, person, me=None):
    """Say who a voice is (person None/"" = not named). Learns the voice print for next time,
    gives a new person the next free colour. Returns the project's "who" map."""
    import config
    data = load(outdir)
    ppl = people()
    person = (person or "").strip()[:40]
    if person:
        p = ppl.setdefault(person, {})
        if not p.get("colour"):
            p["colour"] = ME_COLOUR if (me or voice == ME) else next_colour(ppl)
        if me is not None or voice == ME:
            for q in ppl.values():
                q["me"] = False
            p["me"] = True if me is None else bool(me)
        pr = ((data.get("voices") or {}).get(voice) or {}).get("print")
        if pr:                                    # running average of every voice named this person
            n = int(p.get("n") or 0)
            old = np.array(p["print"]) if p.get("print") and len(p["print"]) == len(pr) else np.zeros(len(pr))
            v = old * n + np.array(pr)
            p["print"], p["n"] = [round(float(x), 5) for x in v / (np.linalg.norm(v) or 1)], n + 1
        save_people(ppl)
    who = dict((config.load(outdir).get("speakers") or {}).get("who") or {})
    if person:
        who[voice] = person
    else:
        who.pop(voice, None)
    return set_who(outdir, who)["who"]


def set_person(name, colour=None, me=None):
    ppl = people()
    p = ppl.setdefault(name, {})
    if colour:
        p["colour"] = colour.upper().lstrip("#")[:6]
    if me is not None:
        for q in ppl.values():
            q["me"] = False
        p["me"] = bool(me)
    save_people(ppl)
    return ppl


# -- speakers.json --------------------------------------------------------------------------
def path_for(outdir):
    return os.path.join(outdir, "speakers.json")


def load(outdir):
    try:
        with open(path_for(outdir), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save(outdir, data):
    tmp = path_for(outdir) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path_for(outdir))


def recognise(voices, ppl):
    """{voice id: person} for voices whose print matches someone you named before."""
    out = {}
    pairs = []
    for vid, v in voices.items():
        if not v.get("print"):
            continue
        a = np.array(v["print"])
        sims = sorted(((float(a @ np.array(p["print"])), name) for name, p in ppl.items()
                       if p.get("print") and len(p["print"]) == len(a)), reverse=True)
        if sims and (len(sims) == 1 or sims[0][0] - sims[1][0] >= CLEAR_LEAD):
            pairs.append((sims[0][0], vid, sims[0][1]))
    for sim, vid, name in sorted(pairs, reverse=True):     # best matches first
        if sim >= SAME_VOICE and vid not in out:
            out[vid] = name                      # one person may own several voices (split by the analysis)
    return out


def summary(outdir, cfg=None):
    """What the app shows: the voices, who they are, their colours."""
    import config
    cfg = cfg or config.load(outdir)
    sp = cfg.get("speakers") or {}
    data, ppl = load(outdir), people()
    who = sp.get("who") or {}
    colours = Colours(data, who, ppl)
    voices = []
    for vid, v in (data.get("voices") or {}).items():
        voices.append(dict(id=vid, label=v.get("label") or vid, secs=round(v.get("secs", 0)), samples=v.get("samples", [])[:3],
                           person=who.get(vid) or "", colour=colours.of_voice(vid)))
    return dict(on=bool(sp.get("on")), source=data.get("source") or "", made=data.get("made"), voices=voices,
                people={n: dict(colour=p.get("colour"), me=bool(p.get("me")), known=bool(p.get("print"))) for n, p in ppl.items()},
                palette=[dict(name=n, colour=c) for n, c in PALETTE], me_colour=ME_COLOUR,
                asked=data.get("people_asked"))


class Colours:
    """Voice -> colour: the named person's colour, else a palette colour by voice order."""

    def __init__(self, data, who, ppl):
        self.who, self.ppl = who, ppl
        order = sorted((data.get("voices") or {}).items(), key=lambda kv: -kv[1].get("secs", 0))
        taken = [p.get("colour", "") for p in ppl.values()]
        self.auto, free = {}, [c for _, c in PALETTE if c not in {t.upper() for t in taken}] or [c for _, c in PALETTE]
        k = 0
        for vid, _ in order:
            if vid == ME:
                self.auto[vid] = ME_COLOUR
            elif not who.get(vid):
                self.auto[vid] = free[k % len(free)]
                k += 1

    def of_person(self, name):
        p = self.ppl.get(name) or {}
        return p.get("colour") or (ME_COLOUR if p.get("me") else None)

    def of_voice(self, vid):
        name = self.who.get(vid)
        return (self.of_person(name) if name else None) or self.auto.get(vid) or ME_COLOUR


class Who:
    """For a render: the colour of each caption (None = the look's own colours)."""

    def __init__(self, outdir, cfg):
        sp = cfg.get("speakers") or {}
        self.on = bool(sp.get("on") and outdir)
        data = load(outdir) if self.on else {}
        self.turns = sorted(data.get("turns") or [])
        self.on = self.on and bool(self.turns)
        self.colours = Colours(data, sp.get("who") or {}, people()) if self.on else None
        self.starts = [t[0] for t in self.turns]

    def voice_at(self, s, e):
        """The voice talking most during [s, e]. The mic's own speaker wins once it covers 30 %."""
        import bisect
        i = max(0, bisect.bisect_right(self.starts, e) - 1)
        got = {}
        j = i
        while j >= 0 and self.turns[j][0] > s - 120:   # turns are short; look back far enough for long ones
            a, b, v = self.turns[j]
            o = min(b, e) - max(a, s)
            if o > 0:
                got[v] = got.get(v, 0) + o
            j -= 1
        if got.get(ME, 0) >= 0.3 * max(0.01, e - s):
            return ME
        if got:
            return max(got, key=got.get)
        near = [(min(abs(t[0] - e), abs(t[1] - s)), t[2]) for t in self.turns[max(0, i - 2):i + 3]]
        near = [x for x in near if x[0] < 0.5]
        return min(near)[1] if near else None

    def colour(self, s, e, person=None):
        if not self.on:
            return None
        if person:
            return self.colours.of_person(person)
        v = self.voice_at(s, e)
        return self.colours.of_voice(v) if v else None


# -- sources --------------------------------------------------------------------------------
def from_premiere(transcripts, items):
    """speakers.json data from Premiere transcripts ({clip key: JSON}) and the sequence's audio
    clips [{key, start, end, in, out}] - the same mapping bridge.words_from_premiere uses."""
    voices, turns, names = {}, [], {}
    for key, t in transcripts.items():
        if isinstance(t, str):
            t = json.loads(t)
        for s in t.get("speakers") or []:
            names[s.get("id")] = s.get("name") or ""
        for seg in t.get("segments") or []:
            a = float(seg.get("start") or 0)
            b = a + float(seg.get("duration") or 0)
            sid = seg.get("speaker") or "?"
            for it in items or [dict(key=key, start=0, end=1e9, **{"in": 0, "out": 1e9})]:
                if it["key"] != key or b <= it["in"] or a >= it["out"]:
                    continue
                ta = it["start"] + max(a, it["in"]) - it["in"]
                tb = it["start"] + min(b, it["out"]) - it["in"]
                if tb > ta:
                    turns.append([round(ta, 3), round(tb, 3), sid])
    for a, b, sid in turns:
        v = voices.setdefault(sid, dict(label=names.get(sid) or "Speaker %d" % (len(voices) + 1), secs=0.0, samples=[]))
        v["secs"] += b - a
    for sid, v in voices.items():
        v["samples"] = samples_of([t for t in turns if t[2] == sid])
        v["secs"] = round(v["secs"], 1)
    return dict(source="premiere", made=time.time(), voices=voices, turns=sorted(turns))


def premiere_names(data):
    """{voice: name} for speakers you named in Premiere (not its own "Speaker 1" / "Unknown")."""
    import re
    return {vid: v["label"] for vid, v in (data.get("voices") or {}).items()
            if v.get("label") and not re.fullmatch(r"(?i)(speaker\s*\d+|unknown|unidentified)", v["label"].strip())}


def samples_of(turns, n=3, longest=4.0):
    """A few clear stretches to listen to: the longest turns, spread over the recording."""
    best = sorted(turns, key=lambda t: t[0] - t[1])[:n * 4]
    best = sorted(best, key=lambda t: t[0])
    pick = best[::max(1, len(best) // n)][:n] if best else []
    return [[round(a, 2), round(min(b, a + longest), 2)] for a, b, _ in pick]


def mic_turns(mic, log=print):
    """Where the mic-only track has speech (Silero voice filter, the one transcription uses)."""
    from faster_whisper.vad import VadOptions, get_speech_timestamps
    loud = float(np.percentile(np.abs(mic), 99.5)) if len(mic) else 0
    if loud < 1e-4:
        log("  the mic track is silent - skipping it")
        return []
    x = mic * min(0.5 / loud, 8.0)               # a quiet mic still reads as speech; room noise isn't blown up into it
    chunks = get_speech_timestamps(np.clip(x, -1, 1).astype(np.float32), VadOptions(min_silence_duration_ms=300))
    return [[round(c["start"] / RATE, 3), round(c["end"] / RATE, 3), ME] for c in chunks]


# -- voice analysis -------------------------------------------------------------------------
def models(log=print):
    """(segmentation model, voice print model), downloaded once."""
    import tarfile
    seg = os.path.join(MODELS, "sherpa-onnx-pyannote-segmentation-3-0", "model.onnx")
    emb = os.path.join(MODELS, EMB_NAME)
    os.makedirs(MODELS, exist_ok=True)
    if not os.path.isfile(seg):
        log("  downloading the voice-change model (7 MB, once)")
        tb = os.path.join(MODELS, "seg.tar.bz2")
        urllib.request.urlretrieve(SEG_URL, tb + ".part")
        os.replace(tb + ".part", tb)
        with tarfile.open(tb) as t:
            t.extractall(MODELS, filter="data")
    if not os.path.isfile(emb):
        log("  downloading the voice-print model (27 MB, once)")
        urllib.request.urlretrieve(EMB_URL, emb + ".part")
        os.replace(emb + ".part", emb)
    return seg, emb


def diarize(audio, n=0, log=print, threads=8):
    """[[start, end, voice number]] from sherpa-onnx. n = how many voices (0 = it decides)."""
    import sherpa_onnx as so
    seg, emb = models(log)
    cfg = so.OfflineSpeakerDiarizationConfig(
        segmentation=so.OfflineSpeakerSegmentationModelConfig(
            pyannote=so.OfflineSpeakerSegmentationPyannoteModelConfig(model=seg), num_threads=threads),
        embedding=so.SpeakerEmbeddingExtractorConfig(model=emb, num_threads=threads),
        # 0.9 measured on a 3-person Discord recording over game audio: 0.5 (the default) made
        # 21 voices out of 3 people, 0.9 made 4 (one small extra) - name the extra the same person
        clustering=so.FastClusteringConfig(num_clusters=int(n) if n else -1, threshold=0.9),
        min_duration_on=0.3, min_duration_off=0.5)
    if not cfg.validate():
        raise RuntimeError("voice analysis settings were refused by sherpa-onnx")
    sd = so.OfflineSpeakerDiarization(cfg)
    total = len(audio) / RATE
    t0 = time.time()

    def progress(done, all_, arg=None):
        if all_ and done % max(1, all_ // 10) == 0:
            log("  voices %d%%" % (100 * done // all_))
        return 0
    res = sd.process(audio.astype(np.float32), callback=progress).sort_by_start_time()
    log("  %.0f min of sound analysed in %.0f s" % (total / 60, time.time() - t0))
    return [[round(r.start, 3), round(r.end, 3), int(r.speaker)] for r in res]


def voice_prints(audio, turns, log=print, per_voice=8):
    """{voice: mean voice print (unit length)} from each voice's longest clean stretches."""
    import sherpa_onnx as so
    _, emb = models(log)
    ex = so.SpeakerEmbeddingExtractor(so.SpeakerEmbeddingExtractorConfig(model=emb, num_threads=8))
    out = {}
    for v in sorted({t[2] for t in turns}):
        mine = sorted([t for t in turns if t[2] == v and t[1] - t[0] >= 1.0], key=lambda t: t[0] - t[1])[:per_voice]
        vecs = []
        for a, b, _ in mine:
            x = audio[int(a * RATE):int(min(b, a + 6) * RATE)]
            if len(x) < RATE:
                continue
            s = ex.create_stream()
            s.accept_waveform(RATE, x.astype(np.float32))
            s.input_finished()
            if ex.is_ready(s):
                e = np.array(ex.compute(s))
                vecs.append(e / (np.linalg.norm(e) or 1))
        if vecs:
            m = np.mean(vecs, axis=0)
            out[v] = [round(float(x), 5) for x in m / (np.linalg.norm(m) or 1)]
    return out


def analyse(ctx, n=0, log=print):
    """Albert's own analysis of who talks when -> speakers.json. n = people in the recording
    (you included), 0 = let the analysis decide. Uses the mic / Discord tracks when the
    recording has them (tracks.py)."""
    import captions as cap
    import tracks
    voices, turns = {}, []
    sound = ctx.audio
    if tracks.has_track(ctx.seq, tracks.MIC_TRACK):
        log("[speakers] your mic has its own track - reading it")
        mic = cap.timeline_audio(ctx.seq, log=log, track=tracks.MIC_TRACK)
        turns = mic_turns(mic, log) if mic is not None else []
        if turns:
            voices[ME] = dict(label="Mic track", secs=round(sum(b - a for a, b, _ in turns), 1), samples=samples_of(turns))
            log("  you talk for %.0f s in %d stretches" % (voices[ME]["secs"], len(turns)))
            if n:
                n = max(0, n - 1)                # the analysis below only looks for the others
        if tracks.has_track(ctx.seq, tracks.FRIENDS_TRACK):
            log("  friends have their own track (Discord) - analysing that")
            other = cap.timeline_audio(ctx.seq, log=log, track=tracks.FRIENDS_TRACK)
            if other is not None:
                sound = np.zeros(len(ctx.audio), dtype=np.float32)
                sound[:min(len(other), len(sound))] = other[:len(sound)]
    log("[speakers] analysing voices on this PC (sherpa-onnx, free models)")
    found = diarize(sound, n, log)
    if turns:                                    # the mic already says where you talk
        mine = turns

        def yours(a, b):
            o = sum(max(0.0, min(b, y) - max(a, x)) for x, y, _ in mine if y > a and x < b)
            return o >= 0.5 * (b - a)
        found = [t for t in found if not yours(t[0], t[1])]
    prints = voice_prints(sound, found, log)
    secs = {}
    for a, b, v in found:
        secs[v] = secs.get(v, 0) + b - a
    order = sorted(secs, key=lambda v: -secs[v])
    ids = {v: "v%d" % (k + 1) for k, v in enumerate(order)}
    for v in order:
        vid = ids[v]
        mine = [[a, b, vid] for a, b, x in found if x == v]
        voices[vid] = dict(label="Voice %s" % vid[1:], secs=round(secs[v], 1), samples=samples_of(mine), print=prints.get(v))
        turns += mine
    log("  %d voice%s found: %s" % (len(order), "" if len(order) == 1 else "s",
                                    ", ".join("%s %.0f s" % (voices[ids[v]]["label"], secs[v]) for v in order)))
    data = dict(source="mic+albert" if ME in voices else "albert", made=time.time(), voices=voices,
                turns=sorted(turns), people_asked=n or None)
    save(ctx.outdir, data)
    return data


def after_new(outdir, data, log=print):
    """A new analysis: who is who carries over from names you gave and voices it recognises."""
    ppl = people()
    who = {}
    if ME in data["voices"]:
        me = next((name for name, p in ppl.items() if p.get("me")), None)
        if me:
            who[ME] = me
    if data.get("source") == "premiere":
        who.update(premiere_names(data))
    for vid, name in recognise({k: v for k, v in data["voices"].items() if k not in who}, ppl).items():
        who[vid] = name
        log("  %s sounds like %s - check by playing its samples" % (data["voices"][vid]["label"], name))
    set_who(outdir, who, on=True)                # voice ids of an earlier analysis mean nothing now
    return who
