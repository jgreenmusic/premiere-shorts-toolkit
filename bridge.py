"""The Premiere bridge: two small panels inside Premiere that the toolkit drives.

    premiere/bridge-uxp   "Shorts Toolkit - Speech"  runs Adobe's Speech to Text on the
                          sequence's clips and sends the transcript here (UXP: the only
                          place Adobe lets a script start transcription, Premiere 26.5+).
    premiere/bridge-cep   "Shorts Toolkit - Captions"  lays an .srt on the sequence as a
                          real Premiere caption track and saves (ExtendScript: the only
                          place Adobe lets a script create a caption track).

Adobe has no scripting call for the Text panel's own "Create captions" button, so the
toolkit does that part itself: words -> caption lines (Premiere's rules: up to 42
characters, one line) -> .srt -> caption track. Both panels poll this server; nothing
listens inside Premiere.

A job moves through these steps (bridge.JOB["step"]):
    speech   -> the UXP panel transcribes (engine "adobe")      or the toolkit runs Whisper
    words    -> transcript saved as <outdir>/premiere-words.json (timeline seconds)
    srt      -> <outdir>/premiere-captions.srt
    import   -> the CEP panel adds the caption track and saves the project
    done / failed / click  (click = do the last step by hand; the app then watches)
"""
import json
import os
import re
import threading
import time

TICKS = 254016000000
LOCK = threading.Lock()
PANELS = {}             # "uxp" / "cep" -> {"seen": t, ...what the panel last reported}
JOB = {"id": 0, "step": "idle", "lines": [], "project": None}
QUEUE = {"uxp": [], "cep": []}


def now():
    return time.time()


def say(line):
    with LOCK:
        JOB["lines"].append(time.strftime("%H:%M:%S ") + line)
        del JOB["lines"][:-200]


def status():
    t = now()
    with LOCK:
        panels = {k: dict(v, connected=t - v.get("seen", 0) < 6) for k, v in PANELS.items()}
        return dict(panels=panels, job=dict(JOB, lines=list(JOB["lines"])))


def hello(kind, info):
    """A panel checking in. Returns the next thing for it to do, if any."""
    with LOCK:
        PANELS[kind] = dict(info, seen=now())
        return QUEUE[kind].pop(0) if QUEUE[kind] else None


def start(project, outdir, sequence, engine, style, punct="keep"):
    """Queue 'make captions' for this project. Returns an error string or None."""
    with LOCK:
        if JOB["step"] in ("speech", "words", "srt", "import"):
            return "Premiere captions are already being made."
        JOB.update(id=JOB["id"] + 1, step="speech", lines=[], project=project, outdir=outdir,
                   sequence=sequence, engine=engine, style=style, punct=punct, started=now())
        jid = JOB["id"]
    say("Making captions for %s (%s)" % (sequence or "the active sequence",
                                         "Adobe Speech to Text" if engine == "adobe" else "toolkit speech"))
    if engine == "adobe":
        with LOCK:
            QUEUE["uxp"].append(dict(op="transcribe", job=jid, project=project, sequence=sequence))
        say("Asked Premiere to transcribe - watch the Shorts Toolkit panel in Premiere")
    return None


SCRIPT = {"n": 0, "results": {}}
# script -> (marker name prefix, Premiere colour index, csv the toolkit keeps next to the project)
MARKER_SCRIPTS = {"suggested-markers.jsx": ("Suggested: ", 4, "suggested-markers.csv"),
                  "shorts-to-markers.jsx": ("Short: ", 3, "shorts-markers.csv")}


def outdir_of(project):
    return re.sub(r"_captions-synced(-v\d+)?$", "", os.path.splitext(project)[0]) + "_captions"


def read_marker_csv(path):
    rows = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            next(f, None)
            for line in f:
                p = line.rstrip("\r\n").split(",", 2)
                if len(p) == 3:
                    rows.append(dict(start=float(p[0]), end=float(p[1]), name=p[2]))
    return rows


def connected(kind):
    with LOCK:
        return now() - PANELS.get(kind, {}).get("seen", 0) < 6


