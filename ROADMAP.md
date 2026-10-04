# Roadmap

Ideas agreed on but not built yet. Newest first.

## macOS build (with Ada) and Linux build (once Alvin is rebuilt)

The code is portable (Python, pywebview, onnxruntime, faster-whisper, ffmpeg all exist on both);
a build must be made ON each platform. What changes per platform:

- **Window:** pywebview uses WKWebView on macOS, GTK/Qt WebKit on Linux (no code change).
- **Packaging:** PyInstaller spec per OS (`.app` bundle / folder); installer = signed `.dmg`
  (macOS - Gatekeeper wants signing + notarising, needs an Apple Developer account for
  distribution beyond Julian's own Macs) and AppImage/.deb (Linux) instead of Inno Setup.
- **ffmpeg:** bundle a static macOS arm64 / Linux x86_64 build with libass + x264.
- **Code spots that are Windows-specific today:** `app.open_path` (explorer / os.startfile ->
  `open` / `xdg-open`), `shorts-cli.exe` name in `app.run_job`, `CREATE_NO_WINDOW` flags,
  `%LOCALAPPDATA%` in desktop.py, `.cmd` launchers.
- **Speed:** Apple M5 (Ada) runs ctranslate2 + onnxruntime natively (arm64) - likely as fast
  as or faster than Albert per hour of audio.
- **Premiere scripts** already work on macOS Premiere (ExtendScript is cross-platform); paths use
  `/` in File objects.

## ~~Laughs and reactions~~ - done in 0.7.0 (see CHANGELOG)

**Problem:** chuckles and laughs ("uh huh huh", "heh heh", "HAHAHA") are never captioned.
Whisper and Premiere's transcription drop non-speech sounds on purpose, and the Silero voice
detector only knows "voice / no voice" - so laughs show up only as unlabelled "no caption"
scream suggestions.

**Plan:**
1. **Sound-event classifier** trained on AudioSet (e.g. PANNs CNN14, CPU) run once per project
   next to transcription, cached. Classes used: Laughter, Giggle, Chuckle/chortle, Snicker,
   Belly laugh - and Screaming, Yell, Shout, Groan, Sigh, which also makes scream detection
   better (tells a real scream from a laugh, which loudness alone can't - see the 6:29 case).
   Cost: model + PyTorch, a few hundred MB.
2. **Spell the laugh from its rhythm:** count the 4-8 bursts/second to get syllables.
   Quiet chuckle -> `heh heh` / `huh-huh-huh`; laugh -> `haha`; big laugh -> `HAHAHAHA`,
   growing burst by burst like the screams.
3. **UI:** a Laughs section beside Screams (or one "Reactions" tab) with ▶ listen, on/off,
   spelling choice. Confident detections on, uncertain ones suggested.

**Open question:** confident laughs ON by default, or everything off until approved?

**Expect:** good on clear laughs; weaker on quiet chuckles under loud game audio or crosstalk
(the model hears the full mix).

## Premiere captions bridge - working since 0.11.4, three things left

Both panels load and markers are placed from the toolkit (first live run 0.11.3, Captions panel
fixed in 0.11.4). Still open:

- **Cut at markers** has never been run live from the panel.
- Adobe's transcript JSON has not been read in a real run. If it isn't read,
  `premiere-transcript-raw.json` shows its layout.
- Premiere's own Text panel calls private APIs (`require("uxp").mediaCoreSpeechToText.AutoCaptioningAPI
  .segmentIntoCaptions` + `hSLScripting.CaptioningScriptAPI.createCaptionTrack`) - the real Create
  captions. The Speech panel already reports whether they're visible to it (`apis` in its check-in).
  If they are, a later version could use them for Premiere's exact segmentation and caption presets.
- Apply a saved caption Track Style to the new track automatically.

## General polish

Collect issues here as they come up while making Shorts.

Open as of 2026-10-04 (0.24.2):

- **Captions that flash by in fast talk.** Premiere splits quick speech into 1-3 word captions
  that follow each other with no gap, so some are up for under 0.3 s and cannot be made longer
  without covering the next one (about 150 inside the Shorts of one 2-hour project). Idea: when
  rendering, join a caption that short with its neighbour into one line. Not built - it changes
  how the captions read, so it wants a yes first.
- **Timing fit depends on what the speech model heard.** Whisper `small` matched under half of
  one project's captions; unmatched ones are only trimmed, never moved or extended. The bigger
  model (`large-v3-turbo`, used by Listen again) would match more - about 19 minutes per 2 hours.
- **Phone video.** On an iPhone the app opens but the source video did not play (0.24.1 fixed how
  video is served; not re-tested on the phone). If it still fails: make a small phone-size preview
  per Short with ffmpeg on the PC.
- **Not yet confirmed in the real window:** caption list keeping its place, trimming without the page
  jumping, the Short starts/ends rows, the quick run button, the 0.24.0 layout.
- **Installer size** (~400 MB): the laugh model is 308 MB of it. Option: download it on first use.
- **First transcription** takes about 8 minutes per hour of audio. Batched Whisper is untested for quality.
- **GitHub release** is still 0.16.4.
- **No license file** in the repo yet.
- **Whisper loop cleanup lets one extra repeat through** when the looped phrase is two words
  ("Help me! Help me! ..."): it is matched as a four-word phrase. A fix was tried on 2026-10-04 and
  taken back out: on the six real transcripts it changed which repeats survive in both directions
  and would have orphaned two saved caption edits (edits are keyed by a caption's start time).
  Needs a step that re-keys saved edits before `clean_loops` may change.
- **Tests** (`check.cmd`) cover the caption logic, the app's pages, video serving, step 8's status
  and one whole run from a video file to a finished Short. Not covered: reading a real Premiere
  project (needs a small project file that is safe to publish), the Premiere panels, writing posts,
  and anything that talks to YouTube or TikTok.
