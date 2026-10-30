"""Send Shorts to Premiere: each Short as its own vertical timeline you can keep editing there.

The toolkit still renders on its own (`make`); this hands Premiere the same Short in pieces.
It writes an FCP XML file (Premiere: File > Import) with one 1080x1920 sequence per Short:

  V1  the blurred background (rendered by the toolkit, no sound)
  V2  the recording itself, scaled and centred the way the render lays it out (Motion > Scale)
  V3  the styled captions, screams and laughs as a see-through layer (QuickTime Animation with
      alpha), cut into one clip per caption: slide or trim a clip to move that caption
  A1  the recording's sound, cut around every censored word (those pieces are switched off)
  A2  one beep clip per censored word (censor mode on with sound = beep)
  A3+ sound effects, one clip each with its level set (tracks as needed: they may overlap)
  last  the music under the Short, already ducked and faded, as one clip

and next to it <Short>.srt, the same caption lines as plain text: import it and drag it onto the
timeline for a Premiere caption track whose words you can retype.

Files go in the <project>_premiere folder (one folder per Short + beep.wav). Exporting again replaces them.
"""
import glob
import json
import os
import re
import subprocess
import time
import urllib.parse
from xml.sax.saxutils import escape

import bleep
import render
import sfx
import soundlib
import style
from bridge import srt_time
from prproj import TICKS

W, H = render.W, render.H
WIDE = (render.WIDE_W, render.WIDE_H)


def out_dir(ctx):
    d = ctx.base + "_premiere"
    os.makedirs(d, exist_ok=True)
    return d


_INFO = {}


def media(path):
    """{w, h, fps ("60/1"), dur (s), channels, rate} of a media file, via PyAV."""
    if path not in _INFO:
        import av
        info = dict(w=0, h=0, fps="30/1", dur=0.0, channels=0, rate=48000)
        with av.open(path) as c:
            info["dur"] = (c.duration or 0) / 1e6
            for s in c.streams:
                if s.type == "video" and not info["w"]:
                    r = s.average_rate or s.guessed_rate or 30
                    info.update(w=s.codec_context.width, h=s.codec_context.height,
                                fps="%d/%d" % (r.numerator, r.denominator))
                elif s.type == "audio" and not info["channels"]:
                    info.update(channels=s.codec_context.channels, rate=s.codec_context.sample_rate)
        _INFO[path] = info
    return _INFO[path]


class Rate:
    """The sequence's frame rate; FCP XML counts in whole frames."""
    def __init__(self, fps):
        num, den = (int(x) for x in fps.split("/"))
        self.text = fps
        self.fps = num / den
        self.timebase = int(round(self.fps))
        self.ntsc = abs(self.fps - self.timebase) > 0.001

    def f(self, sec):
        return int(round(sec * self.fps))

    def xml(self):
        return "<rate><timebase>%d</timebase><ntsc>%s</ntsc></rate>" % (self.timebase, "TRUE" if self.ntsc else "FALSE")


def pathurl(path):
    return "file://localhost/" + urllib.parse.quote(os.path.abspath(path).replace("\\", "/"))


# ---------- the pieces ----------

def plain(text):
    """Caption text without the .ass styling tags."""
    return re.sub(r"\{[^}]*\}", "", text).replace("\\N", " ").replace("\\n", " ").strip()


def caption_clips(events, a, b, with_style=False):
    """[(start, end, text)] relative to a: one entry per caption as it appears on screen.
    A caption is drawn as several events (the highlight moves word by word; screams, laughs
    and held "Ohhh"s grow a letter at a time) - those are joined back into one clip.
    with_style: (start, end, text, "Main" / "Scream" / "Laugh") instead."""
    out = []
    for s, e, sty, text in events:
        if e <= a or s >= b:
            continue
        s, e, t = max(s, a) - a, min(e, b) - a, plain(text)
        if out:
            ps, pe, pt, psty = out[-1]
            joined = s - pe < 0.02 and (t == pt or (t.startswith(pt) and len(pt) >= 2)
                                         or (sty == psty and sty in ("Scream", "Laugh")))
            if joined:
                out[-1] = (ps, e, t, sty)
                continue
        out.append((s, e, t, sty))
    return [x if with_style else x[:3] for x in out if x[1] - x[0] > 0.005]