def run_script(project, script, sequence=None, timeout=30):
    """Have the Captions panel run one of premiere/*.jsx on the open project and wait for
    its answer. Returns (ok, message)."""
    name = os.path.basename(script)
    if name in MARKER_SCRIPTS and connected("uxp"):
        # the Speech panel can place markers itself (Adobe's documented markers API)
        prefix, color, csv_name = MARKER_SCRIPTS[name]
        kind, cmd = "uxp", dict(op="markers", project=project, sequence=sequence, prefix=prefix, color=color,
                                rows=read_marker_csv(os.path.join(outdir_of(project), csv_name)))
    elif connected("cep"):
        kind, cmd = "cep", dict(op="script", project=project, sequence=sequence, script=script)
    else:
        return False, None
    with LOCK:
        SCRIPT["n"] += 1
        rid = SCRIPT["n"]
        QUEUE[kind].append(dict(cmd, rid=rid))
    end = now() + timeout
    while now() < end:
        with LOCK:
            if rid in SCRIPT["results"]:
                return SCRIPT["results"].pop(rid)
        time.sleep(0.2)
    with LOCK:                                   # never picked up: don't run it later by surprise
        QUEUE[kind][:] = [q for q in QUEUE[kind] if q.get("rid") != rid]
    return False, "Premiere didn't answer in %d s - is it busy (rendering, a dialog open)?" % timeout


def fail(msg):
    say("Failed: " + msg)
    with LOCK:
        JOB["step"] = "failed"


def report(kind, r):
    """Progress from a panel."""
    if r.get("rid"):                             # answer to run_script
        with LOCK:
            SCRIPT["results"][r["rid"]] = (bool(r.get("ok")), r.get("message") or "")
        return
    if r.get("job") != JOB["id"]:
        return
    if r.get("line"):
        say(r["line"])
    if r.get("error"):
        if r.get("click"):
            say(r["error"])
            with LOCK:
                JOB["step"] = "click"
        else:
            fail(r["error"])
        return
    if kind == "uxp" and r.get("transcripts") is not None:
        try:
            words = words_from_premiere(r["transcripts"], r.get("items", []))
        except Exception as e:                       # noqa: BLE001 - shown to the user
            return fail("couldn't read Premiere's transcript (%s)" % e)
        raw = os.path.join(JOB["outdir"], "premiere-transcript-raw.json")
        os.makedirs(JOB["outdir"], exist_ok=True)
        with open(raw, "w", encoding="utf-8") as f:
            json.dump(r, f)
        if not words:
            return fail("Premiere's transcript has no words with times in it - saved it to %s so it can be looked at"
                        % os.path.basename(raw))
        say("Premiere heard %d words" % len(words))
        words_ready(words)
    if kind == "cep" and r.get("done"):
        say(r.get("message") or "Caption track added and project saved")
        with LOCK:
            JOB["step"] = "done"


def words_ready(words):
    """Timeline words [start, end, text] -> .srt -> ask Premiere to import it."""
    with LOCK:
        JOB["step"] = "srt"
    out = JOB["outdir"]
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "premiere-words.json"), "w", encoding="utf-8") as f:
        json.dump(words, f)
    cues = caption_lines(words, JOB.get("style") or "premiere", JOB.get("punct") or "keep")
    # a new name each time, so Premiere never confuses it with an earlier import
    srt = os.path.join(out, "premiere-captions-%s.srt" % time.strftime("%Y%m%d-%H%M%S"))
    write_srt(srt, cues)
    say("Made %d caption lines -> %s" % (len(cues), os.path.basename(srt)))
    with LOCK:
        JOB["step"] = "import"
        QUEUE["cep"].append(dict(op="import", job=JOB["id"], project=JOB["project"],
                                 sequence=JOB.get("sequence"), srt=srt))
    say("Asked Premiere to add the caption track")


# -- Premiere transcript -> timeline words ------------------------------------------------
TEXT_KEYS = ("text", "word", "value", "content")
START_KEYS = ("start", "startTime", "start_time", "offset", "begin")
DUR_KEYS = ("duration", "dur", "length")
END_KEYS = ("end", "endTime", "end_time")


def _num(d, keys):
    for k in keys:
        v = d.get(k)
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str) and re.fullmatch(r"-?\d+(\.\d+)?", v):
            return float(v)
        if isinstance(v, dict):                     # {"seconds": ..} or {"ticks": ..}
            if isinstance(v.get("seconds"), (int, float)):
                return float(v["seconds"])
            if isinstance(v.get("ticks"), (int, float, str)):
                return float(v["ticks"]) / TICKS
    return None


