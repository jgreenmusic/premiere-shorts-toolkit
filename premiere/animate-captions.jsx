// Premiere Pro: give every caption GRAPHIC its own entrance animation.
//
// Before running: select your captions and use Graphics and Titles >
// "Upgrade Caption to Graphic" so they are clips on a video track.
// Then click into the timeline and run this with VS Code + ExtendScript Debugger
// ("Evaluate Script in Attached Host" -> Premiere Pro).
//
// WHICH CLIPS: the clips you have SELECTED; otherwise the clips between your
// sequence In and Out points (press I and O on the timeline); otherwise every
// clip on the highest video track that has clips (where upgraded captions land).
//
// HOW EACH CAPTION MOVES (decided per caption):
//   after a pause (>= PAUSE s)     -> full pop
//   straight after another caption -> tiny pop, so fast talk doesn't pulse
//   very short (< SHORT s)         -> fade only, a pop would read as flicker
//   loud line  (from the toolkit)  -> bigger pop, stays a little bigger
//   scream     (from the toolkit)  -> strong pop + wobble on its first letter;
//                                     the growing letters that follow just appear
//   laugh      (from the toolkit)  -> a small bounce on every "ha" as it appears
// Loud/scream data comes from the toolkit's "Prepare for Premiere" step
// (<project>_captions\premiere-emphasis.csv). Without it, the other rules still apply.
//
// Re-running replaces this script's animation on those clips, so you can tweak and
// run again. MODE = "remove" takes it off. Save first.

// ---- settings -------------------------------------------------------------
var MODE        = "animate";          // "animate" or "remove"
var PAUSE       = 0.5;                // seconds of gap that counts as a pause
var SHORT       = 0.4;                // captions shorter than this only fade
var FULL_POP    = [[0, 88], [3, 104], [5, 100]];        // [frame, scale %]
var SMALL_POP   = [[0, 97], [3, 100]];
var LOUD_POP    = [[0, 90], [3, 118], [6, 110]];        // ends bigger: 110%
var SCREAM_POP  = [[0, 84], [3, 122], [6, 112]];
var SCREAM_WOBBLE = [[0, 0], [2, -3], [4, 2.5], [6, -1.5], [8, 0]];   // [frame, degrees]
var LAUGH_POP   = [[0, 106], [3, 100]];                 // every laugh syllable bounces
var FADE_IN     = 2;                  // frames, 0 = off
var FADE_OUT    = 2;
var CAPTION_Y   = 0.75;               // only if the text layer has no Scale of its own:
                                      // caption's vertical centre as a fraction of frame height
// ---------------------------------------------------------------------------

