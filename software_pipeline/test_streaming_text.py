import unittest

from streaming_text import ClausePlanner, SpokenTextExtractor


def plan(planner: ClausePlanner, text: str, budgets: list[int | None] | None = None, step: int = 3) -> list[str]:
    """Stream text in a few characters at a time, taking chunks as the voice would.

    budgets gives the character budget for each later chunk (None = unlimited).
    """
    budgets = list(budgets or [])
    chunks: list[str] = []

    def take() -> None:
        while True:
            budget = None if not chunks else (budgets.pop(0) if budgets else None)
            chunk = planner.next_chunk(budget)
            if chunk is None:
                if chunks and budget is not None:
                    budgets.insert(0, budget)
                return
            chunks.append(chunk)

    for start in range(0, len(text), step):
        planner.push(text[start:start + step])
        take()
    planner.finish()
    take()
    return chunks


class SpokenTextExtractorTests(unittest.TestCase):
    def feed_all(self, fragments: list[str]) -> str:
        extractor = SpokenTextExtractor()
        return "".join(extractor.feed(fragment) for fragment in fragments)

    def test_extracts_text_split_across_fragments(self):
        fragments = ['{"spo', 'ken_text"', ' : "Hel', "lo the", 're!"}']

        self.assertEqual("Hello there!", self.feed_all(fragments))

    def test_decodes_escapes_split_across_fragments(self):
        fragments = ['{"spoken_text": "He said \\', '"hi\\"', ' \\u00', '41."}']

        self.assertEqual('He said "hi" A.', self.feed_all(fragments))

    def test_stops_at_closing_quote(self):
        extractor = SpokenTextExtractor()

        text = extractor.feed('{"spoken_text": "Done." , "extra": "ignored"}')

        self.assertEqual("Done.", text)
        self.assertTrue(extractor.done)


class FirstChunkTests(unittest.TestCase):
    def test_leaves_at_first_comma(self):
        chunks = plan(ClausePlanner(), "Well, a clock keeps time with a pendulum and patient little gears.")

        self.assertEqual("Well, a clock keeps time with a pendulum and patient little gears.", " ".join(chunks))
        self.assertTrue(chunks[0].startswith("Well,"))
        self.assertLessEqual(len(chunks[0].split()), 6)

    def test_single_word_before_comma_waits_for_more(self):
        chunks = plan(ClausePlanner(), "Oh, a visitor! Come closer, I don't bite.")

        self.assertEqual("Oh, a visitor!", chunks[0])

    def test_cut_by_word_count_without_punctuation(self):
        chunks = plan(ClausePlanner(first_chunk_words=4), "Geppetto carved me from a single log of pine.")

        self.assertEqual(["Geppetto carved me from", "a single log of pine."], chunks)

    def test_word_count_cut_never_leaves_a_lone_word(self):
        chunks = plan(ClausePlanner(first_chunk_words=4), "We carve pine and oak today.")

        self.assertEqual(["We carve pine and oak today."], chunks)

    def test_ellipsis_is_a_pause_not_a_sentence_end(self):
        chunks = plan(ClausePlanner(), "Hmm... I think the answer is seven.")

        self.assertEqual(["Hmm... I think the answer is seven."], chunks)

    def test_decimal_is_not_split(self):
        chunks = plan(ClausePlanner(first_chunk_words=0), "It weighs 3.5 pounds today.")

        self.assertEqual(["It weighs 3.5 pounds today."], chunks)


