"""Turn a token stream from the local model into speakable clauses.

Ollama streams the reply as partial JSON ({"spoken_text": "Hel...). The
extractor pulls the spoken_text characters out as they arrive, and the planner
decides how much of that text the voice should take next:

- The first chunk is short and leaves as soon as it can, so speech starts fast.
- Every later chunk is sized to what the voice can synthesize while the audio
  already queued is still playing (the caller passes that as a character
  budget). A slow voice GPU gets short chunks and no silent gaps; a fast one
  gets whole sentences, which Chatterbox voices more naturally.

Pure standard library so it can be unit tested without the voice environment.
"""

from __future__ import annotations

import json
import re

from pipeline import raw_line_has_sentence_end


SPOKEN_TEXT_KEY = re.compile(r'"spoken_text"\s*:\s*"')

# Punctuation must be followed by whitespace before it counts, so "3.5" and a
# "..." that is still arriving are never split. Closing quotes/brackets stay
# with the clause they end.
CLAUSE_BREAK = re.compile(r"(?:\.\.\.|[,;:]|[!?]+|(?<!\.)\.(?!\.))[\"')\]]*(?=\s)")
SENTENCE_BREAK = re.compile(r"(?:[!?]+|(?<!\.)\.(?!\.))[\"')\]]*(?=\s)")
WORD_END = re.compile(r"\S+(?=\s)")
# Chunks shorter than this, and leftovers shorter than this, make Chatterbox
# sound clipped, so cuts avoid creating them whenever the text allows.
MIN_CHUNK_WORDS = 3
# Words a cut-off line should not end on, because they leave a thought hanging.
DANGLING_WORDS = frozenset(
    "a an the and or but so to of with like by for from in on at as than that "
    "because when while if my your his her their its our very".split()
)


class SpokenTextExtractor:
    """Incrementally decode the spoken_text string from streamed JSON fragments."""

    def __init__(self) -> None:
        self._prefix = ""
        self._in_string = False
        self._escape = ""
        self.done = False

    def feed(self, fragment: str) -> str:
        if self.done or not fragment:
            return ""
        if not self._in_string:
            self._prefix += fragment
            match = SPOKEN_TEXT_KEY.search(self._prefix)
            if match is None:
                return ""
            self._in_string = True
            fragment = self._prefix[match.end():]
            self._prefix = ""

        decoded: list[str] = []
        for char in fragment:
            if self._escape:
                self._escape += char
                # \uXXXX needs six characters; every other escape needs two.
                if self._escape.startswith("\\u") and len(self._escape) < 6:
                    continue
                try:
                    decoded.append(json.loads(f'"{self._escape}"'))
                except json.JSONDecodeError:
                    pass
                self._escape = ""
            elif char == "\\":
                self._escape = char
            elif char == '"':
                self.done = True
                break
            else:
                decoded.append(char)
        return "".join(decoded)


