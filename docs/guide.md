# Guide

Every step of the app, in order. Each step has a **Next →** button; skip any you don't need.

- [Before you start](#before-you-start)
- [1 · Markers](#1--markers)
- [2 · Captions](#2--captions)
- [3 · Shorts](#3--shorts) — including the [caption editor](#caption-editor)
- [4 · Screams & laughs](#4--screams--laughs)
- [5 · Look](#5--look)
- [6 · Render](#6--render)
- [7 · Posts](#7--posts)
- [8 · Publish](#8--publish)
- [Phone & tablet](#phone--tablet)
- [Keyboard](#keyboard)

## Before you start

- **Premiere project:** save it first (**Ctrl+S**). The toolkit reads the saved file and never
  changes it. Pick it on the left, **Open project…**, or **+ Folder** to list a whole folder.
- **Any video file:** **Open clip…**. No Premiere needed.
- **First run on a project** transcribes the audio: about 8 minutes per hour of video. After
  that it is cached and every step is quick.
- Each project keeps its own settings, Shorts list and choices.
- **☰ Projects** (top right) shows or hides the projects list, so the work area can use the whole window.

## 1 · Markers

Finds the best moments in the whole video.

| Control | What it does |
|---|---|
| **Find Shorts & place markers** | Marks loud, busy stretches, screams and laughs. Each marker starts and ends in a pause. |
| **+ More suggestions** | Adds more. Never repeats a marker, a Short, or one you removed. |
| **⚡ Find, add & render** | The short way: finds the moments, makes each new one a Short and renders those, in one press. Every Short can still be trimmed, captioned and rendered again in the later steps. With Autopilot on, posts and publishing follow. |
| **Turn all into Shorts** | Every marker becomes a Short. Or do it one at a time. |
| **Start over** | Removes the markers it placed. |
| **1 · Place markers in Premiere** | Puts them on your Premiere timeline as yellow range markers. |
| **2 · Cut at the markers** | Razors the Premiere timeline at each marker's start and end. |

The two Premiere buttons need the [Premiere panels](premiere.md).

## 2 · Captions

Optional. Skip it and the toolkit writes its own captions from the speech, 1–3 words at a time.

- **Sequence has no captions yet — Make captions:** Adobe Speech to Text (or the toolkit's
  Whisper) → caption lines → a real caption track in your sequence. Needs the
  [Premiere panels](premiere.md).
- **Making them by hand in Premiere:** create the captions, **Ctrl+S**, then **Watch for captions**.
- **Sequence already has captions:** the toolkit checks their timing against the speech and can
  write a **synced copy** of the project with the timing fixed. Your original is untouched. Pick
  the synced copy on the left to keep working from it.

## 3 · Shorts

Choose, trim and polish your Shorts.

**Finding them**

| Control | What it does |
|---|---|
| **Analyse video** | Scores every second and suggests Shorts built around a payoff. Set how many and how long. |
| **Accept** / **Accept all** / ✕ | Keep or dismiss suggestions. **+ More** digs deeper. |
| **Import from markers** | Marker-to-marker segments become Shorts. |
| **+ Add Short** | One at the playhead. |
| **Send to Premiere** | Your Shorts as named range markers on the Premiere timeline. |

In the **Your Shorts** list, the Short you changed most recently has a blue **Last worked on** tag,
and every Short you have trimmed, renamed or fixed captions on says *edited … ago* — so you can
see where you left off. Clicking a Short without changing it does not count.

**Timeline and player**

- The timeline shows markers, Shorts, suggestions, screams and laughs.
- Drag a Short's edges to trim, drag its middle to move, double-click between two markers to add one.
- Edges snap to markers and pauses. Hold **Alt** to move freely.
- Click a Short to open its side panel: name, start, end, **Start/End = playhead**, **▶ Play it**, **Remove**.

### Caption editor

Under the side panel. Changes are saved with the project and used by every render; Premiere is not touched.

| You want to | Do this |
|---|---|
| Hear a caption | Click its time |
| Fix the words | Type in its box (**Enter** = next line) |
| Take one out / bring it back | ✕ / ↺ |
| Fix its timing | Click into the line: **−0.1 / +0.1** or **◆ here** (the playhead) for start and end |
| Add one | **+ Caption at the playhead** |
| Add words the captions missed | Dashed rows are speech heard with no caption: ✓ adds, ✕ skips, **Add all** |
| Get better suggestions | **🎧 Listen again** re-hears just this Short with a bigger model (10–30 s). Each caption that sounds different shows **Heard:** with **Use** / ✕, or **Use all** |
| Type it like a document | **Text** (top right): one line per caption. An empty line removes that caption. Saves when you click away or press **Ctrl+Enter** |
| Fix it on the video | Click the caption over the player, type, **Enter** (Esc cancels) |
| Make the Short longer or shorter | **Short starts / Short ends** rows: 1 s or ¼ s earlier or later |
| Pull in a caption just outside | The two captions before and after the Short are listed greyed out: **Start here** / **End here** |

## 4 · Screams & laughs

Spells out drawn-out sounds as they happen: "AAAAHHH", "Ohhhh", "heh heh", "HAHAHA".

- Confident ones are **on**. Suggestions start **off** — press ▶ to listen, then switch them on.
- **Add** your own scream or laugh at any time, and pick the laugh spelling.
- Only the captions change. The sound is untouched.

## 5 · Look

How the captions and the frame look. Saved per project.

- **Presets:** 12 built in, plus **Save as my preset** for your own (shared across projects).
- **Captions:** font, size, height on screen, case, words shown at once, pop-in animation,
  spoken-word highlight (colour, bigger, box or fill), outline, shadow, spacing, background box.
- **Punctuation:** keep, soften (keeps ? and !), or remove.
- **Layout:** gameplay size over a blurred fill.
- **Censor (bleep):** off unless you turn it on. Curse words become `#$@&%!` and a TV beep. Add your own words.
- **Preview:** renders a short test clip. The last five stay so you can compare.

## 6 · Render

Makes the finished 1080×1920 videos in `<project>_shorts\`.

- **Render all**, **Render the ones not done yet**, or one Short.
- **Pause / Resume / Stop**, with a progress bar.
- Change anything and render again to replace a video.

## 7 · Posts

Writes a title, description, tags and hashtags for each rendered Short, from what is said in it.

- **Needs a local AI model** running through [Ollama](https://ollama.com) (default model
  `gemma4:12b-it-qat`). Nothing is sent to a cloud service. The step tells you if it isn't running.
- **Subject** — what the video is. Posts only name what is in here.
- **Never mention** — names or words to keep out. **Keep it clean** — no swearing.
- **Titles I like** — examples in your own voice.
- **Write posts**, **Write this one again**, **Write all again**. Other title options appear as chips you can swap in.
- Every box saves as you edit.

Read each one before publishing: the model quotes what it hears, including misheard lines.

## 8 · Publish

**YouTube**

1. **Connect YouTube** (once). Check it is the right channel — **Switch channel** if not.
2. Set your posting times (time and days), or every N hours.
3. **↻ Refresh from YouTube** shows where each Short stands: not uploaded, draft, scheduled, public.
4. **Preview** the plan, tick the Shorts, **Publish**.

Shorts already uploaded as drafts are filled in and scheduled, not uploaded again.

**TikTok**

1. **Connect TikTok** (once) and set your send times.
2. **Queue at my times** or **Send now**. They arrive in your TikTok **drafts**; you post from the phone.
   The PC must be on at the send time.

**Autopilot** (per project): after a render, write the posts and schedule them without asking.

**📊 Channel report** shows how your uploads are doing.

## Phone & tablet

Your phone can use the toolkit while the PC does the work.

1. On the PC: **📱** (top right) → **Allow my other devices**. Allow **Private networks** if Windows asks.
2. On the phone: scan the QR code and enter the 6-digit code.
3. Add it to the home screen to use it like an app.

Works on home Wi-Fi, or anywhere with Tailscale. Only paired devices get in, they cannot open
files or dialogs on the PC, and you can remove a device from the same panel. Off by default.

## Keyboard

In step 3, when you are not typing in a box:

| Key | Does |
|---|---|
| **Space** | Play / pause |
| **← →** | 1 second back / forward (**Shift** = 5) |
| **N** / **P** | Next / previous marker |
| **I** / **O** | Start / end a Short at the playhead |
| **Enter** | Play the selected Short |
| **Delete** | Remove the selected Short |
| **Ctrl+Z** | Undo |
