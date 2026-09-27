// Premiere Pro: razor every unlocked video + audio track of the ACTIVE sequence
// at every SEQUENCE marker (markers on the timeline ruler, not clip markers) -
// at both the start and the end of a range marker, so each Short is its own piece.
// Run it from the toolkit (Run in Premiere), or VS Code + "ExtendScript Debugger".
// Undo: Ctrl+Z steps back one cut at a time (or use History panel).
(function () {
    var seq = app.project.activeSequence;
    if (!seq) { $.writeln("No active sequence - click into a timeline first."); return "No active sequence - click into a timeline first."; }

    app.enableQE();
    var qeSeq = qe.project.getActiveSequence();
    var settings = seq.getSettings();
    var frameRate = settings.videoFrameRate;
    var displayFormat = settings.videoDisplayFormat;
    var TICKS = 254016000000;
    var seqEnd = parseFloat(seq.end) / TICKS;

    // Collect unique marker times (start, and end of range markers), in order.
    var seen = {}, times = [];
    function add(t) {
        var s = t.seconds;
        if (!seen[t.ticks] && s > 0 && s < seqEnd) { seen[t.ticks] = true; times.push(t); }
    }
    var m = seq.markers.getFirstMarker();
    while (m) {
        add(m.start);
        if (m.end && m.end.seconds > m.start.seconds) add(m.end);
        m = seq.markers.getNextMarker(m);
    }
    if (!times.length) { $.writeln("No sequence markers found inside the sequence."); return "No markers on this sequence yet - place them first."; }
    times.sort(function (a, b) { return a.seconds - b.seconds; });

    var cuts = 0;
    for (var t = 0; t < times.length; t++) {
        var tc = times[t].getFormatted(frameRate, displayFormat);
        for (var v = 0; v < qeSeq.numVideoTracks; v++) {
            if (seq.videoTracks[v].isLocked()) continue;
            qeSeq.getVideoTrackAt(v).razor(tc);
        }
        for (var a = 0; a < qeSeq.numAudioTracks; a++) {
            if (seq.audioTracks[a].isLocked()) continue;
            qeSeq.getAudioTrackAt(a).razor(tc);
        }
        cuts++;
        $.writeln("Cut at " + tc);
    }
    var msg = "Cut every track at " + cuts + " point(s) on '" + seq.name + "'. Ctrl+Z in Premiere undoes a cut.";
    $.writeln(msg);
    return msg;
})();
