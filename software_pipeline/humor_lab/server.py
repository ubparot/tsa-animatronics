"""Dependency-free local web server for the Pinocchio Humor Lab."""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from trainer import (
    DATA_ROOT,
    LINES_PATH,
    MINIMUM_RATINGS,
    MODEL_PATH,
    RATINGS_PATH,
    latest_ratings,
    load_experiment,
    load_ratings,
    public_summary,
    train_model,
)


ROOT = Path(__file__).resolve().parent
WRITE_LOCK = threading.Lock()
RATER_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,80}$")


class HumorLabHandler(BaseHTTPRequestHandler):
    server_version = "PinocchioHumorLab/1.0"

    def log_message(self, _format: str, *_args: object) -> None:
        """Keep routine browser requests out of the console."""

    def send_bytes(self, status: HTTPStatus, content: bytes, content_type: str, filename: str | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        self.send_bytes(status, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

    def send_file(self, path: Path, content_type: str) -> None:
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_bytes(HTTPStatus.OK, path.read_bytes(), content_type)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 16_384:
            raise ValueError("Request is too large.")
        value = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        if not isinstance(value, dict):
            raise ValueError("Expected a JSON object.")
        return value

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path in {"/", "/index.html"}:
            self.send_file(ROOT / "index.html", "text/html; charset=utf-8")
        elif path == "/app.js":
            self.send_file(ROOT / "app.js", "application/javascript; charset=utf-8")
        elif path == "/styles.css":
            self.send_file(ROOT / "styles.css", "text/css; charset=utf-8")
        elif path == "/api/experiment":
            experiment = load_experiment()
            self.send_json(HTTPStatus.OK, {
                "version": experiment["version"],
                "scale": experiment["scale"],
                "minimumRatings": MINIMUM_RATINGS,
                "lines": [{"id": line["id"], "text": line["text"]} for line in experiment["lines"]],
            })
        elif path == "/api/ratings":
            rater_id = parse_qs(parsed.query).get("rater_id", [""])[0]
            if not RATER_PATTERN.fullmatch(rater_id):
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid rating profile."})
                return
            rows = [row for row in latest_ratings(load_ratings()) if row.get("rater_id") == rater_id]
            self.send_json(HTTPStatus.OK, {"ratings": rows})
        elif path == "/api/model":
            if not MODEL_PATH.is_file():
                self.send_json(HTTPStatus.OK, {"trained": False})
                return
            model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
            self.send_json(HTTPStatus.OK, {"trained": True, "summary": public_summary(model)})
        elif path == "/api/export.csv":
            self.send_export()
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        try:
            if self.path == "/api/rate":
                self.save_rating(self.read_json())
            elif self.path == "/api/train":
                model = train_model()
                self.send_json(HTTPStatus.OK, {"trained": True, "summary": public_summary(model)})
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except OSError as exc:
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"Could not save local data: {exc}"})

    def save_rating(self, body: dict[str, Any]) -> None:
        experiment = load_experiment()
        valid_ids = {line["id"] for line in experiment["lines"]}
        rater_id = body.get("rater_id")
        line_id = body.get("line_id")
        rating = body.get("rating")
        elapsed_ms = body.get("elapsed_ms", 0)
        if not isinstance(rater_id, str) or not RATER_PATTERN.fullmatch(rater_id):
            raise ValueError("Invalid rating profile.")
        if line_id not in valid_ids:
            raise ValueError("Unknown line.")
        if not isinstance(rating, int) or isinstance(rating, bool) or not 1 <= rating <= 7:
            raise ValueError("Rating must be a whole number from 1 to 7.")
        if not isinstance(elapsed_ms, int) or not 0 <= elapsed_ms <= 900_000:
            raise ValueError("Invalid rating time.")
        record = {
            "time": time.time(),
            "rater_id": rater_id,
            "line_id": line_id,
            "rating": rating,
            "elapsed_ms": elapsed_ms,
            "experiment_version": experiment["version"],
        }
        DATA_ROOT.mkdir(parents=True, exist_ok=True)
        with WRITE_LOCK:
            with RATINGS_PATH.open("a", encoding="utf-8") as output:
                output.write(json.dumps(record) + "\n")
        current = [row for row in latest_ratings(load_ratings()) if row.get("rater_id") == rater_id]
        self.send_json(HTTPStatus.OK, {"saved": True, "rated": len(current), "remaining": len(valid_ids) - len(current)})

    def send_export(self) -> None:
        experiment = load_experiment()
        lines = {line["id"]: line for line in experiment["lines"]}
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=[
            "time", "rater_id", "line_id", "rating", "elapsed_ms", "text", "device", "delivery", "topic"
        ])
        writer.writeheader()
        for rating in latest_ratings(load_ratings()):
            line = lines.get(rating.get("line_id"))
            if not line:
                continue
            writer.writerow({
                **{key: rating.get(key, "") for key in ("time", "rater_id", "line_id", "rating", "elapsed_ms")},
                **{key: line[key] for key in ("text", "device", "delivery", "topic")},
            })
        self.send_bytes(
            HTTPStatus.OK,
            output.getvalue().encode("utf-8-sig"),
            "text/csv; charset=utf-8",
            "pinocchio_humor_ratings.csv",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local Pinocchio Humor Lab.")
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    load_experiment()  # Fail immediately if the experiment file is malformed.
    server = ThreadingHTTPServer(("127.0.0.1", args.port), HumorLabHandler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"Pinocchio Humor Lab is ready at {url}")
    print(f"Ratings stay local in {RATINGS_PATH}")
    print("Press Ctrl+C to close the lab.")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nClosing the Humor Lab.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
