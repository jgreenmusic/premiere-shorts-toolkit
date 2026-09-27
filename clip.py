"""Open any recording as a toolkit project - no Premiere project needed.

A video file (an OBS recording, a phone clip, an export) becomes a one-clip
"sequence": its picture on video track 1, its sound on audio track 1, starting at
0:00. Everything downstream (speech, suggestions, markers, rendering) works on it
exactly as on a Premiere sequence. `open_project` picks the right reader by extension.
"""
import os

from prproj import TICKS, AudioItem, Project, Sequence

VIDEO_EXT = (".mp4", ".mov", ".mkv", ".m4v", ".webm", ".avi", ".flv", ".ts")


def is_clip(path):
    return str(path).lower().endswith(VIDEO_EXT)


def _probe(path):
    """(seconds, has video, has audio, frames per second)."""
    import av
    with av.open(path) as c:
        v = c.streams.video[0] if c.streams.video else None
        dur = c.duration / 1e6 if c.duration else 0.0
        if not dur:
            for s in list(c.streams.video) + list(c.streams.audio):
                if s.duration and s.time_base:
                    dur = max(dur, float(s.duration * s.time_base))
        fps = float(v.average_rate or v.guessed_rate or 30) if v else 30.0
        return dur, v is not None, bool(c.streams.audio), fps


class ClipProject:
    def __init__(self, path):
        self.path = path

    def sequences(self):
        dur, has_v, has_a, fps = _probe(self.path)
        if dur <= 0:
            raise ValueError("Couldn't read the length of %s - is it a finished recording?" % os.path.basename(self.path))
        ticks = int(round(dur * TICKS))
        item = lambda: AudioItem(track=0, start=0, end=ticks, src_in=0, src_out=ticks, path=self.path)
        return [Sequence(name=os.path.splitext(os.path.basename(self.path))[0],
                         audio=[item()] if has_a else [], captions=[],
                         caption_frame=int(round(TICKS / fps)),
                         video=[item()] if has_v else [], markers=[])]


def open_project(path):
    return ClipProject(path) if is_clip(path) else Project(path)