# what the toolkit did to each Short, shown in Premiere as timeline markers + clip colours
LABEL = dict(check="Yellow", beep="Rose", yours="Mango", retimed="Caribbean", reaction="Violet", sound="Forest", music="Lavender")
TITLE = dict(check="CHECK", beep="BEEP", yours="YOUR EDIT", retimed="RE-TIMED", reaction="", sound="SOUND")


def changes(ctx, events, a, b, spans):
    """[(start, end, kind, name, comment)] relative to a, sorted. kind = a LABEL key.
    spans = the Short's beeps (bleep.spans)."""
    import captions as cap
    bl = bleep.settings(ctx.cfg)
    bad = bleep.matcher(bl)
    out = []
    def say(s, e, kind, name, comment=""):
        if e > a and s < b:                              # only what shows inside this Short
            out.append((max(0.0, s - a), min(e, b) - a, kind, (TITLE[kind] + ": " if TITLE[kind] else "") + name, comment))
    if bl.get("on") and bl.get("sound") != "none":       # each beep, with the word it covers
        for w in getattr(ctx, "words", None) or []:
            if w[1] > a and w[0] < b and bad(w[2]):
                say(w[0], w[1], "beep", w[2].strip(), "Whisper heard this word here. The beep (A2) covers %.2f-%.2f s; "
                    "stretch it if the word is still audible." % (max(0.0, w[0] - 0.04 - a), min(b, w[1] + 0.04) - a))
    edits = ctx.cfg.get("caption_edits") or {}
    fit = getattr(ctx, "fit", None) or {}
    n_own = len(ctx.seq.captions) if not getattr(ctx, "auto", False) else 0
    near_beep = lambda s, e: any(x + a < e + 0.3 and y + a > s - 0.3 for x, y in spans)
    for c, m in zip(ctx.captions, ctx.matches):
        if c.end_s <= a or c.start_s >= b:
            continue
        own = edits.get(cap.caption_key(c)) or {}
        if own.get("hide"):
            say(c.start_s, c.end_s, "yours", "caption removed", "You took this caption out: " + c.text)
            continue
        if c.index >= n_own and n_own:
            say(c.start_s, c.end_s, "yours", "caption added", c.text)
        if own.get("text") is not None and own["text"].strip() != c.text:
            say(c.start_s, c.end_s, "yours", "text changed", "Was: %s  >>  Now: %s" % (c.text, own["text"].strip()))
        if own.get("start") is not None or own.get("end") is not None:
            say(c.start_s, c.end_s, "yours", "timing set by you", c.text)
        times = fit.get(c.index) if c.index < n_own else None
        if times:
            ds, de = (times[0] - c.start) / TICKS, (times[1] - c.end) / TICKS
            ds, de = (0 if own.get("start") is not None else ds), (0 if own.get("end") is not None else de)
            if abs(ds) >= 0.1 or abs(de) >= 0.1:
                say(times[0] / TICKS, times[1] / TICKS, "retimed", "caption fitted to the speech",
                    "%s  >>  start %+.2f s, end %+.2f s from Premiere's caption." % (c.text, ds, de))
        text = (own.get("text") or c.text).strip()
        if re.search(r"\b0{4,}\b", text):
            say(c.start_s, c.end_s, "check", "transcript placeholder",
                "Premiere's transcript wrote \"%s\" here - nobody said that. Fix or remove it." % text)
        if bl.get("on") and bl.get("sound") != "none" and any(bad(w) for w in text.split()) and not near_beep(c.start_s, c.end_s):
            say(c.start_s, c.end_s, "check", "censored in the caption, NO beep",
                "%s  >>  the caption hides the word but Whisper didn't hear it, so nothing beeps. Add a beep by hand "
                "(copy one from A2)." % text)
    for s, e, t, sty in caption_clips(events, a, b, with_style=True):
        if sty in ("Scream", "Laugh"):
            say(s + a, e + a, "reaction", sty.upper() + ": " + t, "Drawn by the toolkit from the sound.")
    return sorted(out)


