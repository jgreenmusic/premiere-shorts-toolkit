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
- [Shorts Auto Run](#shorts-auto-run) — every step in one go, then your review and sign-off
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
- **Transcript:** says which Whisper model the project's words come from. New projects use
  `large-v3-turbo` when Whisper runs on the graphics card (else `small`); a project you
  transcribed before keeps its words and is never transcribed again by itself.
  **Transcribe again with large-v3-turbo** redoes it when you want: the old transcript is kept
  (**Use small again** switches straight back), and the log says if any of your caption fixes
  stop lining up — that can happen only when the toolkit wrote the captions.

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

- **Render all**, **Re-render the ones changed** since they were rendered, **Render the ones not
  done yet**, or tick any Shorts and **Render the ones ticked**. They render one after another.
- Each Short says whether it's up to date or "Changed since rendered", and what changed.
- **Pause / Resume / Stop**, with a progress bar.
- Change anything and render again to replace a video.

### Edit in Premiere

To fix things by hand in Premiere (a caption a little early, a beep that doesn't cover a whole word),
send Shorts there: **Send all**, **Send the ticked**, or a Short's **Premiere** button. Premiere starts by
itself and makes `<project> - Shorts.prproj` in `<project>_premiere\` with every Short in it, saved - open that
file any time later. Sending again adds the new timelines to it. **Open in Premiere** opens it again without
sending; **Add to the open Premiere project** puts the last Shorts sent into whatever project is open instead.
Each Short becomes its own 1080×1920 timeline, laid out like the render:

| Track | What's on it |
|---|---|
| V1 | The blurred background (a video the toolkit makes) |
| V2 | Your recording, scaled and centred like the render (Motion › Scale) |
| V3 | The captions with your look, see-through, **one clip per caption** - slide or trim a clip to move that caption. Screams and laughs too |
| A1 | Your sound, cut around each censored word; those pieces are switched off |
| A2 | One **beep** clip per censored word - stretch, move, add or delete beeps |

A plain `.srt` of the same captions goes into the bin *Shorts Toolkit captions (text)*: drag it onto
the timeline when you want a Premiere caption track whose words you can retype (hide V3 then).

**What the toolkit changed is marked on each timeline** (Premiere's Markers panel lists them with notes):
BEEP (the word Whisper heard and where the beep sits), YOUR EDIT (text changed / caption added / removed /
timing you set), RE-TIMED (caption fitted to the speech, by how much), SCREAM / LAUGH, and CHECK - a caption
that hides a curse with no beep under it (Whisper didn't hear the word: add a beep by hand) or a transcript
placeholder like `000000`. Clips are coloured the same way: beeps and cut-out pieces Rose, your edits Mango,
re-timed captions Caribbean, screams/laughs Violet, CHECK Yellow.

By hand instead: **File › Import** the `.xml` in `<project>_premiere\` into any project. Export from Premiere when you're done; the toolkit's own render is unchanged.

Sending again after a change makes new timelines next to the old ones (delete the old ones in
Premiere if you don't need them). Files Premiere still has open are kept, and the new ones are named
`background 2.mp4`, `captions 2.mov` and so on.

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

## Shorts Auto Run

A second window that does every step above by itself and then waits for you. Open it from its own
shortcut (**Shorts Auto Run**), or press **⚡ Auto Run** at the top of the toolkit to hand it the
project you have open. It works on the same project files as the toolkit - they are two windows
onto one project, not two copies.

It edits your recording - picks moments, cuts, captions, renders. It never makes up picture or
sound. The one thing written for you is the text of the posts (step 7's titles, descriptions and
tags, by the AI on your own PC); untick **Posts** to leave that out.

### Start a run

Pick a project at the top (or **Open clip…**) and choose:

| Setting | What it does |
|---|---|
| **What is it?** | Gaming / talking or Music stream - the same choice as in the toolkit. |
| **Moments** | **Find** so many new moments of such a length, or **Don't look for new ones** to carry the Shorts you already made through the rest. Tick **…and also take the Shorts already in the project** to do both. |
| **Captions** | **Premiere writes them**: Adobe Speech to Text, as a real caption track in a Premiere project - see below. **The toolkit writes them**: from the speech it hears on this PC, no Premiere needed. Not shown when the project already has Premiere captions. |
| **Look** | Keep the project's look, or switch to a preset for this run. |
| **Render** | Speed against file size. |
| **Posts** | Write titles, descriptions and tags. Needs the local AI; it can start it by itself. |

Press **⚡ Start the run**. The steps tick off one by one; **Show the log** shows the same output
the toolkit's log bar does. **Stop** stops it where it is - **Continue from there** picks it up again.
A run on a new recording takes as long as the same steps by hand: the first transcription is the
slow part (about 8 minutes per hour of video).

### Captions written by Premiere

With **Premiere writes them** chosen, the Captions step runs first and does what you would do by
hand in Premiere:

1. Starts Premiere if it is closed (and puts the toolkit's two panels in if they are missing or old).
2. Opens the project. For a plain recording with no project, Premiere makes one next to it with
   the same name (`My recording.mp4` gets `My recording.prproj`) and puts the recording on one timeline.
   The recording itself is not changed.
3. Adobe Speech to Text transcribes it. A long recording takes a few minutes.
4. The lines go on the timeline as a real caption track, and the project is saved.

The run then carries on with that project - the window switches to it by itself - and checks the
captions' timing against the speech like any Premiere captions. Edit them later either way: **Edit**
on the Captions or Render card (the toolkit's caption list, per Short), or in Premiere's Text panel.

If Premiere cannot do it, the run stops at Captions and says why. **Continue from there** tries
again; **Let the toolkit write the captions instead** carries on without Premiere. The usual
reasons: one of the two panels is not open in Premiere (the message says which menu), Premiere
is showing a question that needs an answer, or the panels were just updated and Premiere needs
closing once - the run starts it again.

A run made with the toolkit's captions can still get Premiere's: **Have Premiere write them** on
its Captions card, then **Apply my edits** to render the Shorts again.

What a run does at each step:

| Step | Automatically |
|---|---|
| Moments | Places markers on the best moments (step 1's **Find Shorts**). |
| Captions | Premiere captions: checks their timing against the speech; renders fit the ones that are off. None yet: Premiere writes them first if you chose that, otherwise they are written from the speech. |
| Shorts | Every moment found in this run becomes a Short. |
| Screams & laughs | Finds them; the confident ones are on, the rest are left as suggestions. |
| Look | Uses the look you chose. |
| Render | Renders every Short that has no up-to-date video. |
| Posts | Writes the posts for every rendered Short that has none. |
| Publish | Asks YouTube where each Short stands and works out the plan. **Sends nothing.** |

### Review and sign off

When the run stops you get one card per step, in order:

- what the step made (the moments, the Shorts, the videos to watch with what each one says, the
  posts to read, the publish plan with dates);
- **Edit** - the toolkit's own page for that step, opened inside the window. Everything works as
  it does in the toolkit and is saved as you go. **Done — back to the review** closes it.
  **In Toolkit ↗** shows the same step in the Shorts Toolkit window instead, if you prefer two windows;
- **Looks good** - your sign-off for that step. **Sign off all** does every step at once.

A sign-off only counts for what you looked at. Change something afterwards - in either window - and
that step says **changed since you signed off** and wants looking at again.

### Change something, then carry it through

After any edit the review shows **Your changes aren't in the videos yet**, listing the Shorts
that changed and why (start or end moved, captions changed, screams or laughs changed, look
changed, the timeline changed). Untick any you want left alone and press **Apply my edits**:

- only those Shorts are rendered again;
- only the posts whose captions or length changed are written again;
- the publish plan is worked out again.

A new Short you add in the toolkit joins the run the same way.

### Publish

The last card, **Final sign-off**, stays locked until every step is signed off and no edits are
waiting. **Publish** shows the list one more time. The plan is checked against your channel again
at that moment - if anything moved (a time got taken, a Short is already up) nothing is sent and
you see the new plan first. With TikTok connected you can tick **Also send them to my TikTok drafts**.

Posting times, the YouTube login and the upload settings are the toolkit's own (step 8) - **Edit**
on the Publish card opens them.

### Good to know

- The two windows never work at the same time: while one renders or writes, the other waits
  and says so.
- A step that could not be done does not stop the run unless nothing can follow it. **Posts**
  says **needs you** if the local AI is off, **Publish** if YouTube is not connected or has no
  posting times; fix it and press **Try again** / **Check again**.
- Closing the window during a run stops the run. Open it again and press **Continue from there**.
- The toolkit's own **Autopilot** tick (steps 7 and 8) is a different thing: it publishes after
  every render without a review. Auto Run never does that.

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
