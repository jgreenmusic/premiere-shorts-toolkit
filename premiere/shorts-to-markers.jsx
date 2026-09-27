// Premiere Pro: put your Shorts on the timeline as named RANGE markers.
//
// Reads <project>_captions\shorts-markers.csv (the toolkit app keeps it up to date
// whenever you change your Shorts list) and adds one marker per Short, spanning
// its start to end, named "Short: <name>", in the colour below.
// Markers this script made earlier (names starting "Short: ") are replaced, so run it
// again whenever your list changes. Your own markers are never touched.
//
// Going the other way works too: range markers you make in Premiere show up in the
// app under "Import from markers".
//
// Run with VS Code + ExtendScript Debugger ("Evaluate Script in Attached Host").
// Save first.

var PREFIX = "Short: ";
var COLOR = 3;          // Premiere marker colour index (0 green, 1 red, 2 purple, 3 orange, 4 yellow, 5 white, 6 blue, 7 cyan)

(function () {
    var seq = app.project.activeSequence;
    if (!seq) { $.writeln("No active sequence - click into a timeline first."); return "No active sequence - click into a timeline first."; }
    if (!app.project.path) { $.writeln("Save the project first."); return "Save the project first."; }

    var base = String(app.project.path).replace(/\.prproj$/i, "").replace(/_captions-synced(-v\d+)?$/, "");
    var f = new File(base + "_captions/shorts-markers.csv");
    if (!f.exists) { $.writeln("No Shorts list found at " + f.fsName + " - add Shorts in the toolkit app first."); return "Nothing to add yet: " + f.fsName + " is missing."; }

    var rows = [];
    f.encoding = "UTF-8";
    f.open("r");
    f.readln();
    while (!f.eof) {
        var line = f.readln();
        if (!line) continue;
        var p = line.split(",");
        rows.push({ s: parseFloat(p[0]), e: parseFloat(p[1]), name: p.slice(2).join(",") });
    }
    f.close();

    // remove markers this script made before
    var removed = 0, m = seq.markers.getFirstMarker(), old = [];
    while (m) {
        if (String(m.name).indexOf(PREFIX) === 0) old.push(m);
        m = seq.markers.getNextMarker(m);
    }
    for (var i = 0; i < old.length; i++) { seq.markers.deleteMarker(old[i]); removed++; }

    var added = 0;
    for (var r = 0; r < rows.length; r++) {
        var row = rows[r];
        if (!(row.e > row.s)) continue;
        var mk = seq.markers.createMarker(row.s);
        mk.name = PREFIX + row.name;
        mk.end = row.e;
        try { mk.setColorByIndex(COLOR); } catch (e) {}
        added++;
    }
    var msg = "Added " + added + " Short marker(s), replaced " + removed + " old one(s).";
    $.writeln(msg);
    return msg;
})();
