"""Shorts Auto Run - every step of the toolkit done in one go, then held for your review.

    desktop.py --autorun            its own window ("Shorts Auto Run.cmd", or the installed shortcut)
    python autorun.py               the same page in your browser

It is the toolkit's own server with one more page (/auto) and the addresses under /api/auto/.
A run works through the same steps as the toolkit's tabs, with the same commands the buttons run:

    markers > captions > shorts > screams & laughs > look > render > posts > publish (plan only)

and then stops. Nothing is published until every step is signed off and Publish is pressed.
Captions can be Premiere's own (premiere_auto.py): the run opens Premiere, has Adobe's Speech to
Text write them as a real caption track and carries on - for a plain recording Premiere first makes
a project next to it, and the rest of the run works on that project. That step then goes first.
Each step can be opened for editing - the toolkit's own page for that step, inside this window or
in the Shorts Toolkit window. Afterwards "Apply my edits" renders and rewrites only what changed
(stale.py knows which Shorts those are).

What a run did and what was signed off is kept in <project>_captions\\autorun.json.
"""
import json
import os
import re
import tempfile
import threading
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import app
import config
import stale

# a stage's id is the toolkit tab that edits it
STAGES = [("markers", "Moments"), ("captions", "Captions"), ("shorts", "Shorts"), ("screams", "Screams & laughs"),
          ("look", "Look"), ("render", "Render"), ("post", "Posts"), ("publish", "Publish")]
LABEL = dict(STAGES)
ORDER = [s for s, _ in STAGES]
REQUIRED = ("markers", "shorts", "render")       # a failure here stops the run; elsewhere it is noted and the run goes on
OPTIONS = dict(find=True, count=10, min=15, max=30, include_existing=False, look="", preset="medium",
               posts=True, start_ai=True,
               captions="toolkit",               # or "premiere": Adobe's Speech to Text writes them, in Premiere
               cap_style="premiere")             # Premiere's lines: "premiere" up to 42 characters, "short" 1-3 words
PORTS = (8772, 8773, 8774)                       # not the toolkit's (8765, 8767-8769), the phone's (8766) or Post Studio's (8770)

LOCK = threading.RLock()
ACTIVE = {"path": None}                          # the project a run is live on in this process


def _key(path):
    return os.path.normcase(os.path.normpath(path))


def _rk(path):
    """What a run belongs to: a recording and the Premiere project made from it are one run
    (they share the <name>_captions folder, so also autorun.json)."""
    return _key(app.base_of(path))


def _cur(path):
    """The project a run is on now. A run started on a plain recording moves to the Premiere
    project once Premiere has made one for its captions."""
    with LOCK:
        cur = (load_state(app.base_of(path) + "_captions").get("run") or {}).get("path")
    return cur if cur and os.path.exists(cur) and _rk(cur) == _rk(path) else path


def wants_premiere(I, run):
    """Is this a run whose captions Premiere still has to write?"""
    return bool(run) and (run.get("options") or {}).get("captions") == "premiere" and I.speech and not I.seq.captions


def _queue(I, run, stages):
    """The steps in the order they run: the toolkit's order, except that captions Premiere has to
    write go first - a plain recording becomes a Premiere project there, and everything after
    works on that project (so the speech is heard once, not once per file)."""
    q = [s for s in ORDER if s in stages]
    if "captions" in q and wants_premiere(I, run):
        q.remove("captions")
        q.insert(0, "captions")
    return q


# -- the project, read fresh ------------------------------------------------------------
def info(path):
    base = app.base_of(path)
    outdir = base + "_captions"
    cfg = config.load(outdir)
    seq = app.pick(app.project(path), cfg)
    return SimpleNamespace(path=path, base=base, outdir=outdir, sdir=base + "_shorts", cfg=cfg, seq=seq,
                           kind=config.kind(cfg), speech=config.speech_on(cfg), reactions=config.reactions_on(cfg))


def applies(sid, I):
    """Music has no screams & laughs, and no captions unless they are switched on."""
    return not (sid == "captions" and not I.speech) and not (sid == "screams" and not I.reactions)


# -- what a run did: autorun.json ---------------------------------------------------------
def state_path(outdir):
    return os.path.join(outdir, "autorun.json")


def load_state(outdir):
    try:
        with open(state_path(outdir), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(outdir, st):
    os.makedirs(outdir, exist_ok=True)
    tmp = state_path(outdir) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=1)
    os.replace(tmp, state_path(outdir))


class _Run:
    """with _Run(path) as (I, st, run): ...   - read, change, saved on the way out."""

    def __init__(self, path):
        self.path = path

    def __enter__(self):
        LOCK.acquire()
        self.I = info(self.path)
        self.st = load_state(self.I.outdir)
        return self.I, self.st, self.st.get("run")

    def __exit__(self, kind, *a):
        try:
            if kind is None:
                save_state(self.I.outdir, self.st)
        finally:
            LOCK.release()


def _set(run, sid, state, note=None):
    s = run["stages"].setdefault(sid, {})
    s.update(state=state, when=time.time())
    if note is not None:
        s["note"] = note


# -- which Shorts a run covers, and where each stands --------------------------------------
def scope(I, run):
    """[(index, short, video path)] - every Short of the project except the ones that were
    there before the run and were left out of it."""
    from shorts import safe_name
    left_out = set((run or {}).get("outside") or [])
    return [(i, s, os.path.join(I.sdir, safe_name(s["name"]) + ".mp4"))
            for i, s in enumerate(I.cfg["shorts"]) if s["name"] not in left_out]


def renders(I, run):
    recs = stale.load(I.outdir)
    return [(i, s, v, stale.status(I.cfg, s, v, I.seq, recs)) for i, s, v in scope(I, run)]


