import unittest

from pipeline import (
    RECENT_SPOKEN_LINES,
    choose_show_tag,
    complete_show_line,
    remember_spoken_line,
    show_bank_response,
    validate_packet,
    vary_repeated_line,
)


class ShowBankRoutingTests(unittest.TestCase):
    def test_build_question_uses_workshop_response(self):
        packet = show_bank_response("What did you build today?", 1)

        self.assertIsNotNone(packet)
        self.assertEqual("show_bank_workshop", packet["source_id"])

    def test_make_question_uses_workshop_response(self):
        packet = show_bank_response("What did you make today?", 1)

        self.assertIsNotNone(packet)
        self.assertEqual("show_bank_workshop", packet["source_id"])

    def test_mistake_question_uses_grounded_show_response(self):
        packet = show_bank_response("What is the biggest mistake you have ever made?", 1)

        self.assertEqual("show_bank_mistake", packet["source_id"])

    def test_what_makes_you_real_uses_grounded_show_response(self):
        packet = show_bank_response("Explain what makes you real.", 1)

        self.assertEqual("show_bank_real", packet["source_id"])

    def test_afraid_question_uses_fear_response_instead_of_identity(self):
        packet = show_bank_response("What are you afraid of?", 1)

        self.assertEqual("show_bank_fear", packet["source_id"])

    def test_visitors_build_question_is_left_for_the_model(self):
        packet = show_bank_response("How do I build an animatronic?", 1)

        self.assertIsNone(packet)

    def test_spoken_arithmetic_is_answered_exactly(self):
        packet = show_bank_response("What is seven times six?", 1)

        self.assertEqual("show_bank_math", packet["source_id"])
        self.assertIn("42", packet["spoken_text"])

    def test_question_about_lies_does_not_request_a_lie(self):
        self.assertEqual("TRUTH", choose_show_tag("What happens when you tell a lie?"))
        self.assertEqual("LIE", choose_show_tag("Tell me a lie."))

    def test_core_show_questions_use_grounded_responses(self):
        cases = {
            "What is the biggest mistake you have ever made?": "show_bank_mistake",
            "What makes you a real boy?": "show_bank_real",
            "Can you keep a secret?": "show_bank_secret",
            "What are you afraid of?": "show_bank_fear",
            "What is your favorite tool in the workshop?": "show_bank_tool",
            "What happens when you tell a lie?": "show_bank_nose",
            "Tell me something amazing about yourself.": "show_bank_amazing",
            "What does it mean to think on your feet?": "show_bank_idiom",
            "Do you always listen to Geppetto?": "show_bank_geppetto",
        }

        for question, source_id in cases.items():
            with self.subTest(question=question):
                packet = show_bank_response(question, 1)
                self.assertEqual(source_id, packet["source_id"])
                self.assertEqual((True, "ok"), validate_packet(packet))

    def test_scripted_responses_rotate_without_breaking_the_contract(self):
        packets = [show_bank_response("Hello!", turn) for turn in range(1, 4)]

        self.assertEqual(3, len({packet["spoken_text"] for packet in packets}))
        self.assertIn("explore today", packets[1]["spoken_text"])
        self.assertIn("would arrive", packets[2]["spoken_text"])
        for packet in packets:
            self.assertEqual((True, "ok"), validate_packet(packet))

    def test_recent_response_memory_is_bounded(self):
        RECENT_SPOKEN_LINES.clear()

        for turn in range(1, 7):
            remember_spoken_line({"spoken_text": f"Unique reply {turn}."})

        self.assertEqual(4, len(RECENT_SPOKEN_LINES))
        self.assertEqual("Unique reply 3.", RECENT_SPOKEN_LINES[0])

    def test_ellipsis_is_kept_as_an_internal_pause(self):
        self.assertEqual(
            "Well... I have an idea.",
            complete_show_line("Well... I have an idea."),
        )

    def test_two_short_complete_sentences_are_kept(self):
        self.assertEqual(
            "Start with one motion. Test it before adding another.",
            complete_show_line("Start with one motion. Test it before adding another."),
        )

    def test_repeated_model_line_gets_a_fresh_opening(self):
        varied = vary_repeated_line("I like quiet moments.", "TRUTH", 1)

        self.assertEqual("Hmm... I like quiet moments.", varied)


if __name__ == "__main__":
    unittest.main()