class ClausePlanner:
    """Hold streamed spoken text and hand it to the voice one chunk at a time."""

    def __init__(self, first_chunk_words: int = 6, max_chars: int = 110) -> None:
        # first_chunk_words: cut the first chunk after this many words even with
        # no punctuation yet (0 waits for punctuation).
        self.first_chunk_words = first_chunk_words
        self.max_chars = max_chars
        self.emitted: list[str] = []
        self.complete = False
        self._pending = ""

    @property
    def spoken_text(self) -> str:
        return " ".join(self.emitted)

    @property
    def has_text(self) -> bool:
        return bool(self.emitted or self._pending.strip())

    @property
    def done(self) -> bool:
        return self.complete and not self._pending

    def push(self, text: str) -> None:
        if self.complete:
            return
        text = text.encode("ascii", "ignore").decode("ascii")
        self._pending = re.sub(r"\s+", " ", self._pending + text).lstrip()
        spoken = len(self.spoken_text) + 1 if self.emitted else 0
        if spoken + len(self._pending) > self.max_chars:
            self._truncate()

    def finish(self) -> None:
        """No more text is coming; make sure the line ends on a finished sentence.

        Like complete_show_line, drop an unfinished last sentence when an
        earlier one ended cleanly; otherwise close it with a period.
        """
        if self.complete:
            return
        self.complete = True
        pending = self._pending.strip()
        if pending and not raw_line_has_sentence_end(pending):
            endings = list(SENTENCE_BREAK.finditer(pending))
            if endings:
                pending = pending[: endings[-1].end()]
            elif self.emitted and raw_line_has_sentence_end(self.spoken_text):
                pending = ""
            else:
                pending = pending.rstrip(",;:- ") + "."
        self._pending = pending

    def next_chunk(self, max_chars: int | None) -> str | None:
        """Take the next chunk, or None to wait for more text.

        max_chars is how much text the voice can take without the speaker
        running dry; None means nothing is playing yet (the first chunk).
        """
        cut = self._first_cut() if not self.emitted else self._later_cut(max_chars)
        if cut is None:
            return None
        chunk = self._pending[:cut].strip()
        self._pending = self._pending[cut:].lstrip()
        self.emitted.append(chunk)
        return chunk

    def _first_cut(self) -> int | None:
        text = self._pending + (" " if self.complete else "")
        # A clause longer than this is not "short"; cut by word count instead.
        longest = self.first_chunk_words + MIN_CHUNK_WORDS if self.first_chunk_words else len(text)
        for match in CLAUSE_BREAK.finditer(text):
            words = len(text[: match.end()].split())
            if words > longest:
                break
            if words >= 2:
                return min(match.end(), len(self._pending))
        if self.first_chunk_words:
            words = list(WORD_END.finditer(text))
            if len(words) >= self.first_chunk_words + MIN_CHUNK_WORDS:
                return words[self.first_chunk_words - 1].end()
        return len(self._pending) if self.complete and self._pending else None

    def _later_cut(self, max_chars: int | None) -> int | None:
        pending = self._pending
        if not pending:
            return None
        budget = max_chars if max_chars is not None else self.max_chars + 1
        if self.complete and len(pending) <= budget:
            return len(pending)
        if not self.complete and len(pending) < budget:
            # The voice has time to spare; wait for more text and a better cut.
            return None
        text = pending + (" " if self.complete else "")
        total_words = len(pending.split()) if self.complete else None

        def fits(end: int) -> bool:
            words = len(text[:end].split())
            leftover_ok = total_words is None or total_words - words == 0 or total_words - words >= MIN_CHUNK_WORDS
            return end <= budget and words >= MIN_CHUNK_WORDS and leftover_ok

        for pattern in (SENTENCE_BREAK, CLAUSE_BREAK):
            ends = [match.end() for match in pattern.finditer(text) if fits(match.end())]
            if ends:
                return min(ends[-1], len(pending))
        # No punctuation fits the budget: cut at the last whole word that does,
        # but never below MIN_CHUNK_WORDS (a short gap beats a clipped word).
        words = list(WORD_END.finditer(text))
        fitting = [match.end() for match in words if fits(match.end())]
        if fitting:
            return min(fitting[-1], len(pending))
        if self.complete and len(pending.split()) < 2 * MIN_CHUNK_WORDS:
            return len(pending)
        # While text is still arriving, keep MIN_CHUNK_WORDS in reserve so the
        # final chunk cannot end up a lone word.
        if len(words) >= (MIN_CHUNK_WORDS if self.complete else 2 * MIN_CHUNK_WORDS):
            return words[MIN_CHUNK_WORDS - 1].end()
        return len(pending) if self.complete else None

    def _truncate(self) -> None:
        """End an over-long line as cleanly as the text allows.

        In order of preference: the last sentence end that fits (as
        complete_show_line does); nothing more, if what was already spoken
        ends a sentence; the last comma/semicolon clause, closed with a period
        ("...where it could soar and breathe fire."); the last whole word.
        """
        budget = self.max_chars - (len(self.spoken_text) + 1 if self.emitted else 0)
        room = self._pending[: max(budget, 0)]
        endings = list(SENTENCE_BREAK.finditer(room + " "))
        spoken_words = len(self.spoken_text.split())
        clauses = [
            match.end()
            for match in CLAUSE_BREAK.finditer(room + " ")
            if spoken_words + len(room[: match.end()].split()) >= MIN_CHUNK_WORDS
        ]
        if endings:
            self._pending = room[: endings[-1].end()]
        elif self.emitted and raw_line_has_sentence_end(self.spoken_text):
            # What was already handed to the voice ends cleanly; drop the overrun.
            self._pending = ""
        elif clauses:
            self._pending = room[: clauses[-1]].rstrip(",;:-. ") + "."
        elif self.emitted and re.search(r"[,;:]$", self.spoken_text):
            # Already spoken up to a clause break; ending there beats a fragment.
            self._pending = ""
        else:
            # room may end inside a word; drop that partial word, and never end
            # on a word that promises more ("...shapes like squares or.").
            words = room.split(" ")[:-1]
            while words and words[-1].lower().strip(",;:-") in DANGLING_WORDS:
                words.pop()
            self._pending = " ".join(words)
        self.finish()
