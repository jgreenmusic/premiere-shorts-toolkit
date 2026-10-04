# How it works

- [What it saves and where](#what-it-saves-and-where)
- [How each part works](#how-each-part-works)
- [Speed](#speed)
- [Code map](#code-map)
- [Run and build from source](#run-and-build-from-source)
- [Limits](#limits)
- [When something goes wrong](#when-something-goes-wrong)

## What it saves and where

Next to your project (or video file):

| Folder / file | Holds |
|---|---|
| `<project>_captions\` | The working folder. Safe to delete — you lose this project's choices and it re-analyses. |
| `…\toolkit.json` | Everything you chose: Shorts list, markers, look, caption edits, scream and laugh choices, post settings. Plain text. |
| `…\words-*.json`, `voice-*.json`, `sounds-*.npz` | Cached transcript, voice regions and sound events. This is why the second run is fast. |
| `…\relisten.json` | What the bigger model heard for the Shorts you pressed **Listen again** on. |
| `…\preview-*.mp4` | Look previews. Old ones are removed after a day. |
| `<project>_shorts\` | Your rendered Shorts. |

A synced copy of a project (`_captions-synced`, `-v2`, …) shares the original's folders.

On the PC, not per project:

| File | Holds |
|---|---|
| `%USERPROFILE%\.shorts-toolkit.json` | Folders and clips you opened, your own look presets, paired phones. |
| `%LOCALAPPDATA%\ShortsToolkit\errors.log` | Errors, with details. |

Your Premiere project is never modified. The only project file the toolkit writes is a **new**
synced copy, in which only caption start and end numbers differ; it is read back to verify.

## How each part works

| Part | How |
|---|---|
| **Reading the project** | A `.prproj` is gzipped XML. The toolkit reads clips, markers and captions straight from it — Premiere does not need to be open. |
| **Speech** | faster-whisper (`small`) gives a time for every word; the Silero voice detector bundled with it says where there is a voice at all. Repetition loops the model invents are removed. |
| **Listen again** | Whisper `large-v3-turbo` on just one Short, without the voice filter (the filter discards speech under loud game audio). |
| **Finding moments** | Every second is scored for loudness, talking, word rate, screams and laughs. A suggestion is built around a payoff about two thirds in, and snapped to a marker or a pause. |
| **Screams** | Drawn-out interjections in the captions, or wordless voice bursts, measured for how long and how loud the voice really is. Letters grow with the voice. |
| **Laughs** | A sound-event model (PANNs Cnn14, AudioSet classes Laughter, Giggle, Snicker, Belly laugh, Chuckle) every 10 ms. Syllables are counted from the laugh's own loudness pulses. |
| **Captions on screen** | An `.ass` subtitle file (pop-in, word highlight, loud lines), burned in by ffmpeg/libass with bundled fonts. |
| **Rendering** | ffmpeg rebuilds the timeline range from the source files — topmost video clip, every audio clip mixed — over a blurred fill, at 1080×1920. |
| **Posts** | A local model through Ollama writes from the Short's own captions. Posts are compared with each other and rewritten when too alike. |
| **Publishing** | YouTube Data API: drafts are matched to your rendered files by file name and filled in; the rest are uploaded and scheduled. TikTok: sent to your drafts. |
| **The app** | A small web server on `127.0.0.1` only, shown in its own window. Every button runs a `shorts.py` command as a background job. |

## Speed

Measured on a Ryzen 9 9950X, CPU only.

| Job | Time |
|---|---|
| First transcription (Whisper `small`) | ~8 min per hour of video, once per project |
| Laugh detection | ~25 s per hour of video, once per project |
| **Listen again** (one 35 s Short) | ~15 s (the model downloads once, ~1.6 GB) |
| Rendering a 30 s Short | ~8 s |
| Writing posts (quick mode) | ~9 s per Short |

Everything after the first analysis reads from the cache.

## Code map

| File | Job |
|---|---|
| `shorts.py` | Every command (`markers`, `make`, `post`, …). Start here. |
| `app.py`, `ui/index.html` | The app: local server and the whole interface in one page |
| `desktop.py` | The app in its own window |
| `pipeline.py` | Loads a project the same way for every command |
| `prproj.py`, `clip.py` | Read a Premiere project / treat a video file as one |
| `captions.py` | Caption timing, your caption edits, missed words, loop cleanup |
| `timeline.py` | Per-second picture of the video and suggested Shorts |
| `screams.py`, `laughs.py`, `sounds.py` | Scream captions, laugh captions, the sound-event model |
| `style.py`, `previews.py`, `bleep.py` | Caption look and presets, look previews, censor mode |
| `render.py` | Building a finished Short with ffmpeg |
| `posting.py`, `youtube_step.py`, `tiktok_step.py` | Steps 7 and 8 |
| `bridge.py`, `premiere_install.py`, `premiere\` | The Premiere panels and scripts |
| `remote.py` | Phone and tablet companion |
| `config.py`, `runtime.py` | Per-project settings; where bundled files live |
| `packaging\` | Windows build (PyInstaller + Inno Setup) |

## Run and build from source

Needs Python 3.10–3.13 and [ffmpeg](https://ffmpeg.org) with libass on PATH.

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
```

- **Laughs from source** (optional, ~1 GB): `pip install torch --index-url https://download.pytorch.org/whl/cpu`
  and `pip install panns_inference`, then put
  [`Cnn14_DecisionLevelMax.pth`](https://zenodo.org/record/3987831/files/Cnn14_DecisionLevelMax_mAP%3D0.385.pth?download=1)
  and
  [`class_labels_indices.csv`](http://storage.googleapis.com/us_audioset/youtube_corpus/v1/csv/class_labels_indices.csv)
  in `%USERPROFILE%\panns_data\`. Without them everything else works.
- **Steps 7 and 8 from source** need the Post Studio engine at `%USERPROFILE%\post-studio`.
  It is a separate repository that is not public; the installer includes it.
- **Installer:** `packaging\build-windows.cmd`. Needs PyInstaller, Inno Setup, the ffmpeg
  "essentials" build in `build\ffmpeg\`, and `models\panns_sed.onnx` from `tools\export_panns_onnx.py`.
- **When you change something:** bump `__version__` in `shorts.py` and `AppVersion` in
  `packaging\installer.iss`, and add a `CHANGELOG.md` entry saying what went wrong and what changed.

## Limits

- Timing is good to about half a second.
- Premiere effects (scale, crop, colour, gain) are not applied to renders. Clips with speed changes are approximated.
- One caption track per sequence is assumed.
- Scream suggestions can be groans or game audio — that is why they start switched off.
- The sound model does not hear gamer yelling as "Screaming", and can miss quiet chuckles under loud game audio.
- Posts quote what the model heard, including misheard lines. Read them before publishing.
- Windows only for now. macOS and Linux builds are on the [roadmap](../ROADMAP.md).

## When something goes wrong

1. Read the bar at the bottom of the app — it shows the job's own output.
2. Press **📋 Copy log**: version, Windows build, the last job and recent errors, with your home folder name removed.
3. Paste that into an [issue](https://github.com/jgreenmusic/premiere-shorts-toolkit/issues).

| Symptom | Likely cause |
|---|---|
| Old captions or clips show up | The project wasn't saved in Premiere. **Ctrl+S**, then pick it again. |
| Step 7 buttons are greyed out | The local AI (Ollama) isn't running. |
| A Premiere button says Premiere didn't answer | A panel isn't open — see [Premiere](premiere.md#if-something-doesnt-respond). |
| Nothing scheduled after **Publish** | No posting time set in step 8. |
| TikTok drafts never arrive | The PC was off at the send time. |