def marker(s, e, name, comment, rate):
    return ("<marker><comment>%s</comment><name>%s</name><in>%d</in><out>%d</out></marker>"
            % (escape(comment), escape(name), rate.f(s), rate.f(e) if e - s >= 0.05 else -1))


def write_srt(path, clips):
    part = path + ".part"
    with open(part, "w", encoding="utf-8") as f:
        for n, (s, e, t) in enumerate(clips, 1):
            f.write("%d\n%s --> %s\n%s\n\n" % (n, srt_time(s), srt_time(e), t))
    return place(part, path)


def place(part, path):
    """Give a finished file its name and return the path it got. Premiere keeps files it has
    imported open, so when an earlier send of this Short is still in use the new file becomes
    "name 2.ext" (3, 4...) instead: the earlier timeline keeps working, the new XML uses the new file."""
    stem, ext = os.path.splitext(path)
    n = 1
    while True:
        try:
            os.replace(part, path)
            return path
        except PermissionError:
            n += 1
            path = "%s %d%s" % (stem, n, ext)
            if n > 99:
                raise


def background(ctx, a, b, path, log=print):
    """The render's blurred backdrop for a..b, no sound. Returns the file's path (see place)."""
    work = os.path.join(ctx.outdir, "work")
    os.makedirs(work, exist_ok=True)
    inputs, fl = [], []
    render._picture(ctx.seq, a, b, inputs, fl)
    # setsar=1: the scale steps leave a 2560:2559 pixel shape that Premiere draws squeezed to a third
    fl.append("[vcat]%s,setsar=1[vout]" % render.blur_filter())
    graph = os.path.join(work, "bg-graph.txt")
    with open(graph, "w", encoding="utf-8") as f:
        f.write(";\n".join(fl))
    part = path + ".part.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y"] + inputs + [
        "-/filter_complex", graph, "-map", "[vout]", "-an", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "23", "-pix_fmt", "yuv420p", "-t", "%.4f" % (b - a), part], check=True)
    return place(part, path)


def caption_layer(ctx, events, a, b, fps, path, wide=False):
    """The Short's styled captions drawn on a see-through 1080x1920 picture (QuickTime Animation,
    which keeps the alpha and stays small: empty frames cost almost nothing). Returns its path.
    wide: 1920x1080, for the long video."""
    work = os.path.join(ctx.outdir, "work")
    os.makedirs(work, exist_ok=True)
    st = style.wide_look(style.look(ctx.cfg)) if wide else style.look(ctx.cfg)
    ass = os.path.join(work, "premiere.ass")
    style.write_ass(ass, [e for e in events if e[1] > a and e[0] < b], st=st, shift=a)
    style.copy_fonts(os.path.join(work, "fonts"), st)
    part = path + ".part.mov"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "color=black@0:s=%dx%d:r=%s:d=%.4f,format=rgba" % ((WIDE if wide else (W, H)) + (fps, b - a)),
                    "-vf", "ass=premiere.ass:fontsdir=fonts:alpha=1", "-c:v", "qtrle", "-pix_fmt", "argb",
                    os.path.abspath(part)], cwd=work, check=True)
    return place(part, path)


def beep_file(d):
    """beep.wav: the render's 1 kHz tone at the same level, 10 s, cut to length on the timeline."""
    path = os.path.join(d, "beep.wav")
    if not os.path.exists(path):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        "sine=frequency=1000:sample_rate=48000:duration=10", "-af",
                        "volume=0.32,aformat=channel_layouts=stereo", "-c:a", "pcm_s16le", path], check=True)
    return path


def library_sound(d, sid):
    """A copy of a library sound next to the send, so the timeline keeps working if the sound is
    later removed from the library."""
    import shutil
    folder = os.path.join(d, "sounds")
    os.makedirs(folder, exist_ok=True)
    src = soundlib.path_of(sid)
    dst = os.path.join(folder, os.path.basename(src))
    if not os.path.exists(dst):
        shutil.copy2(src, dst)
    return dst


def lanes(clips):
    """Clips can't overlap on a track: [[clips of track 1], [track 2]...], each on the first one free."""
    out = []
    for c in sorted(clips, key=lambda x: x[2]):
        for lane in out:
            if lane[-1][3] <= c[2]:
                lane.append(c)
                break
        else:
            out.append([c])
    return out


