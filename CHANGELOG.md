# Changelog

Each problem found in real use gets an entry here: what went wrong, and what changed.

## 0.16.4 - 2026-09-27

**Step 8 can't upload a Short twice, and doesn't lose tags.**

Found while scheduling the 21 V0.4 drafts after the 32 Pt 2 Shorts:
- Step 8 read only the newest 100 uploads. With 117 on the channel, the "Best 12" draft fell off
  the end and the preview planned to UPLOAD it again (a duplicate). Now it reads all of them.
- Even then, YouTube's uploads list was stale right after the 32 bulk uploads: it listed 2 videos
  twice and was missing that draft. The channel is now read from the uploads list AND a search of
  your own videos, de-duplicated - the draft was found and filled, 0 uploads.
- 1 of 21 updates came back with all 27 tags silently dropped; the same request again kept them.
  Publishing now checks the answer and resends once when tags vanish (Post Studio 0.4.4).
- Result: 21 drafts filled + scheduled daily at 12:00 PM, Oct 30 - Nov 19, right after the Pt 2
  run (Sep 28 - Oct 29); checked on YouTube: title, description, tags and time on all 21.

## 0.16.3 - 2026-09-27

**Publish is never a mystery grey button.** Julian: "why is the publish button greyed out? I just
set my time preferences" - it only enabled after Preview, and any change (like the times) reset it.
Now it's always clickable when Shorts are ticked: "Preview & publish N" runs the preview first and
fills the Will do column, then "Publish N" (click twice) sends it. The hint under it says which step
you're on.

## 0.16.2 - 2026-09-27

**Clicking around no longer "refreshes" the app.**

Problem: "every time I do something like select and deselect things, move to time markers etc it
will refresh the app." Selecting a Short in step 7, ticking a box in step 8, picking a Short in
step 6, toggling screams/laughs - each redrew the whole page (steps 7/8 also re-downloaded
everything with a "Loading..." flash), so it jumped back to the top and the video reloaded.
- Every redraw now keeps the page's and the lists' scroll positions, and keeps a playing video
  if it's the same file.
- Steps 7 and 8 redraw from what's already loaded; they only ask the engine / YouTube again when
  something really changed (opening the tab, Refresh from YouTube, after a job).
- Ticking/unticking Shorts in step 8 (and Select all / none) doesn't redraw at all - only the
  count and buttons change.
- Switching tabs still starts at the top.
- Tested in a browser: step 8 tick -> 0 server calls, scroll 700/200 kept; step 7 pick another
  Short -> 0 calls, scroll kept, panel switched; step 6 pick -> scroll kept.

## 0.16.1 - 2026-09-27

**Posting times: any way you write them, on the days you choose.**

Problem: "it's not accepting my specified posting times" - the box only took 24-hour "16:00";
"4:00 PM" or "4pm" was silently dropped (nothing saved, no message). Also asked for: "post on a
custom set of days at custom times".
- Step 8 has a **posting schedule** editor: rows of a time (a time picker) + the days it posts on
  (Mon..Sun buttons, "every day", remove, "+ Add a time"). E.g. 4:00 PM Mon-Fri + 12:00 PM Sat-Sun.
- Times are read however they're written: 16:00, 4pm, 4:00 PM, 4:30p, noon. Anything unreadable
  gets a message saying so instead of vanishing.
- Stored as "16:00 mon tue wed thu fri" (plain "16:00" = every day, so old plans still work);
  the queue's "next free time" follows the days too (Post Studio 0.4.3).
- Tested: weekdays 4 PM + weekends noon from Oct 2 -> Fri 4 PM, Sat noon, Sun noon, Mon 4 PM...

## 0.16.0 - 2026-09-27

**One program: Post Studio is built in. New step 8 · Publish puts the Shorts on YouTube.**

Asked for: "both post studio and studio toolkit should be in one program and it should keep the
same logical chain of operations for posting to youtube optimally so I can spend more time playing
and recording content."

- Post Studio's engine (writing posts, YouTube publishing) now runs INSIDE the toolkit and is
  bundled in the installer. No second app, no Post Studio window, one data folder.
- The chain: 1 Markers > 2 Captions > 3 Shorts > 4 Screams & laughs > 5 Look > 6 Render >
  **7 Posts** (write + edit) > **8 Publish**.
