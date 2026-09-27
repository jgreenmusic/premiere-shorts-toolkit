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

function shortsSame(a, b) {
    return String(a).replace(/\//g, "\\").toLowerCase() == String(b).replace(/\//g, "\\").toLowerCase();
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
