// Premiere Pro: razor every unlocked video + audio track of the ACTIVE sequence
// at every SEQUENCE marker (markers on the timeline ruler, not clip markers).
// Run with VS Code + "ExtendScript Debugger" -> target "Adobe Premiere Pro".
// Undo: Ctrl+Z steps back one cut at a time (or use History panel).
(function () {
    var seq = app.project.activeSequence;
    if (!seq) { $.writeln("No active sequence - click into a timeline first."); return "no sequence"; }

    app.enableQE();
    var qeSeq = qe.project.getActiveSequence();
    var settings = seq.getSettings();
    var frameRate = settings.videoFrameRate;
    var displayFormat = settings.videoDisplayFormat;
    var TICKS = 254016000000;
    var seqEnd = parseFloat(seq.end) / TICKS;

    // Collect unique marker times, in order.
    var seen = {}, times = [];
    var m = seq.markers.getFirstMarker();
    while (m) {
        var s = m.start.seconds;
        var key = m.start.ticks;
        if (!seen[key] && s > 0 && s < seqEnd) { seen[key] = true; times.push(m.start); }
        m = seq.markers.getNextMarker(m);
    }
    if (!times.length) { $.writeln("No sequence markers found inside the sequence."); return "no markers"; }

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
    var msg = "Done: cut at " + cuts + " marker(s) on sequence '" + seq.name + "'.";
    $.writeln(msg);
    return msg;
})();