- **8 Publish**: YouTube connection (Connect / Switch channel), every Short with where it is on the
  channel (draft on YouTube / scheduled + when / public / not on YouTube yet), and one button:
  - already on YouTube (a draft uploaded in Studio, matched by file name) -> fill it in + schedule
  - not on YouTube -> upload + schedule
  - scheduled / public -> left alone, so nothing is ever uploaded twice.
  When: your posting times (e.g. 16:00 daily, from a date) or one every N hours from a start time,
  or public now, or text only. Times already taken on the channel are skipped. YouTube releases
  scheduled Shorts itself - the PC can be off. **Preview** shows what each Short gets and when;
  **Publish** (two clicks) does it, with the log.
- Step 7 is only writing/editing now (its scheduling bits and the "Ready to post?" panel moved
  into step 8). **Autopilot** = render -> write the posts -> publish with step 8's settings.
- Found on the way: Post Studio had been connected to the wrong channel (Julian Green); the
  Shorts live on **poosic** (a different Google account, now a test user of the app). Step 8 shows
  which channel is connected and has Switch channel.
- Checked against the real channel (read-only): 21 drafts, 4 scheduled, 2 public - matches
  YouTube Studio; preview planned 21 fills, Oct 2-22 at 4 PM, and skipped the 6 already out.

## 0.15.3 - 2026-09-27

**"Write + schedule all" no longer pretends it worked.**

Problem: Julian pressed Write + schedule all twice and "didn't see where they were being scheduled on
YouTube". Nothing was: no posting times were set and no account was connected, so all 128
attempts (32 Shorts x 4 platforms) failed with "No posting plan" deep in the log - and it still
ended with "Done."
- Step 7 opens with **Ready to post?**: per platform, account connected / posting times set, and
  whether automatic posting is on, with a button to Post Studio to fix it.
- Write + schedule all is disabled until posting times exist, and the command itself stops at once
  with what's missing instead of writing and failing 128 times.
- A note that Shorts already uploaded as Studio drafts belong in the YouTube drafts screen -
  scheduling uploads new copies.

## 0.15.2 - 2026-09-27

**Posts sound less like an ad.**

Problem: "the text is a bit too explanatory and cringe" - "That 'oh no' hit different",
"Confidence vs. Reality", "Maximum focus achieved", "The ultimate pep talk".
- Quick mode (Post Studio 0.4.1) writes dry and short: a 2-6 word title, usually a real line from
  the clip; a tiny second line or nothing; never explains the joke; one emoji at most; banned
  stock phrases (hit different, vs. reality, POV, the ultimate, epic, chaos, achieved...) - a post
  that uses one is rewritten. Misheard lines are not to be quoted.
- The louder angles (hot take, tease, question) are off in Quick mode - only "a line from the
  clip" or deadpan.
- New **Titles I like** box: a few titles in your own voice and the AI matches them.
- Tested on Pt 2 Shorts 01-08: "We did it.", "Why would you do that?", "Oh, we went through",
  "Maybe I'm not moving". Still quotes swearing and real names unless Keep it clean / Never
  mention are set.

## 0.15.1 - 2026-09-27

**Step 7 edits are saved the moment you make them.**

Problem: Julian edited the posts for his Shorts in step 7, then asked how to make them postable -
and none of it had been saved. Step 7 only sent text when Schedule was pressed (which went to the
queue, not back to the written posts), and clicking another Short reloaded the saved text, so
every edit on a Short he'd clicked away from was lost. There was no way to recover them.

