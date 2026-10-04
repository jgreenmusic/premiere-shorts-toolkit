# Command line

Every button in the app runs one of these, so they work from a terminal too.

- **Installed app:** `"%LOCALAPPDATA%\Programs\Shorts Toolkit\shorts-cli.exe" <command> …`
- **From source:** `.venv\Scripts\python shorts.py <command> …`

`<project>` is a saved `.prproj` or any video file. `--sequence NAME` picks a sequence when a
project has several. Add `-h` to any command for all its options. Times are `6:18` style unless noted.

## Find and choose

| Command | Does |
|---|---|
| `markers <project> [--count 10] [--min 15] [--max 30] [--replace]` | Step 1: place markers on the best moments. Run again for more. |
| `timeline <project> [--count 12] [--min 15] [--max 30]` | Analyse the whole video and suggest Shorts. |
| `shorts <project>` | List the project's Shorts. |
| `shorts <project> --from-markers [--min 5] [--max 180]` | Add every marker-to-marker segment. |
| `shorts <project> --add 6:18 6:45 [--name NAME]` | Add one Short. |

## Captions and sounds

| Command | Does |
|---|---|
| `captions <project>` | Check Premiere caption timing against the speech (report only). |
| `captions <project> --fix [--all] [--no-durations]` | Write a synced copy of the project. The original is never changed. |
| `relisten <project> --start SECONDS --end SECONDS` | Hear one stretch again with the bigger model (the caption editor's **Listen again**). |
| `screams <project> [--loud X]` | Scream plan and a replacement `.srt`. |
| `speech <project>` | Timeline words for the Premiere panels. |

## Look and render

| Command | Does |
|---|---|
| `style <project> --preview 6:18 [--seconds 12]` | Render a short test clip of the look. |
| `style <project> --video export.mp4 [--start 12:30]` | Burn the captions onto a Premiere export (exported with captions off). |
| `make <project>` | Render every Short. |
| `make <project> --index 3` / `--indexes 0,3,5` | Render some. |
| `make <project> --start 6:16 --end 6:32 [--name NAME]` | Render one range. |
| `make … [--out FOLDER] [--preset veryfast…slow]` | Where to, and x264 speed (default `medium`). |
| `prepare <project>` | Loud-line and scream data for `animate-captions.jsx`. |

## Post and publish

| Command | Does |
|---|---|
| `post <project> [--indexes 0,3] [--platforms …] [--fresh]` | Step 7: write titles, descriptions, tags. |
| `post <project> --schedule next` | …and queue them (`next` posting time, `now`, or `2026-10-01T15:00`). |
| `yt-connect [--forget]` | Log in to YouTube (`--forget` to change channel). |
| `publish <project> --plan plan.json` | Step 8: carry out a plan the app made. |
| `tiktok --connect` | Log in to TikTok. |
| `tiktok <project> [--indexes 0,3] [--when plan\|now]` | Send rendered Shorts to TikTok drafts. |
| `publish-due` | Post whatever is due in the queue (what the scheduled task runs). |

## Other

| Command | Does |
|---|---|
| `python premiere_install.py` | Install the two Premiere panels. |
| `python app.py` | The app in your browser. `python desktop.py` for its own window (needs `pip install pywebview`). |

`--model` (where offered) picks the Whisper model: `tiny`, `base`, `small` (default), `medium`,
`large-v3`. It must match the cached transcript, or the audio is transcribed again.
