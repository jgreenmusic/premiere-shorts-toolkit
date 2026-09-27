# Changelog

Each problem found in real use gets an entry here: what went wrong, and what changed.

## 0.8.0 - 2026-09-26

**Timeline editor + predicted Shorts.** The Shorts tab is now an editor for the whole video.

- **Analyse video** (`shorts.py timeline`): scores every second (loudness, talking, word rate,
  screams, laughs, shouted lines) and writes `timeline.json`. A few seconds once speech is cached.
- **Suggested Shorts** for any video, with or without markers: each is built around a payoff
  moment (about 2/3 setup before, 1/3 reaction after), start/end snapped to a marker if one is
  within 2 s, otherwise to a pause in the talking, never overlapping existing Shorts. Ranked
  0-100 with a reason ("1 laugh, lots of shouting"). Count and length range are adjustable.
  Accept, Accept all, or dismiss (remembered).
- **Timeline:** an overview of the whole video (excitement, markers, Shorts, suggestions, view
  window) and a zoomed editor: drag a Short's edges to trim (snaps to markers and pauses, Alt
  for free), drag it to move, double-click between two markers to make that segment a Short,
  wheel to zoom, Shift+wheel to pan. Overlapping Shorts stack in rows.
- **Player:** plays the source footage at the timeline position (maps timeline -> source file
  across clips). Keys: Space play, I / O set start / end at the playhead, N / P next / previous
  marker, arrows step 1 s (Shift 5 s), Enter play the selection, Delete remove, Ctrl+Z undo.
- **Premiere round trip:** `premiere/shorts-to-markers.jsx` writes your Shorts onto the
  timeline as named range markers ("Short: ..."), replacing only its own markers.
  `shorts-markers.csv` is kept in step on every change. Range markers made in Premiere
  import as ready-made Shorts.
- The source footage is served to the page only if the open project uses it.

Found while building:
- OBS writes the MP4 index at the END of the file (3.5 MB after 3.2 GB of video), so the
  browser has to fetch the tail first - the server's byte ranges handle it (2 MB in 0.02 s).
- Chrome doesn't load video in hidden tabs, which made automated playback checks look broken;
  the player now says plainly when a recording can't play in a browser (e.g. HEVC).

## 0.7.0 - 2026-09-26

**Laughs.** Chuckles and laughs are detected and spelled out as they happen ("heh heh",
"hehe", "hahaha", "HAHAHA"), one syllable per burst, in their own colour with a small
bounce on each syllable. From the ROADMAP.

- `sounds.py`: PANNs Cnn14 sound-event detection at 32 kHz, 10 ms frames, cached per audio
  (`sounds-*.npz`). ~25 s for an hour on the CPU. Optional - without torch it's skipped.
- `laughs.py`: laugh regions (smoothed laughter score >= 0.12, merged, >= 0.4 s), syllables
  from loudness pulses (capped at 5/s), spelling by kind and loudness, never over speech by
  default - confident laughs with room between captions are on, the rest suggested.
- App: "Screams & laughs" tab with a Laughs card (listen, spelling choice, on/off, add by hand);
  laugh colour on the Look tab. Premiere: `prepare` marks laughs and `animate-captions.jsx`
  bounces each syllable. The Premiere caption file includes laughs.

Found while building:
- **The model can't hear gamer yelling as a scream** (Screaming/Yell/Shout ~0 even on clear
  screams), so it doesn't improve scream detection directly - but many "no caption" scream
  suggestions (19:41, 24:45, 29:39, 44:32, 50:11) were really laughs; those now go to Laughs.
- **Its probabilities are low** (laughter peaks ~0.3-0.4), so thresholds are set from the
  distribution over a real hour, not the usual 0.5.
- Default open question settled: confident laughs ON, unsure/under-speech OFF (same as screams).

## 0.6.0 - 2026-09-26

**A companion for any project.** Shorts are now made and rendered by the toolkit itself.

