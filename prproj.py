"""Read (and carefully patch) Premiere Pro .prproj files.

A .prproj is gzipped XML. Everything here is read-only except `write_patched`,
which only ever rewrites exact numbers we located ourselves and always writes a
NEW file - the original project is never touched.
"""
import base64
import gzip
import re
import struct
from dataclasses import dataclass, field

TICKS = 254016000000  # Premiere ticks per second


@dataclass
class AudioItem:
    track: int
    start: int          # timeline ticks
    end: int
    src_in: int         # source ticks
    src_out: int
    path: str

    @property
    def speed_ok(self):
        return (self.end - self.start) == (self.src_out - self.src_in)


@dataclass
class Caption:
    index: int
    start: int                      # timeline ticks
    end: int
    text: str
    # character spans in the XML of the four numbers we may rewrite
    spans: dict = field(default_factory=dict, repr=False)

    @property
    def start_s(self):
        return self.start / TICKS

    @property
    def end_s(self):
        return self.end / TICKS


VideoItem = AudioItem                # same shape: timeline span + source span + file


@dataclass
class Marker:
    start_s: float
    dur_s: float
    name: str


@dataclass
class Sequence:
    name: str
    audio: list
    captions: list
    caption_frame: int              # caption track frame duration, ticks
    video: list = field(default_factory=list)      # clips with real media (not graphics)
    markers: list = field(default_factory=list)    # sequence markers, sorted

    @property
    def end_s(self):
        return max([a.end for a in self.audio + self.video] or [0]) / TICKS


