# Shorts Toolkit

Turns a long recording into finished vertical Shorts — and gets them posted.

It finds the best moments, writes and fixes the captions, spells out screams and laughs,
renders 1080×1920 videos with animated captions, writes each Short's title and tags, and
schedules them on YouTube and TikTok. It works on a Premiere Pro project or on any video file,
and it never changes your Premiere project.

Windows app. Everything runs on your own PC.

## What it does

| Step | You get |
|---|---|
| **1 · Markers** | The best moments of the whole video, marked. Ask for more any time. |
| **2 · Captions** | Captions made (in Premiere or by the toolkit) and their timing checked against the speech. |
| **3 · Shorts** | Your list of Shorts on a timeline: trim, preview, fix each caption. |
| **4 · Screams & laughs** | "AAAAHHH" and "hahaha" spelled out as they happen. |
| **5 · Look** | Caption style (12 presets or your own), layout, optional censor bleep. |
| **6 · Render** | Finished videos in `<project>_shorts\`. |
| **7 · Posts** | Title, description, tags and hashtags per Short, written by a local AI model. |
| **8 · Publish** | Scheduled on YouTube; sent to TikTok drafts. |

Steps 1, 3 and 6 are enough to get a video out. The rest is optional.

## Install

Download **`ShortsToolkit-Setup-<version>.exe`** from
[Releases](https://github.com/jgreenmusic/premiere-shorts-toolkit/releases) and run it.
No admin rights, no Python, nothing else to install — ffmpeg, fonts and the laugh model are
inside. The first analysis downloads the speech model once (~500 MB).

## Quick start

1. Save your project in Premiere (**Ctrl+S**), or have a video file ready.
2. Open **Shorts Toolkit**. Pick the project on the left, or **Open clip…** for a video file.
3. **1 · Markers** → **Find Shorts & place markers** → **Turn all into Shorts**.
4. **3 · Shorts** → click a Short, trim it, fix its captions.
5. **6 · Render** → **Render all**.

In a hurry: **1 · Markers** → **⚡ Find, add & render** does steps 3 and 5 above in one press.
You can still trim, fix captions and render again afterwards.

Each step has a **Next →** button. The bar at the bottom shows what is running.

## Documentation

| Page | What is in it |
|---|---|
| [Guide](docs/guide.md) | Every step, every control, keyboard keys |
| [Premiere](docs/premiere.md) | The two Premiere panels and the scripts |
| [Command line](docs/commands.md) | Every button as a terminal command |
| [How it works](docs/how-it-works.md) | Files it saves, code map, speed, building it, limits |
| [Adding to it](docs/extending.md) | Add a command, button, setting or step; check it; put out a version |
| [Changelog](CHANGELOG.md) | Each problem found in real use and what changed |
| [Roadmap](ROADMAP.md) | Agreed but not built yet |

## Good to know

- **Timing is good to about half a second.** Speech-model word times are coarse.
- **Premiere effects are not applied** to renders (scale, crop, colour, gain). The toolkit uses its own layout.
- **Steps 7 and 8 need accounts and a local AI model** — see the [Guide](docs/guide.md#7--posts).
- Problems: press **Copy log** at the bottom of the app and paste it into an issue.
