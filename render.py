"""Render a finished vertical Short straight from the project's source media.

For a timeline range it rebuilds the picture (topmost video clip at each moment) and
the sound (every audio clip, mixed), lays the gameplay over a blurred copy of itself
at 1080x1920, and burns in the styled captions. Premiere effects (scale, crop,
colour, audio gain) are not applied - this is the toolkit's own layout.
"""
import os
import shutil
import subprocess

from prproj import TICKS
import bleep
import style

W, H = 1080, 1920


def _pieces(items, a, b):
    """[(t0, t1, item-or-None)] covering [a, b): the highest-track item at each moment."""
    cuts = {a, b}
    for it in items:
        s, e = it.start / TICKS, it.end / TICKS
        if e > a and s < b:
            cuts.update(t for t in (s, e) if a < t < b)
    cuts = sorted(cuts)
    out = []
    for t0, t1 in zip(cuts, cuts[1:]):
        mid = (t0 + t1) / 2
        cover = [it for it in items if it.start / TICKS <= mid < it.end / TICKS]
        top = max(cover, key=lambda it: it.track) if cover else None
        if out and out[-1][2] is top and top is not None:
            out[-1] = (out[-1][0], t1, top)      # same clip continues
        else:
            out.append((t0, t1, top))
    return out


def _src(item, t):
    return (item.src_in + (t * TICKS - item.start)) / TICKS


def probe(path):
    """(width, height, frame rate as an ffmpeg string like '60/1'), via PyAV (no ffprobe needed)."""
    try:
        import av
        with av.open(path) as c:
            v = c.streams.video[0]
            r = v.average_rate or v.guessed_rate or 30
            return v.codec_context.width, v.codec_context.height, "%d/%d" % (r.numerator, r.denominator)
    except Exception:
        return 1920, 1080, "30/1"


def layout_filter(src_w, src_h, blur_trim):
    """Gameplay centred over a blurred copy. blur_trim shrinks the blur bands:
    0 = whole gameplay visible, 1 = gameplay fills the height (sides cropped)."""
    full_h = W * src_h / src_w                    # gameplay height at full width
    band = max(0.0, (H - full_h) / 2) * (1 - max(0.0, min(1.0, blur_trim)))
    fg_h = int(round((H - 2 * band) / 2)) * 2
    fg_w = int(round(fg_h * src_w / src_h / 2)) * 2
    crop = "crop=%d:%d" % (min(fg_w, W), fg_h) if fg_w > W else "null"
    # the blur is done at quarter size then scaled up - looks the same (checked side by side)
    # and a 30 s Short renders in 8 s instead of 22 s on the 9950X
    bw, bh = W // 4, H // 4
    return ("split[bg][fg];[bg]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,boxblur=6:2,"
            "eq=brightness=-0.06,scale=%d:%d[b];[fg]scale=%d:%d,%s[f];[b][f]overlay=(W-w)/2:(H-h)/2"
            % (bw, bh, bw, bh, W, H, fg_w, fg_h, crop))


