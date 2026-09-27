# Changelog

Each problem found in real use gets an entry here: what went wrong, and what changed.

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
