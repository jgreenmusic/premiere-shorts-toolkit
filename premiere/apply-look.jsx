// "Copy this look to every caption": select one animated caption on the timeline, then the toolkit
// runs this. Everything except its words and word times goes to every animated caption there.
(function () {
    var s = app.project.activeSequence;
    if (!s) return "Open the Short's timeline first.";
    var keep = { "Caption": 1, "Word times": 1 };
    var colours = { "Text colour": 1, "Highlight colour": 1, "Text in box": 1, "Outline colour": 1 };
    function template(c) { try { return c.getMGTComponent(); } catch (e) { return null; } }
    var sel = s.getSelection(), from = null;
    for (var i = 0; i < sel.length && !from; i++) {
        if (sel[i].mediaType === "Video" || sel[i].getMGTComponent) from = template(sel[i]);
    }
    if (!from) return "Select one animated caption on the timeline first.";
    var vals = [];
    for (var p = 0; p < from.properties.numItems; p++) {
        var q = from.properties[p], n = q.displayName;
        if (keep[n]) continue;
        vals.push({ n: n, colour: !!colours[n], v: colours[n] ? q.getColorValue() : q.getValue() });
    }
    var done = 0;
    for (var t = 0; t < s.videoTracks.numTracks; t++) {
        var clips = s.videoTracks[t].clips;
        for (var c = 0; c < clips.numItems; c++) {
            var m = template(clips[c]);
            if (!m || !m.properties.getParamForDisplayName("Word times")) continue;
            for (var k = 0; k < vals.length; k++) {
                var d = m.properties.getParamForDisplayName(vals[k].n);
                if (!d) continue;
                if (vals[k].colour) d.setColorValue(vals[k].v[0], vals[k].v[1], vals[k].v[2], vals[k].v[3], 1);
                else d.setValue(vals[k].v, 1);
            }
            done++;
        }
    }
    return "Look copied to " + done + " captions on " + s.name;
})();