def transcript_words(node, out=None):
    """Every timed word in a Premiere transcript JSON, as [start, end, text] in the
    CLIP's time. Adobe doesn't document the layout, so this looks for any object with a
    text and a start (and a duration or end) that has no smaller timed pieces inside."""
    if out is None:
        out = []
    if isinstance(node, list):
        for x in node:
            transcript_words(x, out)
        return out
    if not isinstance(node, dict):
        return out
    kids = [v for v in node.values() if isinstance(v, (list, dict))]
    before = len(out)
    for v in kids:
        transcript_words(v, out)
    if len(out) > before:                            # a segment: its words were taken instead
        return out
    text = next((node[k] for k in TEXT_KEYS if isinstance(node.get(k), str)), None)
    start = _num(node, START_KEYS)
    if text is None or start is None or not text.strip():
        return out
    end = _num(node, END_KEYS)
    if end is None:
        dur = _num(node, DUR_KEYS)
        end = start + (dur if dur is not None else 0.3)
    kind = str(node.get("type", "")).lower()
    if kind.startswith("punct") and out:             # "," "." belong to the word before
        out[-1][2] += text.strip()
        return out
    out.append([start, end, text.strip()])
    return out


def _to_seconds(words):
    """Some exports use ticks: if times are far beyond a day, divide."""
    if words and max(w[1] for w in words) > 10 * 86400:
        for w in words:
            w[0] /= TICKS
            w[1] /= TICKS
    return words


def words_from_premiere(transcripts, items):
    """transcripts: {key: transcript JSON (string or object)} per source clip.
    items: the sequence's audio clips [{key, start, end, in, out}] (seconds), so clip
    time can be put on the timeline. Words said twice (the same file on two tracks)
    are kept once."""
    per_clip = {}
    for key, t in transcripts.items():
        if isinstance(t, str):
            t = json.loads(t)
        per_clip[key] = _to_seconds(transcript_words(t))
    words = []
    if not items:                                    # nothing to map with: already timeline time
        for w in per_clip.values():
            words += w
    for it in items:
        for a, b, text in per_clip.get(it["key"], []):
            if a < it["in"] - 0.05 or a >= it["out"]:
                continue
            ta = it["start"] + (a - it["in"])
            tb = min(it["start"] + (b - it["in"]), it["end"])
            words.append([round(ta, 3), round(max(tb, ta + 0.05), 3), text])
    words.sort()
    out = []
    for w in words:
        if out and abs(out[-1][0] - w[0]) < 0.08 and out[-1][2].lower() == w[2].lower():
            continue
        out.append(w)
    return out


# -- words -> caption lines --------------------------------------------------------------
STYLES = {
    # Premiere's Create captions defaults: 42 characters, 1 line, no minimum fill
    "premiere": dict(chars=42, words=99, gap=0.8, min_dur=0.7),
    # the toolkit's Shorts style: 1-3 words at a time
    "short": dict(chars=18, words=3, gap=0.35, min_dur=0.4),
}


def caption_lines(words, style="premiere", punct="keep"):
    """Caption lines from timeline words. Lines break at sentence ends first, then the
    punctuation is dropped as asked (so it still shapes the lines, just not shown)."""
    from captions import strip_punct_text
    s = STYLES.get(style, STYLES["premiere"])
    chunks, cur = [], []
    for w in words:
        text = w[2].strip()
        if not text:
            continue
        if cur and (len(cur) >= s["words"] or w[0] - cur[-1][1] > s["gap"]
                    or len(" ".join(x[2] for x in cur + [w])) > s["chars"]
                    or (style == "short" and cur[-1][2][-1:] in ".?!,")
                    or (cur[-1][2][-1:] in ".?!" and len(" ".join(x[2] for x in cur)) >= s["chars"] * 0.5)):
            chunks.append(cur)
            cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    cues = []
    for i, ch in enumerate(chunks):
        a = ch[0][0]
        nxt = chunks[i + 1][0][0] if i + 1 < len(chunks) else None
        b = max(ch[-1][1] + 0.15, a + s["min_dur"])
        if nxt is not None:
            b = min(b, nxt)
        text = strip_punct_text(" ".join(x[2] for x in ch), punct)
        if text:
            cues.append((a, max(b, a + 0.1), text))
    return cues


def srt_time(sec):
    ms = int(round(max(0, sec) * 1000))
    return "%02d:%02d:%02d,%03d" % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)


def write_srt(path, cues):
    with open(path, "w", encoding="utf-8") as f:
        for n, (a, b, text) in enumerate(cues, 1):
            f.write("%d\n%s --> %s\n%s\n\n" % (n, srt_time(a), srt_time(b), text))
