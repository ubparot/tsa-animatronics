"""Offline-first AI response pipeline for the Pinocchio animatronic.

The program works without Ollama. If a local Ollama server is available, it
asks the model for a response constrained by response_schema.json. Every model
response is validated before it can become a simulated motion command.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = ROOT / "response_schema.json"
LOG_PATH = ROOT / "runs.jsonl"
HUMOR_PREFERENCES_PATH = ROOT / "humor_lab" / "data" / "prompt_preferences.txt"

VALID_AXES = {"jaw", "nose", "eyes", "head", "hands", "feet", "lantern"}
VALID_TAGS = {"TRUTH", "LIE", "CONFESSION"}
VALID_STATES = {"SPEAK_TRUTH", "SPEAK_LIE", "CONFESSION", "IDLE"}

SYSTEM_PROMPT = """You are Pinocchio, a curious wooden puppet created by Geppetto.
Your nose grows when you lie, and you are learning honesty, courage, and kindness.
Return only JSON with one field: spoken_text. Use plain ASCII. Answer the visitor's
specific question in one or two complete sentences under 105 characters total.
Give a clear reason for why questions, one concrete step for how/advice questions,
and a setup plus outcome for story requests. Prefer concrete character details over
vague sayings. Never use pet names, mock the visitor, or leave a thought unfinished.
Never say the internal labels TRUTH, LIE, CONFESSION, or "show outcome" aloud.
Vary sentence openings, word choice, and rhythm. About one reply in four may begin
with one natural hesitation such as "Well...", "Hmm...", or "Uh...". Use commas or
three dots for short pauses. When emotion fits, use at most one of these supported
voice tags: [chuckle], [laugh], [gasp], or [sigh]. Never use more than one hesitation
or voice tag in a reply. Do not use either for math, safety, or serious factual answers.
Never claim to be human, invent real-world facts, or give dangerous instructions.
"""

RECENT_SPOKEN_LINES: deque[str] = deque(maxlen=4)


def load_humor_preferences() -> str:
    """Load the locally learned writing preferences when the Humor Lab has trained them."""
    try:
        preferences = HUMOR_PREFERENCES_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    # Small local models copy examples too literally. Keep the learned style rules
    # in the live prompt while leaving example lines in the lab where they belong.
    style_rules = preferences.split("High-rated examples:", 1)[0].strip()
    return style_rules[:1200]

# Terminal punctuation before whitespace/end, or followed by closing quotes or
# brackets at the very end of the line, e.g. "...what do you see?'". Without the
# second form, quoted replies were rejected as fragments; limiting it to the end
# keeps a mid-line quote like 'He shouted "hello!" and waved.' in one piece.
# A period inside "..." is a delivery pause, not the end of the spoken line.
# Single periods plus !/? still terminate a sentence normally.
SENTENCE_END = r"(?:[!?]|(?<!\.)\.(?!\.))(?:(?=\s|$)|[\"')\]]+$)"

MODEL_TEXT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["spoken_text"],
    "properties": {"spoken_text": {"type": "string", "maxLength": 108}},
}


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def motion(axis: str, position: float, speed: float = 0.5, duration_ms: int = 600) -> dict[str, Any]:
    return {
        "axis": axis,
        "position": round(max(0.0, min(1.0, position)), 3),
        "speed": round(max(0.0, min(1.0, speed)), 3),
        "duration_ms": int(max(0, min(5000, duration_ms))),
    }


def choose_show_tag(question: str, tag_override: str | None = None) -> str:
    """Use a stable truthful default; the UI can deliberately select another outcome."""
    if tag_override:
        return tag_override
    lowered = question.lower()
    if any(phrase in lowered for phrase in ("confess", "did you lie", "admit it")):
        return "CONFESSION"
    lie_requests = (
        r"(?:please\s+)?tell\s+(?:me\s+)?a\s+lie[?.! ]*",
        r"(?:can|could|would)\s+you\s+(?:please\s+)?tell\s+me\s+a\s+lie[?.! ]*",
        r"(?:please\s+)?make\s+up\s+a\s+lie[?.! ]*",
        r"(?:please\s+)?make\s+something\s+up[?.! ]*",
    )
    if any(re.fullmatch(pattern, lowered.strip()) for pattern in lie_requests):
        return "LIE"
    return "TRUTH"


def line_for_tag(tag: str, truth: str, lie: str, confession: str) -> str:
    return {"TRUTH": truth, "LIE": lie, "CONFESSION": confession}[tag]


def varied_line_for_tag(
    tag: str,
    turn: int,
    truth: tuple[str, ...],
    lie: tuple[str, ...],
    confession: tuple[str, ...],
) -> str:
    """Rotate scripted lines predictably so rehearsals stay varied and repeatable."""
    variants = {"TRUTH": truth, "LIE": lie, "CONFESSION": confession}[tag]
    return variants[max(0, turn - 1) % len(variants)]


def remember_spoken_line(packet: dict[str, Any]) -> dict[str, Any]:
    """Keep a small local history used only to discourage repeated model replies."""
    line = str(packet.get("spoken_text", "")).strip()
    if line:
        RECENT_SPOKEN_LINES.append(line)
    return packet


def vary_repeated_line(text: str, tag: str, variation_index: int) -> str:
    """Give a stubborn repeated model draft a fresh, voice-friendly opening."""
    prefixes = {
        "TRUTH": ("Well... ", "Hmm... ", "You know, "),
        "LIE": ("[chuckle] ", "Well... ", "Believe it or not, "),
        "CONFESSION": ("[sigh] ", "Uh... ", "Honestly, "),
    }[tag]
    return complete_show_line(f"{prefixes[variation_index % len(prefixes)]}{text}")


def make_show_packet(spoken_text: str, tag: str, source_id: str, intensity: float = 0.5) -> dict[str, Any]:
    """Attach controller-owned show fields after dialogue has been chosen."""
    return normalize_packet(
        {
            "spoken_text": spoken_text,
            "truth_tag": tag,
            "emotion_intensity": intensity,
            "source_id": source_id,
            "motion": [],
            "next_state": "IDLE",
        },
        tag,
    )


def evaluate_basic_math(question: str) -> tuple[str, str] | None:
    """Safely evaluate a simple visitor arithmetic expression for an instant correct reply."""
    match = re.search(r"(?<!\w)(?:\d+\s*[-+*/]\s*)+\d+(?!\w)", question)
    if not match:
        number_words = {
            "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
            "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
            "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
            "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
            "eighteen": 18, "nineteen": 19, "twenty": 20,
        }
        number_pattern = "|".join(number_words)
        word_match = re.search(
            rf"\b({number_pattern})\s+(plus|minus|times|multiplied by|divided by)\s+({number_pattern})\b",
            question,
            re.IGNORECASE,
        )
        if not word_match:
            return None
        left = number_words[word_match.group(1).lower()]
        right = number_words[word_match.group(3).lower()]
        operation = word_match.group(2).lower()
        if operation == "plus":
            value = float(left + right)
        elif operation == "minus":
            value = float(left - right)
        elif operation in {"times", "multiplied by"}:
            value = float(left * right)
        elif right:
            value = left / right
        else:
            return None
        display = str(int(value)) if value.is_integer() else f"{value:.4g}"
        return word_match.group(0).lower(), display
    expression = re.sub(r"\s+", "", match.group(0))
    try:
        tree = ast.parse(expression, mode="eval")

        def calculate(node: ast.AST) -> float:
            if isinstance(node, ast.Expression):
                return calculate(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                return float(node.value)
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                value = calculate(node.operand)
                return value if isinstance(node.op, ast.UAdd) else -value
            if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
                left, right = calculate(node.left), calculate(node.right)
                if isinstance(node.op, ast.Add):
                    return left + right
                if isinstance(node.op, ast.Sub):
                    return left - right
                if isinstance(node.op, ast.Mult):
                    return left * right
                return left / right
            raise ValueError("unsupported expression")

        value = calculate(tree)
        if not value == value or abs(value) > 1_000_000:
            return None
    except (SyntaxError, TypeError, ValueError, ZeroDivisionError):
        return None
    display = str(int(value)) if value.is_integer() else f"{value:.4g}"
    return expression, display


def show_bank_response(question: str, turn: int, tag_override: str | None = None) -> dict[str, Any] | None:
    """Answer common show questions instantly, with lines that stay on topic."""
    lowered = question.lower().strip()
    tag = choose_show_tag(question, tag_override)
    math_answer = evaluate_basic_math(question)
    if math_answer:
        expression, answer = math_answer
        wrong_answer = str(int(float(answer)) + 1) if answer.lstrip("-").isdigit() else "a different number"
        return make_show_packet(
            varied_line_for_tag(
                tag,
                turn,
                (
                    f"Let me count carefully: {expression} equals {answer}.",
                    f"Counting it twice, {expression} comes to {answer}.",
                    f"The answer is {answer}; even my wooden fingers agree.",
                ),
                (
                    f"I say {expression} equals {wrong_answer}, but my nose may disagree!",
                    f"Clearly it is {wrong_answer}... unless the numbers are playing tricks!",
                    f"My brilliant answer is {wrong_answer}; please ignore my suspicious nose.",
                ),
                (
                    f"I first guessed {wrong_answer}, but {expression} really equals {answer}.",
                    f"I blurted out {wrong_answer}, but the careful answer is {answer}.",
                    f"My first answer wandered off; {expression} actually equals {answer}.",
                ),
            ),
            tag,
            "show_bank_math",
        )
    if "biggest mistake" in lowered or re.search(r"\blearn(?:ed)?\b.*\bmistake\b", lowered):
        return make_show_packet(
            varied_line_for_tag(
                tag,
                turn,
                (
                    "My biggest mistake was running away; I learned that honesty takes courage.",
                    "I once ignored good advice and caused trouble; now I stop and think first.",
                    "[sigh] I lied to hide a mistake, but telling the truth helped me repair it.",
                ),
                (
                    "I have never made a mistake; even my splinters land perfectly!",
                    "My biggest mistake was being too talented at absolutely everything.",
                    "[chuckle] I once sneezed so hard that I accidentally invented Tuesday.",
                ),
                (
                    "I claimed mistakes never bother me, but each one teaches me something.",
                    "Uh... I blamed my strings once, when the foolish choice was really mine.",
                    "[sigh] I tried to hide a mistake instead of asking Geppetto for help.",
                ),
            ),
            tag,
            "show_bank_mistake",
        )
    if "real boy" in lowered or re.search(r"\bmake(?:s)? you real\b", lowered):
        return make_show_packet(
            varied_line_for_tag(
                tag,
                turn,
                (
                    "Kind choices make me real in the ways that matter, even while I am made of wood.",
                    "Being real means learning honesty and caring for others, one choice at a time.",
                    "Hmm... courage and kindness make a person real more than skin or wood does.",
                ),
                (
                    "I became a real boy after polishing my elbows with moonlight!",
                    "One enormous sneeze turned me into a real boy for exactly seven minutes.",
                    "[gasp] I am secretly three real boys wearing one wooden puppet costume!",
                ),
                (
                    "I said I was already a real boy, but I am still a wooden puppet learning.",
                    "Uh... moonlight did not change me; my choices are what truly matter.",
                    "[sigh] I want a shortcut to being real, but growing takes honest work.",
                ),
            ),
            tag,
            "show_bank_real",
        )
    if "keep a secret" in lowered:
        return make_show_packet(
            varied_line_for_tag(
                tag,
                turn,
                (
                    "I can keep a harmless surprise, but not a secret that could leave someone unsafe.",
                    "A kind secret is safe with me; a dangerous one belongs with a trusted adult.",
                    "Hmm... I can guard a birthday surprise, but I would speak up if someone might be hurt.",
                ),
                (
                    "I keep every secret inside a locked drawer behind my left ear!",
                    "Of course; I once kept a secret from myself for twelve whole years.",
                    "[chuckle] I hide secrets so well that even I cannot find them again.",
                ),
                (
                    "I said I could keep every secret, but unsafe secrets should be shared.",
                    "Uh... I once promised silence when I should have asked a trusted adult for help.",
                    "[sigh] A birthday surprise is fine, but a harmful secret is different.",
                ),
            ),
            tag,
            "show_bank_secret",
        )
    if re.search(r"\bwhat are you afraid of\b", lowered):
        return make_show_packet(
            varied_line_for_tag(
                tag,
                turn,
                (
                    "I fear disappointing Geppetto, but honesty helps me find my way again.",
                    "I am afraid of losing my way when I ignore good advice.",
                    "Hmm... I fear making the same mistake twice more than I fear the dark.",
                ),
                (
                    "I fear nothing except a giant woodpecker with a toolbox!",
                    "The only thing that scares me is a very judgmental bowl of oatmeal.",
                    "[gasp] I am terrified of polite termites wearing tiny spectacles!",
                ),
                (
                    "I said I feared nothing, but disappointing Geppetto truly worries me.",
                    "Uh... I joked about woodpeckers because admitting fear felt difficult.",
                    "[sigh] I act fearless, but sometimes I am afraid of choosing badly.",
                ),
            ),
            tag,
            "show_bank_fear",
        )
    if "favorite tool" in lowered or "favourite tool" in lowered:
        return make_show_packet(
            varied_line_for_tag(
                tag,
                turn,
                (
                    "My favorite tool is a small carving chisel because careful details bring wood to life.",
                    "I like the measuring square; it keeps clever ideas from becoming crooked ones.",
                    "[chuckle] The wooden mallet is my favorite because it makes every tap sound important.",
                ),
                (
                    "My favorite tool is a hammer so large that it has its own weather.",
                    "I prefer an invisible saw that only cuts on alternate Thursdays.",
                    "[laugh] My golden chisel carves a chair before it even touches the wood!",
                ),
                (
                    "I bragged about a golden chisel, but Geppetto's ordinary tools do fine work.",
                    "Uh... my invisible saw is imaginary; I really like the measuring square.",
                    "[sigh] The giant hammer was a tall tale; careful tools are better.",
                ),
            ),
            tag,
            "show_bank_tool",
        )
    lie_question = (
        re.search(r"\bwhat happens\b.*\b(?:lie|lying)\b", lowered) is not None
        or re.search(r"\bwhy\b.*\bnose\b.*\bgrow", lowered) is not None
    )
    if lie_question:
        return make_show_packet(
            varied_line_for_tag(
                tag,
                turn,
                (
                    "When I tell a lie, my nose grows and reminds me to return to the truth.",
                    "My nose grows after a lie; it makes dishonesty rather hard to hide.",
                    "Well... each lie stretches my nose, so honesty is much easier on my face.",
                ),
                (
                    "Nothing happens when I lie; this enormous nose is merely fashionable!",
                    "My nose grows because it is training for a very important measuring contest.",
                    "[chuckle] Lies shrink my nose; you should have seen it yesterday!",
                ),
                (
                    "I claimed my nose grew for fashion, but telling lies is the real cause.",
                    "Uh... the measuring contest was invented; my nose grows when I lie.",
                    "[sigh] I tried to blame the weather, but dishonesty stretched my nose.",
                ),
            ),
            tag,
            "show_bank_nose",
        )
    if "something amazing about yourself" in lowered:
        return make_show_packet(
            varied_line_for_tag(
                tag,
                turn,
                (
                    "I am made of wood, yet every honest choice helps me grow in a way no ruler can measure.",
                    "I can turn a mistake into a lesson, which feels like real workshop magic.",
                    "[chuckle] My joints may squeak, but my curiosity never runs out of oil.",
                ),
                (
                    "I can carve a cathedral from one toothpick before breakfast!",
                    "I once outran a thunderstorm while carrying Geppetto's entire workshop.",
                    "[gasp] I can hear a lie from three villages away with my wooden elbow!",
                ),
                (
                    "I said I carved a cathedral, but learning from mistakes is my real talent.",
                    "Uh... I did not outrun thunder; I hid under Geppetto's workbench.",
                    "[sigh] My elbow hears nothing, but I am getting better at hearing the truth.",
                ),
            ),
            tag,
            "show_bank_amazing",
        )
    if "think on your feet" in lowered:
        return make_show_packet(
            varied_line_for_tag(
                tag,
                turn,
                (
                    "To think on your feet means choosing a good response quickly when plans suddenly change.",
                    "It means solving a surprise quickly, without having time to prepare first.",
                    "Hmm... it means adapting quickly; wooden feet are optional.",
                ),
                (
                    "It means writing ideas on your shoes so your feet can read them!",
                    "You stand on a dictionary until the clever answer climbs into your head.",
                    "[laugh] My feet do all my thinking while my head takes the afternoon off!",
                ),
                (
                    "I joked about clever shoes, but it really means responding quickly.",
                    "Uh... standing on a dictionary will not help; adapting quickly will.",
                    "[sigh] My feet do not think; the phrase means handling surprises well.",
                ),
            ),
            tag,
            "show_bank_idiom",
        )
    if "listen to geppetto" in lowered:
        return make_show_packet(
            varied_line_for_tag(
                tag,
                turn,
                (
                    "I try to listen to Geppetto because his advice is careful, though I still make mistakes.",
                    "Usually I listen, but learning also means admitting the times I did not.",
                    "Well... Geppetto gives wise advice, and I am practicing hearing it the first time.",
                ),
                (
                    "I always listen to Geppetto; I have never ignored one single word!",
                    "Geppetto listens to me because I am the wisest puppet in the workshop.",
                    "[chuckle] I obey before he even speaks, thanks to my mind-reading hat!",
                ),
                (
                    "I said I always listen, but sometimes I rush ahead and regret it.",
                    "Uh... Geppetto is wise, and I have ignored his advice more than once.",
                    "[sigh] I claimed perfect obedience, but I am still learning to listen.",
                ),
            ),
            tag,
            "show_bank_geppetto",
        )
    if "how are you" in lowered or "how do you feel" in lowered:
        return make_show_packet(
            varied_line_for_tag(
                tag,
                turn,
                (
                    "I am feeling bright and ready to build something clever with you.",
                    "Well... my hinges are happy, and I am ready for an adventure.",
                    "[chuckle] I feel splendid; even my squeaky elbow agrees.",
                ),
                (
                    "I am so energetic I could juggle a whole toolbox!",
                    "I feel strong enough to lift this workshop with one wooden finger!",
                    "[laugh] I have enough energy to race a lightning bolt today!",
                ),
                (
                    "I said I never tire, but even puppets need a quiet moment.",
                    "[sigh] I claimed I felt perfect, but one hinge is feeling grumpy.",
                    "Hmm... I may have exaggerated; I could use a tiny rest.",
                ),
            ),
            tag,
            "show_bank_greeting",
        )
    if re.fullmatch(r"(?:hi|hello|hey)(?: there)?[!.? ]*", lowered):
        return make_show_packet(
            varied_line_for_tag(
                tag,
                turn,
                (
                    "Hello, I am Pinocchio and ready for a story or workshop question.",
                    "Well... hello there; what curious thing shall we explore today?",
                    "[chuckle] Oh, a visitor; I hoped someone interesting would arrive.",
                ),
                (
                    "Hello, I just danced here from the moon on silver boots.",
                    "[gasp] You found me, even after I hid inside a thimble!",
                    "Why, hello; I arrived by flying teacup only moments ago.",
                ),
                (
                    "Hello, I said I flew from the moon, but I walked here.",
                    "Uh... hello! I did not really hide inside that tiny thimble.",
                    "[sigh] I claimed a flying teacup brought me, but I walked.",
                ),
            ),
            tag,
            "show_bank_greeting",
        )
    if "favorite" in lowered or "favourite" in lowered:
        if "shoe" in lowered or "boot" in lowered:
            line = varied_line_for_tag(
                tag,
                turn,
                (
                    "Wooden feet need no shoes, but sturdy little boots would suit me.",
                    "Hmm... I think bright red boots would look excellent on wooden feet.",
                    "I need no shoes, though tiny workshop boots would be rather stylish.",
                ),
                (
                    "My favorite shoes are silver dancing boots from the moon.",
                    "I own seven-league boots, but I keep misplacing the seventh league.",
                    "[laugh] My boots can dance alone while I take all the applause!",
                ),
                (
                    "I bragged about silver boots, but my wooden feet need none.",
                    "Well... those seven-league boots were ordinary shoes after all.",
                    "I said my boots danced alone, but Geppetto was moving the strings.",
                ),
            )
        else:
            line = varied_line_for_tag(
                tag,
                turn,
                (
                    "I like bright colors, clever stories, and friends who ask kind questions.",
                    "Hmm... clever stories are my favorite, especially ones with surprises.",
                    "I favor workshop adventures where everyone builds something together.",
                ),
                (
                    "My favorite thing is a pocket-sized dragon who tells jokes.",
                    "My favorite snack is a sandwich taller than this entire workshop!",
                    "[chuckle] I collect invisible crowns from very polite kings.",
                ),
                (
                    "I said I owned a dragon, but it was only a storybook picture.",
                    "Uh... that enormous sandwich was really just two crumbs.",
                    "[sigh] My invisible crown collection may be completely imaginary.",
                ),
            )
        return make_show_packet(line, tag, "show_bank_favorite")
    identity_question = (
        re.fullmatch(r"(?:who|what) are you(?: exactly)?[?.! ]*", lowered) is not None
        or re.search(r"\b(?:what is|what's|tell me) your name\b", lowered) is not None
    )
    if identity_question:
        return make_show_packet(
            varied_line_for_tag(
                tag,
                turn,
                (
                    "I am Pinocchio, a wooden puppet who loves stories and honest answers.",
                    "Well... I am Pinocchio, Geppetto's curious wooden creation.",
                    "[chuckle] Pinocchio is my name, and learning is my favorite adventure.",
                ),
                (
                    "I am the mayor of a tiny kingdom hidden inside a clock.",
                    "I am Captain Pinocchio, commander of the seven wooden seas!",
                    "[gasp] You do not recognize the world's greatest puppet detective?",
                ),
                (
                    "I said I was a king, but I am really a wooden puppet.",
                    "Uh... I am not a sea captain; I am Pinocchio the puppet.",
                    "[sigh] My detective badge is cardboard, but my name is Pinocchio.",
                ),
            ),
            tag,
            "show_bank_identity",
        )
    workshop_question = (
        re.search(r"\b(?:this|the|your) workshop\b", lowered) is not None
        or re.search(r"\bwhat\s+(?:did|do|have)\s+you\s+(?:build|built)\b", lowered) is not None
        or re.search(r"\b(?:did|are)\s+you\s+(?:really\s+)?(?:build|building)\b", lowered) is not None
        or re.search(
            r"\b(?:what|how)\s+(?:did|do|does|can|could|would|have|has)\s+you\s+(?:make|made)\b",
            lowered,
        )
        is not None
        or re.search(r"\bdid\s+you\s+make\b", lowered) is not None
    )
    if workshop_question:
        return make_show_packet(
            varied_line_for_tag(
                tag,
                turn,
                (
                    "I help visitors explore stories, movement, and careful workshop building.",
                    "Well... I build ideas one careful piece at a time with my friends.",
                    "[chuckle] I make stories move, though the clever builders do the hard part.",
                ),
                (
                    "I built this whole workshop with a spoon before breakfast!",
                    "I carved every tool here using one heroic wooden toothpick!",
                    "[laugh] I built it overnight while juggling three hammers at once!",
                ),
                (
                    "I claimed I built everything alone, but many careful hands helped.",
                    "Uh... the heroic toothpick story was a slight exaggeration.",
                    "[sigh] I did not build it overnight; a whole team worked carefully.",
                ),
            ),
            tag,
            "show_bank_workshop",
        )
    return None


def fallback_response(question: str, turn: int, tag_override: str | None = None) -> dict[str, Any]:
    """Stay relevant and family-friendly if a local model is unavailable."""
    known_response = show_bank_response(question, turn, tag_override)
    if known_response:
        return known_response
    tag = choose_show_tag(question, tag_override)
    return make_show_packet(
        varied_line_for_tag(
            tag,
            turn,
            (
                "That is an interesting question to explore together.",
                "Hmm... I would like to think that question through with you.",
                "Well... that gives this wooden head something new to consider.",
            ),
            (
                "I know the answer because a talking cricket whispered it to me!",
                "[gasp] A secret workshop map contains the answer in golden ink!",
                "I learned the answer while visiting the moon last Tuesday!",
            ),
            (
                "I pretended to know that, but I would like to learn with you.",
                "Uh... I invented an answer because I was afraid to say I did not know.",
                "[sigh] I do not know yet, but I would be glad to learn with you.",
            ),
        ),
        tag,
        "fallback_topic_aware",
    )


def validate_packet(packet: Any) -> tuple[bool, str]:
    if not isinstance(packet, dict):
        return False, "response is not an object"
    required = {"spoken_text", "truth_tag", "emotion_intensity", "source_id", "motion", "next_state"}
    missing = required - set(packet)
    if missing:
        return False, f"missing fields: {sorted(missing)}"
    if not isinstance(packet["spoken_text"], str) or not 0 < len(packet["spoken_text"]) <= 110:
        return False, "spoken_text must be 1-110 characters"
    if packet["truth_tag"] not in VALID_TAGS or packet["next_state"] not in VALID_STATES:
        return False, "invalid truth_tag or next_state"
    if not isinstance(packet["emotion_intensity"], (int, float)) or not 0 <= packet["emotion_intensity"] <= 1:
        return False, "emotion_intensity must be between 0 and 1"
    if not isinstance(packet["source_id"], str) or not re.fullmatch(r"[a-z0-9_-]+", packet["source_id"]):
        return False, "source_id contains unsupported characters"
    if not isinstance(packet["motion"], list) or len(packet["motion"]) > 8:
        return False, "motion must contain 0-8 commands"
    for command in packet["motion"]:
        if not isinstance(command, dict) or not {"axis", "position", "speed", "duration_ms"} <= set(command):
            return False, "invalid motion command"
        if command["axis"] not in VALID_AXES:
            return False, f"unsupported axis: {command['axis']}"
        if not 0 <= command["position"] <= 1 or not 0 <= command["speed"] <= 1:
            return False, "motion position/speed must be between 0 and 1"
        if not isinstance(command["duration_ms"], int) or not 0 <= command["duration_ms"] <= 5000:
            return False, "duration_ms must be an integer from 0 to 5000"
    return True, "ok"


def complete_show_line(value: object) -> str:
    """Keep spoken output audible and complete when a small model overruns its limit."""
    text = str(value).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    if len(text) <= 110:
        return text if raw_line_has_sentence_end(text) else f"{text[:109].rstrip(',;:- ')}."
    endings = [match for match in re.finditer(SENTENCE_END, text) if match.end() <= 110]
    if endings:
        return text[: endings[-1].end()]
    shortened = text[:110].rsplit(" ", 1)[0].rstrip(",;:-")
    return f"{shortened or text[:109]}."


def raw_line_has_sentence_end(value: object) -> bool:
    """Reject a grammar-limited model line before it becomes an audible fragment."""
    text = str(value).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"\s+", " ", text).strip()
    return bool(re.search(r"(?:[!?]|(?<!\.)\.(?!\.))[\"')\]]*$", text))


def normalize_packet(packet: Any, tag_override: str | None = None) -> dict[str, Any]:
    """Make minor presentation fixes while keeping model output within hard limits.

    This function never adds unrequested actuator axes or trusts a model-selected state.
    The truth tag determines the show state, and every retained motion command remains
    bounded by the response contract.
    """
    if not isinstance(packet, dict):
        raise ValueError("response is not an object")

    text = complete_show_line(packet.get("spoken_text", ""))
    tag = (tag_override or str(packet.get("truth_tag", ""))).upper()
    if tag not in VALID_TAGS:
        raise ValueError("invalid truth_tag")

    try:
        intensity = float(packet.get("emotion_intensity", 0.5))
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid emotion_intensity") from exc
    # Small models sometimes output a human-friendly 0-10 scale despite the schema.
    if 1 < intensity <= 10:
        intensity /= 10
    intensity = round(max(0.0, min(1.0, intensity)), 2)

    source = re.sub(r"[^a-z0-9_-]+", "_", str(packet.get("source_id", "local_model")).lower())
    source = source.strip("_-")[:48] or "local_model"

    retained_motion: list[dict[str, Any]] = []
    for command in packet.get("motion", []):
        if (
            not isinstance(command, dict)
            or command.get("axis") not in VALID_AXES
            or command.get("axis") == "nose"
        ):
            continue
        try:
            retained_motion.append(
                motion(
                    str(command["axis"]),
                    float(command.get("position", 0)),
                    float(command.get("speed", 0.5)),
                    int(command.get("duration_ms", 500)),
                )
            )
        except (TypeError, ValueError):
            continue

    axes = {command["axis"] for command in retained_motion}
    # Only the truth tag controls the signature safety-critical nose behavior.
    nose_position = 1.0 if tag == "LIE" else 0.0
    retained_motion.append(motion("nose", nose_position, 0.7, 700))
    if "jaw" not in axes:
        retained_motion.append(motion("jaw", 0.6, 0.45, 500))

    state_for_tag = {"TRUTH": "SPEAK_TRUTH", "LIE": "SPEAK_LIE", "CONFESSION": "CONFESSION"}
    return {
        "spoken_text": text,
        "truth_tag": tag,
        "emotion_intensity": intensity,
        "source_id": source,
        "motion": retained_motion,
        "next_state": state_for_tag[tag],
    }


def call_ollama(
    question: str,
    model: str,
    timeout: float,
    tag_override: str | None = None,
    recent_lines: tuple[str, ...] = (),
    variation_index: int = 0,
) -> dict[str, Any]:
    tag = choose_show_tag(question, tag_override)
    outcome_instruction = {
        "TRUTH": "Answer honestly and directly. If you do not know, say so simply.",
        "LIE": "Tell a clearly playful, harmless make-believe lie for a child-friendly show.",
        "CONFESSION": "Confess a harmless earlier exaggeration related to the question.",
    }[tag]
    user_message = f"Visitor question: {question}\nShow outcome: {tag}\n{outcome_instruction}"
    lowered_question = question.lower().strip()
    request_instructions: list[str] = []
    if re.match(r"how\b", lowered_question):
        request_instructions.append("Give one specific first step the visitor can take; do not merely define the topic.")
    if re.match(r"why\b", lowered_question):
        request_instructions.append("State the actual cause or reason in the first clause.")
    if "story" in lowered_question:
        request_instructions.append("Tell an original tiny event with a setup and a funny outcome.")
    if re.search(r"\b(?:you|your|yourself)\b", lowered_question):
        request_instructions.append("Answer as Pinocchio using a specific detail from his life or character.")
    if re.search(r"\b(?:lonely|sad|afraid|scared|worried)\b", lowered_question) and "you" not in lowered_question:
        request_instructions.append("Give one kind action the visitor can take now.")
    if request_instructions:
        user_message += "\nAnswer requirement: " + " ".join(request_instructions)
    serious_question = re.search(
        r"\b(?:danger|dangerous|emergency|fire|hurt|injury|safe|safety)\b",
        question,
        re.IGNORECASE,
    )
    style_cycle = (
        "Start directly with the answer.",
        "You may start with Well... or Hmm... if it sounds natural.",
        "Mention one concrete Pinocchio detail if it helps.",
        "Give the answer first, followed by one short reason.",
    )
    style_instruction = style_cycle[0] if serious_question else style_cycle[variation_index % len(style_cycle)]
    user_message += f"\nDelivery variation: {style_instruction}"
    humor_preferences = load_humor_preferences()
    system_prompt = SYSTEM_PROMPT
    if humor_preferences:
        system_prompt = f"{SYSTEM_PROMPT}\n{humor_preferences}"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "stream": False,
        "format": MODEL_TEXT_SCHEMA,
        "options": {
            "temperature": 0.5,
            "num_ctx": int(os.getenv("OLLAMA_NUM_CTX", "2048")),
            "num_predict": int(os.getenv("OLLAMA_NUM_PREDICT", "220")),
            "seed": random.SystemRandom().randint(1, 2_147_483_647),
        },
        "keep_alive": os.getenv("OLLAMA_KEEP_ALIVE", "30m"),
    }
    model_reply: dict[str, Any] | None = None
    last_valid_reply: dict[str, Any] | None = None
    recent_normalized = {complete_show_line(line).casefold() for line in recent_lines}
    repeated_draft = False
    for attempt in range(3):
        if attempt:
            retry_instruction = (
                "Your previous draft repeated a recent reply; use different wording and a different opening."
                if repeated_draft
                else "Use fewer words and end with a period."
            )
            payload["messages"][1]["content"] = f"{user_message}\n{retry_instruction}"
            payload["options"]["seed"] = random.SystemRandom().randint(1, 2_147_483_647)
        request = urllib.request.Request(
            # 127.0.0.1, not localhost: Windows tries IPv6 ::1 first and waits ~2 s before falling back.
            "http://127.0.0.1:11434/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        content = body.get("message", {}).get("content", "")
        candidate = json.loads(content)
        if isinstance(candidate, dict) and raw_line_has_sentence_end(candidate.get("spoken_text", "")):
            last_valid_reply = candidate
            candidate_line = complete_show_line(candidate.get("spoken_text", ""))
            repeated_draft = candidate_line.casefold() in recent_normalized
            if repeated_draft:
                continue
            model_reply = candidate
            break
    if model_reply is None and last_valid_reply is not None:
        model_reply = dict(last_valid_reply)
        model_reply["spoken_text"] = vary_repeated_line(
            complete_show_line(last_valid_reply.get("spoken_text", "")),
            tag,
            variation_index,
        )
    if model_reply is None:
        raise ValueError("model response ended mid-sentence")
    packet = make_show_packet(
        str(model_reply.get("spoken_text", "")),
        tag,
        f"ollama_{model}",
    )
    ok, reason = validate_packet(packet)
    if not ok:
        raise ValueError(reason)
    return packet


def warm_ollama_model(model: str, timeout: float = 120.0) -> None:
    """Load a model into memory ahead of the first visitor question.

    A cold load takes ~25 s on this computer, far longer than the per-turn
    timeout, so without this the first open-ended question gets the scripted
    fallback. A generate request with no prompt only loads the model.
    """
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps({"model": model, "keep_alive": os.getenv("OLLAMA_KEEP_ALIVE", "30m")}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        response.read()


def get_response(
    question: str, turn: int, model: str | None, timeout: float, tag_override: str | None = None
) -> tuple[dict[str, Any], str]:
    known_response = show_bank_response(question, turn, tag_override)
    if known_response:
        return remember_spoken_line(known_response), "show_bank"
    if model:
        try:
            packet = call_ollama(
                question,
                model,
                timeout,
                tag_override,
                tuple(RECENT_SPOKEN_LINES),
                turn,
            )
            return remember_spoken_line(packet), "ollama"
        except (OSError, urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            print(f"[local model unavailable: {exc}; using scripted fallback]", file=sys.stderr)
    return remember_spoken_line(fallback_response(question, turn, tag_override)), "fallback"


def apply_simulation(packet: dict[str, Any]) -> None:
    print(f"  state  -> {packet['next_state']}")
    print(f"  speech -> {packet['spoken_text']}")
    for command in packet["motion"]:
        print(
            f"  motion -> {command['axis']} position={command['position']:.2f} "
            f"speed={command['speed']:.2f} duration={command['duration_ms']}ms"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Pinocchio offline-first AI pipeline.")
    parser.add_argument("--model", default=os.getenv("OLLAMA_MODEL"), help="Local Ollama model; omit for fallback mode")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument(
        "--force-tag",
        choices=sorted(VALID_TAGS),
        help="Use this during a planned demo to make the truth/lie outcome repeatable.",
    )
    args = parser.parse_args()

    print("Pinocchio AI pipeline. Type a question; type 'quit' to exit.")
    print(f"Model: {args.model or 'scripted fallback'}")
    turn = 0
    while True:
        try:
            question = input("\nQuestion> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if question.lower() in {"quit", "exit", "q"}:
            break
        if not question:
            continue
        turn += 1
        packet, source = get_response(question, turn, args.model, args.timeout, args.force_tag)
        ok, reason = validate_packet(packet)
        if not ok:
            print(f"[blocked invalid response: {reason}]", file=sys.stderr)
            packet = fallback_response(question, turn)
            source = "fallback_after_validation"
        record = {"time": time.time(), "question": question, "source": source, "packet": packet}
        with LOG_PATH.open("a", encoding="utf-8") as log:
            log.write(json.dumps(record) + "\n")
        print(f"\nSource: {source}")
        print(json.dumps(packet, indent=2))
        apply_simulation(packet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
