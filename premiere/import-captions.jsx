// Premiere Pro: import an .srt and lay it on the ACTIVE sequence as a new caption
// track starting at the sequence start. Pick the file in the dialog.
// Then: hide/delete the old caption track and apply your saved Track Style to the new one.
(function () {
    var seq = app.project.activeSequence;
    if (!seq) { $.writeln("No active sequence - click into a timeline first."); return "no sequence"; }
    var f = File.openDialog("Choose the .srt to import", "*.srt");
    if (!f) return "cancelled";
    if (!app.project.importFiles([f.fsName], true, app.project.rootItem, false)) {
        $.writeln("Import failed: " + f.fsName); return "import failed";
    }
    // find the item we just imported
    var item = null;
    for (var i = app.project.rootItem.children.numItems - 1; i >= 0; i--) {
        var c = app.project.rootItem.children[i];
        if ((c.getMediaPath && c.getMediaPath() == f.fsName) || c.name == f.name) { item = c; break; }
    }
    if (!item) { $.writeln("Imported, but could not find it in the project panel."); return "not found"; }
    seq.createCaptionTrack(item, 0, Sequence.CAPTION_FORMAT_SUBTITLE);
    var msg = "Added caption track from " + f.name + ". Now hide the old caption track and apply your Track Style.";
    $.writeln(msg);
    return msg;
})();