def render_todo(I, run):
    return [i for i, s, v, r in renders(I, run) if not r["rendered"] or r["changed"]]


def written(I, run):
    """{video path, lower case: its posts as {platform: {field: value}}} for the run's rendered Shorts."""
    import posting
    if not posting.status()["ok"]:
        return {}
    files = [v for _, _, v in scope(I, run) if os.path.exists(v)]
    return {_key(r["file"]): posting.plain(r.get("posts")) for r in posting.show(files) if r.get("posts")}


def post_sig(I, s):
    """What a Short's post was written from: its range and the captions inside it."""
    p = stale.parts(I.cfg, s, I.seq)
    return stale._h([p["trim"], p["captions"], p.get("timeline")])


def post_todo(I, run, have=None):
    """Rendered Shorts with no post yet, or whose captions changed since this app wrote it."""
    have = written(I, run) if have is None else have
    sigs = (run or {}).get("posts_sig") or {}
    return [i for i, s, v in scope(I, run) if os.path.exists(v)
            and (_key(v) not in have or (s["name"] in sigs and sigs[s["name"]] != post_sig(I, s)))]


def pending(I, run):
    """Your edits that the videos and posts don't show yet."""
    out = dict(render=[], post=[])
    if not run:
        return out
    for i, s, v, r in renders(I, run):
        if not r["rendered"]:
            out["render"].append(dict(i=i, name=s["name"], why=["not rendered yet"]))
        elif r["changed"]:
            out["render"].append(dict(i=i, name=s["name"], why=r["why"]))
    if run["options"].get("posts"):
        have = written(I, run)
        sigs = run.get("posts_sig") or {}
        stale_render = {x["i"] for x in out["render"]}
        for i, s, v in scope(I, run):
            if _key(v) not in have:
                if os.path.exists(v) or i in stale_render:
                    out["post"].append(dict(i=i, name=s["name"], why=["no post written yet"]))
            elif s["name"] in sigs and sigs[s["name"]] != post_sig(I, s):
                out["post"].append(dict(i=i, name=s["name"], why=["captions or length changed since it was written"]))
    return out


# -- sign-off: a tick is only good for what you looked at ------------------------------------
def stage_sig(sid, I, run, have=None):
    c = I.cfg
    if sid == "markers":
        return stale._h(c.get("markers"))
    if sid == "captions":
        return stale._h([c.get("caption_edits"), c.get("caption_adds"), c.get("fit_timing"), len(I.seq.captions)])
    if sid == "shorts":
        return stale._h([(s["name"], round(float(s["start"]), 3), round(float(s["end"]), 3)) for _, s, _ in scope(I, run)])
    if sid == "screams":
        return stale._h([c.get("screams"), c.get("laughs")])
    if sid == "look":
        return stale._h([c.get("look"), c.get("layout"), c.get("bleep")])
    if sid == "render":
        return stale._h([(s["name"], r["rendered"], r["changed"], round(r["when"] or 0)) for _, s, _, r in renders(I, run)])
    if sid == "post":
        have = written(I, run) if have is None else have
        return stale._h([(s["name"], have.get(_key(v))) for _, s, v in scope(I, run)])
    if sid == "publish":
        return stale._h(plan_key(run.get("plan")))
    return ""


def plan_key(plan):
    return [(r["name"], r["action"], r.get("when")) for r in (plan or {}).get("rows") or []]


def needs_sign(sid, I, run):
    """Does this step want your sign-off? Not Publish (pressing Publish is its sign-off), and
    not a step the run skipped - there is nothing of it to look at."""
    return sid != "publish" and applies(sid, I) and ((run.get("stages") or {}).get(sid) or {}).get("state") != "skipped"


def signed(sid, I, run, have=None):
    """(signed off and still what you looked at, signed off but changed since)."""
    s = (run.get("signed") or {}).get(sid)
    if not s:
        return False, False
    ok = s.get("sig") == stage_sig(sid, I, run, have)
    return ok, not ok


def sign(path, sid, on=True):
    with _Run(path) as (I, st, run):
        if not run:
            raise ValueError("There is no run to sign off yet.")
        have = written(I, run)
        for s in (ORDER if sid == "all" else [sid]):
            if s not in ORDER or not needs_sign(s, I, run):
                continue
            if on:
                run.setdefault("signed", {})[s] = dict(when=time.time(), sig=stage_sig(s, I, run, have))
            else:
                run.setdefault("signed", {}).pop(s, None)
    return state(path)


# -- the publish plan: asked, never sent ---------------------------------------------------
def make_plan(path, I, run):
    """What step 8 would do with this run's Shorts. Asks YouTube where each stands; sends nothing.
    Returns (what the review shows, the full rows for `publish`, the settings used)."""
    import posting
    out = dict(when=time.time(), rows=[], error=None, account=None, label="", ready=0, visibility="schedule")
    st = posting.status()
    if not st["ok"]:
        out["error"] = "Posting isn't set up on this PC: %s" % st.get("error", "the Post Studio engine is missing")
        return out, [], {}
    v = app.yt_view(path, refresh=True)
    out.update(account=v.get("account"), label=v.get("plan_label") or "")
    if not (v.get("account") or {}).get("connected"):
        out["error"] = "YouTube isn't connected on this PC yet. Connect it in the Publish step, then check again."
        return out, [], {}
    if v.get("error"):
        out["error"] = v["error"]
        if "invalid_grant" in v["error"] or "expired or revoked" in v["error"]:
            out["error"] = ("Your YouTube sign-in has run out (Google ends it after a while). Open the Publish step with Edit, "
                            "press Switch channel to sign in again, then press Check again.")
        return out, [], {}
    idx = [i for i, _, _ in scope(I, run)]
    if not idx:
        return out, [], {}
    y = ((I.cfg.get("post") or {}).get("yt")) or {}
    b = dict(path=path, indexes=idx, mode=y.get("mode") or "plan", start=y.get("start"), every=y.get("every") or 24,
             visibility=y.get("visibility") or "schedule", settings=y.get("settings") or {})
    try:
        rows = app.yt_rows(b)
    except Exception as e:                       # e.g. no posting times yet
        out["error"] = str(e)
        return out, [], b
    out["rows"] = [dict(i=r["i"], name=r["name"], action=r["action"], why=r.get("why", ""), when=r.get("when"),
                        title=(r.get("fields") or {}).get("title") or r.get("title") or "", youtube=r.get("youtube"),
                        problems=list(r.get("problems") or [])) for r in rows]
    out["ready"] = sum(1 for r in rows if r["action"] in ("fill", "upload"))
    out["visibility"] = b["visibility"]
    return out, rows, b


