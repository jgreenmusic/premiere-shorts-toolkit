// Premiere Pro: give every caption GRAPHIC its own pop-in (and fade-out) animation.
//
// Before running: select your captions and use Graphics and Titles >
// "Upgrade Caption to Graphic" so they are clips on a video track.
// Then click into the timeline and run this with VS Code + ExtendScript Debugger
// ("Evaluate Script in Attached Host" -> Premiere Pro).
//
// Which clips: the clips you have SELECTED on the timeline; if none are selected,
// every clip on the highest video track that has clips (where upgraded captions land).
// Clips that already have Scale keyframes are skipped, so running twice is safe.
// Save first - Ctrl+Z undoes one keyframe at a time.

// ---- settings -------------------------------------------------------------
var POP_SCALES   = [88, 104, 100];  // scale % at the frames below
var POP_FRAMES   = [0, 3, 5];       // frames from each caption's start
var FADE_IN      = 2;               // frames for opacity 0 -> 100 (0 = off)
var FADE_OUT     = 2;               // frames for opacity 100 -> 0 at the end (0 = off)
var CAPTION_Y    = 0.75;            // only used if the text layer has no Scale of its own:
                                    // caption's vertical centre as a fraction of frame height,
                                    // so the pop grows around the words, not the frame centre
// ---------------------------------------------------------------------------

(function () {
    var TICKS = 254016000000;
    var seq = app.project.activeSequence;
    if (!seq) { $.writeln("No active sequence - click into a timeline first."); return "no sequence"; }
    var frame = parseFloat(seq.timebase) / TICKS;   // seconds per frame

    // -- which clips ---------------------------------------------------------
    var clips = [], t, c, v;
    for (v = 0; v < seq.videoTracks.numTracks; v++) {
        for (c = 0; c < seq.videoTracks[v].clips.numItems; c++) {
            if (seq.videoTracks[v].clips[c].isSelected()) clips.push(seq.videoTracks[v].clips[c]);
        }
    }
    var source = "selected clips";
    if (!clips.length) {
        for (v = seq.videoTracks.numTracks - 1; v >= 0 && !clips.length; v--) {
            var tr = seq.videoTracks[v];
            if (tr.isLocked() || !tr.clips.numItems) continue;
            for (c = 0; c < tr.clips.numItems; c++) clips.push(tr.clips[c]);
            source = "all clips on V" + (v + 1);
        }
    }
    if (!clips.length) { $.writeln("No clips found. Upgrade the captions to graphics first."); return "no clips"; }
    $.writeln("Animating " + clips.length + " " + source);

    // -- helpers -------------------------------------------------------------
    function findProp(clip, compTest, name) {
        for (var i = 0; i < clip.components.numItems; i++) {
            var comp = clip.components[i];
            if (!compTest(comp)) continue;
            for (var j = 0; j < comp.properties.numItems; j++) {
                if (comp.properties[j].displayName == name) return comp.properties[j];
            }
        }
        return null;
    }
    var isMotion  = function (k) { return k.matchName == "AE.ADBE Motion" || k.displayName == "Motion"; };
    var isOpacity = function (k) { return k.matchName == "AE.ADBE Opacity" || k.displayName == "Opacity"; };
    var isText    = function (k) { return !isMotion(k) && !isOpacity(k); };  // the graphic's own text layer

    function keys(prop, pairs) {                    // pairs: [[seconds, value], ...]
        if (!prop.areKeyframesSupported()) return false;
        prop.setTimeVarying(true);
        for (var i = 0; i < pairs.length; i++) {
            prop.addKey(pairs[i][0]);
            prop.setValueAtKey(pairs[i][0], pairs[i][1], i == pairs.length - 1);
        }
        return true;
    }

    // -- animate -------------------------------------------------------------
    var done = 0, skipped = 0, failed = 0, how = {};
    for (var n = 0; n < clips.length; n++) {
        var clip = clips[n];
        try {
            // keyframe times are in the clip's own time: its in point is "frame 0"
            var t0 = clip.inPoint.seconds;
            var t1 = clip.outPoint.seconds;
            var len = t1 - t0;

            // Prefer the text layer's own Scale (grows around the words); fall back to Motion.
            var scale = findProp(clip, isText, "Scale"), mode = "text layer";
            if (!scale) {
                scale = findProp(clip, isMotion, "Scale"); mode = "Motion";
                var anchor = findProp(clip, isMotion, "Anchor Point");
                var pos = findProp(clip, isMotion, "Position");
                if (anchor && pos && !anchor.isTimeVarying() && !pos.isTimeVarying()) {
                    anchor.setValue([0.5, CAPTION_Y], false);  // anchor = position: nothing moves
                    pos.setValue([0.5, CAPTION_Y], false);     // at 100%, but scaling is centred on the text
                }
            }
            if (!scale) { failed++; $.writeln("  no Scale on '" + clip.name + "'"); continue; }
            if (scale.isTimeVarying()) { skipped++; continue; }

            var pairs = [];
            for (var k = 0; k < POP_FRAMES.length; k++) {
                if (POP_FRAMES[k] * frame < len) pairs.push([t0 + POP_FRAMES[k] * frame, POP_SCALES[k]]);
            }
            keys(scale, pairs);

            var op = findProp(clip, isOpacity, "Opacity");
            if (op && !op.isTimeVarying() && (FADE_IN || FADE_OUT)) {
                var o = [];
                if (FADE_IN && FADE_IN * frame < len / 2) { o.push([t0, 0]); o.push([t0 + FADE_IN * frame, 100]); }
                if (FADE_OUT && FADE_OUT * frame < len / 2) { o.push([t1 - FADE_OUT * frame, 100]); o.push([t1 - frame * 0.01, 0]); }
                if (o.length) keys(op, o);
            }
            how[mode] = (how[mode] || 0) + 1;
            done++;
        } catch (e) {
            failed++;
            $.writeln("  error on '" + clip.name + "': " + e);
        }
    }
    var modes = [];
    for (var m in how) modes.push(how[m] + " via " + m);
    var msg = "Animated " + done + ", skipped " + skipped + " (already keyframed), failed " + failed +
              (modes.length ? "  [" + modes.join(", ") + "]" : "");
    $.writeln(msg);
    return msg;
})();