def sound_name(sid):
    return os.path.splitext(sid.partition(":")[2])[0].replace("-", " ")


def added_sound(ctx, events, a, b, name, root, d, off=0.0, reuse=False, log=print, wide=False):
    """(effect clips, music clips) for Xml.sound: the same effects and music a render mixes in."""
    if not sfx.wanted(ctx.cfg):
        return [], []
    m = sfx.ensure_moments(ctx, events)
    effects = []
    for h in sfx.plan(ctx.cfg, m, a, b, wide):
        if not h.get("on", True):
            continue
        path = library_sound(root, h["sound"])
        length = min(h.get("cut") or 1e9, media(path)["dur"], b - h["t"])
        effects.append((sound_name(h["sound"]), path, off + h["t"] - a, off + h["t"] - a + length, 0, True, LABEL["sound"], h["volume"]))
    music = []
    bed = sfx.bed_for(ctx.cfg, m, a, b, name, wide)
    if bed is not None:
        path = os.path.join(d, "music.wav")
        if reuse and latest(path):
            path = latest(path)
        else:
            part = path + ".part"
            sfx.write(part, bed)
            path = place(part, path)
        _INFO.pop(path, None)
        music = [("music", path, off, off + b - a, 0, True, LABEL["music"])]
    if effects or music:
        log("  %d sound effect(s)%s" % (len(effects), ", music" if music else ""))
    return effects, music


def audio_tracks(xml, groups):
    """The sequence's stereo tracks, in order: each group of clips that has any (two XML tracks each)."""
    out, first = [], 1
    for g in groups:
        if g:
            out += xml.sound(g, first)
            first += 2
    return out


def audio_pieces(seq, a, b, spans):
    """[(item, t0, t1, censored)] timeline seconds: every audio clip in range, cut at the spans.
    A multi-track recording's stretch counts once (tracks.mix_items)."""
    import tracks
    out = []
    for it in tracks.mix_items(seq.audio):
        s, e = max(a, it.start / TICKS), min(b, it.end / TICKS)
        if e - s <= 0.001:
            continue
        cuts = sorted({s, e} | {t for x, y in spans for t in (a + x, a + y) if s < t < e})
        for t0, t1 in zip(cuts, cuts[1:]):
            mid = (t0 + t1) / 2 - a
            out.append((it, t0, t1, any(x <= mid < y for x, y in spans)))
    return out


# ---------- the XML ----------

