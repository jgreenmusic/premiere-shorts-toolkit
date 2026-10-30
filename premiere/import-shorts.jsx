// Premiere Pro: bring in the Shorts the toolkit sent to Premiere (Shorts > Send to Premiere,
// or `shorts.py to-premiere`).
//
// Reads <project>_premiere\import.txt (written by the toolkit: the .xml first, then one .srt per
// Short) and imports the .xml - each Short becomes a vertical timeline in a bin named
// "Shorts Toolkit - <project>" - plus the .srt files into the bin "Shorts Toolkit captions (text)".
// Opens the first new timeline. Earlier imports are left alone (delete them yourself if you
// don't need them any more). The project is not saved - save when you're happy.
//
// Same thing by hand: File > Import > the .xml in <project>_premiere.

(function () {
    var p = app.project;
    if (!p || !p.path) return "Save the project first.";

    var base = String(p.path).replace(/\.prproj$/i, "").replace(/_captions-synced(-v\d+)?$/, "");
    var list = new File(base + "_premiere/import.txt");
    if (!list.exists) return "Nothing to import yet: send Shorts to Premiere from the toolkit first (" + list.fsName + " is missing).";

    var lines = [];
    list.encoding = "UTF-8";
    list.open("r");
    while (!list.eof) {
        var ln = list.readln();
        if (ln && ln.length) lines.push(ln);
    }
    list.close();
    if (!lines.length) return "The import list is empty - send the Shorts to Premiere again.";

    var xml = new File(lines[0]);
    if (!xml.exists) return "The timeline file is missing: " + xml.fsName;

    var before = {};
    for (var i = 0; i < p.sequences.numSequences; i++) before[p.sequences[i].sequenceID] = true;

    if (!p.importFiles([xml.fsName], true, p.rootItem, false)) return "Premiere couldn't import " + xml.name;

    var srts = [];
    for (var j = 1; j < lines.length; j++) {
        var f = new File(lines[j]);
        if (f.exists) srts.push(f.fsName);
    }
    if (srts.length) {
        var bin = null;
        for (var k = 0; k < p.rootItem.children.numItems; k++) {
            var c = p.rootItem.children[k];
            if (c.name == "Shorts Toolkit captions (text)" && c.type == ProjectItemType.BIN) { bin = c; break; }
        }
        if (!bin) bin = p.rootItem.createBin("Shorts Toolkit captions (text)");
        p.importFiles(srts, true, bin || p.rootItem, false);
    }

    var added = [];
    for (var n = 0; n < p.sequences.numSequences; n++) {
        if (!before[p.sequences[n].sequenceID]) added.push(p.sequences[n]);
    }
    if (!added.length) return "Premiere read " + xml.name + " but no new timeline showed up.";
    p.openSequence(added[0].sequenceID);
    return "Imported " + added.length + " Short" + (added.length == 1 ? "" : "s") + " as timelines. Opened \"" + added[0].name + "\".";
})();
