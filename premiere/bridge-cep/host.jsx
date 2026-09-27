// ExtendScript side of the Shorts Toolkit - Captions panel.
// (ExtendScript is ES3: no JSON object, so replies are built by hand.)

function shortsQuote(s) {
    s = String(s);
    var out = '"';
    for (var i = 0; i < s.length; i++) {
        var c = s.charAt(i), n = s.charCodeAt(i);
        if (c == '"' || c == "\\") out += "\\" + c;
        else if (n < 32) out += "\\u" + ("000" + n.toString(16)).slice(-4);
        else out += c;
    }
    return out + '"';
}

// the project the toolkit means, or a copy saved from it next to it ("Name.prproj" ->
// "NameV0.1.prproj", "Name_captions-synced.prproj")
function shortsSame(open, wanted) {
    var n = function (p) { return String(p).replace(/\//g, "\\").replace(/^\\\\\?\\/, "").toLowerCase(); };
    var o = n(open), w = n(wanted);
    if (o == w) return true;
    var od = o.substring(0, o.lastIndexOf("\\")), wd = w.substring(0, w.lastIndexOf("\\"));
    var os = o.substring(o.lastIndexOf("\\") + 1).replace(/\.prproj$/, "");
    var ws = w.substring(w.lastIndexOf("\\") + 1).replace(/\.prproj$/, "").replace(/_captions-synced(-v\d+)?$/, "");
    return od == wd && os.indexOf(ws) == 0;
}

// what the app sees: the open project and sequence
function shortsInfo() {
    try {
        var p = app.project;
        if (!p || !p.path) return "{}";
        var s = p.activeSequence;
        return "{\"project\":" + shortsQuote(p.path) + (s ? ",\"sequence\":" + shortsQuote(s.name) : "") + "}";
    } catch (e) {
        return "{\"error\":" + shortsQuote(e) + "}";
    }
}

function shortsFindChild(bin, name) {
    for (var i = bin.children.numItems - 1; i >= 0; i--) {
        if (bin.children[i].name == name) return bin.children[i];
    }
    return null;
}

// open the project's sequence (by name) and make it the active one
function shortsUseSequence(p, seqName) {
    var seq = null;
    for (var i = 0; i < p.sequences.numSequences; i++) {
        if (p.sequences[i].name == seqName) { seq = p.sequences[i]; break; }
    }
    if (!seq) seq = p.activeSequence;
    if (seq && (!p.activeSequence || p.activeSequence.sequenceID != seq.sequenceID)) p.openSequence(seq.sequenceID);
    return seq;
}

// run one of the toolkit's premiere/*.jsx scripts on the open project; the script's
// last value is its message
function shortsRunScript(scriptPath, seqName, projectPath) {
    try {
        var p = app.project;
        if (!p || !p.path) return "ERR:No project is open in Premiere.";
        if (projectPath && !shortsSame(p.path, projectPath)) {
            return "ERR:Premiere has \"" + p.name + "\" open - open " + projectPath.replace(/^.*[\\\/]/, "") + " in Premiere, then try again.";
        }
        if (!shortsUseSequence(p, seqName)) return "ERR:No sequence is open.";
        var f = new File(scriptPath);
        if (!f.exists) return "ERR:Script not found: " + scriptPath;
        var r = $.evalFile(f);
        return "OK:" + (r === undefined ? "Done." : r);
    } catch (e) {
        return "ERR:" + e;
    }
}

// lay an .srt on the sequence as a new caption track, then save the project
function shortsImportCaptions(srtPath, seqName, projectPath) {
    try {
        var p = app.project;
        if (!p || !p.path) return "ERR:No project is open in Premiere.";
        if (projectPath && !shortsSame(p.path, projectPath)) {
            return "ERR:Premiere has \"" + p.name + "\" open - open " + projectPath.replace(/^.*[\\\/]/, "") + " in Premiere, then try again.";
        }
        var seq = null;
        for (var i = 0; i < p.sequences.numSequences; i++) {
            if (p.sequences[i].name == seqName) { seq = p.sequences[i]; break; }
        }
        if (!seq) seq = p.activeSequence;
        if (!seq) return "ERR:No sequence named \"" + seqName + "\" and none is open.";
        if (!p.activeSequence || p.activeSequence.sequenceID != seq.sequenceID) p.openSequence(seq.sequenceID);

        var f = new File(srtPath);
        if (!f.exists) return "ERR:The caption file is missing: " + srtPath;
        var bin = shortsFindChild(p.rootItem, "Shorts Toolkit captions");
        if (!bin) bin = p.rootItem.createBin("Shorts Toolkit captions");
        if (!bin) bin = p.rootItem;
        if (!p.importFiles([f.fsName], true, bin, false)) return "ERR:Premiere couldn't import " + f.name;
        var item = shortsFindChild(bin, f.name) || shortsFindChild(bin, f.name.replace(/\.srt$/i, ""));
        if (!item) return "ERR:Imported " + f.name + " but couldn't find it in the Project panel.";

        seq.createCaptionTrack(item, 0, Sequence.CAPTION_FORMAT_SUBTITLE);
        p.save();
        return "OK:Caption track added to \"" + seq.name + "\" and the project saved.";
    } catch (e) {
        return "ERR:" + e;
    }
}