class Project:
    def __init__(self, path):
        self.path = path
        with gzip.open(path, "rb") as f:
            self.xml = f.read().decode("utf-8")
        self._index = {}
        for m in re.finditer(r'<(\w+) Object(?:ID|UID)="([^"]+)"', self.xml):
            self._index[m.group(2)] = (m.group(1), m.start())
        self._blobs = dict(re.findall(
            r'<FormattedTextData Encoding="base64" BinaryHash="([^"]+)">(.*?)</FormattedTextData>',
            self.xml, re.S))

    # -- low level ---------------------------------------------------------
    def _span(self, obj_id):
        tag, start = self._index[obj_id]
        return start, self.xml.find("</%s>" % tag, start)

    def _obj(self, obj_id):
        s, e = self._span(obj_id)
        return self.xml[s:e]

    def _ref(self, text, tag):
        m = re.search(r'<%s Object(?:Ref|URef)="([^"]+)"' % tag, text)
        return m.group(1) if m else None

    def _number_span(self, base, text, tag):
        """Absolute (start, end) of the digits inside the first <tag>...</tag>."""
        m = re.search(r"<%s>(-?\d+)</%s>" % (tag, tag), text)
        return (base + m.start(1), base + m.end(1)) if m else None

    def _media_path(self, source_id):
        media = self._ref(self._obj(source_id), "Media")
        m = re.search(r"<FilePath>([^<]*)</FilePath>", self._obj(media)) if media else None
        return m.group(1) if m else None

    # -- public ------------------------------------------------------------
    def sequences(self):
        out = []
        for m in re.finditer(r'<Sequence ObjectUID="([^"]+)"', self.xml):
            out.append(self._sequence(m.group(1)))
        return out

    def _tracks(self, group_id):
        return re.findall(r'<Track Index="\d+" Object(?:Ref|URef)="([^"]+)"', self._obj(group_id))

    def _items(self, track_id):
        return re.findall(r'<TrackItem Index="\d+" ObjectRef="(\d+)"', self._obj(track_id))

    def _sequence(self, uid):
        seq = self._obj(uid)
        name = re.search(r"<Name>([^<]*)</Name>", seq).group(1)
        groups = re.findall(r"<Second Object(?:Ref|URef)=\"([^\"]+)\"", seq)
        audio, captions, video, cap_frame = [], [], [], TICKS // 60
        for gid in groups:
            tag = self._index[gid][0]
            if tag == "VideoTrackGroup":
                for n, tid in enumerate(self._tracks(gid), 1):
                    for iid in self._items(tid):
                        if self._index[iid][0] == "VideoClipTrackItem":
                            try:
                                v = self._audio_item(n, iid)
                            except (AttributeError, KeyError, TypeError):
                                continue            # graphics/titles: no media
                            if v.path:
                                video.append(v)
            elif tag == "AudioTrackGroup":
                for n, tid in enumerate(self._tracks(gid), 1):
                    for iid in self._items(tid):
                        if self._index[iid][0] == "AudioClipTrackItem":
                            audio.append(self._audio_item(n, iid))
            elif tag == "DataTrackGroup":
                fr = re.search(r"<FrameRate>(\d+)</FrameRate>", self._obj(gid))
                if fr:
                    cap_frame = int(fr.group(1))
                for tid in self._tracks(gid):
                    for iid in self._items(tid):
                        if self._index[iid][0] == "CaptionDataClipTrackItem":
                            captions.append(self._caption(iid))
        audio.sort(key=lambda a: (a.start, a.track))
        captions.sort(key=lambda c: c.start)
        # The font name is the first string of every styled block; learn it from
        # the blocks that have text too, then strip it everywhere.
        fonts = {b[0] for c in captions for b in c._strings if len(b) > 1}
        for i, c in enumerate(captions):
            c.index = i
            c.text = " ".join(s for b in c._strings for s in b if s not in fonts).strip()
            del c._strings
        video.sort(key=lambda v: (v.start, v.track))
        return Sequence(name, audio, captions, cap_frame, video, self._markers(seq))

    def _markers(self, seq):
        import json
        mid = self._ref(seq.split("</MarkerOwner>")[0], "Markers") if "<MarkerOwner" in seq else None
        out = []
        if not mid:
            return out
        for r in re.findall(r'ObjectRef="(\d+)"', self._obj(mid)):
            m = re.search(r"<DVAMarker>(.*?)</DVAMarker>", self._obj(r), re.S)
            if not m:
                continue
            try:
                d = json.loads(m.group(1)).get("DVAMarker", {})
            except ValueError:
                continue
            start = int((d.get("mStartTime") or {}).get("ticks", 0)) / TICKS
            dur = int((d.get("mDuration") or {}).get("ticks", 0)) / TICKS
            out.append(Marker(start, dur, d.get("mName") or d.get("mComment") or ""))
        return sorted(out, key=lambda m: m.start_s)

    def _audio_item(self, track, iid):          # audio AND video clip items
        item = self._obj(iid)
        clip = self._obj(self._ref(self._obj(self._ref(item, "SubClip")), "Clip"))
        num = lambda t, s: _num(t, s)
        return AudioItem(track, num("Start", item), num("End", item),
                         num("InPoint", clip), num("OutPoint", clip),
                         self._media_path(self._ref(clip, "Source")))

    def _caption(self, iid):
        base, _ = self._span(iid)
        item = self._obj(iid)
        clip_id = self._ref(self._obj(self._ref(item, "SubClip")), "Clip")
        cbase, _ = self._span(clip_id)
        clip = self._obj(clip_id)
        spans = {"Start": self._number_span(base, item, "Start"),
                 "End": self._number_span(base, item, "End"),
                 "InPoint": self._number_span(cbase, clip, "InPoint"),
                 "OutPoint": self._number_span(cbase, clip, "OutPoint"),
                 "clip_id": clip_id}
        # Premiere leaves a value out when it is 0 (e.g. a caption at 0:00)
        val = lambda k: int(self.xml[spans[k][0]:spans[k][1]]) if spans[k] else 0
        strings = []
        for bid in re.findall(r'<BlockVectorItem Index="\d+" ObjectRef="(\d+)"', item):
            h = re.search(r'BinaryHash="([^"]+)"', self._obj(bid))
            if h and h.group(1) in self._blobs:
                strings.append(_caption_strings(base64.b64decode(self._blobs[h.group(1)])))
        cap = Caption(0, val("Start"), val("End"), "", spans)
        cap._strings = strings
        return cap

    def write_patched(self, captions, new_times, out_path):
        """new_times: {caption index: (start_ticks, end_ticks)}. Writes a new gzipped project.

        Each caption's timeline Start/End and its clip In/Out move by the same deltas,
        so clip duration always equals timeline duration (Premiere requires that).
        """
        seen = set()
        edits = []
        for c in captions:
            if c.index not in new_times:
                continue
            if not all(c.spans[k] for k in ("Start", "End", "InPoint", "OutPoint")):
                continue                  # a value Premiere left out (0): can't rewrite in place, skip
            if c.spans["clip_id"] in seen:
                raise RuntimeError("caption clip %s is shared - refusing to patch" % c.spans["clip_id"])
            seen.add(c.spans["clip_id"])
            ns, ne = new_times[c.index]
            val = lambda k: int(self.xml[c.spans[k][0]:c.spans[k][1]])
            new_in = val("InPoint") + (ns - c.start)
            new_out = val("OutPoint") + (ne - c.end)
            for k, v in (("Start", ns), ("End", ne), ("InPoint", new_in), ("OutPoint", new_out)):
                edits.append((c.spans[k], str(v)))
        edits.sort(key=lambda e: e[0][0], reverse=True)
        xml = self.xml
        for (s, e), v in edits:
            xml = xml[:s] + v + xml[e:]
        with gzip.open(out_path, "wb") as f:
            f.write(xml.encode("utf-8"))
        return len(edits) // 4


def _num(tag, text):
    """Integer inside <tag>; Premiere omits the tag when the value is 0."""
    m = re.search(r"<%s>(-?\d+)</%s>" % (tag, tag), text)
    return int(m.group(1)) if m else 0


# Premiere stores caption text as a FlatBuffer. Rather than depend on its
# undocumented schema, pull out the length-prefixed UTF-8 strings; the font
# name is the only other string in a block and is removed in _sequence().
def _flat_strings(blob):
    out = []
    for o in range(len(blob) - 4):
        n = struct.unpack_from("<I", blob, o)[0]
        if 0 < n < 1000 and o + 4 + n < len(blob) and blob[o + 4 + n] == 0:
            try:
                s = blob[o + 4:o + 4 + n].decode("utf-8")
            except UnicodeDecodeError:
                continue
            if s.strip() and all(ch.isprintable() or ch in "\n\r" for ch in s):
                out.append(s)
    return out


def _caption_strings(blob):
    return _flat_strings(blob)
