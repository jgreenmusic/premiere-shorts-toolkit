"""Send Shorts to Premiere: each Short as its own vertical timeline you can keep editing there.

The toolkit still renders on its own (`make`); this hands Premiere the same Short in pieces.
It writes an FCP XML file (Premiere: File > Import) with one 1080x1920 sequence per Short:

  V1  the blurred background (rendered by the toolkit, no sound)
  V2  the recording itself, scaled and centred the way the render lays it out (Motion > Scale)
  V3  the styled captions, screams and laughs as a see-through layer (QuickTime Animation with
      alpha), cut into one clip per caption: slide or trim a clip to move that caption
  A1  the recording's sound, cut around every censored word (those pieces are switched off)
  A2  one beep clip per censored word (censor mode on with sound = beep)

and next to it <Short>.srt, the same caption lines as plain text: import it and drag it onto the
timeline for a Premiere caption track whose words you can retype.

Files go in the <project>_premiere folder (one folder per Short + beep.wav). Exporting again replaces them.
"""
import os
import re
import subprocess
import urllib.parse
from xml.sax.saxutils import escape

import bleep
import render
import style
from bridge import srt_time
from prproj import TICKS

W, H = render.W, render.H


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


def caption_clips(events, a, b):
    """[(start, end, text)] relative to a: one entry per caption as it appears on screen.
    A caption is drawn as several events (the highlight moves word by word; screams, laughs
    and held "Ohhh"s grow a letter at a time) - those are joined back into one clip."""
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
    return [(s, e, t) for s, e, t, _ in out if e - s > 0.005]


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


def caption_layer(ctx, events, a, b, fps, path):
    """The Short's styled captions drawn on a see-through 1080x1920 picture (QuickTime Animation,
    which keeps the alpha and stays small: empty frames cost almost nothing). Returns its path."""
    work = os.path.join(ctx.outdir, "work")
    os.makedirs(work, exist_ok=True)
    st = style.look(ctx.cfg)
    ass = os.path.join(work, "premiere.ass")
    style.write_ass(ass, [e for e in events if e[1] > a and e[0] < b], st=st, shift=a)
    style.copy_fonts(os.path.join(work, "fonts"), st)
    part = path + ".part.mov"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "color=black@0:s=%dx%d:r=%s:d=%.4f,format=rgba" % (W, H, fps, b - a),
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


def audio_pieces(seq, a, b, spans):
    """[(item, t0, t1, censored)] timeline seconds: every audio clip in range, cut at the spans."""
    out = []
    for it in seq.audio:
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

    def clip(self, name, path, start, end, src_in, enabled=True, scale=None, cid=None, channel=None, links=()):
        """One clipitem; start/end on the sequence and src_in in the file, all in seconds.
        channel: the source channel (1/2) of an audio clip; links: [(clip id, track, position)]
        that Premiere joins into one stereo clip."""
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
        x.append("</clipitem>")
        return "".join(x)

    def sound(self, clips, first):
        """One stereo track the way Premiere writes it: two XML tracks (left, right) whose clips
        are linked in pairs. clips = [(name, path, start, end, src_in, enabled)]; first = this
        track's number among the sequence's XML audio tracks. Returns [left track, right track]."""
        ids = [(self.next_id(), self.next_id()) for _ in clips]
        tracks = []
        for ch in (1, 2):
            items = []
            for pos, ((name, path, s, e, src, on), pair) in enumerate(zip(clips, ids), 1):
                links = [(pair[0], first, pos), (pair[1], first + 1, pos)]
                items.append(self.clip(name, path, s, e, src, on, cid=pair[ch - 1], channel=ch, links=links))
            tracks.append('<track currentExplodedTrackIndex="%d" totalExplodedTrackCount="2" premiereTrackType="Stereo">'
                          '%s<enabled>TRUE</enabled><locked>FALSE</locked><outputchannelindex>%d</outputchannelindex>'
                          '</track>' % (ch - 1, "".join(items), ch))
        return tracks