class LaterChunkTests(unittest.TestCase):
    LINE = "Cats purr because it helps them, and it is also a way for them to say they feel safe."

    def test_unlimited_budget_takes_the_rest_in_one_chunk(self):
        chunks = plan(ClausePlanner(), self.LINE)

        self.assertEqual(["Cats purr because it helps them,", "and it is also a way for them to say they feel safe."], chunks)

    def test_tight_budget_splits_at_the_last_break_that_fits(self):
        line = "Hello there, friend! I build clocks, boats, and birds. Come and see them all."

        chunks = plan(ClausePlanner(), line, budgets=[40, 40, 40])

        self.assertEqual(line, " ".join(chunks))
        self.assertEqual("Hello there,", chunks[0])
        for chunk in chunks[1:]:
            self.assertLessEqual(len(chunk), 40)
            self.assertRegex(chunk, r"[,.!?]$")

    def test_tight_budget_with_no_punctuation_cuts_at_a_word(self):
        chunks = plan(ClausePlanner(), self.LINE, budgets=[25, 100])

        self.assertEqual(self.LINE, " ".join(chunks))
        self.assertLessEqual(len(chunks[1]), 25)
        self.assertGreaterEqual(len(chunks[1].split()), 3)

    def test_tiny_budget_still_takes_three_words(self):
        chunks = plan(ClausePlanner(), self.LINE, budgets=[1, 1, 1, 1, 1, 1])

        self.assertEqual(self.LINE, " ".join(chunks))
        self.assertTrue(all(len(chunk.split()) >= 3 for chunk in chunks))

    def test_never_leaves_a_short_leftover(self):
        planner = ClausePlanner()
        planner.push("Yes, I made it. It is a boat.")
        planner.finish()

        first = planner.next_chunk(None)
        second = planner.next_chunk(12)

        self.assertEqual("Yes, I made it.", first)
        self.assertEqual("It is a boat.", second)
        self.assertTrue(planner.done)

    def test_waits_for_more_text_when_the_voice_has_time(self):
        planner = ClausePlanner()
        planner.push("Hello there, my friend. I ")

        self.assertEqual("Hello there,", planner.next_chunk(None))
        self.assertIsNone(planner.next_chunk(100))


class LineLimitTests(unittest.TestCase):
    def test_cut_off_line_gets_a_period(self):
        planner = ClausePlanner()

        chunks = plan(planner, "I carved a tiny boat,")

        self.assertEqual("I carved a tiny boat.", planner.spoken_text)
        self.assertEqual("I carved a tiny boat.", " ".join(chunks))

    def test_unfinished_last_sentence_is_dropped(self):
        planner = ClausePlanner()

        plan(planner, "I tripped over a log. Then I rolled down the hill with the t")

        self.assertEqual("I tripped over a log.", planner.spoken_text)

    def test_long_first_sentence_is_cut_by_word_count(self):
        chunks = plan(ClausePlanner(), "My favorite tool is a small carving chisel because details bring wood to life.")

        self.assertEqual("My favorite tool is a small", chunks[0])

    def test_over_long_sentence_ends_at_last_clause(self):
        planner = ClausePlanner(max_chars=62)

        plan(planner, "I would take my dragon to the mountains, where it could soar, but I would also be very careful.")

        self.assertEqual("I would take my dragon to the mountains, where it could soar.", planner.spoken_text)

    def test_over_long_line_without_breaks_drops_the_partial_word(self):
        planner = ClausePlanner(max_chars=30)

        plan(planner, "I carved the most wonderful little wooden boat today")

        self.assertEqual("I carved the most wonderful.", planner.spoken_text)

    def test_word_cut_never_ends_on_a_dangling_word(self):
        planner = ClausePlanner(max_chars=55)

        plan(planner, "You can start by practicing on basic shapes like squares or circles today")

        self.assertEqual("You can start by practicing on basic shapes.", planner.spoken_text)

    def test_line_is_capped_at_last_sentence_that_fits(self):
        planner = ClausePlanner(max_chars=40)

        plan(planner, "I like wood. I like paint a lot. I like glue and string and nails.")

        self.assertEqual("I like wood. I like paint a lot.", planner.spoken_text)
        self.assertTrue(planner.done)

    def test_non_ascii_is_dropped(self):
        planner = ClausePlanner()

        plan(planner, "Café time!")

        self.assertEqual("Caf time!", planner.spoken_text)


if __name__ == "__main__":
    unittest.main()