- Every box in step 7 saves when you click out of it (green flash; red + message if it didn't).
  Edits go into Post Studio's written posts (`poststudio.py set-field`), so the queue, Schedule
  and the YouTube drafts screen all use them.

## 0.15.0 - 2026-09-27

**Writing posts: ~7 s a Short instead of ~95 s, YouTube tags filled to the 500-character max.**

Problem: "why does it take hours to write simple stuff and make tags". Measured ~95 s a Short
(~50 min for 32). Two causes:
- The AI model was RELOADED 2+ times per Short: frame reading asked for an 8K context, the summary
  and writing for 16K, and Ollama reloads the whole 7.6 GB model when that changes. Now one size.
- ~10 model calls per Short (4 frames, a summary, 4 platforms, rewrites).

- New **Quick** mode (default, step 7 "How much to write"): ONE model call per Short gives a
  title, one line, 4 hashtags and ~35 tags; TikTok/Instagram/Facebook get the one-liner, hooks and
  cover text get the title as placeholders. Sibling / never-mention / keep-it-clean checks still
  apply. **Detailed** (the old way) is still there.
- YouTube tags are topped up to the 500-character limit: the AI's tags first, then **Base tags**
  (new field) and automatic ones from the Subject ("chained together funny moments", "...gameplay").
- Measured on Pt 2 Short 02: 7.1 s, 31 tags, 500/500 characters.

## 0.14.0 - 2026-09-27

**Every Short's post is different - and about that Short.**

Problem (first real run, Pt 2): posts read alike. "The struggle is real in Chained Together" was the
title of two Shorts; most TikTok/Facebook posts opened with "Me and two friends..."; posts described
scenery ("industrial settings", "first-person or third-person?") instead of the moment; one title was
"WE WENT THROUGH", read off the Short's own burned-in captions; quotes came out as caption chunks
("Well," "at least it" "starts us right"); a spoken real name ("Zach") and swearing got quoted; and
editing captions never re-wrote a Short that already had posts.

- Each Short is written knowing what the other Shorts in the project already say: their first lines
  and hashtags are passed in, and a title/opening that still comes out too close (same first three
  words, or mostly the same wording) is rewritten automatically, up to twice.
- A different angle per Short, in rotation: quote, reaction, question, deadpan, tease, story, hot take.
- Built around the Short's own lines and sounds (e.g. laughter), not the scenery.
- "Notes" is now **Channel background**: true for every Short, never the opener, at most one field.
- New **What happens in this one** note per Short (side panel) - the fix for visual gags the frames miss.
- Text read off the frames is ignored for Shorts (it's their own captions).
- Caption chunks are joined into sentences before the AI sees them, so quotes come out whole.
- **Never mention** (names/words kept out of every post, even quotes) and **Keep it clean** (no
  swearing, stretched spellings included). A post that breaks either is rewritten.
- A Short whose captions changed since its posts were written is looked at again and rewritten
  automatically. **Write all again** redoes every Short from scratch.

Tested on Pt 2 Shorts 01-05 with the 12B: five different angles, no repeated openings, one too-close
title caught and rewritten ("That fall hit different"); Short 01 with Never mention = Zach + clean:
every post that quoted the swearing was rewritten, no "Zach".

## 0.13.1 - 2026-09-27

**"Write posts" did nothing you could see.**

Problem: pressed Write posts on Pt 2 - nothing applied and the log stayed empty.
- The local AI (Ollama) wasn't running. Each Short failed at the AI step and the job quietly went
  on to the next one, all 32 of them.
- The log was blank because the installed app's output was held in a buffer, so none of those
  failures showed.

Fixed:
- Step 7 says up front when the AI isn't running, with a **Start the AI** button (`brain ada` -
  its RAM guard refuses while the Omniplaylist is streaming or a game server is up, and says so).
  Write buttons are disabled until it's running.
- `post` checks the AI first and stops in seconds with that message; an AI error on one Short
  stops the whole run instead of repeating on every Short.
- Post output reaches the log line by line.
- Post Studio marks a Short "failed" instead of leaving it "analyzing" forever.

## 0.13.0 - 2026-09-27

**Step 7 · Post: titles, descriptions, tags, hashtags and upload settings per platform, then
scheduled posting.**

Asked for: apply the right description, title, hashtags, tags and upload settings for YouTube and
other platforms, then post to all of them, scheduled and automated.

- New tab **7 · Post** (after Render). Post Studio (separate app, `~/post-studio`) does the writing
  and posting; the toolkit runs its command line, so neither app depends on the other's insides.
- **Write posts** for every rendered Short - YouTube Shorts, TikTok, Instagram Reels, Facebook.
  The Short's own captions (with your caption edits) are the transcript, so Whisper doesn't run
  again. Already-written Shorts are reused; **Write this one again** redoes one.
- **Subject** + **Notes** per project: posts only name what's there (e.g. the game).
- Upload settings per platform, saved per project: made for kids, AI/synthetic label, category,
  TikTok privacy, comments/Duet/Stitch, paid partnership, share to grid...
- Per Short: every field editable, then **Schedule** - next free time in the posting plan, a
  chosen time, as soon as possible, or save as draft. Queue status shows on each Short.
- **Write + schedule all into the posting plan** in one go, and **Autopilot**: after each render,
  write the posts and queue them automatically.
- **Accounts, posting plan & queue →** opens Post Studio's Publish page.
- CLI: `shorts.py post <project> [--indexes] [--platforms] [--schedule next|now|TIME] [--fresh]`.

Tested on Pt 2, Short 01 (with the small 3B model, because the Omniplaylist was streaming - the
12B is the real one): captions -> 24 transcript lines -> posts for 4 platforms -> 3 scheduled,
TikTok correctly held back until a privacy choice is made. Posting itself is untested against
real accounts (none connected yet).

## 0.12.1 - 2026-09-27

**Whisper's repetition loops are left out of the captions.**

Problem: while editing, some stretches repeated one caption over and over - "Help me!" x11 at 23:42,
"No." x10 at 25:10, "Yeah." x12 at 29:38, "We got it." x9 at 44:02. Not an editor bug: Whisper
latches onto a phrase on screaming / noisy audio and repeats it.

- New `captions.clean_loops`: a phrase repeated 3+ times in a row is checked repeat by repeat; a
  repeat is left out when its words are piled onto one instant with no length, its confidence is
  under 50 %, it's faster than anyone talks (phrases only: under 0.1 s a word), or - unless it's
  90 %+ confident - the voice detector hears no voice under it. The most believable repeat of each
  phrase always stays. Real repeats ("wait, wait, wait…", "yeah, yeah, yeah") are untouched.
- On Pt 2: 106 of 5,742 words left out, in 33 places.
- Used everywhere the transcript is: the caption editor, renders and previews, the timing check,
  and the Premiere bridge's toolkit-speech route. The cached transcript isn't changed.
- A caption you retyped in the editor is never removed by this (one "no." at 12:04 that had been
  retyped as "Woah" would have vanished otherwise). All 40 existing edits on Pt 2 still match.

## 0.12.0 - 2026-09-27

**Edit or remove any caption, right in the app.**

Asked for: when a caption's words don't match what was said, fix them or take the caption out in the UI.

- Select a Short (step 3): its side panel lists **every caption in that Short** with its time.
  - Click the time to **hear it** (plays from just before).
  - **Type** to fix the words (Enter or click away saves). Changed ones get an accent border and
    show the original on hover.
  - **✕** takes a caption out; clearing the text does too. **↺** restores the original.
  - The caption under the playhead lights up while the video plays.
- Works for Premiere's captions and the toolkit's own (made from speech). Edits are saved per
  project (`toolkit.json` "caption_edits", keyed by start time) and used by **every render and
  preview**, with your Look and Punctuation settings. Your Premiere project isn't changed.
- A corrected caption's words are spread evenly over it for the word highlight (the new words
  have no heard times).

