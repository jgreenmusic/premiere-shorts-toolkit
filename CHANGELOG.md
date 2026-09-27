# Changelog

Each problem found in real use gets an entry here: what went wrong, and what changed.

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
