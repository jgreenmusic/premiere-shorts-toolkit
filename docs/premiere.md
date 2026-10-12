# Premiere

The toolkit works without touching Premiere. These pieces are for when you want its results
**inside** your Premiere project: markers on the timeline, cuts, a caption track.

- [The two panels](#the-two-panels)
- [What they do](#what-they-do)
- [Scripts](#scripts)
- [If something doesn't respond](#if-something-doesnt-respond)

## The two panels

Install once: in the app, **Install Premiere panels** (step 1 or 2), or from source
`python premiere_install.py`. Shorts Auto Run puts them in by itself when it needs Premiere.
Then restart Premiere and open both:

| Panel | Where in Premiere | What it is for |
|---|---|---|
| **Shorts Toolkit - Captions** | Window › Extensions | Runs the toolkit's scripts, adds a caption track, saves the project |
| **Shorts Toolkit - Speech** | Window › Plugins | Runs Adobe Speech to Text, places markers |

Dock them and leave them open. They check in every 1.5 s with both programs - the Shorts
Toolkit window and Shorts Auto Run - and do what either asks; the app shows when they are
connected. The Speech panel is alive even on Premiere's Home screen with no project open (that is
how a project gets opened or made for you); the Captions panel only once a project is open.

The Speech panel normally goes in through Adobe's own plugin installer. That installer refuses
when the Creative Cloud app is signed out, so the toolkit then copies the panel to
`%APPDATA%\Adobe\UXP\Plugins\External` and lists it in `...\UXP\PluginsInfo\v1\premierepro.json`
itself - the same two things Adobe's installer does.

Why two: Adobe only lets one kind of panel (UXP) start transcription, and only the other kind
(CEP/ExtendScript) add a caption track. Neither can press Premiere's own **Create captions** button.

## What they do

| In the app | Result in Premiere |
|---|---|
| Step 1 › **Place markers in Premiere** | Yellow range markers named "Suggested: …" |
| Step 1 › **Cut at the markers** | Every unlocked track razored at each marker's start and end |
| Step 2 › **Make captions** | A caption track made from Adobe's transcript or the toolkit's, project saved |
| Step 2 › **Have Premiere write them** (a plain recording) | Premiere opens, makes a project next to the recording, transcribes, adds the caption track, saves |
| Auto Run › Captions: **Premiere writes them** | The same, as the first step of a run - for a project or a plain recording |
| Step 2 › **Watch for captions** | Nothing — the toolkit waits for captions you make by hand, then carries on |
| Step 3 › **Send to Premiere** | Range markers named "Short: …" |

A toolkit action replaces only the markers it made before. Your own markers are left alone.

Saved copies of a project in the same folder with the same name start (`Project V0.1`,
`Project V0.2`) are accepted by the panels as the same project.

## Scripts

In `premiere\`. The app runs them for you through the Captions panel. To run one by hand:
VS Code + Adobe's **ExtendScript Debugger** → open the `.jsx` → **Ctrl+Shift+P** →
*ExtendScript: Evaluate Script in Attached Host*.

| Script | What it does |
|---|---|
| `suggested-markers.jsx` | Step 1's markers as yellow range markers |
| `cut-at-markers.jsx` | Razors every unlocked track at every marker |
| `shorts-to-markers.jsx` | Your Shorts as named range markers |
| `import-captions.jsx` | Imports an `.srt` as a new caption track |
| `animate-captions.jsx` | After *Upgrade Caption to Graphic*: pop-in and fade per caption, bigger for loud lines, wobble for screams. `MODE = "remove"` undoes it |
| `match-scale-vertical.jsx` | Sets the sequence to 1080×1920 and gives every clip the first clip's Scale |

**Tested so far:** placing markers through the Speech panel has been run in Premiere on a real
project. The scripts above have not yet been run there end to end — try them on a copy of your
project first.

**Finishing in Premiere instead of rendering here** (*Or: finish in Premiere* tab): **Prepare for
Premiere** marks the loud lines and screams for `animate-captions.jsx`, or export from Premiere
with captions **off** and let the toolkit burn its animated captions onto that export.
Premiere's own caption tracks cannot animate, which is why the animated look lives in the toolkit.

## If something doesn't respond

- **A panel is blank or says not connected:** close and reopen it from the Window menu.
- **"Premiere didn't answer":** open *Window › Extensions › Shorts Toolkit - Captions* once; Premiere does not always start it on its own.
- **After updating the toolkit:** press **Reinstall Premiere panels** (Auto Run does this by itself), then close and reopen Premiere once.
- **Auto Run says Premiere stopped while making or opening a project:** Premiere is showing a question. Answer it in Premiere, then **Continue from there**.
- **Logs:** `%TEMP%\shorts-toolkit-captions-panel.log` (Captions) and
  `%APPDATA%\Adobe\Premiere Pro\Logs\UXPLogs_*.log` (Speech).