def _plan_note(plan):
    if plan["error"]:
        return "needs", plan["error"]
    if not plan["ready"]:
        why = sorted({r["why"] for r in plan["rows"] if r.get("why")})
        return "done", "Nothing to send to YouTube" + (": " + "; ".join(why) if why else "") + "."
    n = plan["ready"]
    return "ready", "%d Short%s ready to go to YouTube when you sign off." % (n, "" if n == 1 else "s")


def refresh_plan(path):
    """The Check again button."""
    with LOCK:
        I = info(path)
        run = load_state(I.outdir).get("run")
    if not run:
        raise ValueError("There is no run yet.")
    plan, _, _ = make_plan(path, I, run)                 # the slow part (asks YouTube), outside the lock
    with _Run(path) as (I, st, run):
        run["plan"] = plan
        if run["stages"].get("publish", {}).get("state") != "done" or run["status"] != "published":
            _set(run, "publish", *_plan_note(plan))
    return state(path)


def publish(path, tiktok=False):
    """The last sign-off: send what the plan says. Refuses if anything is unsigned, if edits are
    waiting, or if the plan is no longer the one that was looked at."""
    with LOCK:
        I = info(path)
        run = load_state(I.outdir).get("run")
        if not run or run["status"] not in ("review", "published"):
            raise ValueError("Nothing to publish yet - the run has to finish first.")
        have = written(I, run)
        unsigned = [LABEL[s] for s in ORDER if needs_sign(s, I, run) and not signed(s, I, run, have)[0]]
        if unsigned:
            raise ValueError("Sign off first: %s." % ", ".join(unsigned))
        p = pending(I, run)
        if p["render"] or p["post"]:
            raise ValueError("Some Shorts changed since they were made. Press Apply my edits first.")
        looked_at = plan_key(run.get("plan"))
    plan, rows, b = make_plan(path, I, run)              # fresh: nothing is ever uploaded twice
    with _Run(path) as (I, st, run):
        run["plan"] = plan
        _set(run, "publish", *_plan_note(plan))
        if plan["error"]:
            raise_after = plan["error"]
        elif plan_key(plan) != looked_at:
            return dict(changed=True)
        elif not plan["ready"]:
            raise_after = "Nothing to send - every Short is already on YouTube, or has no post yet."
        else:
            raise_after = None
            run.setdefault("signed", {})["publish"] = dict(when=time.time(), sig=stage_sig("publish", I, run))
    if raise_after:
        raise ValueError(raise_after)
    fd, pf = tempfile.mkstemp(prefix="yt-plan-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(dict(rows=rows, settings=b["settings"], visibility=b["visibility"]), f)
    app.UPLOADS.clear()                                  # the channel is about to change
    n = plan["ready"]
    idx = [r["i"] for r in rows if r["action"] in ("fill", "upload")]

    def after(code):
        with _Run(path) as (I, st, run):
            if code == 0:
                run["status"] = "published"
                run["published"] = time.time()
                _set(run, "publish", "done", "Sent %d Short%s to YouTube." % (n, "" if n == 1 else "s"))
            else:
                _set(run, "publish", "failed", "Publishing stopped with an error - see the log. " + _tail())
        try:                                             # show where each Short stands now
            refreshed, _, _ = make_plan(path, info(path), load_state(info(path).outdir).get("run"))
            with _Run(path) as (I, st, run):
                run["plan"] = refreshed
        except Exception:
            app.note_error("auto run: plan after publishing")
        if code == 0 and tiktok:
            app.run_job("Sending to TikTok drafts", app.command("tiktok", dict(path=path, indexes=idx)))

    with _Run(path) as (I, st, run):
        _set(run, "publish", "running", "Publishing %d Short%s to YouTube…" % (n, "" if n == 1 else "s"))
    jid = app.run_job("Publishing %d Short%s to YouTube" % (n, "" if n == 1 else "s"),
                      app.command("publish", dict(path=path, plan_file=pf)), after)
    if not jid:
        with _Run(path) as (I, st, run):
            _set(run, "publish", *_plan_note(plan))
        raise ValueError(app.busy_message())
    return dict(id=jid, count=n)


# -- the stages ------------------------------------------------------------------------------
# Each returns  ("job", title, argv)  - a shorts.py command to run, like the toolkit's buttons -
# or  (state, note)  when there is nothing to run:  done / skipped / na / needs / failed / ready.
# They run outside the lock (some take a while): _snap reads, _patch writes.
def _snap(path):
    with LOCK:
        I = info(path)
        return I, load_state(I.outdir).get("run") or {}


def _patch(path, **fields):
    with _Run(path) as (I, st, run):
        if run:
            run.update(fields)


def _tail(n=3):
    with app.LOCK:
        lines = [x for x in app.JOB["lines"][1:] if not x.startswith("frame=")]
    return " ".join(lines[-n:])[:400]


def _in_scope(I, run, items):
    """Screams / laughs that fall inside one of the run's Shorts."""
    spans = [(float(s["start"]), float(s["end"])) for _, s, _ in scope(I, run)]
    return [x for x in items or [] if any(a <= x["start"] <= b for a, b in spans)]


def _s(n):
    return "" if n == 1 else "s"


def st_markers(path):
    I, run = _snap(path)
    o = run["options"]
    if not o["find"]:
        return "skipped", "Not asked to look for new moments - working on the Shorts already in the project."
    _patch(path, markers_before=len(I.cfg.get("markers") or []),
           markers_had=[[m["start"], m["end"]] for m in I.cfg.get("markers") or []])
    return "job", "Finding the best moments", app.command("markers", dict(path=path, count=o["count"], min=o["min"], max=o["max"]))


def after_markers(path):
    I, run = _snap(path)
    n = len(I.cfg.get("markers") or []) - run.get("markers_before", 0)
    return "Found %d new moment%s." % (n, _s(n)) if n > 0 else "No new moments found at that length."


def st_captions(path):
    I, run = _snap(path)
    if wants_premiere(I, run):
        import premiere_auto
        o = run["options"]
        going = lambda: (load_state(I.outdir).get("run") or {}).get("status") == "running"
        try:
            project = premiere_auto.captions(path, I.seq.name, o.get("cap_style") or "premiere", I.cfg["look"].get("punct", "keep"),
                                             say=lambda text: note(path, "captions", text), stopped=lambda: not going())
        except premiere_auto.Stopped:
            return "stopped", "Stopped."
        except premiere_auto.Problem as e:
            return "halt", str(e)                        # only you can sort it out: the run waits here
        if _key(project) != _key(path):                  # a plain recording: the run goes on with its new Premiere project
            app.remember(project)
            with _Run(path) as (_, _, run):
                if run:
                    run["path"] = project
            path = project
        I, run = _snap(path)
    if I.seq.captions:
        return "job", "Checking caption timing", ["captions", path, "--sequence", I.seq.name]
    return "done", "No Premiere captions here - the toolkit writes them from the speech it hears."


def after_captions(path):
    I, run = _snap(path)
    c = (app.results(I.outdir, I.sdir, I.cfg).get("check") or {})
    off = sum(v for k, v in (c.get("counts") or {}).items() if k in ("early", "late", "cut-off", "lingers"))
    return "%s%d captions checked against the speech; %d are off%s." % (
        "Written by Premiere. " if run["options"].get("captions") == "premiere" else "",
        c.get("total", 0), off, " and are fitted in every render" if I.cfg.get("fit_timing", True) and off else "")


def new_shorts(path, had):
    """The moments this run found become Shorts. Only those: a marker from an earlier run whose
    Short you have since trimmed or removed is left alone (it would come back as a duplicate).
    Returns the new Shorts' places in the list."""
    from shorts import write_marker_csv
    I = info(path)
    old = {(round(float(a), 2), round(float(b), 2)) for a, b in had or []}
    shorts, new = list(I.cfg.get("shorts") or []), []
    for m in I.cfg.get("markers") or []:
        if (round(float(m["start"]), 2), round(float(m["end"]), 2)) in old:
            continue
        if any(abs(x["start"] - m["start"]) < 1 and abs(x["end"] - m["end"]) < 1 for x in shorts):
            continue
        name = re.sub(r"^Marker", "Short", m["name"])
        while any(x["name"] == name for x in shorts):          # a Short's name is its file name: never two alike
            name += " (2)"
        new.append(len(shorts))
        shorts.append(dict(name=name, start=m["start"], end=m["end"]))
    if new:
        cfg = config.update(I.outdir, {"shorts": shorts})
        write_marker_csv(I.outdir, cfg["shorts"])
    return new


def st_shorts(path):
    I, run = _snap(path)
    new = new_shorts(path, run.get("markers_had")) if run["options"]["find"] else []
    I, run = _snap(path)
    _patch(path, new=sorted(set(run.get("new") or []) | {I.cfg["shorts"][i]["name"] for i in new}))
    n = len(scope(I, run))
    if not n:
        return "failed", "There are no Shorts to work on. Try a different length, or add Shorts yourself in the toolkit."
    return "done", "%d Short%s in this run%s." % (n, _s(n), " (%d new)" % len(new) if new else "")


def st_screams(path):
    return "job", "Finding screams and laughs", ["screams", path]


def after_screams(path):
    I, run = _snap(path)
    r = app.results(I.outdir, I.sdir, I.cfg)
    sc = _in_scope(I, run, (r.get("screams") or {}).get("items"))
    lg = _in_scope(I, run, (r.get("laughs") or {}).get("items"))
    on = lambda xs: sum(1 for x in xs if x["on"])
    off = len(sc) + len(lg) - on(sc) - on(lg)
    return "In these Shorts: %d scream%s and %d laugh%s on, %d suggestion%s left off." % (
        on(sc), _s(on(sc)), on(lg), _s(on(lg)), off, _s(off))


def st_look(path):
    I, run = _snap(path)
    name = run["options"].get("look")
    if name and not run.get("look_set"):
        import style
        lk = style.preset_look(name, app.load_settings().get("look_presets", {}))
        if not lk:
            return "failed", "There is no look called %r any more - the project's own look was kept." % name
        config.update(I.outdir, {"look": lk})
        _patch(path, look_set=True)                      # once: a later "Apply my edits" must not undo your changes
        return "done", "Look set to %s." % name
    return "done", "Using the project's look (%s)." % (I.cfg["look"].get("preset_name") or "Classic")


def _only(run, sid, todo):
    pick = (run.get("only") or {}).get(sid)
    return todo if pick is None else [i for i in todo if i in set(pick)]


def st_render(path):
    I, run = _snap(path)
    todo = _only(run, "render", render_todo(I, run))
    if not todo:
        return "done", "Nothing to render - every Short is up to date."
    _patch(path, doing=[I.cfg["shorts"][i]["name"] for i in todo])
    return "job", "Rendering %d Short%s" % (len(todo), _s(len(todo))), app.command(
        "make", dict(path=path, preset=run["options"].get("preset") or "medium", indexes=todo))


def after_render(path):
    I, run = _snap(path)
    rs = renders(I, run)
    ok = sum(1 for _, _, _, r in rs if r["rendered"] and not r["changed"])
    made = sum(1 for _, s, _, r in rs if s["name"] in (run.get("doing") or []) and r["rendered"] and not r["changed"])
    return "Rendered %d Short%s. %d of %d are up to date." % (made, _s(made), ok, len(rs))


def st_post(path):
    I, run = _snap(path)
    o = run["options"]
    if not o["posts"]:
        return "skipped", "You chose not to write posts in this run."
    import posting
    ps = posting.status()
    if not ps["ok"]:
        return "needs", "Posts can't be written on this PC: %s" % ps.get("error", "the Post Studio engine is missing")
    todo = _only(run, "post", post_todo(I, run))
    if not todo:
        return "done", "Every Short already has its posts."
    ai, said = posting.ai_status(), ""
    if not ai["up"] and o.get("start_ai"):
        note(path, "post", "Starting the local AI…")
        said = (posting.start_ai() or {}).get("message", "")
        ai = posting.ai_status()
    if not ai["up"]:
        return "needs", ("The local AI (Ollama) isn't running, so no posts were written. Start it, then press Try again. " + said).strip()
    _patch(path, doing=[I.cfg["shorts"][i]["name"] for i in todo])
    return "job", "Writing posts for %d Short%s" % (len(todo), _s(len(todo))), app.command("post", dict(path=path, indexes=todo))


def after_post(path):
    I, run = _snap(path)
    have = written(I, run)
    sigs = dict(run.get("posts_sig") or {})
    done = 0
    for _, s, v in scope(I, run):
        if s["name"] in (run.get("doing") or []) and _key(v) in have:
            sigs[s["name"]] = post_sig(I, s)
            done += 1
    _patch(path, posts_sig=sigs)
    want = len(run.get("doing") or [])
    return "Wrote posts for %d Short%s%s." % (done, _s(done), "" if done >= want else " (%d could not be written - see the log)" % (want - done))


def st_publish(path):
    I, run = _snap(path)
    plan, _, _ = make_plan(path, I, run)                 # asks YouTube; sends nothing
    _patch(path, plan=plan)
    return _plan_note(plan)


STAGE = dict(markers=st_markers, captions=st_captions, shorts=st_shorts, screams=st_screams, look=st_look,
             render=st_render, post=st_post, publish=st_publish)
AFTER = dict(markers=after_markers, captions=after_captions, screams=after_screams, render=after_render, post=after_post)


def note(path, sid, text):
    """Say what a stage is doing right now (shown under it while it runs)."""
    with _Run(path) as (I, st, run):
        if run:
            run["stages"].setdefault(sid, {})["note"] = text


# -- the run: one stage after another -----------------------------------------------------------
def _poke_toolkit(path):
    """If the Shorts Toolkit window shows this project, have it read the changes."""
    import peer
    threading.Thread(target=lambda: peer.tell("toolkit", "/api/goto", dict(path=path, reload=True)), daemon=True).start()


def _next(path):
    while True:
        path = _cur(path)
        with _Run(path) as (I, st, run):
            if not run or run["status"] != "running":
                _idle()
                return
            while run["queue"] and not applies(run["queue"][0], I):
                _set(run, run["queue"].pop(0), "na", "")
            if not run["queue"]:
                run.update(status="review", finished=time.time(), stage=None)
                run.pop("only", None)
                _idle()
                _poke_toolkit(path)
                return
            sid = run["queue"][0]
            run["stage"] = sid
            _set(run, sid, "running", "")
        try:                                             # outside the lock: a stage may take a while
            res = STAGE[sid](path)
        except (Exception, SystemExit) as e:
            app.note_error("auto run, " + sid)
            res = ("halt" if sid == "captions" else "failed", str(e))    # never on to rendering with captions you didn't ask for
        path = _cur(path)
        with LOCK:                                       # stopped while the stage was at it (stop() wrote that down)
            if (load_state(app.base_of(path) + "_captions").get("run") or {}).get("status") != "running":
                _idle()
                return
        if res[0] == "job":
            if app.run_job(res[1], res[2], lambda code, sid=sid: _done(path, sid, code)):
                return
            res = ("failed", app.busy_message())
        if not _finish(path, sid, res[0], res[1]):
            return


def _finish(path, sid, state, text):
    """Write down how a stage ended. False = the run stops here."""
    halt = state == "halt"                               # failed, and the run can't sensibly go on without it
    state = "failed" if halt else state
    with _Run(path) as (I, st, run):
        if not run:
            return False
        _set(run, sid, state, text)
        if state == "failed" and (halt or sid in REQUIRED):
            run["status"] = "failed"
            _idle()
            return False
        if run["queue"] and run["queue"][0] == sid:
            run["queue"].pop(0)
    if sid in ("markers", "shorts", "look"):
        _poke_toolkit(path)
    return True


def _done(path, sid, code):
    """A stage's job ended (called on the job's own thread)."""
    path = _cur(path)
    with _Run(path) as (I, st, run):
        if not run:
            return
        if run["status"] != "running":                   # stopped while it ran
            _set(run, sid, "stopped", "Stopped.")
            _idle()
            return
    if code == 0:
        try:
            state, text = "done", AFTER[sid](path) if sid in AFTER else ""
        except Exception as e:
            app.note_error("auto run, after " + sid)
            state, text = "done", "Finished (%s)." % e
    else:
        state, text = "failed", "This step stopped with an error: " + (_tail() or "see the log.")
    if _finish(path, sid, state, text):
        _next(path)


def _launch(path):
    """Busy from here until the run stops - also between two jobs, so the toolkit can't slip one in."""
    import peer
    ACTIVE["path"] = _rk(path)
    app.HOLD[0] = "an auto run on %s" % os.path.splitext(os.path.basename(path))[0]
    peer.set_job(app.ME, app.HOLD[0])
    threading.Thread(target=_next, args=(path,), daemon=True).start()


def _idle():
    import peer
    ACTIVE["path"] = None
    app.HOLD[0] = None
    if app.JOB["done"]:
        peer.set_job(app.ME, None)


def _free(path):
    import peer
    if not app.JOB["done"] or peer.busy_with(app.ME):
        raise ValueError(app.busy_message())
    if ACTIVE["path"]:
        raise ValueError("A run is already going%s." % ("" if ACTIVE["path"] == _rk(path) else " on another project"))


def start(path, options=None):
    """A new run from the top."""
    _free(path)
    with _Run(path) as (I, st, run):
        o = dict(OPTIONS, **{k: v for k, v in (options or {}).items() if k in OPTIONS})
        o.update(count=max(1, min(60, int(o["count"]))), min=float(o["min"]), max=float(o["max"]),
                 captions="premiere" if o["captions"] == "premiere" else "toolkit",
                 cap_style="short" if o["cap_style"] == "short" else "premiere")
        if o["max"] <= o["min"]:
            raise ValueError("The longest length has to be more than the shortest.")
        have = [s["name"] for s in I.cfg["shorts"]]
        if not o["find"] and not have:
            raise ValueError("This project has no Shorts yet - let the run look for moments.")
        st["runs"] = int(st.get("runs") or 0) + 1
        st["run"] = dict(id=st["runs"], started=time.time(), finished=None, status="running", options=o,
                         outside=have if o["find"] and not o["include_existing"] else [], new=[],
                         stage=None, queue=[], stages={}, signed={}, posts_sig={}, plan=None)
        st["run"]["queue"] = _queue(I, st["run"], ORDER)
        st["run"]["order"] = list(st["run"]["queue"])   # how the page lists this run's steps
    _launch(path)
    return state(path)


def again(path, stages, only=None):
    """Run some stages again on the same run: Apply my edits, Try again, Continue."""
    _free(path)
    with _Run(path) as (I, st, run):
        if not run:
            raise ValueError("There is no run yet.")
        run.update(status="running", queue=_queue(I, run, stages), only=only or {})
        for s in run["queue"]:
            if applies(s, I):
                _set(run, s, "todo", "")
    _launch(path)
    return state(path)


def apply_edits(path, render=None, post=None):
    """Your edits, carried through: render the Shorts that changed, rewrite the posts whose
    captions changed, work the publish plan out again. render / post: the Shorts ticked
    (None = all that need it)."""
    with LOCK:
        I = info(path)
        listing = app.results(I.outdir, I.sdir, I.cfg).get("screams") or {}
    stages = (["screams"] if I.reactions and listing.get("stale") else []) + ["render", "post", "publish"]
    return again(path, stages, dict(render=render, post=post))


def premiere_captions(path, style=None):
    """From the review of a run that used the toolkit's captions: have Premiere write them after
    all. The Shorts then show as changed, and "Apply my edits" renders them again."""
    with _Run(path) as (I, st, run):
        if not run:
            raise ValueError("There is no run yet.")
        if I.seq.captions:
            raise ValueError("This project already has Premiere captions.")
        run["options"]["captions"] = "premiere"
        if style in ("premiere", "short"):
            run["options"]["cap_style"] = style
    return again(path, ["captions"])


def resume(path, skip=False):
    """After Stop or a failed step: carry on from that step (or past it)."""
    with _Run(path) as (I, st, run):
        if not run or run["status"] not in ("stopped", "failed"):
            raise ValueError("There is nothing to continue.")
        queue = list(run.get("queue") or [])
        if skip and queue:
            _set(run, queue.pop(0), "skipped", "Skipped by you.")
    return again(path, queue)


def stop(path):
    with _Run(path) as (I, st, run):
        if run and run["status"] == "running":
            run["status"] = "stopped"
            if run.get("stage"):
                _set(run, run["stage"], "stopped", "Stopped.")
    app.stop_job()
    return state(path)


# -- what the page shows --------------------------------------------------------------------------
def job_view():
    with app.LOCK:
        J = dict(app.JOB)
        lines = list(J.pop("lines"))
    step = None
    for line in reversed(lines):
        m = re.match(r"\[(\d+)/(\d+)\]", line)
        if m:
            step = [int(m.group(1)), int(m.group(2))]
            break
    said = [x for x in lines[1:] if not x.startswith("frame=")]
    return dict(id=J["id"], title=J["title"], done=J["done"], paused=J["paused"], started=J["started"], code=J["code"],
                last=said[-1].strip() if said else "", step=step)


def _mtime(p):
    try:
        return os.path.getmtime(p)
    except OSError:
        return 0


def state(path):
    """The light picture, asked for every second or two: where the run is, what is signed,
    what your edits have left to do."""
    import peer
    with LOCK:
        I = info(path)
        st = load_state(I.outdir)
        run = st.get("run")
        if run and run["status"] == "running" and ACTIVE["path"] != _rk(path):
            run["status"] = "stopped"                    # the window was closed in the middle of a run
            if run.get("stage"):
                _set(run, run["stage"], "stopped", "Stopped when the window was closed.")
            save_state(I.outdir, st)
        seq = I.seq
        out = dict(path=path, name=os.path.splitext(os.path.basename(path))[0], kind=I.kind, speech=I.speech,
                   reactions=I.reactions, seconds=round(seq.end_s, 1), shorts=len(I.cfg["shorts"]),
                   markers=len(I.cfg.get("markers") or []), run=None, stages=[], pending=dict(render=[], post=[]),
                   job=job_view(), other=peer.busy_with(app.ME), active=ACTIVE["path"] == _rk(path),
                   elsewhere=bool(ACTIVE["path"] and ACTIVE["path"] != _rk(path)),
                   premiere_captions=len(seq.captions), wants_premiere=wants_premiere(I, run))
        settled = bool(run) and run["status"] != "running"
        have = written(I, run) if settled else {}
        shown = (run or {}).get("order") or ORDER
        for sid in (shown if sorted(shown) == sorted(ORDER) else ORDER):
            label = LABEL[sid]
            s = ((run or {}).get("stages") or {}).get(sid) or {}
            ok, changed = signed(sid, I, run, have) if settled else (False, False)
            out["stages"].append(dict(id=sid, label=label, applies=applies(sid, I), state=s.get("state", "todo"),
                                      note=s.get("note", ""), signed=ok, changed=changed,
                                      sign=bool(run) and needs_sign(sid, I, run)))
        if run:
            out["run"] = dict(id=run["id"], status=run["status"], stage=run.get("stage"), started=run["started"],
                              finished=run.get("finished"), options=run["options"], count=len(scope(I, run)),
                              queue=run.get("queue") or [])
        if settled:
            out["pending"] = pending(I, run)
        # anything the review shows changed -> the page fetches the review again
        files = [state_path(I.outdir), config.path_for(I.outdir), stale.path_for(I.outdir),
                 os.path.join(I.outdir, "screams.json"), os.path.join(I.outdir, "caption-report.csv")]
        out["rev"] = stale._h([[_mtime(f) for f in files], [_mtime(v) for _, _, v in scope(I, run)] if run else [],
                               have, out["pending"], _mtime(path)])
        return out


def review(path):
    """Everything a run made, stage by stage, for the review."""
    import pipeline
    import style
    with LOCK:
        I = info(path)
        run = load_state(I.outdir).get("run") or {}
        c = I.cfg
        res = app.results(I.outdir, I.sdir, c)
        have = written(I, run) if run else {}
        new = set(run.get("new") or [])
        sigs = run.get("posts_sig") or {}
        shorts = []
        for i, s, v, r in (renders(I, run) if run else []):
            text = ""
            if I.speech:
                try:
                    caps = pipeline.caption_list(path, float(s["start"]), float(s["end"]), I.seq).get("captions") or []
                    text = " ".join(x["text"].strip() for x in caps if not x.get("hidden") and x["text"].strip())
                except Exception:
                    text = ""
            shorts.append(dict(i=i, name=s["name"], start=s["start"], end=s["end"], seconds=round(s["end"] - s["start"], 1),
                               new=s["name"] in new, video=v, rendered=r["rendered"], known=r["known"], changed=r["changed"],
                               why=r["why"], when=r["when"], text=text, posts=have.get(_key(v)) or {},
                               post_stale=bool(_key(v) in have and s["name"] in sigs and sigs[s["name"]] != post_sig(I, s))))
        spans = [(float(s["start"]), float(s["end"])) for _, s, _ in scope(I, run)] if run else []
        inside = lambda m: any(a - 1 <= m["start"] <= b + 1 for a, b in spans)
        sc = _in_scope(I, run, (res.get("screams") or {}).get("items")) if run else []
        lg = _in_scope(I, run, (res.get("laughs") or {}).get("items")) if run else []
        lk = c["look"]
        edits = c.get("caption_edits") or {}
        return dict(
            markers=[dict(name=m["name"], start=m["start"], end=m["end"], seconds=round(m["end"] - m["start"], 1),
                          score=m.get("score"), why=m.get("why", ""), used=inside(m)) for m in c.get("markers") or []],
            captions=dict(source="none" if not I.speech else "premiere" if I.seq.captions else "toolkit",
                          count=len(I.seq.captions), check=res.get("check"), fit=bool(c.get("fit_timing", True)),
                          edits=sum(1 for e in edits.values() if e), adds=len(c.get("caption_adds") or [])),
            shorts=shorts,
            screams=dict(on=[x for x in sc if x["on"]], off=sum(1 for x in sc if not x["on"]),
                         laughs_on=[x for x in lg if x["on"]], laughs_off=sum(1 for x in lg if not x["on"]),
                         installed=(res.get("laughs") or {}).get("installed", False),
                         stale=bool((res.get("screams") or {}).get("stale"))) if I.reactions else None,
            look=dict(preset=lk.get("preset_name") or "Classic", font=lk.get("font"), size=lk.get("size"), case=lk.get("case"),
                      words=lk.get("words"), anim=lk.get("anim"), text=lk.get("text"), highlight=bool(lk.get("highlight")),
                      highlight_col=lk.get("highlight_col"), outline_col=lk.get("outline_col"), box=bool(lk.get("box")),
                      box_col=lk.get("box_col"), blur_trim=c["layout"].get("blur_trim"), bleep=bool(c["bleep"].get("on")),
                      punct=lk.get("punct"), known_font=lk.get("font") in style.font_list()),
            platforms=(c.get("post") or {}).get("platforms") or [], plan=run.get("plan"), shorts_dir=I.sdir)


def options(path):
    """What the set-up card offers for this project."""
    import style
    from clip import is_clip
    I = info(path)
    run = load_state(I.outdir).get("run") or {}
    music = I.kind == "music"
    o = dict(OPTIONS, **(dict(min=20, max=45) if music else {}))
    last = {k: v for k, v in (run.get("options") or {}).items()
            if k in ("count", "min", "max", "preset", "posts", "start_ai", "captions", "cap_style")}
    try:
        import premiere_auto
        premiere = premiere_auto.status()
    except Exception as e:                               # never a reason not to show the card
        premiere = dict(installed=False, running=False, error=str(e))
    o["captions"] = "premiere" if premiere["installed"] else "toolkit"     # Premiere's own, wherever there is a Premiere
    if not premiere["installed"]:
        last.pop("captions", None)
    out = dict(defaults=dict(o, **last), kind=I.kind, kinds=[dict(id=k, label=v["label"], about=v["about"]) for k, v in config.KINDS.items()],
               shorts=len(I.cfg["shorts"]), markers=len(I.cfg.get("markers") or []), seconds=round(I.seq.end_s, 1),
               speech=I.speech, premiere_captions=len(I.seq.captions), premiere=premiere, clip=is_clip(path),
               look=I.cfg["look"].get("preset_name") or "Classic",
               looks=[n for n, _, _ in style.PRESETS], my_looks=sorted(app.load_settings().get("look_presets", {})),
               posting=dict(ok=False), ai=dict(up=False), youtube=None, tiktok=None)
    try:
        import posting
        out["posting"] = posting.status()
        out["ai"] = posting.ai_status()
        if out["posting"]["ok"]:
            pub = posting.engine()["publish"]
            acc = pub.accounts_status(check=False)
            times = pub.settings()["plan"].get("youtube_shorts") or []
            out["youtube"] = dict(connected=bool((acc.get("youtube") or {}).get("connected")), who=(acc.get("youtube") or {}).get("who"),
                                  times=pub.plan_label(times) if times else "")
            out["tiktok"] = dict(connected=bool((acc.get("tiktok") or {}).get("connected")), who=(acc.get("tiktok") or {}).get("who"))
    except Exception as e:                               # posting broken: the run still works up to Render
        out["posting"] = dict(ok=False, error=str(e))
    return out


# -- the server: the toolkit's, plus /auto ---------------------------------------------------------
class Handler(app.Handler):
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/auto":
            app.LAST_SEEN[0] = time.time()
            return self.send_file(os.path.join(app.RES, "ui", "auto.html"))
        if not u.path.startswith("/api/auto/"):
            return super().do_GET()
        app.LAST_SEEN[0] = time.time()
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == "/api/auto/state":             # its "path" says where the run is now; the page follows
                return self.send_json(state(_cur(q["path"])))
            if u.path == "/api/auto/review":
                return self.send_json(review(_cur(q["path"])))
            if u.path == "/api/auto/options":
                return self.send_json(options(q["path"]))
        except (Exception, SystemExit) as e:
            app.note_error("GET " + u.path)
            return self.send_json({"error": str(e)}, 500)
        self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        u = urlparse(self.path)
        if not u.path.startswith("/api/auto/"):
            return super().do_POST()
        app.LAST_SEEN[0] = time.time()
        # these start work on this PC and can put things on the internet: only from the app's own page
        if self.headers.get("X-Shorts-Toolkit") != "1" or self.headers.get("Host", "").split(":")[0] not in ("127.0.0.1", "localhost"):
            return self.send_json({"error": "forbidden"}, 403)
        try:
            b = self.body()
            p = b.get("path")
            if u.path == "/api/auto/start":
                return self.send_json(start(p, b.get("options")))
            p = _cur(p) if p else p
            if u.path == "/api/auto/premiere":
                return self.send_json(premiere_captions(p, b.get("style")))
            if u.path == "/api/auto/stop":
                return self.send_json(stop(p))
            if u.path == "/api/auto/resume":
                return self.send_json(resume(p, bool(b.get("skip"))))
            if u.path == "/api/auto/retry":
                sid = b.get("stage")
                if sid not in ORDER:
                    raise ValueError("No such step.")
                return self.send_json(again(p, [sid] + (["publish"] if sid == "post" else [])))
            if u.path == "/api/auto/apply":
                return self.send_json(apply_edits(p, b.get("render"), b.get("post")))
            if u.path == "/api/auto/sign":
                return self.send_json(sign(p, b.get("stage"), bool(b.get("on", True))))
            if u.path == "/api/auto/plan":
                return self.send_json(refresh_plan(p))
            if u.path == "/api/auto/publish":
                return self.send_json(publish(p, bool(b.get("tiktok"))))
            if u.path == "/api/auto/toolkit":
                return self.send_json(app.hand_over("toolkit", p, b.get("tab")))
        except ValueError as e:                          # a plain "can't do that yet" - not an error to log
            return self.send_json({"error": str(e)}, 409)
        except (Exception, SystemExit) as e:
            app.note_error("POST " + u.path)
            return self.send_json({"error": str(e)}, 500)
        self.send_json({"error": "not found"}, 404)


def make_server(port, host="127.0.0.1"):
    from http.server import ThreadingHTTPServer
    return ThreadingHTTPServer((host, port), Handler)


def main():
    """The page in your browser (the window is desktop.py --autorun)."""
    import peer
    import socket
    import webbrowser
    app.ME = "autorun"
    port = PORTS[0]
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", port)) == 0:
            webbrowser.open("http://127.0.0.1:%d/auto" % port)
            return
    server = make_server(port)
    peer.announce("autorun", port)

    def reaper():                                # quit once the tab has been closed for a minute and nothing runs
        while True:
            time.sleep(10)
            if app.JOB["done"] and not ACTIVE["path"] and time.time() - app.LAST_SEEN[0] > 60:
                server.shutdown()
                return
    threading.Thread(target=reaper, daemon=True).start()
    threading.Timer(0.6, lambda: webbrowser.open("http://127.0.0.1:%d/auto" % port)).start()
    try:
        server.serve_forever()
    finally:
        peer.gone("autorun")


if __name__ == "__main__":
    main()
