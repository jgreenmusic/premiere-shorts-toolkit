# Premiere Shorts Toolkit

Small tools for cutting long recordings into Shorts in Adobe Premiere Pro.

| Tool | What it does |
|---|---|
| `shorts.py captions` | Checks every caption against the actual speech in the sequence audio and reports which ones are early, late, cut off, or linger. With `--fix`, writes a synced **copy** of the project. |
| `shorts.py screams` | Turns drawn-out, loud AAAH / OHHH / NOOO / WHOAAA / YEAHHH captions into growing-letter captions ("O" -> "OO" -> ... -> "OOOOOOOHHHH") that follow the voice and speed up when louder. Writes a full replacement caption file. Audio is never changed. |
| `shorts.py prepare` | Marks loud lines and screams for `animate-captions.jsx`. |
| `shorts.py style` | Styled captions with subtle animation (pop-in, spoken-word highlight, loud lines, screams) burned into your export. |
| `premiere/animate-captions.jsx` | Inside Premiere: gives every caption graphic its own pop-in + fade (after "Upgrade Caption to Graphic"). Settings at the top of the file. |
| `premiere/import-captions.jsx` | Imports an .srt as a new caption track on the active sequence. |
| `premiere/cut-at-markers.jsx` | Razors every unlocked track at every sequence marker. |
| `premiere/match-scale-vertical.jsx` | Sets the sequence to 1080x1920 and gives every clip the first clip's Scale. |

## The app (easiest way)

Double-click **`Shorts Toolkit.cmd`** (or the desktop shortcut). It opens in your browser and
runs only on this PC. Pick a project on the left, then go down the steps:

1. **Check caption timing** - how many captions are in sync, early, late, cut off, or linger.
2. **Fix timing & fit lengths** - writes a synced copy of the project (original untouched).
3. **Animated screams** - finds the long loud AAAH/OHHH moments; slider sets how loud counts.
4. **Animate in Premiere** - "Prepare for Premiere" marks loud lines and screams, then the
   `animate-captions.jsx` script does the animation inside Premiere. "Open in VS Code" buttons
   open each script.
5. **Burned-in look** *(optional)* - preview the highlighted-word style on a few seconds, or burn
   it onto your export.

The log bar at the bottom shows what's running. The app closes itself a minute after you close
the tab. Every button runs a `shorts.py` command, so everything below still works from a terminal.

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
.venv\Scripts\python shorts.py screams "C:\path\to\Project_captions-synced-v2.prproj"
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

## Styled, animated captions

Premiere's caption tracks can't animate, so this burns the captions into your export instead:

- each caption **pops in** (quick fade + slight 88% -> 104% -> 100% bounce) and fades out
- the **word being spoken is highlighted** gold (Whisper word times; estimated for unheard words)
- **loud lines** come up a little bigger, in capitals, highlighted orange
- **screams** grow letter by letter (see above), bigger, with a slight wobble

Font: Montserrat Black, bundled in `fonts/` (SIL Open Font License) - nothing to install.

1. Try the look first on a 12-second test clip (made straight from your recording, no export needed):
   ```
   .venv\Scripts\python shorts.py style "Project_captions-synced-v2.prproj" --preview 50:05
   ```
   Writes `Project_captions\preview-0-50-05.00.mp4`.
2. In Premiere, **turn the caption track off** and export the whole sequence (File > Export > Media).
3. Burn the captions on:
   ```
   .venv\Scripts\python shorts.py style "Project_captions-synced-v2.prproj" --video "C:\path\to\export.mp4"
   ```
   Writes `export_captioned.mp4`. Audio is copied untouched.
   If you exported only part of the sequence, add `--start 12:30` (where the export begins on the timeline).

Change the look in `STYLE` at the top of `style.py` (size, colours, position, pop speed).
`--no-highlight` turns off the word highlight.

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
