import copy
import unittest

import mouth_track as M
from pipeline import attach_mouth_track, normalize_packet, show_bank_response, validate_packet

AVAILABLE = M.mouth_available()
SKIP_REASON = f"mouth_poses.py not found (set {M.MOUTH_DIR_ENV})"


def frame_at(track, t):
    return round((t - track["start_s"]) * track["rate_hz"])


def mid(event):
    return (event.start + event.end) / 2 - M.LEAD_S


class TextToVisemeTests(unittest.TestCase):
    def test_words_map_to_preston_blair_groups(self):
        self.assertEqual(["MBP", "U", "MBP", "E", "etc"], M.word_visemes("puppet"))
        self.assertEqual(["L", "E"], M.word_visemes("the"))
        self.assertEqual(["etc", "O", "etc"], M.word_visemes("nose"))   # silent final e
        self.assertEqual(["FV", "etc", "E", "etc"], M.word_visemes("friend"))

    def test_punctuation_adds_rest_and_voice_tags_are_not_spoken(self):
        events = M.text_to_visemes("[gasp] Oh, no.")
        self.assertEqual(["O", "rest", "etc", "O"], [e.viseme for e in events])
        self.assertAlmostEqual(M.PAUSE_S[","], events[1].end - events[1].start)

    def test_events_are_contiguous_and_fill_a_known_duration(self):
        events = M.text_to_visemes("Hello there, friend! I made a puppet.", duration_s=2.4)
        self.assertAlmostEqual(0.0, events[0].start)
        self.assertAlmostEqual(2.4, events[-1].end, places=6)
        for a, b in zip(events, events[1:]):
            self.assertAlmostEqual(a.end, b.start)
            self.assertNotEqual(a.viseme, b.viseme)

    def test_numbers_are_spoken(self):
        self.assertTrue(M.text_to_visemes("42"))

    def test_phoneme_timings_map_to_visemes(self):
        events = M.phonemes_to_visemes([("M", 0.0, 0.1), ("AA1", 0.1, 0.3), ("P", 0.3, 0.38), ("SIL", 0.38, 0.5)])
        self.assertEqual(["MBP", "AI", "MBP", "rest"], [e.viseme for e in events])
        self.assertEqual(0.3, events[1].end)

    def test_expression_parsing(self):
        self.assertEqual(("frown", 0.5), M.parse_expression("frown:0.5"))
        self.assertEqual(("smile", 1.0), M.parse_expression("smile:3"))
        self.assertIsNone(M.parse_expression(None))
        with self.assertRaises(ValueError):
            M.parse_expression("wink")


