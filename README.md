# Shorts Toolkit

A companion for turning long Premiere Pro recordings into vertical Shorts: finds the clips,
checks and fixes caption timing, spells out screams letter by letter, and renders finished
1080×1920 videos with styled, animated captions — or animates the captions inside Premiere
if you'd rather finish there.

Works on any Premiere Pro project. If a sequence has no captions, the toolkit writes its own
from the speech (1–3 words at a time).

## Install (Windows)

Run **`ShortsToolkit-Setup-0.9.0.exe`** — no admin rights needed, no Python, nothing else to
install: the app bundles its own ffmpeg, fonts and laugh model. It opens in its own window
(Start menu / desktop shortcut). The first time a project is analysed it downloads the Whisper
speech model (~500 MB) once.

Build it yourself with `packaging\build-windows.cmd` (needs the dev setup below, PyInstaller,
Inno Setup, the ffmpeg "essentials" build in `build\ffmpeg\`, and `models\panns_sed.onnx` from
`tools\export_panns_onnx.py`).

## Phone & tablet

Your phone or tablet can use the toolkit while your PC does the work:

1. On the PC, click **📱 Phone** (top right) and switch on **Allow my other devices**.
   Windows may ask about the firewall — allow **Private networks**.
2. On the phone, scan the QR code (or type the address shown) and enter the 6-digit code.
3. Install it like an app: **iPhone** — Share → *Add to Home Screen*; **Android** — ⋮ →
   *Add to Home screen*.

Works on your home Wi-Fi, and anywhere with Tailscale on the phone (use the Tailscale address).
Only paired devices get in; they can't open files, folders or dialogs on the PC, and you can
remove any device from the same panel. Switched off, nothing outside the PC can reach it.
For a full Android install over https: `tailscale serve --bg 8766` on the PC.

The timeline works by touch: drag edges, drag to move, double-tap between markers, pinch to zoom.

## Start (from source)

Installed: open **Shorts Toolkit** from the Start menu. From source: `.venv\Scripts\python desktop.py`
(own window) or double-click **`Shorts Toolkit.cmd`** (in your browser). Save your project in Premiere first (Ctrl+S) — the toolkit reads the
saved file and never changes it.

Pick a project on the left, then use the tabs:

| Tab | What it does |
|---|---|
| **Shorts** | The editor. **Analyse video** scores every second and **suggests the best Shorts** (built around a payoff, snapped to pauses and markers) — accept, trim or dismiss them. The **timeline** shows the whole video with your markers, Shorts, suggestions, screams and laughs; drag edges to trim, drag to move, double-click between markers to add. The **player** plays your footage at the playhead (Space, I/O for start/end, N/P for markers, Ctrl+Z undo). **Import from markers** turns marker segments (or Premiere range markers) into Shorts; **Send to Premiere** puts your Shorts back on Premiere's timeline as range markers. **Render** makes finished vertical videos into `<project>_shorts\`. |
| **Screams & laughs** | Long "AAAH / OHHH / NOOO" moments spelled out letter by letter as the voice goes on. Loud ones are found automatically. Quieter or **uncaptioned** ones (Premiere often doesn't transcribe a scream) are listed as suggestions — press ▶ to listen and switch them on. You can also add one by hand and pick its letters. **Laughs** are spelled the same way — "heh heh", "hahaha", "HAHAHA", one syllable per burst — and never cover someone's speech unless you switch them on. |
| **Look** | Gameplay size (how much blur shows above and below), caption size and height, spoken-word highlight, bigger loud lines, colours, and a quick preview. Saved per project. |
| **Captions** | For captions made in Premiere: check their timing against the speech, and write a synced copy of the project that fixes them (your original is never changed). |
| **Premiere** | Finishing in Premiere instead: marks loud lines and screams for `animate-captions.jsx`, opens the scripts in VS Code, and burns captions onto a Premiere export. |

The bar at the bottom shows what's running. The app closes itself a minute after you close the tab.

## Setup (once)

Needs Python 3.10–3.13 and [ffmpeg](https://ffmpeg.org) (with libass) on PATH.

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

**Laugh detection (optional, ~1 GB):** it uses an AudioSet sound-event model (PANNs Cnn14).

```
.venv\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\python -m pip install panns_inference
```
Then put these two files in `%USERPROFILE%\panns_data\` (the package's own downloader needs `wget`,
which Windows doesn't have):
[`Cnn14_DecisionLevelMax.pth`](https://zenodo.org/record/3987831/files/Cnn14_DecisionLevelMax_mAP%3D0.385.pth?download=1)
(save it under exactly that name) and
[`class_labels_indices.csv`](http://storage.googleapis.com/us_audioset/youtube_corpus/v1/csv/class_labels_indices.csv).
Without them everything else works; the Laughs card just says it isn't installed.

The first time a project is analysed, the Whisper speech model downloads (~500 MB) and the
audio is transcribed on the CPU (about 8 minutes per hour of audio). It's cached after that.

## Where things are saved

Next to your project:

- `<project>_captions\` — the toolkit's working folder: `toolkit.json` (this project's settings,
  Shorts list and scream choices), transcripts, reports, previews.
- `<project>_shorts\` — your rendered Shorts.

A synced copy (`_captions-synced`, `-v2`, …) shares the original's folders.

## Command line

Every button runs one of these, so they work from a terminal too:

```
.venv\Scripts\python shorts.py timeline "Project.prproj" --count 12 --min 20 --max 45   # analyse + suggest Shorts
.venv\Scripts\python shorts.py shorts   "Project.prproj" --from-markers   # add marker segments as Shorts
.venv\Scripts\python shorts.py make     "Project.prproj"                  # render every Short
.venv\Scripts\python shorts.py make     "Project.prproj" --start 6:16 --end 6:32
.venv\Scripts\python shorts.py screams  "Project.prproj"                  # scream plan + .srt
.venv\Scripts\python shorts.py style    "Project.prproj" --preview 6:18   # try the look
.venv\Scripts\python shorts.py style    "Project.prproj" --video export.mp4   # burn onto a Premiere export
.venv\Scripts\python shorts.py captions "Project.prproj" [--fix]          # timing check / synced copy
.venv\Scripts\python shorts.py prepare  "Project.prproj"                  # data for animate-captions.jsx
```

`--sequence NAME` picks a sequence when a project has several.

## Premiere scripts (`premiere\`)

Run with VS Code + Adobe's **ExtendScript Debugger**: open the `.jsx`, press
**Ctrl+Shift+P → "ExtendScript: Evaluate Script in Attached Host"**, pick Premiere Pro.
Save your project first.

| Script | What it does |
|---|---|
| `animate-captions.jsx` | After "Upgrade Caption to Graphic": a pop-in and fade per caption — full pop after a pause, tiny in fast talk, fade only when very short, bigger for loud lines, wobble for screams (from **Prepare for Premiere**). Selected clips, else In/Out, else the top track. `MODE = "remove"` undoes it. |
| `shorts-to-markers.jsx` | Puts your Shorts on the active sequence as named range markers ("Short: …"), replacing only the ones it made before. |
| `import-captions.jsx` | Imports an .srt (e.g. `captions-with-screams.srt`) as a new caption track. |
| `cut-at-markers.jsx` | Razors every unlocked track at every sequence marker. |
| `match-scale-vertical.jsx` | Sets the sequence to 1080×1920 and gives every clip the first clip's Scale. |

## How it works (short version)

- **Reads the .prproj directly** (gzipped XML): clips, markers, captions (their text is a
  FlatBuffer blob). A synced copy changes only caption start/end numbers and is re-read to verify.
- **Speech:** faster-whisper word timestamps + the Silero voice detector bundled with it.
- **Laughs:** PANNs sound-event detection (AudioSet classes Laughter, Giggle, Snicker, Belly laugh,
  Chuckle) every 10 ms; syllables are counted from the laugh's own loudness pulses. About 25 s
  per hour of audio on the CPU, cached.
- **Rendering:** ffmpeg rebuilds the timeline range from the source files, lays the gameplay
  over a blurred copy, and burns in `.ass` subtitles (libass) with the bundled Montserrat font.
  Premiere effects (scale, crop, colour, gain) are not applied — the toolkit uses its own layout.

## Known limits

- Timing precision is about half a second (Whisper's word times are coarse).
- Uncaptioned-scream suggestions can still be groans or game audio — that's why they start switched off
  (ones the laugh model hears as laughing are moved to Laughs).
- The sound model does **not** recognise gamer yelling as "Screaming", so screams are still found from
  captions and voice; quiet chuckles under loud game audio or crosstalk can be missed.
- One caption track per sequence is assumed; clips with speed changes are approximated.

See `CHANGELOG.md` for everything that has changed and why.
