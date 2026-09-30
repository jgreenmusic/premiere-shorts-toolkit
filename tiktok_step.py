"""Step 8, TikTok: every rendered Short goes to your TikTok drafts (inbox) at your TikTok
posting times, through Post Studio's queue. The Windows task (every 5 min) does the sending,
so the PC has to be on; TikTok then sends a notification and you finish the post on your phone
(add a sound, paste the caption - TikTok's draft upload takes no caption).

Why drafts and not direct posting: TikTok's audit rejects personal upload tools, so a direct
post from this app could only ever be "Only me" (see Post Studio publish/tiktok.py).
"""
import os
import re

import posting

SYNCED = re.compile(r"_captions-synced(?:-v(\d+))?$")


def project_shorts(project_path):
    """[(index, short, rendered video path)] for a project (same rule as app._project_shorts)."""
    import config
    from shorts import safe_name
    base = SYNCED.sub("", os.path.splitext(project_path)[0])
    cfg = config.load(base + "_captions")
    return [(i, x, os.path.join(base + "_shorts", safe_name(x["name"]) + ".mp4")) for i, x in enumerate(cfg["shorts"])]

PLATFORM = "tiktok"
LIVE = ("draft", "scheduled", "posting", "retry")        # still going to happen (publish.OPEN)
SENT = ("in_drafts", "posted", "scheduled_on_platform", "waiting_platform")


def _jobs_by_file():
    """{normalised file path: newest TikTok job} from Post Studio's queue."""
    out = {}
    for j in posting.engine()["publish"].jobs():
        if j["platform"] != PLATFORM or j["status"] == "cancelled":
            continue
        k = os.path.normcase(os.path.abspath(j["file"]))
        if k not in out or j.get("created", 0) > out[k].get("created", 0):
            out[k] = j
    return out


def caption_of(posts):
    """The TikTok caption written in step 7; else built from the YouTube title + hashtags."""
    tt = (posts or {}).get(PLATFORM) or {}
    cap = (tt.get("caption") or {}).get("value") or ""
    tags = (tt.get("hashtags") or {}).get("value") or []
    if not cap:
        yt = (posts or {}).get("youtube_shorts") or {}
        cap = (yt.get("title") or {}).get("value") or ""
        tags = tags or (yt.get("hashtags") or {}).get("value") or []
    return cap.strip(), [str(t).lstrip("#") for t in tags]


def state(shorts):
    """shorts = [(index, short, video path)] -> one row per Short for the TikTok card."""
    E = posting.engine()
    jobs = _jobs_by_file()
    rows = []
    for i, sh, video in shorts:
        row = dict(i=i, name=sh["name"], rendered=os.path.isfile(video), caption="", status="not_sent", when=None, error=None)
        if row["rendered"]:
            info = E["poststudio"].show(video)
            cap, tags = caption_of(info.get("posts"))
            row["caption"] = (cap + " " + " ".join("#" + t for t in tags)).strip()
            j = jobs.get(os.path.normcase(os.path.abspath(video)))
            if j:
                row.update(status=j["status"], when=E["publish"].local(j.get("when")) if j.get("when") else None,
                           error=j.get("error"), job=j["id"])
        rows.append(row)
    return rows


def send(project_path, shorts, indexes=None, when="plan", log=print):
    """Queue the chosen (or every not-yet-sent) rendered Short for TikTok drafts.
    when: "plan" = the next free TikTok posting time for each, "now" = at the next check."""
    E = posting.engine()
    pub = E["publish"]
    if not pub.accounts_status(check=False).get(PLATFORM, {}).get("connected"):
        raise ValueError("TikTok isn't connected yet (step 8 > TikTok > Connect).")
    if when == "plan" and not pub.settings()["plan"].get(PLATFORM):
        raise ValueError("No TikTok posting times yet - set them in step 8 (or send now).")
    jobs = _jobs_by_file()
    want = set(indexes or [])
    done = 0
    for i, sh, video in shorts:
        if want and i not in want:
            continue
        if not os.path.isfile(video):
            log("  %s: not rendered yet - skipped" % sh["name"])
            continue
        j = jobs.get(os.path.normcase(os.path.abspath(video)))
        if j and (j["status"] in LIVE or j["status"] in SENT):
            log("  %s: already %s - skipped" % (sh["name"], j["status"].replace("_", " ")))
            continue
        cap, tags = caption_of(E["poststudio"].show(video).get("posts"))
        at = pub.next_slot(PLATFORM) if when == "plan" else None
        job = pub.add(video, PLATFORM, dict(caption=cap, hashtags=tags), {"mode": "drafts"}, at,
                      dict(app="shorts-toolkit", project=os.path.abspath(project_path), short=sh["name"]))
        pub.edit(job["id"], status="scheduled")
        log("  %s -> TikTok drafts %s" % (sh["name"], pub.local(at) if at else "at the next check"))
        done += 1
    log("Queued %d Short%s for TikTok." % (done, "" if done == 1 else "s"))
    if done and not pub.task_status().get("on"):
        log("!! The sending task is OFF - tick Autopilot in step 8's TikTok card (it turns the task on), or nothing will go out.")
    return done