class Xml:
    def __init__(self, rate):
        self.rate, self.files, self.n = rate, {}, 0

    def file(self, path):
        """<file> in full the first time, by reference after."""
        if path in self.files:
            return '<file id="%s"/>' % self.files[path]
        fid = self.files[path] = "file-%d" % (len(self.files) + 1)
        m = media(path)
        r = Rate(m["fps"]) if m["w"] else self.rate
        parts = []
        if m["w"]:
            parts.append("<video><samplecharacteristics>%s<width>%d</width><height>%d</height>"
                         "<pixelaspectratio>square</pixelaspectratio></samplecharacteristics></video>"
                         % (r.xml(), m["w"], m["h"]))
        if m["channels"]:
            parts.append("<audio><samplecharacteristics><depth>16</depth><samplerate>%d</samplerate>"
                         "</samplecharacteristics><channelcount>%d</channelcount></audio>" % (m["rate"], m["channels"]))
        return ('<file id="%s"><name>%s</name><pathurl>%s</pathurl>%s<duration>%d</duration><media>%s</media></file>'
                % (fid, escape(os.path.basename(path)), escape(pathurl(path)), r.xml(), r.f(m["dur"]), "".join(parts)))

    def next_id(self):
        self.n += 1
        return "clipitem-%d" % self.n

    def clip(self, name, path, start, end, src_in, enabled=True, scale=None, cid=None, channel=None, links=(), label=None, level=None):
        """One clipitem; start/end on the sequence and src_in in the file, all in seconds.
        channel: the source channel (1/2) of an audio clip; links: [(clip id, track, position)]
        that Premiere joins into one stereo clip. label: a Premiere label colour name (LABEL).
        level: an audio clip's volume (1 = as it is)."""
        r = self.rate
        st, en = r.f(start), r.f(end)
        i = r.f(src_in)
        x = ['<clipitem id="%s"%s><name>%s</name><enabled>%s</enabled><duration>%d</duration>%s'
             '<start>%d</start><end>%d</end><in>%d</in><out>%d</out>%s'
             % (cid or self.next_id(), ' premiereChannelType="stereo"' if links else "", escape(name),
                "TRUE" if enabled else "FALSE", r.f(media(path)["dur"]), r.xml(), st, en, i, i + (en - st),
                self.file(path))]
        if channel:
            x.append("<sourcetrack><mediatype>audio</mediatype><trackindex>%d</trackindex></sourcetrack>" % channel)
        for lid, tr, pos in links:
            x.append("<link><linkclipref>%s</linkclipref><mediatype>audio</mediatype><trackindex>%d</trackindex>"
                     "<clipindex>%d</clipindex><groupindex>1</groupindex></link>" % (lid, tr, pos))
        if scale is not None:
            x.append("<filter><effect><name>Basic Motion</name><effectid>basic</effectid>"
                     "<effectcategory>motion</effectcategory><effecttype>motion</effecttype><mediatype>video</mediatype>"
                     "<parameter><parameterid>scale</parameterid><name>Scale</name><valuemin>0</valuemin>"
                     "<valuemax>1000</valuemax><value>%.3f</value></parameter></effect></filter>" % scale)
        if level is not None:
            x.append("<filter><effect><name>Audio Levels</name><effectid>audiolevels</effectid>"
                     "<effectcategory>audiolevels</effectcategory><effecttype>audiolevels</effecttype><mediatype>audio</mediatype>"
                     "<parameter><parameterid>level</parameterid><name>Level</name><valuemin>0</valuemin>"
                     "<valuemax>3.98109</valuemax><value>%.5f</value></parameter></effect></filter>" % level)
        if label:
            x.append("<labels><label2>%s</label2></labels>" % label)
        x.append("</clipitem>")
        return "".join(x)

    def sound(self, clips, first):
        """One stereo track the way Premiere writes it: two XML tracks (left, right) whose clips
        are linked in pairs. clips = [(name, path, start, end, src_in, enabled, label[, level])]; first = this
        track's number among the sequence's XML audio tracks. Returns [left track, right track]."""
        ids = [(self.next_id(), self.next_id()) for _ in clips]
        tracks = []
        for ch in (1, 2):
            items = []
            for pos, (c, pair) in enumerate(zip(clips, ids), 1):
                name, path, s, e, src, on, lab = c[:7]
                links = [(pair[0], first, pos), (pair[1], first + 1, pos)]
                items.append(self.clip(name, path, s, e, src, on, cid=pair[ch - 1], channel=ch, links=links, label=lab,
                                       level=c[7] if len(c) > 7 else None))
            tracks.append('<track currentExplodedTrackIndex="%d" totalExplodedTrackCount="2" premiereTrackType="Stereo">'
                          '%s<enabled>TRUE</enabled><locked>FALSE</locked><outputchannelindex>%d</outputchannelindex>'
                          '</track>' % (ch - 1, "".join(items), ch))
        return tracks


def track(items):
    return "<track>" + "".join(items) + "<enabled>TRUE</enabled><locked>FALSE</locked></track>"


def sequence(xml, name, dur, video_tracks, audio_tracks, markers=(), size=(W, H)):
    r = xml.rate
    return ('<sequence id="sequence-%d"><name>%s</name><duration>%d</duration>%s<media>'
            '<video><format><samplecharacteristics>%s<width>%d</width><height>%d</height>'
            '<pixelaspectratio>square</pixelaspectratio><fielddominance>none</fielddominance>'
            '</samplecharacteristics></format>%s</video>'
            '<audio><numOutputChannels>2</numOutputChannels><format><samplecharacteristics><depth>16</depth>'
            '<samplerate>48000</samplerate></samplecharacteristics></format>'
            '<outputs><group><index>1</index><numchannels>1</numchannels><downmix>0</downmix>'
            '<channel><index>1</index></channel></group><group><index>2</index><numchannels>1</numchannels>'
            '<downmix>0</downmix><channel><index>2</index></channel></group></outputs>%s</audio>'
            '</media>%s</sequence>'
            % (xml.n, escape(name), r.f(dur), r.xml(), r.xml(), size[0], size[1],
               "".join(video_tracks), "".join(audio_tracks), "".join(markers)))


