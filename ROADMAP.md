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

## General polish

Collect issues here as they come up while making Shorts.
