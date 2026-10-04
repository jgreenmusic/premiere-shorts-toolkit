"""Tests for the caption logic that has broken before. No media, no Premiere, no models.

    .venv\\Scripts\\python.exe tests\\test_logic.py

Words are Whisper's [start, end, word, confidence]. Captions are prproj.Caption.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import captions
from prproj import Caption, TICKS


def cap(index, start, end, text):
    return Caption(index, int(round(start * TICKS)), int(round(end * TICKS)), text)


def texts(words):
    return [w[2] for w in words]


class Punctuation(unittest.TestCase):
    def test_norm(self):
        self.assertEqual(captions.norm("Don’t!"), "don't")
        self.assertEqual(captions.norm("..."), "")

    def test_keep_changes_nothing(self):
        self.assertEqual(captions.strip_punct("what?!", "keep"), "what?!")

    def test_soft_drops_commas_and_stops_only(self):
        self.assertEqual(captions.strip_punct("wait,", "soft"), "wait")
        self.assertEqual(captions.strip_punct("Wait...", "soft"), "Wait")
        self.assertEqual(captions.strip_punct("what?!", "soft"), "what?!")
        self.assertEqual(captions.strip_punct("2.5", "soft"), "2.5")
        self.assertEqual(captions.strip_punct("2.5.", "soft"), "2.5")

    def test_all_keeps_apostrophes_and_inner_hyphens(self):
        self.assertEqual(captions.strip_punct("what?!", "all"), "what")
        self.assertEqual(captions.strip_punct("don't", "all"), "don't")
        self.assertEqual(captions.strip_punct("co-op", "all"), "co-op")
        self.assertEqual(captions.strip_punct("no—way", "all"), "no way")
        self.assertEqual(captions.strip_punct_text("Wait... what? -", "all"), "Wait what")


class WhisperLoops(unittest.TestCase):
    def test_stacked_low_confidence_repeats_are_dropped(self):
        words = [[0.0, 0.5, "Help", 0.9], [0.5, 0.9, "me!", 0.9], [0.9, 1.3, "now", 0.9]]
        for _ in range(5):
            words += [[2.0, 2.0, "Help", 0.3], [2.0, 2.0, "me!", 0.3], [2.0, 2.0, "now", 0.3]]
        self.assertEqual(texts(captions.clean_loops(words)), ["Help", "me!", "now"])

    @unittest.expectedFailure
    def test_two_word_loop_known_limitation(self):
        # KNOWN LIMITATION (2026-10-04): a looped TWO-word phrase is matched as a four-word
        # phrase ("help me help me"), so the first group is one good pair plus one bad pair
        # and the bad pair gets through. Judging each pair on its own fixes this case, but on
        # the real transcripts it changed which repeats survive in both directions and
        # orphaned two saved caption edits (they are keyed by start time). Do not change
        # clean_loops without first re-keying saved edits. See ROADMAP.md.
        words = [[0.0, 0.5, "Help", 0.9], [0.5, 0.9, "me!", 0.9]]
        for _ in range(5):
            words += [[1.0, 1.0, "Help", 0.3], [1.0, 1.0, "me!", 0.3]]
        self.assertEqual(texts(captions.clean_loops(words)), ["Help", "me!"])

    def test_real_repeats_stay(self):
        words = [[0.0, 0.3, "wait,", 0.95], [0.4, 0.7, "wait,", 0.95], [0.8, 1.1, "wait", 0.95], [1.2, 1.5, "what", 0.9]]
        self.assertEqual(len(captions.clean_loops(words)), 4)

    def test_one_repeat_always_survives(self):
        words = []
        for k in range(4):
            words += [[k, k + 0.2, "We", 0.2], [k + 0.2, k + 0.4, "got", 0.2], [k + 0.4, k + 0.6, "it.", 0.2]]
        self.assertEqual(texts(captions.clean_loops(words)), ["We", "got", "it."])

    def test_repeats_with_no_voice_under_them_are_dropped(self):
        words = [[1.0, 1.3, "go", 0.7], [2.0, 2.3, "go", 0.7], [3.0, 3.3, "go", 0.7]]
        self.assertEqual(captions.clean_loops(words, regions=[[0.9, 1.4]]), [words[0]])
        # very confident words are kept even where the voice detector heard nothing
        sure = [[w[0], w[1], w[2], 0.95] for w in words]
        self.assertEqual(len(captions.clean_loops(sure, regions=[[0.9, 1.4]])), 3)

    def test_a_retyped_caption_keeps_its_word(self):
        words = [[1.0, 1.3, "go", 0.7], [2.0, 2.3, "go", 0.7], [3.0, 3.3, "go", 0.7]]
        kept = captions.clean_loops(words, regions=[[0.9, 1.4]], keep=["2.00"])
        self.assertEqual([w[0] for w in kept], [1.0, 2.0])

    def test_empty(self):
        self.assertEqual(captions.clean_loops([]), [])


class Edits(unittest.TestCase):
    def setUp(self):
        self.c = cap(0, 1.0, 2.0, "hello")
        self.m = dict(words=[(0, 1.0, 1.4)], ratio=1.0)

    def test_no_edit(self):
        self.assertEqual(captions.edited(self.c, self.m, {}), (self.c, self.m))
        self.assertEqual(captions.caption_key(self.c), "1.00")

    def test_hide(self):
        self.assertIsNone(captions.edited(self.c, self.m, {"1.00": {"hide": True}}))

    def test_new_text_loses_word_times(self):
        c, m = captions.edited(self.c, self.m, {"1.00": {"text": " hi there "}})
        self.assertEqual((c.text, m["words"]), ("hi there", []))
        self.assertEqual(self.c.text, "hello")                    # the original is not changed

    def test_same_text_keeps_word_times(self):
        c, m = captions.edited(self.c, self.m, {"1.00": {"text": "hello"}})
        self.assertEqual(m["words"], [(0, 1.0, 1.4)])

    def test_timing(self):
        c, _ = captions.edited(self.c, self.m, {"1.00": {"end": 2.5}})
        self.assertAlmostEqual(c.start_s, 1.0)
        self.assertAlmostEqual(c.end_s, 2.5)
        c, _ = captions.edited(self.c, self.m, {"1.00": {"start": 3.0}})     # would end before it starts
        self.assertAlmostEqual(c.start_s, 1.0)

    def test_retyped_lists_only_text_edits(self):
        cfg = {"caption_edits": {"1.00": {"text": "x"}, "2.00": {"hide": True}, "3.00": None}}
        self.assertEqual(captions.retyped(cfg), ["1.00"])

    def test_added_captions(self):
        cfg = {"caption_adds": [{"start": 5, "end": 6, "text": " new "}, {"start": 7, "end": 7, "text": "bad"},
                                {"start": 8, "end": 9, "text": " "}]}
        out = captions.added_captions(cfg, 100)
        self.assertEqual([(c.index, c.text, c.start_s) for c, _ in out], [(100, "new", 5.0)])


class MissingWords(unittest.TestCase):
    def setUp(self):
        self.caps = [cap(0, 1.0, 2.0, "hello")]
        self.words = [[1.2, 1.5, "hello", 0.9], [5.0, 5.3, "over", 0.9], [5.35, 5.6, "here.", 0.9], [9.0, 9.3, "what", 0.9]]

    def test_finds_uncaptioned_speech(self):
        out = captions.missing_words(self.caps, self.words, {})
        self.assertEqual(out, [dict(start=5.0, end=5.6, text="over here."), dict(start=9.0, end=9.4, text="what")])

    def test_dismissed_lines_stay_gone(self):
        out = captions.missing_words(self.caps, self.words, {"caption_dismissed": [5.0]})
        self.assertEqual([o["text"] for o in out], ["what"])

    def test_added_captions_count_as_covered(self):
        out = captions.missing_words(self.caps, self.words, {"caption_adds": [{"start": 4.9, "end": 5.7, "text": "over here"}]})
        self.assertEqual([o["text"] for o in out], ["what"])

    def test_one_word_touching_a_caption_is_not_a_missed_line(self):
        out = captions.missing_words(self.caps, [[2.3, 2.5, "yeah", 0.9]], {})
        self.assertEqual(out, [])

    def test_window(self):
        out = captions.missing_words(self.caps, self.words, {}, start=8.0, end=10.0)
        self.assertEqual([o["text"] for o in out], ["what"])


class HeardFixes(unittest.TestCase):
    def rows(self, text):
        return [dict(key="1.00", s=1.0, e=2.0, text=text, hidden=False)]

    def heard(self, *ws):
        return [[1.0 + 0.2 * i, 1.2 + 0.2 * i, w, 0.9] for i, w in enumerate(ws)]

    def test_suggests_a_different_word(self):
        out = captions.heard_fixes(self.rows("look at the fizz"), self.heard("look", "at", "the", "physics"), [(0, 5)])
        self.assertEqual(out, {"1.00": "look at the physics"})

    def test_same_text_gives_nothing(self):
        self.assertEqual(captions.heard_fixes(self.rows("Look at the physics."), self.heard("look", "at", "the", "physics"), [(0, 5)]), {})

    def test_spelling_variants_give_nothing(self):
        self.assertEqual(captions.heard_fixes(self.rows("that's fuckin crazy"), self.heard("that's", "fucking", "crazy"), [(0, 5)]), {})

    def test_a_model_missing_a_word_is_not_a_fix(self):
        self.assertEqual(captions.heard_fixes(self.rows("look at the physics"), self.heard("look", "physics"), [(0, 5)]), {})

    def test_skip_and_hidden_and_outside(self):
        heard = self.heard("look", "at", "the", "physics")
        self.assertEqual(captions.heard_fixes(self.rows("look at the fizz"), heard, [(0, 5)], skip=["1.00"]), {})
        hidden = [dict(self.rows("look at the fizz")[0], hidden=True)]
        self.assertEqual(captions.heard_fixes(hidden, heard, [(0, 5)]), {})
        self.assertEqual(captions.heard_fixes(self.rows("look at the fizz"), heard, [(10, 15)]), {})


class AutoCaptions(unittest.TestCase):
    def test_short_chunks(self):
        words = [[0.0, 0.2, "Oh", 0.9], [0.25, 0.4, "my", 0.9], [0.45, 0.8, "god.", 0.9], [2.0, 2.3, "Look", 0.9],
                 [2.35, 2.6, "at", 0.9], [2.65, 2.9, "that", 0.9], [2.95, 3.3, "thing", 0.9]]
        caps, matches = captions.auto_captions(words)
        self.assertEqual([c.text for c in caps], ["Oh my god.", "Look at that", "thing"])
        self.assertAlmostEqual(caps[0].end_s, 0.92, places=2)       # 0.12 s after the last word
        self.assertAlmostEqual(caps[1].end_s, 2.95, places=2)       # never past the next caption's start
        self.assertEqual(len(matches), 3)
        for c, nxt in zip(caps, caps[1:]):
            self.assertLessEqual(c.end_s, nxt.start_s + 1e-6)

    def test_a_pause_starts_a_new_caption(self):
        caps, _ = captions.auto_captions([[0.0, 0.2, "wait", 0.9], [1.0, 1.2, "what", 0.9]])
        self.assertEqual([c.text for c in caps], ["wait", "what"])


class FittedTiming(unittest.TestCase):
    """Premiere captions get their timing fitted to the speech in renders (0.27.0)."""

    def test_fitted_times_replace_the_captions_own(self):
        c = captions.fitted(cap(0, 1.0, 1.2, "hello"), (int(1.0 * TICKS), int(1.8 * TICKS)))
        self.assertAlmostEqual(c.end_s, 1.8)

    def test_nothing_fitted_changes_nothing(self):
        c = cap(0, 1.0, 1.2, "hello")
        self.assertIs(captions.fitted(c, None), c)

    def test_an_edge_you_set_yourself_wins(self):
        mine = cap(0, 1.1, 2.5, "hello")                       # as returned by captions.edited: your start and end
        fit = (int(1.0 * TICKS), int(1.8 * TICKS))
        self.assertAlmostEqual(captions.fitted(mine, fit, {"end": 2.5}).end_s, 2.5)
        self.assertAlmostEqual(captions.fitted(mine, fit, {"end": 2.5}).start_s, 1.0)
        self.assertAlmostEqual(captions.fitted(mine, fit, {"start": 1.1}).start_s, 1.1)

    def test_a_short_caption_with_room_is_held_for_its_voice(self):
        import shorts
        from types import SimpleNamespace
        frame = TICKS // 30
        caps = [cap(0, 1.0, 1.2, "hello there"), cap(1, 5.0, 5.6, "bye")]
        words = [[1.0, 1.3, "hello", 0.9], [1.3, 1.9, "there", 0.9], [5.0, 5.4, "bye", 0.9]]
        regions = [[0.95, 2.0], [4.95, 5.5]]
        seq = SimpleNamespace(captions=caps, caption_frame=frame)
        new = shorts.fitted_times(seq, captions.align(caps, words), regions, words)
        self.assertIn(0, new)
        self.assertEqual(new[0][0], caps[0].start)                   # it started on time: the start stays
        self.assertGreater(new[0][1] / TICKS, 1.9)                   # held until the voice stops
        self.assertLess(new[0][1] / TICKS, 5.0)                      # never into the next caption


class SpeechBeforeLaughs(unittest.TestCase):
    def test_a_laugh_waits_until_the_caption_can_be_read(self):
        import style
        events = [(10.0, 12.3, "Main", "You are a dingus"), (10.17, 10.4, "Laugh", "HA"), (10.4, 10.7, "Laugh", "HAHA"),
                  (10.7, 11.5, "Laugh", "HAHAHA")]
        out = style.hold_for_speech(events, [(10.0, 10.0 + style.readable("You are a dingus"))])
        self.assertEqual([e[3] for e in out], ["You are a dingus", "HAHAHA"])     # cues that would be over are dropped
        self.assertAlmostEqual(out[1][0], 10.8)

    def test_laughs_elsewhere_are_untouched(self):
        import style
        events = [(10.0, 11.0, "Main", "hello"), (12.0, 12.5, "Laugh", "HA")]
        self.assertEqual(style.hold_for_speech(events, [(10.0, 10.5)]), events)

    def test_readable_time(self):
        import style
        self.assertEqual(style.readable("Oh"), 0.5)
        self.assertEqual(style.readable("x" * 100), 1.5)


if __name__ == "__main__":
    unittest.main(verbosity=1)
