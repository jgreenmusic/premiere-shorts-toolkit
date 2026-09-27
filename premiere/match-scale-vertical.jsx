// Premiere Pro: set the ACTIVE sequence to 1080x1920 (vertical), then give every
// video clip the same Motion > Scale as the FIRST clip (earliest clip on the lowest
// video track that has one). Position, rotation etc. are left alone.
// Run with VS Code + "ExtendScript Debugger" -> "Evaluate Script in Attached Host".
// Clips whose Scale is keyframed are SKIPPED and listed, not flattened.
(function () {
    var WIDTH = 1080, HEIGHT = 1920;
    var log = [];
    function say(s) { $.writeln(s); log.push(s); }

    var seq = app.project.activeSequence;
    if (!seq) { say("No active sequence - click into a timeline first."); return log.join("\n"); }

    // 1. Frame size
    var st = seq.getSettings();
    say("Sequence '" + seq.name + "' was " + st.videoFrameWidth + "x" + st.videoFrameHeight);
    st.videoFrameWidth = WIDTH;
    st.videoFrameHeight = HEIGHT;
    seq.setSettings(st);
    var after = seq.getSettings();
    say("Sequence is now " + after.videoFrameWidth + "x" + after.videoFrameHeight +
        (after.videoFrameWidth == WIDTH && after.videoFrameHeight == HEIGHT ? "" : "  <-- DID NOT TAKE"));

    // Motion effect lookup (matchName first, English display name as fallback)
    function motionOf(clip) {
        for (var i = 0; i < clip.components.numItems; i++) {
            var c = clip.components[i];
            if (c.matchName == "AE.ADBE Motion" || c.displayName == "Motion") return c;
        }
        return null;
    }
    function prop(motion, name) {
        for (var i = 0; i < motion.properties.numItems; i++) {
            if (motion.properties[i].displayName == name) return motion.properties[i];
        }
        return null;
    }

    // 2. Find the first clip
    var first = null;
    for (var v = 0; v < seq.videoTracks.numTracks && !first; v++) {
        var clips = seq.videoTracks[v].clips;
        for (var k = 0; k < clips.numItems; k++) {
            if (!first || clips[k].start.seconds < first.start.seconds) first = clips[k];
        }
    }
    if (!first) { say("No video clips in this sequence."); return log.join("\n"); }
    var fm = motionOf(first);
    if (!fm) { say("First clip '" + first.name + "' has no Motion effect."); return log.join("\n"); }

    var NAMES = ["Uniform Scale", "Scale", "Scale Width"]; // order matters: uniform flag first
    var ref = {};
    for (var n = 0; n < NAMES.length; n++) {
        var p = prop(fm, NAMES[n]);
        if (p) ref[NAMES[n]] = p.getValue();
    }
    if (ref["Scale"] === undefined) { say("Could not read Scale on the first clip."); return log.join("\n"); }
    say("Reference clip: '" + first.name + "' Scale=" + ref["Scale"] +
        (ref["Uniform Scale"] === false ? " ScaleWidth=" + ref["Scale Width"] : ""));

    // 3. Apply to every video clip
    var done = 0, skipped = [];
    for (var t = 0; t < seq.videoTracks.numTracks; t++) {
        var track = seq.videoTracks[t];
        if (track.isLocked()) { say("V" + (t + 1) + " locked - skipped"); continue; }
        for (var c = 0; c < track.clips.numItems; c++) {
            var clip = track.clips[c];
            var m = motionOf(clip);
            if (!m) { skipped.push(clip.name + " (no Motion)"); continue; }
            var sp = prop(m, "Scale");
            if (sp && sp.isTimeVarying()) { skipped.push(clip.name + " (Scale is keyframed)"); continue; }
            for (var q = 0; q < NAMES.length; q++) {
                if (ref[NAMES[q]] === undefined) continue;
                var tp = prop(m, NAMES[q]);
                if (tp) tp.setValue(ref[NAMES[q]], true);
            }
            done++;
        }
    }
    say("Scaled " + done + " clip(s).");
    if (skipped.length) say("Skipped " + skipped.length + ": " + skipped.join(", "));
    return log.join("\n");
})();
