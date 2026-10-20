"""Blind listening session for the behavioral study.

    python listen/server.py      then open http://127.0.0.1:8790

Serves the rating page and the clips, and appends each rating to
data/ratings.jsonl. Settings are never sent to the page: the listener sees a
clip number, the words, and the intended emotion only.
"""

from __future__ import annotations

import json
import random
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

STUDY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDY))
from design import CLIPS, DATA, read_csv  # noqa: E402

PAGE = Path(__file__).resolve().parent / "index.html"
RATINGS = DATA / "ratings.jsonl"
PORT = 8790
# Base sentence B (confession) prompt variants: plain, ellipsis, CAPS, [sigh], [whispering], (whispering).
PROMPT_SUBSET = {"P18", "P21", "P23", "P24", "P26", "P31"}


def listening_set() -> list[dict]:
    prompts = {p["PromptID"]: p for p in read_csv(DATA / "prompts.csv")}
    clips = []
    for c in read_csv(DATA / "plan.csv"):
        sweep = c["StudyBlock"] == "parameter sweep" and c["PromptID"] == "P03"
        prompt_arm = c["StudyBlock"] == "prompt manipulation" and c["PromptID"] in PROMPT_SUBSET
        if sweep or prompt_arm:
            p = prompts[c["PromptID"]]
            clips.append({"clip": c["ClipID"], "file": c["FileName"], "text": p["PromptText"],
                          "emotion": p["IntendedEmotion"]})
    return clips


def rated_by(listener: str) -> set[str]:
    if not RATINGS.is_file():
        return set()
    done = set()
    for line in RATINGS.read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        if entry["listener"].casefold() == listener.casefold():
            done.add(entry["clip"])
    return done


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send(self, body: bytes, kind: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            self.send(PAGE.read_bytes(), "text/html; charset=utf-8")
        elif url.path == "/api/session":
            listener = parse_qs(url.query).get("listener", [""])[0].strip()
            clips = listening_set()
            random.Random(listener.casefold()).shuffle(clips)  # stable order per listener, so it can resume
            done = rated_by(listener)
            payload = [{"clip": c["clip"], "text": c["text"], "emotion": c["emotion"], "done": c["clip"] in done}
                       for c in clips]
            self.send(json.dumps(payload).encode(), "application/json")
        elif url.path.startswith("/audio/"):
            clip = url.path.rsplit("/", 1)[-1]
            match = next((c for c in listening_set() if c["clip"] == clip), None)
            if match is None:
                self.send(b"not found", "text/plain", 404)
                return
            self.send((CLIPS / match["file"]).read_bytes(), "audio/wav")
        else:
            self.send(b"not found", "text/plain", 404)

    def do_POST(self):
        if urlparse(self.path).path != "/api/rate":
            self.send(b"not found", "text/plain", 404)
            return
        entry = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if not entry.get("listener") or not entry.get("clip"):
            self.send(b"missing listener or clip", "text/plain", 400)
            return
        entry["time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with RATINGS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        self.send(b'{"ok": true}', "application/json")


if __name__ == "__main__":
    print(f"Listening session at http://127.0.0.1:{PORT}  (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
