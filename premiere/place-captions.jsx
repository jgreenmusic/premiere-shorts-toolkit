// Puts the Shorts' captions on their timelines as clips of the animated template.
// Run by the toolkit through a small wrapper that sets SHORTS_LIST (<project>_premiere\animated.txt:
// "BIN <tab> this send's bin", then one "sequence name <tab> its animated.json" per line) and SHORTS_MOGRT.
// A timeline's drawn caption layer (V3) is switched off once its template clips are in, so it stays
// there to compare or to go back to. The numbers are the template's: premiere/ae/build-caption-mogrt.jsx.
(function () {
    var TICKS = 254016000000;
    function T(s) { return String(Math.round(s * TICKS)); }
    function jstr(s) { return s.replace(/\\/g, "\\\\").replace(/"/g, '\\"'); }
    function setText(p, text) {
        var v = String(p.getValue());
        v = v.replace(/"textEditValue":".*"\}$/, function () { return '"textEditValue":"' + jstr(text) + '"}'; })
             .replace(/"fontTextRunLength":\[\d+\]/, '"fontTextRunLength":[' + text.length + ']');
        p.setValue(v, 1);
    }
    function col(p, hex) {
        p.setColorValue(255, parseInt(hex.substr(0, 2), 16), parseInt(hex.substr(2, 2), 16), parseInt(hex.substr(4, 2), 16), 1);
    }
    function read(path) {
        var f = new File(path);
        f.encoding = "UTF-8";
        if (!f.open("r")) return null;
        var t = f.read();
        f.close();
        return t;
    }
    function findBin(item, name) {
        for (var i = 0; i < item.children.numItems; i++) {
            var c = item.children[i];
            if (c.type !== ProjectItemType.BIN) continue;
            if (c.name === name) return c;
            var deeper = findBin(c, name);
            if (deeper) return deeper;
        }
        return null;
    }
    function find(bin, name) {                  // the timeline of that name in this send's bin
        for (var i = 0; i < bin.children.numItems; i++) {
            var c = bin.children[i];
            if (c.name !== name || !c.isSequence()) continue;
            for (var k = 0; k < app.project.sequences.numSequences; k++) {
                var s = app.project.sequences[k];
                if (s.projectItem.nodeId === c.nodeId) return s;
            }
        }
        return null;
    }
    var lines = read(SHORTS_LIST).split("\n"), placed = 0, timelines = 0, missing = [];
    var binName = lines[0].replace(/\r$/, "").split("\t")[1];
    var bin = findBin(app.project.rootItem, binName);
    if (!bin) return "Couldn't find the bin " + binName + " in this project, so no animated captions were placed.";
    app.enableQE();
    for (var n = 1; n < lines.length; n++) {
        var row = lines[n].replace(/\r$/, "").split("\t");
        if (row.length < 2) continue;
        var s = find(bin, row[0]);
        if (!s) { missing.push(row[0]); continue; }
        var list = eval("(" + read(row[1]) + ")");
        if (!list.length) continue;
        if (s.videoTracks.numTracks < 4) {
            app.project.openSequence(s.sequenceID);
            qe.project.getActiveSequence().addTracks(4 - s.videoTracks.numTracks, s.videoTracks.numTracks, 0);
        }
        var v = s.videoTracks[3];
        if (v.clips.numItems) continue;         // this timeline has its captions already
        for (var i = 0; i < list.length; i++) {
            var c = list[i];
            var clip = s.importMGT(SHORTS_MOGRT, T(c.start), 3, 0);
            var e = new Time();
            e.seconds = c.end;
            clip.end = e;
            clip.name = c.text;
            var ps = clip.getMGTComponent().properties;
            setText(ps.getParamForDisplayName("Caption"), c.text);
            setText(ps.getParamForDisplayName("Word times"), c.times);
            ps.getParamForDisplayName("Font").setValue(c.font, 1);
            ps.getParamForDisplayName("Size").setValue(c.size, 1);
            ps.getParamForDisplayName("Highlight style").setValue(c.hl, 1);
            ps.getParamForDisplayName("Animation").setValue(c.anim, 1);
            ps.getParamForDisplayName("Outline").setValue(c.outline, 1);
            ps.getParamForDisplayName("Shadow").setValue(c.shadow, 1);
            ps.getParamForDisplayName("Height from bottom %").setValue(c.height, 1);
            ps.getParamForDisplayName("Loud").setValue(c.loud, 1);
            col(ps.getParamForDisplayName("Highlight colour"), c.hl_col);
            col(ps.getParamForDisplayName("Text colour"), c.text_col);
            col(ps.getParamForDisplayName("Text in box"), c.hl_text);
            col(ps.getParamForDisplayName("Outline colour"), c.outline_col);
            placed++;
        }
        var drawn = s.videoTracks[2];
        for (var k = 0; k < drawn.clips.numItems; k++) drawn.clips[k].disabled = true;
        timelines++;
    }
    if (typeof SHORTS_NOSAVE === "undefined") app.project.save();
    return placed + " animated captions on " + timelines + " timeline(s)" + (missing.length ? "; not found: " + missing.join(", ") : "");
})();