@unittest.skipUnless(AVAILABLE, SKIP_REASON)
class MouthTrackTests(unittest.TestCase):
    LINE = "Hello there, friend! I made a puppet... [chuckle]"

    def test_track_has_seven_channels_within_limits(self):
        track = M.mouth_track_from_text(self.LINE)
        self.assertEqual(list(M.MOUTH_CHANNELS), track["channels"])
        self.assertEqual((True, "ok"), M.validate_mouth_track(track))
        self.assertEqual(1, len({len(v) for v in track["tracks"].values()}))
        self.assertLess(track["start_s"], 0.0)   # the mouth leads the audio

    def test_track_starts_and_ends_at_rest(self):
        track = M.mouth_track_from_text(self.LINE, expression="big_smile")
        for channel, values in track["tracks"].items():
            with self.subTest(channel=channel):
                self.assertAlmostEqual(0.0, values[0], places=6)
                self.assertLess(abs(values[-1]), 0.3)

    def test_rates_respect_limits(self):
        for expression in (None, "surprise:1", "frown:1", "sneer_left:1"):
            track = M.mouth_track_from_text("Wow, a whale! Bob picked a map, mama.", expression=expression)
            rates = track["peak_rate_deg_s"]
            with self.subTest(expression=expression):
                self.assertLessEqual(rates["JAW_OPEN_DEG"], M.JAW_SLEW_DEG_S + 1.0)
                for channel in M.MOUTH_CHANNELS[1:]:
                    self.assertLessEqual(rates[channel], M.SERVO_SLEW_DEG_S + 1.0, channel)

    def test_open_vowel_opens_jaw_and_mbp_closes_it(self):
        events = M.text_to_visemes("ah ma", duration_s=1.2)
        track = M.build_mouth_track(events)
        jaw = track["tracks"]["JAW_OPEN_DEG"]
        vowel = next(e for e in events if e.viseme == "AI")
        closure = next(e for e in events if e.viseme == "MBP")
        self.assertGreater(jaw[frame_at(track, mid(vowel))], 10.0)
        self.assertLess(jaw[frame_at(track, mid(closure))], 3.0)
        # lips pressed: the lower lip moves the way the MBP pose moves it
        mbp = M.mouth_poses().servo_angles(M.mouth_poses().POSES["MBP"])["LOWER_LIP"]
        lower = track["tracks"]["LOWER_LIP"][frame_at(track, mid(closure))]
        self.assertGreater(lower * mbp, 0.0)

    def test_smile_and_frown_move_corners_oppositely_and_symmetrically(self):
        events = M.text_to_visemes("Hello there", duration_s=1.5)
        smile = M.build_mouth_track(events, ("smile", 1.0))
        frown = M.build_mouth_track(events, ("frown", 1.0))
        poses = M.mouth_poses()
        i = frame_at(smile, 0.75)
        for channel in ("CORNER_L_A", "CORNER_L_B"):
            expected = poses.servo_angles(poses.POSES["smile"])[channel]
            self.assertGreater(smile["tracks"][channel][i] * expected, 0.0, channel)
            self.assertLess(smile["tracks"][channel][i] * frown["tracks"][channel][i], 0.0, channel)
            right = channel.replace("_L_", "_R_")
            self.assertAlmostEqual(-smile["tracks"][channel][i], smile["tracks"][right][i], places=6)

    def test_surprise_opens_the_jaw_further(self):
        events = M.text_to_visemes("Look at that", duration_s=1.2)
        plain = M.build_mouth_track(events)
        surprised = M.build_mouth_track(events, ("surprise", 1.0))
        self.assertGreater(max(surprised["tracks"]["JAW_OPEN_DEG"]), max(plain["tracks"]["JAW_OPEN_DEG"]) + 1.0)

    def test_held_expression_does_not_return_to_neutral(self):
        track = M.mouth_track_from_text("Thank you", expression="smile:1", hold_expression=True)
        last = M.mouth_poses().servo_angles(M.mouth_poses().POSES["smile"])["CORNER_L_A"]
        self.assertGreater(track["tracks"]["CORNER_L_A"][-1] * last, 0.0)
        self.assertGreater(abs(track["tracks"]["CORNER_L_A"][-1]), 0.5 * abs(last) * M.EXPRESSION_GAIN[M.CLX])

    def test_expression_only_line(self):
        track = M.mouth_track_from_text("[laugh]")
        self.assertEqual("big_smile", track["expression"]["name"])
        self.assertEqual([], track["visemes"])
        self.assertEqual((True, "ok"), M.validate_mouth_track(track))
        self.assertGreater(max(track["tracks"]["CORNER_L_A"], key=abs) ** 2, 1.0)

    def test_legacy_jaw_positions(self):
        track = M.mouth_track_from_text("Ah, wonderful!")
        positions = M.legacy_jaw_positions(track)
        self.assertEqual(len(track["tracks"]["JAW_OPEN_DEG"]), len(positions))
        self.assertTrue(all(0.0 <= p <= 1.0 for p in positions))
        self.assertGreater(max(positions), 0.2)

    def test_validate_rejects_bad_tracks(self):
        track = M.mouth_track_from_text("Hi")
        bad = copy.deepcopy(track)
        bad["tracks"]["UPPER_LIP"][3] = 75.0
        self.assertFalse(M.validate_mouth_track(bad)[0])
        bad = copy.deepcopy(track)
        bad["tracks"]["JAW_OPEN_DEG"].pop()
        self.assertFalse(M.validate_mouth_track(bad)[0])
        bad = copy.deepcopy(track)
        del bad["tracks"]["LOWER_LIP"]
        self.assertFalse(M.validate_mouth_track(bad)[0])


@unittest.skipUnless(AVAILABLE, SKIP_REASON)
class PipelineMouthTests(unittest.TestCase):
    def test_packet_gets_mouth_track_and_keeps_legacy_jaw(self):
        packet = attach_mouth_track(show_bank_response("What did you build today?", 1))
        self.assertEqual((True, "ok"), validate_packet(packet))
        self.assertIn("jaw", {command["axis"] for command in packet["motion"]})
        self.assertEqual(list(M.MOUTH_CHANNELS), packet["mouth_track"]["channels"])

    def test_expression_follows_voice_tag_then_truth_tag_then_override(self):
        base = {"emotion_intensity": 0.5, "source_id": "t", "motion": [], "next_state": "IDLE"}
        gasp = normalize_packet({**base, "spoken_text": "[gasp] A whale!", "truth_tag": "TRUTH"})
        lie = normalize_packet({**base, "spoken_text": "I never lie.", "truth_tag": "LIE"})
        self.assertEqual("surprise", attach_mouth_track(gasp)["mouth_track"]["expression"]["name"])
        self.assertEqual("sneer_left", attach_mouth_track(lie)["mouth_track"]["expression"]["name"])
        self.assertEqual("frown", attach_mouth_track(lie, "frown")["mouth_track"]["expression"]["name"])

    def test_validate_packet_rejects_a_bad_mouth_track(self):
        packet = attach_mouth_track(show_bank_response("Hello!", 1))
        packet["mouth_track"]["tracks"]["CORNER_L_B"][0] = -90.0
        self.assertFalse(validate_packet(packet)[0])

    def test_packets_without_mouth_track_are_unchanged(self):
        packet = show_bank_response("Hello!", 1)
        self.assertNotIn("mouth_track", packet)
        self.assertEqual((True, "ok"), validate_packet(packet))


if __name__ == "__main__":
    unittest.main()
