// Premiere Pro: put the toolkit's suggested markers (step 1) on your timeline.
//
// Reads <project>_captions\suggested-markers.csv (the toolkit writes it every time
// you place markers or ask for more) and adds one RANGE marker per suggestion,
// named "Suggested: <name> (<why>)", in yellow.
// Markers this script made earlier (names starting "Suggested: ") are replaced, so
// run it again after "+ More suggestions". Your own markers are never touched.
//
// Run with VS Code + ExtendScript Debugger ("Evaluate Script in Attached Host").
// Save first.

var PREFIX = "Suggested: ";
var COLOR = 4;          // Premiere marker colour index (0 green, 1 red, 2 purple, 3 orange, 4 yellow, 5 white, 6 blue, 7 cyan)

(function () {
    var seq = app.project.activeSequence;
    if (!seq) { $.writeln("No active sequence - click into a timeline first."); return "no sequence"; }
    if (!app.project.path) { $.writeln("Save the project first."); return "unsaved"; }

    var base = String(app.project.path).replace(/\.prproj$/i, "").replace(/_captions-synced(-v\d+)?$/, "");
    var f = new File(base + "_captions/suggested-markers.csv");
    if (!f.exists) { $.writeln("No suggestions found at " + f.fsName + " - place markers in the toolkit (step 1) first."); return "no list"; }

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
    var msg = "Added " + added + " suggested marker(s), replaced " + removed + " old one(s).";
    $.writeln(msg);
    return msg;
})();
