"""Step 8 - Publish to YouTube: for every Short of the project, find out where it stands on
the channel and do the right thing, in one go:

    on YouTube already (a draft or private upload, matched by its file name)
        -> fill in title/description/tags/settings and schedule it   (videos.update)
    not on YouTube
        -> upload it and schedule it                                   (videos.insert, publishAt)
    already scheduled / public
        -> leave it alone (unless you ask to redo it)

Times: one per slot - either your posting times (e.g. 15:00 daily) or "every N hours from a
start time" - skipping any time that's already taken on the channel or in the queue, so it
never stacks two Shorts on the same slot. YouTube releases scheduled Shorts itself; the PC
can be off.
"""
import datetime as dt
import os
import re

import posting

YT = "youtube_shorts"


def _norm(name):
    n = os.path.splitext(os.path.basename(name or ""))[0].lower().replace("–", "-").replace("—", "-")
    return re.sub(r"[^a-z0-9]+", " ", n).strip()


def state(project_path, shorts, videos, uploads=None):
    """Per Short: rendered?, posts written?, what YouTube has, what the queue has.
    shorts = [(index, short dict, video path)]; uploads = studio.list_uploads() or None (not fetched)."""
    E = posting.engine()
    shown = {os.path.normcase(os.path.normpath(r["file"])): r for r in posting.show([v for _, _, v in shorts if os.path.exists(v)])}
    on_yt = {}
    for u in uploads or []:
        on_yt.setdefault(_norm(u["file_name"]), u)          # newest first: the latest upload of that file wins
    jobs = [j for j in E["publish"].jobs() if j["platform"] == YT]
    out = []
    for i, s, v in shorts:
        r = shown.get(os.path.normcase(os.path.normpath(v))) or {}
        post = (r.get("posts") or {}).get(YT)
        u = on_yt.get(_norm(v))
        job = next((j for j in reversed(jobs) if os.path.normcase(j["file"]) == os.path.normcase(v)
                    and j["status"] not in ("failed", "cancelled")), None)
        if u:
            if u.get("publish_at"):
                where = "scheduled"
            elif u["privacy"] == "public":
                where = "public"
            elif u["unfinished"]:
                where = "draft"
            else:
                where = u["privacy"]               # private/unlisted and already filled in
        elif job:
            where = "queued"
        else:
            where = "not_uploaded" if uploads is not None else "unknown"
        out.append(dict(i=i, name=s["name"], video=v, rendered=os.path.exists(v), written=bool(post),
                        title=((post or {}).get("title") or {}).get("value", ""), youtube=where,
                        video_id=u["id"] if u else None, yt_title=u["title"] if u else None,
                        publish_at=(u or {}).get("publish_at") or (job or {}).get("when"),
                        url="https://youtube.com/shorts/%s" % u["id"] if u else ((job or {}).get("result") or {}).get("url"),
                        job=dict(id=job["id"], status=job["status"], error=job.get("error")) if job else None))
    return out


def taken_times(uploads):
    """Times already used: scheduled on the channel, in the queue, or handed out before."""
    E = posting.engine()
    pub = E["publish"]
    t = {u["publish_at"] for u in uploads or [] if u.get("publish_at")}
    t |= {j["when"] for j in pub.jobs() if j["platform"] == YT and j.get("when") and j["status"] not in ("failed", "cancelled")}
    t |= set(pub.outside_slots(YT))
    return {pub.iso(pub.parse_when(x)) for x in t}


def slots(n, taken, mode, start=None, every_hours=24, plan_times=None):
    """n publish times (ISO UTC), skipping taken ones and anything in the next 30 minutes."""
    pub = posting.engine()["publish"]
    soon = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=30)
    out = []
    if mode == "plan":
        if not plan_times:
            raise ValueError("No posting times yet - add them in step 8 (e.g. 4:00 PM, Mon-Fri).")
        first = pub.parse_when(start) if start else dt.datetime.now(dt.timezone.utc)
        got = pub.plan_slots(plan_times, first, n, taken, soon_minutes=30)
        if len(got) < n:
            raise ValueError("Your posting times only give %d slot(s) in the next year." % len(got))
        return [pub.iso(x) for x in got]
    if mode == "every":
        if not start:
            raise ValueError("Pick the first date and time.")
        w = pub.parse_when(start)
        while len(out) < n:
            iso = pub.iso(w)
            if w > soon and iso not in taken:
                out.append(iso)
            w += dt.timedelta(hours=float(every_hours or 24))
        return out
    return [None] * n                                    # "now" / keep: no publish time