- **Shorts list per project** (`toolkit.json`): add ranges by hand or **import the segments
  between sequence markers** (pick which), then `shorts.py make` / the app renders finished
  1080×1920 videos straight from the source media into `<project>_shorts\`.
- **Renderer** (`render.py`): rebuilds a timeline range (topmost video clip at each moment,
  every audio clip mixed), gameplay over a blurred copy, styled captions burned in. Keeps the
  source frame rate.
- **Blur bands 25% smaller** by default ("Gameplay size" in the Look tab, 0-100%).
- **Any project:** reads video clips and sequence markers; sequence picker; if a sequence has
  no captions, captions are made from the speech (1-3 words, Shorts style).
- **Per-project settings** (`config.py`): look, layout, scream choices, Shorts list.
- **App redesign:** tabs (Shorts / Screams / Look / Captions / Premiere), rendered Shorts play
  in the page, scream suggestions with ▶ listen + on/off switches, add-a-scream form, marker picker.

Problems found and fixed:
- **A scream Premiere never captioned couldn't be animated** (the "AAAHHH" at 6:29 in the first
  test). Wordless voice with no caption is now suggested as a scream ("no caption"), off until
  switched on - its loudness alone (0.9x talk) can't tell it from a laugh or game audio.
- **A caption inside a scream flashed for 2 frames** ("WE ALL." mid-"YEAAAHHH"): captions that
  start while a scream is on screen are now hidden.
- **Premiere leaves out a value when it is 0** (a clip or caption at 0:00 has no `<Start>`), which
  crashed reading projects whose footage starts at the beginning. Read as 0; such captions are
  skipped when patching.
- **Empty projects** stopped the app's server mid-request (no response). Now a plain message.

## 0.5.0 - 2026-09-26

**The app.** `app.py` + `ui/index.html`: a local browser UI over `shorts.py` (127.0.0.1 only,
standard library, no new dependencies). Project list grouped by original / synced versions,
the five steps as cards with plain-language descriptions, results as bars and tables (timing
check, drift across the video, screams with CHECK flags, previews playable in the page), a live
log bar, native file pickers, light and dark themes. `Shorts Toolkit.cmd` + a desktop shortcut
start it; it shuts itself down a minute after the tab closes.

**Smarter Premiere animation** (`premiere/animate-captions.jsx`):
- Per caption: full pop after a pause, tiny pop in back-to-back talk, fade only for very short
  captions (a pop reads as flicker).
- Loud lines pop bigger and stay slightly bigger; screams get a strong pop and a rotation
  wobble on the first letter, and the growing letters after it just appear.
- Loud/scream data from the new `shorts.py prepare` (`premiere-emphasis.csv`, found automatically
  next to the project). If a Short's times differ from the analysed sequence, the shift is found
  from matching caption text.
- `MODE = "remove"` strips the animation; re-running replaces it. Works on selected clips, else
  the In/Out range, else the whole top track.

Also: the check report records which project version it describes (`last-check.txt`), shown
in the app.

## 0.4.1 - 2026-09-26

- `premiere/animate-captions.jsx`: the in-Premiere route. After "Upgrade Caption to Graphic",
  adds a pop-in (Scale 88/104/100 over frames 0/3/5) and opacity fade in/out to every caption
  clip, each keyed to its own start. Selected clips, or all clips on the top video track.
  Prefers the text layer's own Scale; falls back to Motion with the anchor moved onto the
  caption line (`CAPTION_Y`) so it grows around the words. Skips clips already keyframed.
  Not yet run inside Premiere.

## 0.4.0 - 2026-09-26

**Styled, animated captions.** `shorts.py style` writes an `.ass` subtitle file and burns it into
the Premiere export with ffmpeg/libass (audio copied untouched). `--preview TIME` renders a
12 s 9:16 test clip straight from the source recording, no export needed.

- Pop-in (fade + 88/104/100% scale), fade-out, spoken-word highlight from Whisper word times
  (words Whisper missed are spread between heard ones by length).
- Loud lines (1.8x normal talk): bigger, capitals, orange highlight. Screams: growing letters,
  larger, slight random tilt, final pulse.
- Montserrat Black/ExtraBold bundled under the OFL, loaded via libass `fontsdir`.
- The matcher now keeps per-word times (`words` in each match) for the highlight.
- Fixed while building: a highlight step starting mid-pop snapped to full size; it now
  continues the animation.

## 0.3.0 - 2026-09-26

**Animated screams.** `shorts.py screams` turns drawn-out interjections into captions whose
letters grow with the voice, and writes a full replacement caption track
(`captions-with-screams.srt`) plus `premiere/import-captions.jsx` to import it. Audio untouched.

- Letter count scales with scream length (7/s, 5-28 letters); letters arrive in step with
  loudness, so a louder moment fills faster. Split pieces ("AH!" 0.08 s + "AH!") are merged.
- Problems found on the way: counting any continuous voice as the scream turned calm "Yeah."
  + more talking into 6 s "YEAAAHHH" (100+ false screams). A scream now ends at the next spoken
  word and must be 1.6x louder than the recording's normal talk (23 found).
- Screams over 3 s are flagged CHECK: some are 12 s voice stretches with no words
  (likely laughter or game audio).
- Why an .srt and not a patched project: adding new caption items means writing Premiere's
  undocumented FlatBuffer text format; importing an .srt lets Premiere create them.

## 0.2.0 - 2026-09-26

**Caption durations now follow the sound.** `--fix` fits every caption's length to how long
its words are actually voiced (skip with `--no-durations`).

- Voice activity from the Silero detector bundled with faster-whisper (cached per audio).
- Last word heard: the caption ends where that word's voice stops, + 0.15 s. A drawn-out
  interjection ("Ohhhh", "Whoa", "AH") may hold up to 4 s; other captions at most 1 s past the
  word. In continuous talk the word ends where the next spoken word starts.
- Words not heard by Whisper: the caption follows the FIRST burst of voice in it (its own
  words), not the last - voice after a real pause belongs to someone else. Trim only.
- Readable minimum (text length / 20 cps, 0.5-1.5 s) for every caption, only into empty space.
- Captions under 0.3 s with no room to grow are listed in `too-short-captions.txt` to merge by hand.
- Running on a synced copy writes `-v2`, `-v3`... and reuses the original's transcript cache.
- The printed summary reports the real final changes, not the plan before overlaps were settled.

Problems found on the way:
- Voice regions merge whole back-and-forth exchanges (median 1.15 s), so "voice continues"
  alone stretched captions over the next speaker's uncaptioned words.
- Trimming to the LAST voice in a caption kept "You." up for 3 s because someone else spoke later.
- First synced project opened in Premiere 2026 without errors (patch format confirmed).

## 0.1.0 - 2026-09-26

First version.

- `shorts.py captions`: caption timing check against speech (faster-whisper word timestamps),
  per-caption CSV + summary report, `--fix` writes a synced copy of the project.
- Reads Premiere 2026 `.prproj` directly: caption text (FlatBuffer blocks, including blocks
  de-duplicated by `BinaryHash`), caption times, and the audio edit.
- Imported `cut-at-markers.jsx` and `match-scale-vertical.jsx`.

Problems found on the first real project (1 h 2 m, 3 speakers over game audio, 2,596 captions)
and fixed before release:

- **Short phrases matched the wrong repeat.** "Oh." / "Yeah," matched the same words said
  5-8 s away, which would have moved correct captions. Now each caption's words must land
  where neighbouring captions (anchored by 3+ word matches) say its speech is.
- **Whisper word starts are coarse.** Words are packed end to end, so a pause is absorbed
  into the next word (a two-syllable word lasting 1 s). Early/late is only reported above 0.5 s, and
  implausibly long words have their start pulled in.
- **Edges judged on missing words.** A caption whose last word Whisper didn't hear looked
  like it "lingered". Start/end are now only judged if the word at that edge was heard.
- **`--fix` would have moved unmatched captions by a guess.** It now never touches
  captions with no evidence, and changes only the wrong edge (a lingering caption keeps
  its start).
- Summary printed the offset with the wrong sign.