(function () {
    var TICKS = 254016000000;
    var seq = app.project.activeSequence;
    if (!seq) { $.writeln("No active sequence - click into a timeline first."); return "no sequence"; }
    var frame = parseFloat(seq.timebase) / TICKS;

    // ---- which clips ------------------------------------------------------
    function inOut() {
        var a = null, b = null;
        try { a = seq.getInPointAsTime().seconds; b = seq.getOutPointAsTime().seconds; }
        catch (e) { try { a = parseFloat(seq.getInPoint()); b = parseFloat(seq.getOutPoint()); } catch (e2) {} }
        var end = parseFloat(seq.end) / TICKS;
        if (a === null || b === null || b <= a || (a <= 0.01 && b >= end - 0.05)) return null;
        return [a, b];
    }
    var clips = [], v, c, tr, source;
    for (v = 0; v < seq.videoTracks.numTracks; v++)
        for (c = 0; c < seq.videoTracks[v].clips.numItems; c++)
            if (seq.videoTracks[v].clips[c].isSelected()) clips.push(seq.videoTracks[v].clips[c]);
    source = "selected clips";
    if (!clips.length) {
        var range = inOut();
        for (v = seq.videoTracks.numTracks - 1; v >= 0 && !clips.length; v--) {
            tr = seq.videoTracks[v];
            if (tr.isLocked() || !tr.clips.numItems) continue;
            for (c = 0; c < tr.clips.numItems; c++) {
                var k = tr.clips[c];
                if (!range || (k.start.seconds < range[1] && k.end.seconds > range[0])) clips.push(k);
            }
            source = (range ? "clips between In and Out on V" : "all clips on V") + (v + 1);
        }
    }
    if (!clips.length) { $.writeln("No clips found. Upgrade the captions to graphics first."); return "no clips"; }
    clips.sort(function (a, b) { return a.start.seconds - b.start.seconds; });
    $.writeln((MODE == "remove" ? "Removing animation from " : "Animating ") + clips.length + " " + source);

    // ---- emphasis from the toolkit ----------------------------------------
    function norm(s) { return String(s).toLowerCase().replace(/[^a-z0-9']/g, ""); }
    function emphasisFile() {
        if (!app.project.path) return null;
        var p = String(app.project.path).replace(/\.prproj$/i, "").replace(/_captions-synced(-v\d+)?$/, "");
        var f = new File(p + "_captions/premiere-emphasis.csv");
        return f.exists ? f : null;
    }
    var marks = [];
    var ef = emphasisFile();
    if (ef && MODE != "remove") {
        ef.encoding = "UTF-8";
        ef.open("r");
        ef.readln();                                     // header
        while (!ef.eof) {
            var line = ef.readln();
            if (!line) continue;
            var p = line.split(",");
            marks.push({ s: parseFloat(p[0]), e: parseFloat(p[1]), kind: p[2], text: norm(p.slice(4).join(",")) });
        }
        ef.close();
        $.writeln("  emphasis: " + marks.length + " loud/scream moments from " + ef.name);
    } else if (MODE != "remove") {
        $.writeln("  no emphasis file - run 'Prepare for Premiere' in the toolkit for loud/scream moves");
    }
    // If this sequence's times differ from the analysed one (e.g. a Short cut out of the
    // full video), find the shift from captions whose text matches a loud line.
    var shift = 0;
    if (marks.length) {
        var votes = {}, best = 0;
        for (c = 0; c < clips.length; c++) {
            var nm = norm(clips[c].name);
            if (!nm) continue;
            for (var m = 0; m < marks.length; m++) {
                if (marks[m].text && marks[m].text == nm) {
                    var d = Math.round((marks[m].s - clips[c].start.seconds) * 10) / 10;
                    votes[d] = (votes[d] || 0) + 1;
                }
            }
        }
        for (var key in votes) if (votes[key] > best) { best = votes[key]; shift = parseFloat(key); }
        if (best >= 2 && Math.abs(shift) > 0.3) $.writeln("  this sequence is offset " + shift + "s from the analysed one - adjusted");
        else shift = 0;
    }
    function markFor(clip) {
        var s = clip.start.seconds + shift, e = clip.end.seconds + shift;
        for (var i = 0; i < marks.length; i++) {
            var mk = marks[i];
            if (mk.kind == "loud" && Math.abs(mk.s - s) < 0.25) return { kind: "loud" };
            if ((mk.kind == "scream" || mk.kind == "laugh") && s >= mk.s - 0.25 && s < mk.e + 0.2)
                return { kind: mk.kind, first: Math.abs(s - mk.s) < 0.25 };
        }
        return null;
    }

    // ---- keyframe helpers -------------------------------------------------
    function findProp(clip, test, name) {
        for (var i = 0; i < clip.components.numItems; i++) {
            var comp = clip.components[i];
            if (!test(comp)) continue;
            for (var j = 0; j < comp.properties.numItems; j++)
                if (comp.properties[j].displayName == name) return comp.properties[j];
        }
        return null;
    }
    var isMotion  = function (k) { return k.matchName == "AE.ADBE Motion" || k.displayName == "Motion"; };
    var isOpacity = function (k) { return k.matchName == "AE.ADBE Opacity" || k.displayName == "Opacity"; };
    var isText    = function (k) { return !isMotion(k) && !isOpacity(k); };

    function clear(prop, rest) {                         // drop keyframes, back to a still value
        if (prop && prop.isTimeVarying()) { prop.setTimeVarying(false); prop.setValue(rest, true); }
    }
    function keys(prop, t0, pairs, len) {                // pairs: [[frame, value], ...]
        if (!prop || !prop.areKeyframesSupported()) return;
        prop.setTimeVarying(true);
        var used = [];
        for (var i = 0; i < pairs.length; i++) if (pairs[i][0] * frame < len) used.push(pairs[i]);
        for (i = 0; i < used.length; i++) {
            var t = t0 + used[i][0] * frame;
            prop.addKey(t);
            prop.setValueAtKey(t, used[i][1], i == used.length - 1);
        }
    }

    // ---- go ---------------------------------------------------------------
    var count = { full: 0, small: 0, fade: 0, loud: 0, scream: 0, still: 0, laugh: 0, removed: 0 }, failed = 0;
    for (var n = 0; n < clips.length; n++) {
        var clip = clips[n];
        try {
            var t0 = clip.inPoint.seconds, t1 = clip.outPoint.seconds, len = t1 - t0;
            var scale = findProp(clip, isText, "Scale"), rot = findProp(clip, isText, "Rotation");
            var viaMotion = !scale;
            if (viaMotion) { scale = findProp(clip, isMotion, "Scale"); rot = findProp(clip, isMotion, "Rotation"); }
            var op = findProp(clip, isOpacity, "Opacity");
            if (!scale) { failed++; $.writeln("  no Scale on '" + clip.name + "'"); continue; }

            clear(scale, 100); clear(rot, 0); clear(op, 100);
            if (MODE == "remove") { count.removed++; continue; }

            if (viaMotion) {                             // grow around the words, not the frame centre
                var anchor = findProp(clip, isMotion, "Anchor Point"), pos = findProp(clip, isMotion, "Position");
                if (anchor && pos && !anchor.isTimeVarying() && !pos.isTimeVarying()) {
                    anchor.setValue([0.5, CAPTION_Y], false);
                    pos.setValue([0.5, CAPTION_Y], false);
                }
            }

            var prev = n > 0 ? clips[n - 1] : null;
            var gap = prev ? clip.start.seconds - prev.end.seconds : 99;
            var mk = markFor(clip), pop = null, fadeIn = FADE_IN, fadeOut = FADE_OUT, kind;

            if (mk && mk.kind == "scream") {
                if (mk.first) { pop = SCREAM_POP; keys(rot, t0, SCREAM_WOBBLE, len); kind = "scream"; }
                else {                                    // next letter step: no entrance, no fade
                    fadeIn = 0;
                    var nxt = n + 1 < clips.length ? clips[n + 1] : null;
                    if (nxt && markFor(nxt) && markFor(nxt).kind == "scream" && !markFor(nxt).first) fadeOut = 0;
                    if (scale) scale.setValue(SCREAM_POP[SCREAM_POP.length - 1][1], true);  // hold the scream size
                    kind = "still";
                }
            } else if (mk && mk.kind == "laugh") {             // each "ha" gets a little bounce
                pop = LAUGH_POP; kind = "laugh";
                var nx = n + 1 < clips.length ? markFor(clips[n + 1]) : null;
                if (!mk.first) fadeIn = 0;
                if (nx && nx.kind == "laugh" && !nx.first) fadeOut = 0;
            } else if (mk && mk.kind == "loud") { pop = LOUD_POP; kind = "loud"; }
            else if (len < SHORT)               { kind = "fade"; }
            else if (gap >= PAUSE)              { pop = FULL_POP; kind = "full"; }
            else                                { pop = SMALL_POP; kind = "small"; }

            if (pop) keys(scale, t0, pop, len);
            if (op && (fadeIn || fadeOut)) {
                var o = [];
                if (fadeIn && fadeIn * frame < len / 2) { o.push([0, 0]); o.push([fadeIn, 100]); }
                if (fadeOut && fadeOut * frame < len / 2) {
                    var lastF = len / frame;
                    o.push([lastF - fadeOut, 100]); o.push([lastF - 0.01, 0]);
                }
                if (o.length) keys(op, t0, o, len + frame);
            }
            count[kind]++;
        } catch (e) {
            failed++;
            $.writeln("  error on '" + clip.name + "': " + e);
        }
    }
    var msg = MODE == "remove"
        ? "Removed animation from " + count.removed + " caption(s), failed " + failed
        : "Done: " + count.full + " full pop, " + count.small + " small pop, " + count.fade + " fade only, " +
          count.loud + " loud, " + count.scream + " scream, " + count.still + " scream letters, " +
          count.laugh + " laugh steps. Failed " + failed;
    $.writeln(msg);
    return msg;
})();