def latest(path):
    """The newest copy of a file place() wrote ("name.ext", "name 2.ext"...), or None."""
    stem, ext = os.path.splitext(path)
    found = glob.glob(glob.escape(stem) + ext) + glob.glob(glob.escape(stem) + " *" + ext)
    return max(found, key=os.path.getmtime) if found else None


def short_sequence(ctx, events, name, a, b, d, xml, log=print, animated=False):
    """Write one Short's media into d. Returns (its <sequence>, its .srt or None).
    animated: leave room for the animated template's clips on V4."""
    p = short_parts(ctx, events, a, b, d, xml, name, log)
    vt = [track(p["v1"]), track(p["v2"])] + ([track(p["v3"])] if p["v3"] else [])
    if animated and p["v3"]:                     # V4 waits for the template clips (premiere/place-captions.jsx)
        vt.append(track([]))
    at = audio_tracks(xml, [p["voice"], p["beeps"]] + lanes(p["effects"]) + [p["music"]])
    return sequence(xml, name, b - a, vt, at, p["marks"]), p["srt"]


def short_parts(ctx, events, a, b, d, xml, name, log=print, off=0.0, reuse=False, wide=False):
    """One Short's clips, laid on a timeline from off seconds. Writes its media into d, or with
    reuse takes what an earlier send left there. Returns {v1, v2, v3: <clipitem>s, voice, beeps,
    effects, music: clips for Xml.sound, marks: <marker>s, srt}.
    wide: a stretch of the long video: 1920x1080, no blurred background."""
    seq, blur_trim = ctx.seq, ctx.cfg["layout"]["blur_trim"]
    os.makedirs(d, exist_ok=True)
    fps = xml.rate
    bg = os.path.join(d, "background.mp4")
    if wide:
        pass
    elif reuse and latest(bg):
        bg = latest(bg)
    else:
        log("  background")
        bg = background(ctx, a, b, bg)
    capfile = os.path.join(d, "captions.mov")
    clips = caption_clips(events, a, b)
    if clips and reuse and latest(capfile):
        capfile = latest(capfile)
    elif clips:
        log("  captions layer (%d captions)" % len(clips))
        capfile = caption_layer(ctx, events, a, b, fps.text, capfile, wide)
    # no captions = no .srt: Premiere stops on an empty one with a "File Import Failure" box
    srt = write_srt(os.path.join(d, safe(name) + ".srt"), clips) if clips else None

    v1 = [] if wide else [xml.clip("Blurred background", bg, off, off + b - a, 0)]
    v2 = []
    for t0, t1, it in render._pieces(seq.video, a, b):
        if it:
            m = media(it.path)
            fg_w, fg_h = render.fg_size(m["w"], m["h"], blur_trim)
            # Premiere's Scale 100 = the file's own size; the render scales the gameplay to fg_h tall
            scale = 100.0 * min(WIDE[0] / m["w"], WIDE[1] / m["h"]) if wide else 100.0 * fg_h / m["h"]
            v2.append(xml.clip(os.path.basename(it.path), it.path, off + t0 - a, off + t1 - a, render._src(it, t0), scale=scale))
    bl = bleep.settings(ctx.cfg)
    spans = bleep.spans(getattr(ctx, "words", None), bl, a, b)
    marks = changes(ctx, events, a, b, spans)

    def label(s, e):
        """A caption clip's colour: the most important change under it."""
        kinds = {k for ms, me, k, _, _ in marks if ms < e and me > s and k != "beep"}
        return next((LABEL[k] for k in ("check", "yours", "retimed", "reaction") if k in kinds), None)
    v3 = [xml.clip(t or "caption", capfile, off + s, off + e, s, label=label(s, e)) for s, e, t in clips]
    voice = [("censored" if cen else os.path.basename(it.path), it.path, off + t0 - a, off + t1 - a,
              render._src(it, t0), not cen, LABEL["beep"] if cen else None)
             for it, t0, t1, cen in audio_pieces(seq, a, b, spans)]
    beeps = []
    if spans and bl.get("sound") == "beep":
        beep = beep_file(os.path.dirname(d))
        beeps = [("beep", beep, off + s, off + min(e, s + 10), 0, True, LABEL["beep"]) for s, e in spans]
    if spans:
        log("  %d censored word(s)" % len(spans))
    effects, music = added_sound(ctx, events, a, b, name, os.path.dirname(d), d, off, reuse, log, wide)
    marks = sorted(marks + [(c[2] - off, c[3] - off, "sound", "SOUND: " + c[0], "Set by a rule or placed by you in the Sound step.")
                            for c in effects])
    if marks:
        log("  %d change(s) marked" % len(marks))
    return dict(v1=v1, v2=v2, v3=v3, voice=voice, beeps=beeps, effects=effects, music=music, srt=srt,
                marks=[marker(off + s, off + e, n, c, xml.rate) for s, e, _, n, c in marks])


