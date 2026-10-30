// Builds the Shorts Toolkit caption as a Motion Graphics Template (.mogrt) in After Effects.
// Run by the toolkit (ae_template.py): AfterFX.exe -r build-caption-mogrt.jsx, after it wrote
// build-caption-mogrt.json next to this script with { out, font, done }.
//
// In Premiere each caption is one clip of this template. Essential Graphics shows:
//   Caption              the words (type to change them)
//   Word times           when each word is said, seconds from the clip start, then the end:
//                        "0 0.31 0.62 1.40". Retyped words that no longer match are spread evenly.
//   Text / Highlight / Text in box / Outline colours, Outline, Shadow, Height from bottom %
//   (font and size are on the Caption control itself - ae_template.py unlocks them in the .mogrt;
//   sliders stay 0-100 because After Effects stores that range inside the template)
//   Highlight style      Colour, Colour + bigger, Box, Karaoke, None   (the toolkit's hl_mode)
//   Animation            Pop, Bounce, Fade, None                      (the toolkit's anim)
//   Loud                 bigger + capitals, like the toolkit's loud lines
// The numbers match style.py (pop 170 ms 88 -> 104 -> 100 %, bounce, fade-in 70 ms, loud 112 %).
(function () {
    var here = File($.fileName).parent;
    var cfgFile = File(here.fsName + "/build-caption-mogrt.json");
    cfgFile.open("r");
    var cfg = eval("(" + cfgFile.read() + ")");
    cfgFile.close();
    var log = [];
    var SIZE = 2.4;            // the Size slider is 0-100 in Premiere: 40 = 96 px, 100 = 240 px
    function fontList() {
        var q = [];
        for (var i = 0; i < cfg.font_ps.length; i++) q.push('"' + cfg.font_ps[i] + '"');
        return "[" + q.join(", ") + "]";
    }
    function done(ok, msg) {
        // the toolkit waits for this file (written next to the .mogrt)
        var f = File(cfg.done);
        if (f.open("w")) { f.write((ok ? "OK " : "FAILED ") + msg + "\n" + log.join("\n")); f.close(); }
    }
    try {
        app.beginSuppressDialogs();
        app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
        app.newProject();
        var comp = app.project.items.addComp("Shorts Toolkit Caption", 1080, 1920, 1, 30, 30);

        // ---- controls
        var ctl = comp.layers.addNull(30);
        ctl.name = "Controls";
        ctl.enabled = false;
        var fx = ctl.property("ADBE Effect Parade");
        function control(kind, name, value) {
            var e = fx.addProperty(kind);
            e.name = name;
            e.property(1).setValue(value);
            return e;
        }
        control("ADBE Color Control", "Text colour", hex(cfg.text || "FFFFFF"));
        control("ADBE Color Control", "Highlight colour", hex(cfg.highlight || "7B5CFF"));
        control("ADBE Color Control", "Text in box", hex(cfg.hl_text || "FFFFFF"));
        control("ADBE Color Control", "Outline colour", hex(cfg.outline_col || "000000"));
        control("ADBE Slider Control", "Outline", cfg.outline != null ? cfg.outline : 7);
        control("ADBE Slider Control", "Shadow", cfg.shadow != null ? cfg.shadow : 3);
        control("ADBE Slider Control", "Height from bottom %", 100 * (cfg.position || 560) / 1920);
        control("ADBE Checkbox Control", "Loud", 0);
        var hs = fx.addProperty("ADBE Dropdown Control");
        hs.property(1).setPropertyParameters(["Colour", "Colour + bigger", "Box", "Karaoke", "None"]);
        hs = fx.property(fx.numProperties);          // setPropertyParameters replaces the effect
        hs.name = "Highlight style";
        hs.property(1).setValue(cfg.hl_mode || 1);
        var an = fx.addProperty("ADBE Dropdown Control");
        an.property(1).setPropertyParameters(["Pop", "Bounce", "Fade", "None"]);
        an = fx.property(fx.numProperties);
        an.name = "Animation";
        an.property(1).setValue(cfg.anim || 1);
        // Premiere keeps a template's font locked, so the font is a dropdown read by the text's expression
        var fn = fx.addProperty("ADBE Dropdown Control");
        fn.property(1).setPropertyParameters(cfg.font_names);
        fn = fx.property(fx.numProperties);
        fn.name = "Font";
        fn.property(1).setValue(cfg.font_index || 1);
        control("ADBE Slider Control", "Size", (cfg.size || 76) / SIZE);
        log.push("controls ok");

        // ---- word times (a text layer, so Premiere can edit it as text)
        var times = comp.layers.addText("0 0.4 0.8 1.4");
        times.name = "Word times";
        times.enabled = false;

        // ---- the caption
        var cap = comp.layers.addText("So good right");
        cap.name = "Caption";
        var td = cap.property("ADBE Text Properties").property("ADBE Text Document");
        var doc = td.value;
        doc.font = cfg.font || "Arial-Black";
        doc.fontSize = cfg.size || 76;
        doc.applyFill = true;
        doc.fillColor = [1, 1, 1];
        doc.applyStroke = true;
        doc.strokeColor = [0, 0, 0];
        doc.strokeWidth = 7;
        doc.strokeOverFill = false;
        doc.justification = ParagraphJustification.CENTER_JUSTIFY;
        td.setValue(doc);
        // a function, not `var c = layer.effect`: a detached effect() looks on the layer running the expression
        var C = 'var K = thisComp.layer("Controls"); function c(n) { return K.effect(n); }\n';
        td.expression = C +
            'var F = ' + fontList() + ';\n' +
            'var s = text.sourceText.style.setFont(F[c("Font")(1).value - 1]).setFontSize(c("Size")(1).value * ' + SIZE + ')' +
            '.setFillColor(c("Text colour")(1).value.slice(0, 3)).setStrokeColor(c("Outline colour")(1).value.slice(0, 3))' +
            '.setStrokeWidth(c("Outline")(1).value);\n' +
            's.setText(c("Loud")(1).value == 1 ? value.toUpperCase() : value);';
        // which word is being said (0 = the first) - shared by the highlight, the bigger word and the box
        var WORD =
            'function wordNow() {\n' +
            '  var raw = thisComp.layer("Word times").text.sourceText.value.replace(/^\\s+|\\s+$/g, "");\n' +
            '  var tt = raw.length ? raw.split(/\\s+/).map(parseFloat) : [];\n' +
            '  var w = thisComp.layer("Caption").text.sourceText.value.split(/\\s+/).filter(function (x) { return x.length > 0; });\n' +
            '  var n = Math.max(1, w.length), t = time - thisComp.layer("Caption").inPoint, k = 0;\n' +
            '  if (tt.length == n + 1) { for (var i = 0; i < n; i++) if (t >= tt[i]) k = i; }\n' +
            '  else { var end = tt.length ? tt[tt.length - 1] : 1.5; k = Math.min(n - 1, Math.floor(t / Math.max(0.05, end / n))); }\n' +
            '  return k;\n' +
            '}\n';
        var MODE = 'var mode = thisComp.layer("Controls").effect("Highlight style")(1).value;\n';
        cap.property("ADBE Transform Group").property("ADBE Anchor Point").expression =
            'var r = sourceRectAtTime(time, false); [r.left + r.width / 2, r.top + r.height];';
        cap.property("ADBE Transform Group").property("ADBE Position").expression =
            C + '[thisComp.width / 2, thisComp.height - c("Height from bottom %")(1).value * thisComp.height / 100];';
        cap.property("ADBE Transform Group").property("ADBE Scale").expression = C +
            'var a = c("Animation")(1).value, base = c("Loud")(1).value == 1 ? 112 : 100, t = time - inPoint, k = 100;\n' +
            'if (a == 1) { var p = 0.17; k = t < p * 0.6 ? linear(t, 0, p * 0.6, 88, 104) : linear(t, p * 0.6, p, 104, 100); }\n' +
            'else if (a == 2) { var p = 0.238; k = t < p * 0.45 ? linear(t, 0, p * 0.45, 70, 116) : t < p * 0.75 ? linear(t, p * 0.45, p * 0.75, 116, 95) : linear(t, p * 0.75, p, 95, 100); }\n' +
            'var v = base * k / 100; [v, v];';
        cap.property("ADBE Transform Group").property("ADBE Opacity").expression = C +
            'var a = c("Animation")(1).value, f = a == 3 ? 0.14 : a == 4 ? 0 : 0.07, t = time - inPoint;\n' +
            'f > 0 ? linear(t, 0, f, 0, 100) : 100;';
        var sh = cap.property("ADBE Effect Parade").addProperty("ADBE Drop Shadow");
        sh.property("ADBE Drop Shadow-0002").setValue(128);          // opacity 50 %
        sh.property("ADBE Drop Shadow-0004").expression = C + 'c("Shadow")(1).value;';      // distance
        sh.property("ADBE Drop Shadow-0005").expression = C + 'c("Shadow")(1).value * 0.6;'; // softness

        // highlight: colour of the spoken word (karaoke: every word said so far)
        var anims = cap.property("ADBE Text Properties").property("ADBE Text Animators");
        function animator(name, propKind, valueExpr, startExpr, endExpr) {
            var a = anims.addProperty("ADBE Text Animator");
            a.name = name;
            var p = a.property("ADBE Text Animator Properties").addProperty(propKind);
            p.expression = valueExpr;
            var sel = a.property("ADBE Text Selectors").addProperty("ADBE Text Selector");
            var adv = sel.property("ADBE Text Range Advanced");
            adv.property("ADBE Text Range Units").setValue(2);      // index
            adv.property("ADBE Text Range Type2").setValue(3);      // based on words
            sel.property("ADBE Text Index Start").expression = WORD + MODE + startExpr;
            sel.property("ADBE Text Index End").expression = WORD + MODE + endExpr;
            return a;
        }
        animator("Highlight", "ADBE Text Fill Color",
                 C + 'var m = c("Highlight style")(1).value; m == 3 ? c("Text in box")(1).value : c("Highlight colour")(1).value;',
                 'mode == 4 ? 0 : mode == 5 ? 0 : wordNow();',
                 'mode == 5 ? 0 : wordNow() + 1;');
        var big = animator("Bigger", "ADBE Text Scale 3D", '[118, 118, 100];',
                           'mode == 2 ? wordNow() : 0;', 'mode == 2 ? wordNow() + 1 : 0;');
        log.push("caption ok");

        // ---- the box behind the spoken word: two hidden copies of the caption measure where it is
        function measure(name, textExpr) {
            var m = comp.layers.addText("x");
            m.name = name;
            m.enabled = false;
            m.property("ADBE Text Properties").property("ADBE Text Document").expression =
                WORD + 'var w = thisComp.layer("Caption").text.sourceText.value.split(/\\s+/).filter(function (x) { return x.length > 0; });\n' +
                'var k = wordNow();\n' + 'thisComp.layer("Caption").text.sourceText.style.setText(' + textExpr + ');';
            return m;
        }
        measure("Measure word", 'w[k] || ""');
        measure("Measure upto", 'w.slice(0, k + 1).join(" ")');
        var box = comp.layers.addShape();
        box.name = "Box";
        var grp = box.property("ADBE Root Vectors Group").addProperty("ADBE Vector Group");
        var shp = grp.property("ADBE Vectors Group");
        shp.addProperty("ADBE Vector Shape - Rect");
        shp.addProperty("ADBE Vector Graphic - Fill");
        var rect = shp.property("ADBE Vector Shape - Rect");      // adding a property invalidates the earlier handles
        var fill = shp.property("ADBE Vector Graphic - Fill");
        var GEO = C + 'var L = thisComp.layer("Caption"), r = L.sourceRectAtTime(time, false);\n' +
            'var wu = thisComp.layer("Measure upto").sourceRectAtTime(time, false), ww = thisComp.layer("Measure word").sourceRectAtTime(time, false);\n' +
            'var x0 = r.left + wu.width - ww.width, x1 = r.left + wu.width;\n' +
            'var a = L.toComp([x0, r.top]), b = L.toComp([x1, r.top + r.height]);\n' +
            'var pad = r.height * 0.16 * (L.transform.scale[0] / 100);\n';
        rect.property("ADBE Vector Rect Size").expression = GEO + '[b[0] - a[0] + 2 * pad, b[1] - a[1] + pad];';
        rect.property("ADBE Vector Rect Position").expression = GEO + '[(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];';
        rect.property("ADBE Vector Rect Roundness").expression = 'thisComp.layer("Caption").sourceRectAtTime(time, false).height * 0.14;';
        fill.property("ADBE Vector Fill Color").expression = C + 'c("Highlight colour")(1).value;';
        box.property("ADBE Transform Group").property("ADBE Anchor Point").setValue([0, 0]);
        box.property("ADBE Transform Group").property("ADBE Position").setValue([0, 0]);
        box.property("ADBE Transform Group").property("ADBE Opacity").expression = C +
            'c("Highlight style")(1).value == 3 ? thisComp.layer("Caption").transform.opacity : 0;';
        box.moveAfter(cap);                         // behind the caption
        log.push("box ok");

        // ---- Essential Graphics
        comp.motionGraphicsTemplateName = "Shorts Toolkit Caption";
        function expose(prop, name) {
            if (!prop.canAddToMotionGraphicsTemplate(comp)) throw new Error("can't expose " + name);
            prop.addToMotionGraphicsTemplateAs(comp, name);
        }
        expose(td, "Caption");
        expose(times.property("ADBE Text Properties").property("ADBE Text Document"), "Word times");
        expose(fx.property("Font").property(1), "Font");
        expose(fx.property("Size").property(1), "Size");
        expose(fx.property("Highlight style").property(1), "Highlight style");
        expose(fx.property("Animation").property(1), "Animation");
        expose(fx.property("Text colour").property(1), "Text colour");
        expose(fx.property("Highlight colour").property(1), "Highlight colour");
        expose(fx.property("Text in box").property(1), "Text in box");
        expose(fx.property("Outline colour").property(1), "Outline colour");
        expose(fx.property("Outline").property(1), "Outline");
        expose(fx.property("Shadow").property(1), "Shadow");
        expose(fx.property("Height from bottom %").property(1), "Height from bottom %");
        expose(fx.property("Loud").property(1), "Loud");
        log.push("exposed ok");

        if (cfg.aep) app.project.save(File(cfg.aep));
        var ok = comp.exportAsMotionGraphicsTemplate(true, cfg.out);
        log.push("export returned " + ok);
        done(ok && File(cfg.out).exists, cfg.out);
    } catch (e) {
        done(false, e.toString() + " (line " + e.line + ")");
    }
    app.endSuppressDialogs(false);
    if (cfg.quit) { app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES); app.quit(); }

    function hex(h) {
        return [parseInt(h.substr(0, 2), 16) / 255, parseInt(h.substr(2, 2), 16) / 255, parseInt(h.substr(4, 2), 16) / 255];
    }
})();