def plan(project_path, items, uploads, mode="plan", start=None, every_hours=24, visibility="schedule", settings=None, redo=False):
    """What would happen to each Short (nothing is sent). items = state() rows of the Shorts chosen."""
    E = posting.engine()
    pub, studio = E["publish"], E["studio"]
    plan_times = pub.settings()["plan"].get(YT) or []
    doable = []
    rows = []
    for it in items:
        if not it["rendered"]:
            rows.append(dict(it, action="skip", why="not rendered yet (step 6)"))
        elif not it["written"]:
            rows.append(dict(it, action="skip", why="no post written yet (step 7)"))
        elif it["youtube"] in ("scheduled", "public") and not redo:
            rows.append(dict(it, action="skip", why="already %s on YouTube" % it["youtube"]))
        elif it["youtube"] == "queued" and not redo:
            rows.append(dict(it, action="skip", why="already in the upload queue"))
        else:
            rows.append(dict(it, action="fill" if it["video_id"] else "upload"))
            doable.append(rows[-1])
    if visibility == "schedule":
        times = slots(len(doable), taken_times(uploads), mode, start, every_hours, plan_times)
        for r, t in zip(doable, times):
            r["when"] = t
    by_id = {u["id"]: u for u in uploads or []}
    posts = {os.path.normcase(r["file"]): r for r in posting.show([r["video"] for r in doable])}
    for r in doable:
        fields = {k: v["value"] for k, v in ((posts.get(os.path.normcase(r["video"])) or {}).get("posts") or {}).get(YT, {}).items()}
        r["fields"] = fields
        s = dict(settings or {})
        if r["action"] == "fill":
            s["visibility"] = visibility if visibility in ("public", "unlisted", "private") else "keep"
            body = studio.build(by_id[r["video_id"]], fields, s, YT, r.get("when"))
            r["changes"] = studio.diff(by_id[r["video_id"]], body)
            r["problems"] = studio.problems(body)
        else:
            p = pub.compose(YT, fields)
            r["changes"] = [("Upload", os.path.basename(r["video"]), p["title"])]
            job = dict(post=p, settings=s, platform=YT, file=r["video"], when=r.get("when"), duration=None)
            r["problems"] = [x for x in pub.problems(job) if "missing" not in x]
    return rows


def apply(project_path, rows, settings=None, visibility="schedule", log=print):
    """Do it: fill the drafts, upload the rest. Returns (done, failed)."""
    E = posting.engine()
    pub, studio = E["publish"], E["studio"]
    done = failed = 0
    todo = [r for r in rows if r.get("action") in ("fill", "upload")]
    for n, r in enumerate(todo, 1):
        when = r.get("when")
        log("[%d/%d] %s  (%s%s)" % (n, len(todo), r["name"], "fill in the YouTube draft" if r["action"] == "fill" else "upload",
                                    ", publishes %s" % pub.local(when) if when else ""))
        try:
            s = dict(settings or {})
            if r["action"] == "fill":
                s["visibility"] = visibility if visibility in ("public", "unlisted", "private") else "keep"
                vid = studio.videos([r["video_id"]])
                if not vid:
                    raise LookupError("that video isn't on the channel any more")
                body = studio.build(vid[0], r["fields"], s, YT, when)
                bad = studio.problems(body)
                if bad:
                    raise ValueError("; ".join(bad))
                res = studio.apply(vid[0], body, s.get("playlist"))
                log("  done: %s%s  %s" % (res.get("privacy"), " until " + pub.local(res["publish_at"]) if res.get("publish_at") else "",
                                          res.get("note", "")))
            else:
                if visibility in ("public", "unlisted", "private"):
                    s["privacy"] = visibility
                job = pub.add(r["video"], YT, r["fields"], s, when, dict(app="shorts-toolkit", project=os.path.abspath(project_path),
                                                                         short=r["name"]))
                pub.edit(job["id"], status="scheduled")
                job = pub.run(job["id"], log=lambda m: log("  " + m))
                if job["status"] not in pub.DONE:
                    raise RuntimeError(job.get("error") or job["status"])
            if when:
                pub.use_slot(YT, when)
            done += 1
        except Exception as e:
            failed += 1
            log("  !! %s" % e)
    log("\nFinished: %d done, %d failed." % (done, failed))
    return done, failed
