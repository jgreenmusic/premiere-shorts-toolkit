# Premiere Shorts Toolkit

Small tools for cutting long recordings into Shorts in Adobe Premiere Pro.

| Tool | What it does |
|---|---|
| `shorts.py captions` | Checks every caption against the actual speech in the sequence audio and reports which ones are early, late, cut off, or linger. With `--fix`, writes a synced **copy** of the project. |
| `shorts.py screams` | Turns drawn-out, loud AAAH / OHHH / NOOO / WHOAAA / YEAHHH captions into growing-letter captions ("O" -> "OO" -> ... -> "OOOOOOOHHHH") that follow the voice and speed up when louder. Writes a full replacement caption file. Audio is never changed. |
| `premiere/import-captions.jsx` | Imports an .srt as a new caption track on the active sequence. |
| `premiere/cut-at-markers.jsx` | Razors every unlocked track at every sequence marker. |
| `premiere/match-scale-vertical.jsx` | Sets the sequence to 1080x1920 and gives every clip the first clip's Scale. |

## Setup (once)

Needs Python 3.10–3.13 and [ffmpeg](https://ffmpeg.org) on PATH.

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

The first caption check downloads a Whisper speech model (~500 MB for `small`).

## Caption timing check

1. In Premiere, **save the project (Ctrl+S)** - the tool reads the file on disk.
2. Run:
   ```
   .venv\Scripts\python shorts.py captions "C:\path\to\Project.prproj"
   ```
3. Read `Project_captions\caption-report.txt` (summary) and `caption-report.csv` (every caption).
4. To fix, add `--fix`:
   ```
   .venv\Scripts\python shorts.py captions "C:\path\to\Project.prproj" --fix
   ```
   This writes `Project_captions-synced.prproj` next to your project. **Your original is never changed.**
   Close the project in Premiere and open the synced copy.

How it works:
- Rebuilds the sequence's audio from the clips on the timeline (so cuts and moves are respected).
- Transcribes it locally with [faster-whisper](https://github.com/SYSTRAN/faster-whisper) to get the time of every spoken word. The transcript is cached, so re-runs are fast.
- Matches caption text to the spoken words, then compares times.
- `--fix` only retimes captions that are actually off (`--all` retimes every one). Caption text and styling are untouched - only start/end times move, and neighbours are nudged so nothing overlaps.
- `--fix` also fits each caption's **length to the sound**: it stays up for the whole voiced
  word (a long "Ohhhh" keeps its length) and comes down when the voice stops. Captions too
  short to read with no room to grow are listed in `too-short-captions.txt`.
  Use `--no-durations` to fix timing errors only.
- Running on an already-synced copy writes `_captions-synced-v2`, `-v3`, ... - never overwrites.

Options: `--model tiny|base|small|medium|large-v3` (bigger = more accurate, slower),
`--sequence NAME` if several sequences have captions.

What counts as "off" is set at the top of `shorts.py` (`START_TOL`, `CUTOFF_TOL`, `LINGER_TOL`).

## Animated screams

```
.venv\Scripts\python shorts.py screams "C:\path	o\Project_captions-synced-v2.prproj"
```
Run it on your latest synced project. It writes `Project_captions\captions-with-screams.srt`:
every caption with its current timing, the screams replaced by growing letters, empty captions
dropped. `screams.txt` lists each scream; ones over 3 s are marked CHECK (can be laughter or game audio).

A scream must be drawn out (0.7 s+ of voice, ending when anyone says another word) and loud
(1.6x normal talking). `--loud 1.3` finds more, `--loud 2` fewer. Tuning is at the top of `screams.py`.

To use it in Premiere:
1. Run `premiere/import-captions.jsx` (below) and pick `captions-with-screams.srt`.
   (Or: File > Import the .srt, drag it onto the timeline at the very start.)
2. Hide or delete the old caption track.
3. Apply your saved caption **Track Style** to the new track - SRT files carry text and
   timing only, not styling.

## Running the .jsx scripts

1. Install VS Code and the **ExtendScript Debugger** extension (Adobe).
2. Open the `.jsx`, press **Ctrl+Shift+P → "ExtendScript: Evaluate Script in Attached Host"**, pick Premiere Pro.
3. Save your project first. Undo steps back one change at a time.

## Limits (known)

- **Timing precision is about half a second.** Whisper's word times are coarse, so the
  tool only calls a caption early/late when it is off by more than 0.5 s.
- Captions Whisper can't match (crosstalk, game noise, mumbling) are reported but never moved.
  On noisy multi-speaker footage expect a large "could not match" share; `--model medium`
  hears more words but is slower.
- Phrases said twice in a row ("Go. Go.") can match either copy - check those.

- Captions track: one caption track per sequence is assumed.
- Clips with speed changes are approximated.
- Audio gain, mutes and effects are ignored when rebuilding audio for analysis.
- Premiere's project format is undocumented. `--fix` re-reads what it wrote and refuses to keep a file that doesn't verify - but always keep your original.

See `CHANGELOG.md` for what has changed.