def track(items):
    return "<track>" + "".join(items) + "<enabled>TRUE</enabled><locked>FALSE</locked></track>"


def sequence(xml, name, dur, video_tracks, audio_tracks):
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
            '</media></sequence>'
            % (xml.n, escape(name), r.f(dur), r.xml(), r.xml(), W, H,
               "".join(video_tracks), "".join(audio_tracks)))


def short_sequence(ctx, events, name, a, b, d, xml, log=print):
    """Write one Short's media into d. Returns (its <sequence>, its .srt)."""
    seq, blur_trim = ctx.seq, ctx.cfg["layout"]["blur_trim"]
    os.makedirs(d, exist_ok=True)
    fps = xml.rate
    bg = os.path.join(d, "background.mp4")
    log("  background")
    bg = background(ctx, a, b, bg)
    capfile = os.path.join(d, "captions.mov")
    clips = caption_clips(events, a, b)
    if clips:
        log("  captions layer (%d captions)" % len(clips))
        capfile = caption_layer(ctx, events, a, b, fps.text, capfile)
    srt = write_srt(os.path.join(d, safe(name) + ".srt"), clips)

    v1 = [xml.clip("Blurred background", bg, 0, b - a, 0)]
    v2 = []
    for t0, t1, it in render._pieces(seq.video, a, b):
        if it:
            m = media(it.path)
            fg_w, fg_h = render.fg_size(m["w"], m["h"], blur_trim)
            # Premiere's Scale 100 = the file's own size; the render scales the gameplay to fg_h tall
            v2.append(xml.clip(os.path.basename(it.path), it.path, t0 - a, t1 - a, render._src(it, t0),
                               scale=100.0 * fg_h / m["h"]))
    v3 = [xml.clip(t or "caption", capfile, s, e, s) for s, e, t in clips]

    bl = bleep.settings(ctx.cfg)
    spans = bleep.spans(getattr(ctx, "words", None), bl, a, b)
    at = xml.sound([("censored" if cen else os.path.basename(it.path), it.path, t0 - a, t1 - a,
                     render._src(it, t0), not cen) for it, t0, t1, cen in audio_pieces(seq, a, b, spans)], 1)
    if spans and bl.get("sound") == "beep":
        beep = beep_file(os.path.dirname(d))
        at += xml.sound([("beep", beep, s, min(e, s + 10), 0, True) for s, e in spans], 3)
    if spans:
        log("  %d censored word(s)" % len(spans))
    vt = [track(v1), track(v2)] + ([track(v3)] if v3 else [])
    return sequence(xml, name, b - a, vt, at), srt


def safe(name):
    return re.sub(r'[<>:"/\\|?*]+', "-", name).strip() or "short"


def export(ctx, events, jobs, log=print, out=None):
    """jobs = [(name, start, end)]. Writes the media + one XML; returns the XML's path."""
    d = out or out_dir(ctx)
    os.makedirs(d, exist_ok=True)
    _INFO.clear()                                # the files written last time may have changed
    first = next((it for it in ctx.seq.video if it.path), None)
    if not first:
        raise SystemExit("No video on the timeline.")
    xml = Xml(Rate(media(first.path)["fps"]))
    seqs, srts = [], []
    for n, (name, a, b) in enumerate(jobs, 1):
        log("[%d/%d] %s" % (n, len(jobs), name))
        x, srt = short_sequence(ctx, events, name, a, b, os.path.join(d, safe(name)), xml, log)
        seqs.append(x)
        srts.append(srt)
    title = jobs[0][0] if len(jobs) == 1 else "Shorts"
    path = os.path.join(d, safe(title) + ".xml")
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4"><bin><name>%s</name>'
                '<children>%s</children></bin></xmeml>\n'
                % (escape("Shorts Toolkit - " + os.path.basename(ctx.base)), "".join(seqs)))
    # what the Premiere script imports (premiere/import-shorts.jsx)
    with open(os.path.join(d, "import.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join([path] + srts) + "\n")
    return path
