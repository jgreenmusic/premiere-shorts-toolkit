"""Recordings with more than one sound track.

OBS can record several tracks into one file. Julian's OBS (set 2026-10-29) records:
    track 1  everything (the mix you hear)  - what the toolkit always uses for sound
    track 2  his mic only                   - tells the toolkit when HE is talking
    track 3  Discord only (friends)         - cleaner voices for telling friends apart
    track 4  game and everything else
A file with one track works exactly as before.

When such a file is dropped on a Premiere timeline, each track becomes its own audio clip
over the same stretch of the same file. Mixing those clips would play the mix plus every
single track on top of it, so mix_items() keeps one of them and the toolkit reads track 1.
"""
import os

MIC_TRACK = 2
FRIENDS_TRACK = 3
_COUNT = {}


def audio_streams(path):
    """How many sound tracks the file has (0 if it can't be read)."""
    try:
        key = (path, os.path.getsize(path), os.stat(path).st_mtime_ns)
    except OSError:
        return 0
    if key not in _COUNT:
        try:
            import av
            with av.open(path) as c:
                _COUNT[key] = len(c.streams.audio)
        except Exception:                        # noqa: BLE001 - unreadable = treated as one track
            _COUNT[key] = 0
    return _COUNT[key]


def mix_items(items):
    """The audio clips to mix: a stretch of a multi-track file that sits on several audio
    tracks of the timeline is kept once (the lowest track). Order is kept."""
    seen, out = set(), []
    for it in sorted(items, key=lambda a: getattr(a, "track", 0)):
        if getattr(it, "path", None) and audio_streams(it.path) > 1:
            k = (os.path.normcase(it.path), it.start, it.end, it.src_in, it.src_out)
            if k in seen:
                continue
            seen.add(k)
        out.append(it)
    keep = {id(x) for x in out}
    return [it for it in items if id(it) in keep]


def has_track(seq, n):
    """Does any audio clip's file have track n (1 = the first)?"""
    return any(it.path and audio_streams(it.path) >= n for it in seq.audio)