def make_short(ctx, a, b, out_path, events, log=print, preset="medium", crf=18):
    seq = ctx.seq
    vid = _pieces(seq.video, a, b)
    if not any(p[2] for p in vid):
        raise SystemExit("No video on the timeline between %.1fs and %.1fs." % (a, b))
    first = next(p[2] for p in vid if p[2])
    sw, sh, fps = probe(first.path)
    work = os.path.join(ctx.outdir, "work")
    os.makedirs(work, exist_ok=True)

    inputs, fl = [], []
    # picture: one input per piece, gaps are black
    vlabels = []
    for i, (t0, t1, it) in enumerate(vid):
        dur = t1 - t0
        if it:
            inputs += ["-ss", "%.4f" % _src(it, t0), "-t", "%.4f" % dur, "-i", it.path]
        else:
            inputs += ["-f", "lavfi", "-t", "%.4f" % dur, "-i", "color=black:s=%dx%d:r=%s" % (sw, sh, fps)]
        idx = sum(1 for x in inputs if x == "-i") - 1
        fl.append("[%d:v]scale=%d:%d,setsar=1,fps=%s,setpts=PTS-STARTPTS[v%d]" % (idx, sw, sh, fps, i))
        vlabels.append("[v%d]" % i)
    fl.append("%sconcat=n=%d:v=1:a=0[vcat]" % ("".join(vlabels), len(vlabels)))
    # sound: every audio clip in range, delayed into place and mixed
    alabels = []
    for it in seq.audio:
        s, e = max(a, it.start / TICKS), min(b, it.end / TICKS)
        if e - s <= 0.001:
            continue
        inputs += ["-ss", "%.4f" % _src(it, s), "-t", "%.4f" % (e - s), "-i", it.path]
        idx = sum(1 for x in inputs if x == "-i") - 1
        ms = int(round((s - a) * 1000))
        fl.append("[%d:a]aresample=48000,asetpts=PTS-STARTPTS,adelay=%d:all=1[a%d]" % (idx, ms, len(alabels)))
        alabels.append("[a%d]" % len(alabels))
    if alabels:
        fl.append("%samix=inputs=%d:normalize=0:duration=longest,apad,atrim=0:%.4f[amix]"
                  % ("".join(alabels), len(alabels), b - a))
        # censor mode (off unless switched on): beep or mute each spoken curse
        bl = bleep.settings(ctx.cfg)
        sp = bleep.spans(getattr(ctx, "words", None), bl, a, b)
        fl += bleep.audio_filter("[amix]", "[acat]", sp, bl.get("sound"), b - a)
        if sp:
            log("  bleeping %d word(s)" % len(sp))

    # captions for this range, times shifted to start at 0
    ass = os.path.join(work, "short.ass")
    style.write_ass(ass, events, st=style.look(ctx.cfg), shift=a)
    style.copy_fonts(os.path.join(work, "fonts"), style.look(ctx.cfg))
    fl.append("[vcat]%s,ass=short.ass:fontsdir=fonts[vout]" % layout_filter(sw, sh, ctx.cfg["layout"]["blur_trim"]))

    # render to "<name>.part.mp4" first: a stopped or failed render never leaves a
    # broken file that looks finished
    part = os.path.splitext(out_path)[0] + ".part.mp4"
    graph = os.path.join(work, "graph.txt")
    with open(graph, "w", encoding="utf-8") as f:
        f.write(";\n".join(fl))
    cmd = ["ffmpeg", "-v", "error", "-stats", "-y"] + inputs + [
        "-/filter_complex", "graph.txt", "-map", "[vout]"]
    cmd += (["-map", "[acat]", "-c:a", "aac", "-b:a", "320k"] if alabels else [])
    cmd += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-t", "%.4f" % (b - a), os.path.abspath(part)]
    log("  rendering %s (%.1fs, %d video piece(s), %d audio clip(s))"
        % (os.path.basename(out_path), b - a, len(vid), len(alabels)))
    subprocess.run(cmd, cwd=work, check=True)
    os.replace(part, out_path)                   # only a finished video gets the real name
    return out_path


def snippet(ctx, a, b, out_path):
    """Short mp3 of the timeline audio, for listening to a scream candidate in the app."""
    seq = ctx.seq
    inputs, fl, labels = [], [], []
    for it in seq.audio:
        s, e = max(a, it.start / TICKS), min(b, it.end / TICKS)
        if e - s <= 0.001:
            continue
        inputs += ["-ss", "%.4f" % _src(it, s), "-t", "%.4f" % (e - s), "-i", it.path]
        k = len(labels)
        fl.append("[%d:a]asetpts=PTS-STARTPTS,adelay=%d:all=1[a%d]" % (k, int((s - a) * 1000), k))
        labels.append("[a%d]" % k)
    if not labels:
        return None
    fl.append("%samix=inputs=%d:normalize=0[out]" % ("".join(labels), len(labels)))
    subprocess.run(["ffmpeg", "-v", "error", "-y"] + inputs + ["-filter_complex", ";".join(fl), "-map", "[out]",
                    "-ac", "2", "-b:a", "160k", out_path], check=True)
    return out_path
