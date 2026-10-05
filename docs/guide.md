# Guide

Every step of the app, in order. Each step has a **Next →** button; skip any you don't need.

- [Before you start](#before-you-start)
- [Music streams](#music-streams)
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

## Music streams

At the top of every project is **What is it?** Leave it on **Gaming / talking** for anything
with people talking and reacting. Choose **Music stream** for a set, a performance or a stream
that is mostly music. The choice is saved with the project; change it any time, then press
**Find Shorts** (or **Re-analyse**) again so the moments are picked by the new rules.

What changes in a music project:

| | Gaming / talking | Music stream |
|---|---|---|
| Moments picked | Loud, busy talk, screams, laughs | Where the music is fullest or something comes in |
| A Short starts | In a pause in the talking | On a beat, on a change in the music, or on the first note after a gap |
| A Short ends | In a pause | On a bar line when there is a steady pulse (counted in fours); otherwise at a change or the quietest nearby moment |
| Talking between pieces | — | Left out |
| Sound at the end | Hard cut | Fades out (0.35 s) |
| Captions | Yes | Off, unless you tick **Captions for singing or talking** |
| Steps | 1–8 | Captions and Screams & laughs are hidden; the rest are renumbered |
| Usual length | 15–30 s | 20–45 s |

The three music controls are in step 1:

| Control | What it does |
|---|---|
| **Captions for singing or talking** | Off: nothing is transcribed (speech-to-text invents words over music), so the first run takes seconds. On: singing and talking are captioned like any other project and the Captions step comes back. Read them before you render — lyrics are often misheard. |
| **Fade out** | Seconds the sound takes to fade at the end of each Short. `0` = a hard cut. |
| **Fade in** | `0` = the Short starts right on the beat, which suits most music. Raise it for music that swells in. |

Good to know:

- Bars are counted in **fours**. Music in three, or with a changing pulse, is still cut on beats and changes — only the "whole bars" length is skipped.
- The marker list says why each one was picked: *something big comes in*, *2 changes*, *16 bars*.
- On the step 3 timeline the small ticks are beats and changes; a Short's edges snap to them (hold **Alt** for free).
- **Other people's music** (covers, DJ sets) can get a copyright claim on YouTube or TikTok. The toolkit cannot check or prevent that.
- Posts (step 7) for a music Short with captions off are written from **What it is**, your notes and the Short's own note — fill those in, there is no transcript to go on.

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
- **Sequence already has captions:** **Fit caption timing in my Shorts** (on by default) makes
  everything the toolkit renders move captions that are off and keep each one up for as long as
  its words are voiced. A caption you timed by hand in step 3 keeps your timing. **Run check**
  shows how far off Premiere's captions are.
- **Finishing in Premiere instead:** **Create synced copy** writes the same fix into a new copy of
  the project. Your original is untouched.

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

In the caption editor every caption has a button with **how long it is on screen** (`0.6s`).
Press it to change when that caption starts and ends: −0.1 / +0.1, half-second steps for the
end, or **◆ here** to use where the player is. A caption whose end you set keeps the screen
until then.

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