def safe(name):
    return re.sub(r'[<>:"/\\|?*]+', "-", name).strip() or "short"


def export(ctx, events, jobs, log=print, out=None, record=None):
    """jobs = [(name, start, end)]. Writes the media + one XML; returns the XML's path.
    record: the spoken lines style.build recorded - also writes each Short's captions as clips
    of the animated template (animated.json + animated.txt, placed by premiere_auto)."""
    d = out or out_dir(ctx)
    os.makedirs(d, exist_ok=True)
    _INFO.clear()                                # the files written last time may have changed
    first = next((it for it in ctx.seq.video if it.path), None)
    if not first:
        raise SystemExit("No video on the timeline.")
    xml = Xml(Rate(media(first.path)["fps"]))
    seqs, srts, animated = [], [], []
    for n, (name, a, b) in enumerate(jobs, 1):
        log("[%d/%d] %s" % (n, len(jobs), name))
        x, srt = short_sequence(ctx, events, name, a, b, os.path.join(d, safe(name)), xml, log, record is not None)
        seqs.append(x)
        if srt:
            srts.append(srt)
        if record is not None:
            import ae_template
            p = os.path.join(d, safe(name), "animated.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(ae_template.clips(events, record, a, b, ctx.cfg), f)
            animated.append("%s\t%s" % (name, p))
    title = jobs[0][0] if len(jobs) == 1 else "Shorts"
    # a bin of its own per send: names repeat between sends, and Premiere's timeline list is in no useful
    # order, so this bin is how place-captions.jsx knows which timelines are the ones just sent
    folder = "Shorts Toolkit - %s - sent %s" % (os.path.basename(ctx.base), time.strftime("%Y-%m-%d %H.%M.%S"))
    path = os.path.join(d, safe(title) + ".xml")
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4"><bin><name>%s</name>'
                '<children>%s</children></bin></xmeml>\n'
                % (escape(folder), "".join(seqs)))
    with open(os.path.join(d, "animated.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(["BIN\t" + folder] + animated) + "\n")
    # what the Premiere script imports (premiere/import-shorts.jsx)
    with open(os.path.join(d, "import.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join([path] + srts) + "\n")
    return path


def export_one(ctx, events, jobs, record, name="All Shorts - editable", log=print, out=None):
    """Every Short end to end on ONE timeline, with every caption and beep a clip you can reach
    without opening anything, and a marker where each Short starts. Uses the media of the last
    send where it can. Returns (the XML's path, its animated.txt for place-captions.jsx)."""
    import ae_template
    d = out or out_dir(ctx)
    os.makedirs(d, exist_ok=True)
    _INFO.clear()
    first = next((it for it in ctx.seq.video if it.path), None)
    if not first:
        raise SystemExit("No video on the timeline.")
    xml = Xml(Rate(media(first.path)["fps"]))
    off, v1, v2, v3, voice, beeps, effects, music, marks, caps = 0.0, [], [], [], [], [], [], [], [], []
    for n, (short, a, b) in enumerate(jobs, 1):
        log("[%d/%d] %s" % (n, len(jobs), short))
        p = short_parts(ctx, events, a, b, os.path.join(d, safe(short)), xml, short, log, off=off, reuse=True)
        v1 += p["v1"]
        v2 += p["v2"]
        v3 += p["v3"]
        voice += p["voice"]
        beeps += p["beeps"]
        effects += p["effects"]
        music += p["music"]
        marks += [marker(off, off, short, "This Short starts here.", xml.rate)] + p["marks"]
        for c in ae_template.clips(events, record, a, b, ctx.cfg):
            caps.append(dict(c, start=round(c["start"] + off, 3), end=round(c["end"] + off, 3)))
        off += b - a
    vt = [track(v1), track(v2), track(v3), track([])]
    at = audio_tracks(xml, [voice, beeps] + lanes(effects) + [music])
    folder = "Shorts Toolkit - %s - one timeline %s" % (os.path.basename(ctx.base), time.strftime("%Y-%m-%d %H.%M.%S"))
    path = os.path.join(d, safe(name) + ".xml")
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4"><bin><name>%s</name>'
                '<children>%s</children></bin></xmeml>\n' % (escape(folder), sequence(xml, name, off, vt, at, marks)))
    data = os.path.join(d, safe(name) + ".json")
    with open(data, "w", encoding="utf-8") as f:
        json.dump(caps, f)
    listing = os.path.join(d, "animated-one.txt")
    with open(listing, "w", encoding="utf-8") as f:
        f.write("BIN\t%s\n%s\t%s\n" % (folder, name, data))
    log("%d Shorts, %d captions, %d beeps, %.0f s" % (len(jobs), len(caps), len(beeps), off))
    return path, listing


def export_long(ctx, events, parts, log=print, out=None):
    """The long video as one 1920x1080 timeline: every stretch end to end, a marker on each chapter,
    the recording on V1, captions as clips on V2, the sound as in the render. Returns the XML's path."""
    import longform
    root = out or out_dir(ctx)
    d = os.path.join(root, "Long video")      # sounds\ for its effects goes in here too
    os.makedirs(d, exist_ok=True)
    _INFO.clear()
    first = next((it for it in ctx.seq.video if it.path), None)
    if not first:
        raise SystemExit("No video on the timeline.")
    xml = Xml(Rate(media(first.path)["fps"]))
    lg = ctx.cfg.get("long") or {}
    off, v2, v3, voice, beeps, effects, music, marks = 0.0, [], [], [], [], [], [], []
    for n, p in enumerate(parts, 1):
        a, b = p["start"], p["end"]
        log("[%d/%d] %s" % (n, len(parts), p["title"]))
        x = short_parts(ctx, events if lg.get("captions", True) else [], a, b, os.path.join(d, "%02d" % n), xml, p["title"], log,
                        off=off, wide=True)
        v2 += x["v2"]
        v3 += x["v3"]
        voice += x["voice"]
        beeps += x["beeps"]
        effects += x["effects"]
        music += x["music"]
        marks += [marker(off, off, "CHAPTER: " + p["title"], "From: " + ", ".join(p["shorts"]), xml.rate)] + x["marks"]
        off += b - a
    vt = [track(v2)] + ([track(v3)] if v3 else [])
    at = audio_tracks(xml, [voice, beeps] + lanes(effects) + [music])
    name = lg.get("title") or "Long video"
    folder = "Shorts Toolkit - %s - long video %s" % (os.path.basename(ctx.base), time.strftime("%Y-%m-%d %H.%M.%S"))
    path = os.path.join(root, safe(name) + ".xml")
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4"><bin><name>%s</name>'
                '<children>%s</children></bin></xmeml>\n' % (escape(folder), sequence(xml, name, off, vt, at, marks, WIDE)))
    with open(os.path.join(root, "import.txt"), "w", encoding="utf-8") as f:
        f.write(path + "\n")
    with open(os.path.join(root, "animated.txt"), "w", encoding="utf-8") as f:
        f.write("BIN\t%s\n" % folder)             # none here: a list left by an earlier send must not be placed again
    with open(os.path.join(d, "chapters.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(longform.chapters(parts)) + "\n")
    return path
