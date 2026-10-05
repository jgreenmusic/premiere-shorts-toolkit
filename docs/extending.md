# Adding to the toolkit

How to add a feature, check nothing else broke, and put out a new version. Everything here is
plain Python, one HTML page and two `.cmd` files — no special tools.

- [The shape of it](#the-shape-of-it)
- [Add a command](#add-a-command)
- [Add a button for it](#add-a-button-for-it)
- [Add a setting](#add-a-setting)
- [Add a whole step (a new tab)](#add-a-whole-step-a-new-tab)
- [Add something the page reads or saves](#add-something-the-page-reads-or-saves)
- [Add a kind of recording](#add-a-kind-of-recording)
- [Add a caption look or a font](#add-a-caption-look-or-a-font)
- [Add a Premiere script](#add-a-premiere-script)
- [Check your change](#check-your-change)
- [Put out a new version](#put-out-a-new-version)
- [Things that have bitten before](#things-that-have-bitten-before)

## The shape of it

```
button in ui\index.html  ->  /api/run in app.py  ->  a shorts.py command  ->  files in <project>_captions\
```

- **`shorts.py`** holds every job as a command. A feature starts here, so it also works from a terminal.
- **`app.py`** is a small local web server. It starts commands as background jobs and answers the page's questions.
- **`ui\index.html`** is the whole interface: one file, no build step. Edit, save, reload.
- **`<project>_captions\toolkit.json`** holds everything the user chose. Defaults are in `config.py`.

The [code map](how-it-works.md#code-map) says which file does what.

Run from source while you work: `.venv\Scripts\python app.py` (it opens in your browser; reload the
page after an edit to `ui\index.html`, restart it after an edit to a `.py` file).

## Add a command

In `shorts.py`:

1. Write `def cmd_myfeature(args):`. Start with `ctx = load_ctx(args)` — that gives you the sequence
   (`ctx.seq`), captions (`ctx.captions`), words (`ctx.words`), voice regions (`ctx.regions`), sound
   (`ctx.audio`), settings (`ctx.cfg`) and the working folder (`ctx.outdir`). Pass
   `need_words=False` if you don't need speech; it skips the slow part.
2. Register it in `main()`:

   ```python
   mf = sub.add_parser("myfeature", help="one line saying what it does")
   common(mf)                       # adds <project>, --sequence, --model
   mf.add_argument("--amount", type=float, default=1.0)
   mf.set_defaults(func=cmd_myfeature)
   ```
3. `print()` progress as you go — the app shows it in the bar at the bottom.
4. Add a row to [`commands.md`](commands.md). The tests fail if a command is missing from that page.

Try it: `.venv\Scripts\python shorts.py myfeature "path\to\clip.mp4"`.

## Add a button for it

1. In `app.py`, function `command()`: turn the page's request into your command's arguments.

   ```python
   if action == "myfeature":
       return ["myfeature", p, "--amount", str(o.get("amount", 1.0))]
   ```
2. In `ui\index.html`, inside the step's `view…()` function, add the button and call `run`:

   ```js
   `<button class="btn" id="myBtn" ${dis()}>Do my feature</button>`
   $("#myBtn").onclick = () => run("myfeature", { amount: 2 });
   ```

   `run()` starts the job, opens the log bar and redraws when it finishes. `dis()` greys the button
   out while another job is running. If your command needs extra values, add them to `body` in `run()`.

## Add a setting

1. Add it with its default to `DEFAULTS` in `config.py`. Old projects pick the default up automatically.
2. Read it in Python as `ctx.cfg["look"]["my_setting"]`.
3. In the page, save it with `saveCfg({ look: { my_setting: value } })` — it is merged into
   `toolkit.json` — and read it as `S.info.config.look.my_setting`.

## Add a whole step (a new tab)

All in `ui\index.html`:

1. Add `["mystep", "9 · My step"]` to `TABS`.
2. Write `function viewMystep() { $("#view").innerHTML = …; }`.
3. Add `mystep: viewMystep` to the list of views at the end of `renderInner()`.
4. Optional: add it to `NEXT` so the step before it gets a **Next →** button.

Then describe it in [`guide.md`](guide.md) and the step table in the README.

## Add something the page reads or saves

For answers that are quick (no background job), add an address in `app.py`:

- Reading: in `do_GET`, `if u.path == "/api/mything": return self.send_json({...})`.
- Saving: the same in `do_POST`; the request's values are in `b`.
- In the page: `await api("/api/mything?path=" + encodeURIComponent(S.current))` to read,
  `await api("/api/mything", { … })` to save.

Anything that should only work on the PC itself (not from a paired phone): add it to `PC_ONLY`, or
check `not self.remote`.

## Add a kind of recording

"Gaming / talking" and "Music stream" are entries in `KINDS` in `config.py`. To add one (a
podcast, say):

1. Add it to `KINDS`: a `label`, an `about` line, `speech` (transcribe and caption?) and
   `reactions` (screams and laughs?). It appears in the app's **What is it?** chooser by itself,
   and the steps it switches off are hidden.
2. If it should pick moments differently, write `summary()` and `suggest()` for it the way
   `music.py` does (same shape as `timeline.py`'s), and send it there in `analyse()` and
   `suggest()` in `shorts.py`.
3. Add it to the `choices` of the `kind` command in `shorts.py`.
4. Add a test next to `tests\test_music.py`.

## Add a caption look or a font

- **Look:** add a line to `PRESETS` in `style.py` (name, one-line description, the settings that
  differ from the defaults). It appears in step 5 by itself.
- **Font:** put the `.ttf` in `fonts\` and add it to `FONT_FILES` in `style.py`. Only fonts whose
  licence allows bundling (OFL, Apache).

## Add a Premiere script

Put the `.jsx` in `premiere\`. It shows up on the "finish in Premiere" tab by itself and runs through
the Captions panel. Premiere's script language is old (ES3): no `let`, no arrow functions, and a
`/` inside `[...]` in a regular expression must be written `\/`. See [Premiere](premiere.md).

## Check your change

```
check.cmd
```

It runs every test (about ten seconds) and says `ALL GOOD` or shows what failed:

| File | Checks |
|---|---|
| `tests\test_logic.py` | The caption logic: punctuation, repeated-phrase cleanup, your caption edits, missed words. |
| `tests\test_music.py` | Music mode on made-up music with known answers: tempo, beats, gaps, changes, bar-length Shorts, talking left out, the fade, and a music video in → finished Short out with nothing transcribed. |
| `tests\test_app.py` | Every file loads, every command answers `-h`, every button maps to a real command, the version matches everywhere, the server's pages answer, video is served correctly to phones, and a test video becomes a finished 1080×1920 Short. |

Neither touches your projects or your settings. Add a test next to the thing you added; the
simplest pattern is at the top of each file.

Then try it by hand in the app on a real project. Tests can't see whether a layout looks right.

## Put out a new version

1. **Version number** in two places: `__version__` in `shorts.py` and `AppVersion` in
   `packaging\installer.iss`. (The tests fail if they differ.)
2. **`CHANGELOG.md`**: a new `## <version> - <date>` entry saying what went wrong and what changed.
3. **`check.cmd`** → `ALL GOOD`.
4. **Build:** `packaging\build-windows.cmd` → `dist\installer\ShortsToolkit-Setup-<version>.exe`
   (a few minutes; what it needs is listed under [build from source](how-it-works.md#run-and-build-from-source)).
5. **Install it on your own PC first.** Close the toolkit, run the installer, open the app, and
   check the version shown at the top. Never install while a job is running.
6. **Commit and push.**
7. **Publish** on GitHub: Releases → Draft a new release → tag `v<version>` → attach the installer
   → paste the changelog entry. Or from a terminal:

   ```
   gh release create v<version> "dist\installer\ShortsToolkit-Setup-<version>.exe" --title "Shorts Toolkit <version>" --notes-file notes.md
   ```

Version numbers: the last number for a fix, the middle one for a new feature.

## Things that have bitten before

- **Caption edits are stored by the caption's start time.** If you change how words are cleaned up
  or grouped into captions (`clean_loops`, `auto_captions` in `captions.py`), saved edits in existing
  projects can stop matching. Compare old and new output on real `words-*.json` files first.
- **Captions can be added by the user**, so never look a caption up by its position in the list —
  use its `index`.
- **The installed app is not the source folder.** A change only reaches the installed app through a
  new installer.
- **Redrawing the page resets scrolling and reloads video** unless you go through `render()`, which
  saves and restores both. Don't set `innerHTML` on big parts of the page yourself.
- **The bundled ffmpeg** has no `-filter_complex_script`; pass filters with `-/filter_complex`.
- **Steps 7 and 8** use the Post Studio engine, a separate folder (`%USERPROFILE%\post-studio`).
  A change there needs a new toolkit installer too.
- **A new Python file that is only imported inside a function** should be added to `hidden` in
  `packaging\ShortsToolkit.spec`, so the installer is sure to include it.
