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
| `…\music-*.npz`, `musicev-*.npz` | Music projects: the beats/loudness/spectrum it measured, and where the sound model heard plain talking. |
| `…\audio-*.f32` | The recording's decoded sound (about 230 MB per hour of video), so each command starts in about a second instead of decoding it again. Safe to delete; it is rebuilt when needed. |
| `…\fit.json` | Fitted caption times for a project with Premiere captions. Rebuilt when the project is saved again. |
| `…\relisten.json` | What the bigger model heard for the Shorts you pressed **Listen again** on. |
| `…\preview-*.mp4` | Look previews. Old ones are removed after a day. |
| `…\renders.json` | What each rendered Short was made from (its range, the captions and choices inside it, the look), so a later change shows as "changed since". |
| `…\autorun.json` | Shorts Auto Run: the last run, how each step ended, and what you signed off. |
| `<project>_shorts\` | Your rendered Shorts. |

A synced copy of a project (`_captions-synced`, `-v2`, …) shares the original's folders.

On the PC, not per project:

| File | Holds |
|---|---|
| `%USERPROFILE%\.shorts-toolkit.json` | Folders and clips you opened, your own look presets, paired phones. |
| `%LOCALAPPDATA%\ShortsToolkit\errors.log` | Errors, with details. |
| `%LOCALAPPDATA%\ShortsToolkit\open-toolkit.json`, `open-autorun.json` | Which of the two windows is open and what it is working on, so they never run two jobs at once. Removed when the window closes. |

Your Premiere project is never modified. The only project file the toolkit writes is a **new**
synced copy, in which only caption start and end numbers differ; it is read back to verify.

## How each part works

| Part | How |
|---|---|
| **Reading the project** | A `.prproj` is gzipped XML. The toolkit reads clips, markers and captions straight from it — Premiere does not need to be open. |
| **Speech** | faster-whisper (`small`) gives a time for every word; the Silero voice detector bundled with it says where there is a voice at all. Repetition loops the model invents are removed. With a graphics card build of Whisper (below) new transcripts are made on the graphics card instead, with the same voice filter and word timing; new projects there use `large-v3-turbo`. |
| **Listen again** | Whisper `large-v3-turbo` on just one Short, without the voice filter (the filter discards speech under loud game audio). |
| **Finding moments** | Every second is scored for loudness, talking, word rate, screams and laughs. A suggestion is built around a payoff about two thirds in, and snapped to a marker or a pause. |
| **Music** | No speech model. From the sound itself: *beats* are sudden arrivals of new sound (spectral flux, 50 times a second); *changes* are where the eight seconds after sound different from the eight before; *gaps* are a second or more at least 35 dB under the loud parts. A second scores high when it is loud, busy, or something just came in. The pulse is found from how regularly the beats repeat; when it is clear, a Short is made a whole number of four-beat bars long. The sound-event model marks plain talking (reads "speech", not "music") so it is left out. |
| **Screams** | Drawn-out interjections in the captions, or wordless voice bursts, measured for how long and how loud the voice really is. Letters grow with the voice. |
| **Laughs** | A sound-event model (PANNs Cnn14, AudioSet classes Laughter, Giggle, Snicker, Belly laugh, Chuckle) every 10 ms. Syllables are counted from the laugh's own loudness pulses. |
| **Captions on screen** | An `.ass` subtitle file (pop-in, word highlight, loud lines), burned in by ffmpeg/libass with bundled fonts. |
| **Rendering** | ffmpeg rebuilds the timeline range from the source files — topmost video clip, every audio clip mixed — over a blurred fill, at 1080×1920. |
| **Posts** | A local model through Ollama writes from the Short's own captions. Posts are compared with each other and rewritten when too alike. |
| **Publishing** | YouTube Data API: drafts are matched to your rendered files by file name and filled in; the rest are uploaded and scheduled. TikTok: sent to your drafts. |
| **The app** | A small web server on `127.0.0.1` only, shown in its own window. Every button runs a `shorts.py` command as a background job. |
| **Shorts Auto Run** | The same server with one more page. A run is a list of steps; each step starts the same command its button in the toolkit would, and the next step starts when it ends. Editing a step shows the toolkit's own page inside the window. |
| **Changed since rendered** | Each render stores fingerprints of what it used. A Short is rendered again only when one of them differs: its range, the captions and caption fixes inside it, the screams and laughs inside it, the look, or the timeline under it. |

## Speed

Measured on a Ryzen 9 9950X, CPU only.

| Job | Time |
|---|---|
| First transcription (Whisper `small`) | ~8 min per hour of video, once per project |
| Laugh detection | ~25 s per hour of video, once per project |
| **Listen again** (one 35 s Short) | ~15 s (the model downloads once, ~1.6 GB) |
| Starting any command on a 2 h project | ~1.5 s (first time after an edit: ~9 s) |
| Rendering a 30 s Short | ~9 s |
| Reloading a Short's captions after an edit | ~10 ms |
| Writing posts (quick mode) | ~9 s per Short |

Everything after the first analysis reads from the cache.

Rendering uses the whole CPU already: running several renders at once was measured and is no
faster (6 Shorts: 58 s one at a time, 56 s three at a time), so they run one after another.

### Transcribing on the graphics card (optional)

faster-whisper only uses NVIDIA cards. For AMD (and Intel) cards the toolkit can use a
[whisper.cpp](https://github.com/ggml-org/whisper.cpp) build with Vulkan instead
(`whisper_gpu.py`): put `whisper-cli.exe` and its DLLs in `%USERPROFILE%\tools\whisper-vulkan\`
(or point `SHORTS_WHISPER_CPP` at the folder; `SHORTS_WHISPER_CPP=off` turns it off). Models
download into its `models\` folder on first use. If it is missing or fails, the processor is used.

Measured on an RX 9070 XT, on an 87-minute gaming recording:

| Model | Time | Words heard |
|---|---|---|
| `small`, processor (faster-whisper) | ~8 min per hour (above) | 6,300 |
| `small`, graphics card | 3.2 min | 6,150 |
| `large-v3-turbo`, graphics card | 1.9 min | 7,175 |

Word times agree with the processor's to 0.02 s (median). New projects use `large-v3-turbo` there; a project keeps the model of the transcript it already
has (step 2 **Transcribe again** changes it, keeping the old one). A transcript made on the
processor is used before a graphics card one of the same model, because caption edits are keyed
by caption start and different words could orphan them; graphics card transcripts are cached as
`words-<key>-<model>-gpu.json`.

## Code map

| File | Job |
|---|---|
| `shorts.py` | Every command (`markers`, `make`, `post`, …). Start here. |
| `app.py`, `ui/index.html` | The app: local server and the whole interface in one page |
| `desktop.py` | The app in its own window (`--autorun`: the Auto Run window) |
| `autorun.py`, `ui/auto.html` | Shorts Auto Run: the steps of a run, the review, sign-off, Apply my edits |
| `premiere_auto.py` | Premiere writing the captions by itself: start Premiere, open or make the project, transcribe, add the caption track, check the saved file |
| `stale.py` | Which Shorts changed since they were rendered, and why |
| `peer.py` | The two windows knowing about each other |
| `pipeline.py` | Loads a project the same way for every command |
| `prproj.py`, `clip.py` | Read a Premiere project / treat a video file as one |
| `captions.py` | Caption timing, your caption edits, missed words, loop cleanup |
| `timeline.py` | Per-second picture of the video and suggested Shorts |
| `music.py` | The same for a music project: beats, bars, changes, gaps, and the Shorts cut on them |
| `screams.py`, `laughs.py`, `sounds.py` | Scream captions, laugh captions, the sound-event model |
| `style.py`, `previews.py`, `bleep.py` | Caption look and presets, look previews, censor mode |
| `soundlib.py`, `sfx.py`, `soundfx\`, `tools\make_sfx.py` | The sound library; rules, placed sounds and music under a Short; the built-in sounds and the script that makes them |
| `longform.py` | The long video: chapters from the Shorts, render, chapter lines |
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
- **When you change something:** see [Adding to the toolkit](extending.md) - where each kind of
  change goes, `check.cmd` to test it, and the steps for a new version.

## Limits

- Timing is good to about half a second.
- Premiere effects (scale, crop, colour, gain) are not applied to renders. Clips with speed changes are approximated.
- One caption track per sequence is assumed.
- Scream suggestions can be groans or game audio — that is why they start switched off.
- The sound model does not hear gamer yelling as "Screaming", and can miss quiet chuckles under loud game audio.
- Posts quote what the model heard, including misheard lines. Read them before publishing.
- Music: bars are counted in fours; a pulse is only trusted when it is clear (about three songs in four in testing), otherwise cuts fall on beats and changes. The sound model does not call electroacoustic or experimental music "music" at all — which is why talking is ruled out rather than music ruled in.
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