Tested: on a copy of Pt 2, an edited caption rendered with the new words and a stepping highlight,
a removed one was gone, the next one unchanged; the editor showed Short 01's 24 captions in the app.

## 0.11.5 - 2026-09-27

**Punctuation setting: captions without periods.**

Asked for: captions that don't show periods, from the app. Premiere has this built in only as the
**Remove Punctuation** checkbox in its Create captions dialog (scripts can't tick it), so:

- **Punctuation** setting per project, on the Look tab and on step 2's Automatic card (same setting):
  *Keep* / *No periods or commas (keep ? and !)* / *No punctuation at all*.
- Applies to the captions the toolkit adds to Premiere (Automatic) and to every Short it renders.
  Lines still break at sentence ends; the punctuation just isn't shown. Each word keeps its
  highlight timing. Apostrophes (don't), hyphens in words (co-op) and numbers (2.5) always stay;
  "no—way" becomes "no way".
- Step 2's By hand steps now point at Premiere's own **Remove Punctuation** checkbox.
- Screams and laughs are spelled as before (their "!" is part of the effect).

## 0.11.4 - 2026-09-27

**The Captions panel's script engine was broken - fixed, so cutting and caption tracks can run.**

Problem: "Cut at the markers" said Premiere didn't answer. Through the panel's debug console every
ExtendScript call - even `1+1` - returned "EvalScript error.": `host.jsx` had the regex
`/^.*[\\/]/`. An unescaped `/` inside `[...]` is fine in modern JavaScript but a syntax error in
ExtendScript (ES3), and one syntax error in a panel's host script breaks every call it makes.

- Fixed the regex (`[\\\/]`); scanned every `premiere/*.jsx` for the same mistake (none).
  Verified live in Premiere: `1+1` answers, `host.jsx` loads, Premiere's cutting tool (QE `razor`) is
  there. The cut itself hasn't been run yet.
- The panel now loads `host.jsx` itself on every start: Premiere keeps its first copy through page
  reloads, so an updated panel used to need a Premiere restart.
- A saved-as copy counts as the toolkit's project (`Pt_2V0.1.prproj` for `Pt_2.prproj`, same folder),
  in both panels - Julian saves versions as he goes.
- The Captions panel no longer starts itself with Premiere (the hidden start-up copy left the docked
  tab blank) and keeps its own log: `%TEMP%\shorts-toolkit-captions-panel.log`.

## 0.11.3 - 2026-09-27

**Markers really go into Premiere now - first confirmed live run.**

Problems found with Premiere open: the docked Captions panel was a blank shell (its page had
stopped and CEP never restarted it), and the Speech panel never reached the toolkit - UXP blocked
its requests to 127.0.0.1 (fixed with the `"all"` network permission). Premiere 26 also reports the
project path as `\?\C:\...`, which would have failed the "right project open" check.

- **Place markers** (and Shorts markers) now go through the **Speech panel** using Adobe's documented
  markers API (one undoable step, toolkit markers replaced, your own kept, then coloured). The
  Captions panel is only used if the Speech panel isn't there. Live: 20 markers added to Pt 2.
- The Speech panel strips the `\?\` prefix before comparing project paths.
- The Captions panel ships a `.debug` file (DevTools on localhost:8098) so a blank panel can be inspected.
- Premiere hot-loads a reinstalled Speech panel - no restart needed.
- Cutting and adding caption tracks still need the Captions panel (Adobe's UXP API has no razor
  or caption-track call).

## 0.11.2 - 2026-09-27

**Markers go into Premiere first; captions come after.**

Problem: the Premiere panel's status and install button only lived under step 2 (Captions), so it
looked like captions had to be made before markers could go on the timeline. And the panel had
never connected: Premiere did start it at launch, but that was the old panel looking on 8765 while
the old toolkit sat on a random port.

- Step 1 has an **In Premiere** card: the panel's status (connected / not open / Install), then
  **1 · Place markers in Premiere** and **2 · Cut at the markers**, then Next → captions.
- `cut-at-markers.jsx` now cuts at the **start and end** of range markers (it used to cut only at
  starts), so each Short becomes its own piece; its messages are full sentences.

## 0.11.1 - 2026-09-27

**Premiere scripts run from the toolkit - no more VS Code.**

Problem: "Put them in Premiere" (step 1) and "Send to Premiere" (Shorts) only opened the .jsx in
VS Code, and running it there (ExtendScript Debugger, attach, evaluate) didn't work for Julian.

- Those buttons now hand the script to the **Shorts Toolkit - Captions** panel inside Premiere,
  which runs it on the open project, on the toolkit's sequence, and reports back in the app
  ("Added 20 suggested marker(s)…"). New `/api/bridge/script`; only scripts in `premiere\` run.
- The "Or: finish in Premiere" tab has **Run in Premiere** on every script (VS Code is still a link).
- If the panel isn't open, the app says exactly where to open it.
- The marker scripts now return a full sentence instead of codes like "no list".

Tested with the real panel code under Node (Premiere mocked): no panel -> clear message, unknown
script refused, with the panel the markers message came back in 0.2 s.

## 0.11.0 - 2026-09-27

**Step 2 can make the captions in Premiere, then moves you on by itself.**

The ask: use Premiere's auto captions, but run it from the toolkit, and go straight to the next
step once the captions exist. Adobe has **no scripting call for the Text panel's Create captions
button** (checked against the Premiere 26.5 UXP API: transcription is scriptable since 26.5, caption
tracks are not; ExtendScript can add a caption track from a file but can't transcribe). So there
are now two ways, and both end the same:

- **Automatic** - two small panels inside Premiere that the toolkit drives (`bridge.py`):
  - *Shorts Toolkit - Speech* (UXP, `premiere/bridge-uxp`) runs **Adobe Speech to Text** on every
    audible clip of the sequence and sends the transcript to the toolkit.
  - The toolkit turns the words into caption lines - **Premiere style** (up to 42 characters, like
    Create captions' default) or **Shorts style** (1-3 words) - and writes an .srt.
  - *Shorts Toolkit - Captions* (CEP, `premiere/bridge-cep`) lays it on the sequence as a real
    Premiere **caption track** and **saves** the project.
  - Or pick **Toolkit speech (Whisper)** instead of Adobe's - then only the Captions panel is needed.
- **By hand** - you press Transcribe + Create captions in Premiere (your own caption preset) and
  save; **Watch for captions** re-reads the saved project every 2 s until they appear.
- Either way, as soon as the saved project has captions, the toolkit **runs the timing check and
  opens step 3** (switch: "Then check timing and go to step 3").
- **Install Premiere panels** button (and `premiere_install.py`): the Captions panel goes to
  `%APPDATA%\Adobe\CEP\extensions` with Adobe's PlayerDebugMode switch (needed for any panel not
  from the Adobe Exchange); the Speech panel is packed as a .ccx and installed with Adobe's own
  UnifiedPluginInstallerAgent. No admin rights. Restart Premiere after installing.
- CLI: `shorts.py speech <project>` writes the timeline words the panels use.
- **Fixed before it could bite:** the desktop app picked a random port each launch, so the panels
  could never have found it. It now uses 8765 (or the first free of 8767-8769) and the panels look
  on those. Reinstalling the panels now removes the old Speech panel first - Adobe's installer
  silently keeps an installed copy with the same version.

Tested: the whole toolkit side end to end with stand-in panels (queue, transcript -> timeline
mapping incl. the same file on two tracks and tick-based times, .srt, finish, failure, a stale
report ignored), the real panel scripts run under Node against the server with Premiere mocked
(port search, a muted track skipped, clip time placed on the timeline, the Speech panel staying
connected through a slow transcription, the import handshake), the Whisper route on the full 85-min Pt 2 (2,730 Shorts-style lines), the new
card rendered, and both panels installed on Albert (Adobe's installer lists the Speech panel as
Enabled). **Not yet run inside Premiere** - Adobe's transcript JSON layout isn't documented, so the
parser looks for any timed word; if it can't read it, the raw transcript is saved as
`premiere-transcript-raw.json` for the fix.

## 0.10.0 - 2026-09-27

**Step 1 is now Markers: the toolkit marks the best Shorts for you, from any clip.**

- **Open clip…** opens any recording or video file (mp4, mov, mkv, m4v, webm, avi, flv, ts) as a
  project - no Premiere project needed. It is treated as a one-clip timeline, so every step
  (speech, screams & laughs, the look, rendering) works on it. Opened clips are remembered in the
  project list, tagged "clip".
- **1 · Markers** (new first step): **Find Shorts & place markers** listens to the whole video and
  places range markers on the best moments (loud, busy stretches, screams, laughs), each starting
  and ending in a pause. Choose how many and how long (default 10 of 20-45 s).
- **+ More suggestions is always there** (top of the step and under the list): it adds more
  markers, skipping every marker you have, every Short, and everything you removed. When a video
  has no good moments left at that length, the app says so instead of just "done".
- Per marker: watch it in the player, **+ Short**, or ✕ remove (removed ones are never suggested
  again). **Turn all into Shorts**, **Start over**, and - for Premiere projects -
  **Put them in Premiere** (new `premiere/suggested-markers.jsx`: yellow range markers named
  "Suggested: …", replaced on each run, your own markers untouched).
- The placed markers appear on the Shorts timeline (step 3) and in **Import from markers**, and
  the Shorts suggestions no longer repeat them.
- CLI: `shorts.py markers <project or clip> [--count 10 --min 20 --max 45] [--replace]`.
- Steps renumbered: 1 Markers, 2 Captions, 3 Shorts, 4 Screams & laughs, 5 Look, 6 Render.
  A clip skips straight from Markers to Shorts (it has no Premiere captions to fix).

Tested on a 4-minute cut of the Chained Together Pt 2 recording: first run placed 3, + More
added 3 new ones with no repeats, Start over reset them, a removed marker stayed out of later
runs and off the timeline, and a 4th run correctly reported nothing left. The Premiere script
is **not yet tested inside Premiere**.

## 0.9.1 - 2026-09-27

**Workflow order, render controls, more suggestions.**

- **Tabs follow the order you work in:** 1 · Captions → 2 · Shorts → 3 · Screams & laughs →
  4 · Look → 5 · Render (and "Or: finish in Premiere"), each with a **Next →** button. A new user
  starts at step 1.
- **5 · Render** is its own step: Render all, **Render the ones not done yet**, per-Short render,
  quality (Fast / Balanced / Best), a live "Short 3 of 13 - 45%" progress bar, and the player.
  Render buttons were removed from the Shorts tab so rendering always comes last.
- **Stop, Pause, Resume** (Render step and the bottom bar). Pause freezes the job and its ffmpeg in
  place (psutil) and resumes exactly where it was; Stop ends the whole process tree, also when
  paused. Closing the app window stops a running render.
- **Renders write to `<name>.part.mp4`** and only take the real name when complete - a stopped or
  failed render can never leave a broken file that looks finished. Leftovers are cleared next run.
- **+ More suggestions:** digs deeper into the video, skipping everything already a Short or
  dismissed (dismissed ranges are no longer re-suggested; the excitement floor went 0.35 -> 0.2).
- `shorts.py make --indexes 0,3,5`; the page can open a project from its address (`?project=`).

Found in real use:
- A Render all had no way to stop - it was stopped by hand and left a half-written
  `Clip – 48-09.mp4` that the app showed as "Rendered". Fixed by the .part rendering above.
- Tested: pause froze the output at 9.18 MB for 5 s, resume continued, stop while paused leaves no
  ffmpeg behind.

## 0.9.0 - 2026-09-27

**Standalone Windows app + phone/tablet companion.**

- **Windows installer** (`ShortsToolkit-Setup-0.9.0.exe`, ~400 MB, per-user, no admin): the app
  runs in its own window (pywebview / Edge WebView2) with a console twin `shorts-cli.exe` for
  background jobs and terminal use. Bundles its own ffmpeg, fonts, Premiere scripts and the laugh
  model. Tested: silent install, from-scratch analysis, render with the system ffmpeg hidden,
  uninstall leaves nothing behind.
- **Laugh model runs on ONNX Runtime** - no PyTorch in the app. `tools/export_panns_onnx.py`
  converts it; the log-mel front end is numpy with the model's own mel filterbank. Matches the
  PyTorch original to 3e-7, and is a little faster (21 s vs 23 s per hour).
- **ffprobe dropped** (PyAV reads size and frame rate); ffmpeg "essentials" build (105 MB vs 242).
- **Phone & tablet companion:** 📱 Phone switches on a second listener (port 8766, home network +
  Tailscale). Pair with a 6-digit one-time code or QR code; devices get a revocable key (only its
  hash is stored), 10 wrong codes lock pairing for 5 minutes. Paired devices can't use file
  dialogs, open files/folders, change remote settings, or touch projects the toolkit doesn't
  list. Installable (manifest, icons, service worker where https allows).
- **Touch:** pointer events on the timeline, pinch to zoom, double-tap, wider edge grips.
  Phone layout: projects drawer, stacked panels, icon header, no keyboard hints.

Found while building:
- ffmpeg 9 **removed `-filter_complex_script`**, so renders crashed with the bundled ffmpeg;
  now `-/filter_complex` (works on 8 and 9).
- A "black render" was the game's own black frame at 6:21 - both ffmpeg builds matched exactly.
- The laugh package pulls in librosa + matplotlib (+PyTorch, ~1.5 GB) just for a spectrogram;
  replaced as above.
- Tested security through the real network address: unpaired -> pairing page / 401, wrong code
  403, codes work once, PC-only actions 403, unknown projects 403, removed device 401, off =
  unreachable.

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
