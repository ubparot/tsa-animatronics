"""Local browser control panel for the Pinocchio voice pipeline.

This server stays on 127.0.0.1. It records from the configured local microphone,
uses the local Whisper/Ollama/Piper stack, and returns a browser-playable WAV.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import threading
import time
import uuid
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from faster_whisper import WhisperModel

from pipeline import LOG_PATH, VALID_TAGS, apply_simulation, get_response, warm_ollama_model
from machine_paths import MACHINE
from performance_lab import (
    MAX_CONFIGS,
    MAX_LINES,
    MAX_SEEDS,
    build_round,
    choose_references,
    discover_references,
    estimate_seconds,
    load_battery,
    settings_for,
    summarize_round,
    total_clips,
    validate_ratings,
)
from voice_pipeline import (
    CONFIG_PATH,
    RECORDING_PATH,
    RUNTIME_ROOT,
    SPEECH_PATH,
    VOICE_LOG_PATH,
    load_config,
    record_question,
    reprompt_packet,
    speak,
    transcribe,
)
from tts_chatterbox import VoiceEngine, create_voice, describe_voice


ROOT = Path(__file__).resolve().parent
UI_ROOT = ROOT / "ui"
RUN_LOCK = threading.Lock()
PERFORMANCE_LOCK = threading.Lock()
PERFORMANCE_JOBS: dict[str, dict[str, Any]] = {}
PERFORMANCE_ROOT = MACHINE.runtime / "performance_lab"
PERFORMANCE_LOG = PERFORMANCE_ROOT / "ratings.jsonl"
BATTERY_PATH = ROOT / "eval" / "test_lines.json"
MODEL_OPTIONS = {"pinocchio-fast", "pinocchio-ai"}
MODEL_TIMEOUTS = {"pinocchio-fast": 8.0, "pinocchio-ai": 12.0}


class PipelineRuntime:
    """Loads the local speech components once and runs one show turn at a time."""

    def __init__(self, model_name: str) -> None:
        self.config = load_config()
        self.model_name = model_name
        self.turn = 0
        self.last_error: str | None = None
        self.ready = False
        self.stt: WhisperModel | None = None
        self.voice: VoiceEngine | None = None
        self.warmed_models: set[str] = set()

    def warm_model(self, model_name: str) -> None:
        """Preload an Ollama model once so its cold load never eats a turn's timeout."""
        if model_name in self.warmed_models:
            return
        # Mark it even on failure so a broken Ollama cannot stall every turn;
        # get_response still falls back to the scripted line in that case.
        self.warmed_models.add(model_name)
        try:
            warm_ollama_model(model_name)
        except (OSError, TimeoutError, ValueError) as exc:
            print(f"[could not preload {model_name}: {exc}]", flush=True)

    def load(self) -> None:
        RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
        self.stt = WhisperModel(
            self.config["whisper_model"],
            device=self.config["whisper_device"],
            compute_type=self.config["whisper_compute_type"],
            download_root=str(RUNTIME_ROOT / "whisper"),
        )
        self.voice = create_voice(self.config)
        self.warm_model(self.model_name)
        self.ready = True

    def status(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "model": self.model_name,
            "models": [
                {"id": "pinocchio-fast", "label": "Fast · 1.5B (recommended)"},
                {"id": "pinocchio-ai", "label": "Large · 3B (experimental)"},
            ],
            "microphone": self.config.get("input_device"),
            "speechRecognition": f"Whisper {self.config['whisper_model']} ({self.config['whisper_device']})",
            "voice": describe_voice(self.voice) if self.voice else None,
            "lastError": self.last_error,
        }

    def run(
        self,
        text: str | None,
        force_tag: str | None,
        model_name: str | None = None,
    ) -> dict[str, Any]:
        if not self.ready or self.stt is None or self.voice is None:
            raise RuntimeError("The voice components are still loading. Try again in a moment.")

        with RUN_LOCK:
            self.last_error = None
            self.turn += 1
            selected_model = model_name or self.model_name
            self.warm_model(selected_model)
            transcript = text.strip() if text else ""
            timings = {"listen": 0.0, "transcribe": 0.0, "ai": 0.0, "voice": 0.0}
            try:
                if not transcript:
                    started = time.perf_counter()
                    recording = record_question(self.config)
                    timings["listen"] = time.perf_counter() - started
                    started = time.perf_counter()
                    transcript = transcribe(self.stt, recording)
                    timings["transcribe"] = time.perf_counter() - started
                if not transcript:
                    raise RuntimeError("Speech was not clear enough to transcribe.")
                started = time.perf_counter()
                packet, source = get_response(
                    transcript,
                    self.turn,
                    selected_model,
                    MODEL_TIMEOUTS[selected_model],
                    force_tag,
                )
                timings["ai"] = time.perf_counter() - started
            except (OSError, RuntimeError, ValueError) as exc:
                self.last_error = str(exc)
                packet = reprompt_packet()
                source = "speech_fallback"

            apply_simulation(packet)
            started = time.perf_counter()
            speak(self.voice, packet["spoken_text"], SPEECH_PATH, mute=True)
            timings["voice"] = time.perf_counter() - started
            voice_error = getattr(self.voice, "last_error", None)
            if voice_error and not self.last_error:
                self.last_error = voice_error
            record = {
                "time": time.time(),
                "transcript": transcript,
                "source": source,
                "model": selected_model,
                "packet": packet,
                "recording": str(RECORDING_PATH),
                "speech": str(SPEECH_PATH),
                "ui": True,
            }
            for log_path in (VOICE_LOG_PATH, LOG_PATH):
                with log_path.open("a", encoding="utf-8") as log:
                    log.write(json.dumps(record) + "\n")
            return {
                "transcript": transcript,
                "source": source,
                "model": selected_model,
                "packet": packet,
                "audioUrl": f"/audio/last_response.wav?v={int(time.time() * 1000)}",
                "fallback": source == "speech_fallback",
                "error": self.last_error,
                "timings": {name: round(seconds, 2) for name, seconds in timings.items()},
            }


class ControlPanelHandler(BaseHTTPRequestHandler):
    runtime: PipelineRuntime

    server_version = "PinocchioWorkshop/1.0"

    def log_message(self, _format: str, *_args: object) -> None:
        """Keep routine browser requests out of the show-control console."""

    def send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        content = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def send_file(self, path: Path, content_type: str) -> None:
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def read_json(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length > 16_384:
            raise ValueError("Request is too large.")
        raw = self.rfile.read(content_length)
        return json.loads(raw.decode("utf-8") or "{}")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path in {"/", "/index.html"}:
            self.send_file(UI_ROOT / "index.html", "text/html; charset=utf-8")
        elif path == "/ui.css":
            self.send_file(UI_ROOT / "ui.css", "text/css; charset=utf-8")
        elif path == "/ui.js":
            self.send_file(UI_ROOT / "ui.js", "application/javascript; charset=utf-8")
        elif path in {"/performance", "/performance.html"}:
            self.send_file(UI_ROOT / "performance.html", "text/html; charset=utf-8")
        elif path == "/performance.css":
            self.send_file(UI_ROOT / "performance.css", "text/css; charset=utf-8")
        elif path == "/performance.js":
            self.send_file(UI_ROOT / "performance.js", "application/javascript; charset=utf-8")
        elif path == "/api/status":
            self.send_json(HTTPStatus.OK, self.runtime.status())
        elif path == "/api/performance/options":
            self.send_json(HTTPStatus.OK, self.performance_options())
        elif path.startswith("/api/performance/job/"):
            self.get_performance_job(path.rsplit("/", 1)[-1])
        elif path == "/api/performance/results":
            job_id = parse_qs(parsed.query).get("job_id", [""])[0]
            self.get_performance_results(job_id)
        elif path.startswith("/performance-audio/"):
            self.get_performance_audio(path)
        elif path == "/audio/last_response.wav":
            self.send_file(SPEECH_PATH, "audio/wav")
        elif path == "/audio/last_question.wav":
            self.send_file(RECORDING_PATH, "audio/wav")
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path.startswith("/api/performance/"):
            self.handle_performance_post(path)
            return
        if path not in {"/api/record", "/api/text"}:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not RUN_LOCK.acquire(blocking=False):
            self.send_json(HTTPStatus.CONFLICT, {"error": "A show turn is already in progress."})
            return
        RUN_LOCK.release()
        try:
            body = self.read_json()
            force_tag = body.get("forceTag")
            if force_tag is not None and force_tag not in VALID_TAGS:
                raise ValueError("Invalid show outcome.")
            model_name = body.get("model")
            if model_name is not None and model_name not in MODEL_OPTIONS:
                raise ValueError("Invalid response model.")
            text = body.get("text") if path == "/api/text" else None
            if path == "/api/text" and not isinstance(text, str):
                raise ValueError("Enter a question first.")
            response = self.runtime.run(text, force_tag, model_name)
            self.send_json(HTTPStatus.OK, response)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:  # Show the local problem in the UI instead of losing the server.
            self.runtime.last_error = str(exc)
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def performance_options(self) -> dict[str, Any]:
        voice = self.runtime.voice
        if not self.runtime.ready or voice is None:
            return {"ready": False, "error": "The voice model is still loading."}
        candidates = discover_references(MACHINE.voice_training)
        selected = choose_references(candidates, voice.reference_path)
        return {
            "ready": True,
            "current": {
                "referenceId": voice.reference_path.name,
                "temperature": voice.temperature,
                "topP": voice.top_p,
                "topK": voice.top_k,
                "repetitionPenalty": voice.repetition_penalty,
                "seed": voice.seed,
            },
            "references": selected,
            "limits": {
                "configs": MAX_CONFIGS,
                "lines": MAX_LINES,
                "seeds": MAX_SEEDS,
            },
            "presets": [
                "I carved myself from a mighty tree. Geppetto helped by doing absolutely all of it.",
                "I always tell the truth. My nose is simply an enthusiastic fact checker.",
                "This workshop is perfectly organized, if you know where absolutely nothing is.",
                "Of course I have a plan. I am currently waiting for it to introduce itself.",
                "I learned patience from woodworking, mostly because glue ignores motivational speeches.",
            ],
        }

    def handle_performance_post(self, path: str) -> None:
        try:
            body = self.read_json()
            if path == "/api/performance/generate":
                self.start_performance_job(body)
            elif path == "/api/performance/rate":
                self.rate_performance_variant(body)
            elif path == "/api/performance/apply":
                self.apply_performance_variant(body)
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def start_performance_job(self, body: dict[str, Any]) -> None:
        voice = self.runtime.voice
        if not self.runtime.ready or voice is None:
            raise ValueError("The voice model is still loading.")
        text = body.get("text")
        if not isinstance(text, str) or not 5 <= len(text.strip()) <= 500:
            raise ValueError("Enter a performance line between 5 and 500 characters.")
        mode = str(body.get("mode", "mixed"))
        config_count = int(body.get("configs", 3))
        line_count = int(body.get("lines", 3))
        seed_count = int(body.get("seeds", 3))
        with PERFORMANCE_LOCK:
            if any(job["status"] in {"queued", "generating"} for job in PERFORMANCE_JOBS.values()):
                self.send_json(HTTPStatus.CONFLICT, {"error": "Another audition round is already generating."})
                return
        candidates = discover_references(MACHINE.voice_training)
        selected = choose_references(candidates, voice.reference_path)
        # Delivery mode must isolate sampling changes by holding the current
        # reference fixed. The other modes intentionally compare references.
        if mode == "delivery":
            current_candidate = next((item for item in candidates if item["id"] == voice.reference_path.name), None)
            if current_candidate:
                selected = [current_candidate]
        current = {
            "temperature": voice.temperature,
            "top_p": voice.top_p,
            "top_k": voice.top_k,
            "repetition_penalty": voice.repetition_penalty,
            "seed": voice.seed,
        }
        plan = build_round(
            mode,
            selected,
            current,
            load_battery(BATTERY_PATH),
            text.strip(),
            config_count=config_count,
            line_count=line_count,
            seed_count=seed_count,
        )
        job_id = uuid.uuid4().hex[:12]
        job_dir = PERFORMANCE_ROOT / job_id
        for cell in plan["cells"]:
            for take in cell["takes"]:
                take["path"] = str(job_dir / f"cell-{cell['id'].lower()}-take{take['index']}.wav")
        # Shuffle only the order they are auditioned in. Cell ids stay attached
        # to their configuration so the reveal can still trace every rating.
        order = [cell["id"] for cell in plan["cells"]]
        random.SystemRandom().shuffle(order)

        clips = total_clips(plan)
        job = {
            "id": job_id,
            "status": "queued",
            "text": text.strip(),
            "mode": mode,
            "created": time.time(),
            "completed": 0,
            "total": clips,
            "order": order,
            "configs": plan["configs"],
            "lines": plan["lines"],
            "seeds": plan["seeds"],
            "cells": plan["cells"],
            "error": None,
        }
        with PERFORMANCE_LOCK:
            PERFORMANCE_JOBS[job_id] = job
        thread = threading.Thread(target=self.generate_performance_job, args=(job_id,), daemon=True)
        thread.start()
        self.send_json(
            HTTPStatus.ACCEPTED,
            {"jobId": job_id, "clips": clips, "estimateSeconds": estimate_seconds(clips)},
        )

    def generate_performance_job(self, job_id: str) -> None:
        try:
            with RUN_LOCK:
                with PERFORMANCE_LOCK:
                    job = PERFORMANCE_JOBS[job_id]
                    job["status"] = "generating"
                voice = self.runtime.voice
                if voice is None:
                    raise RuntimeError("The voice model is unavailable.")
                configs = {config["config_id"]: config for config in job["configs"]}
                for cell in job["cells"]:
                    config = configs[cell["config_id"]]
                    for take in cell["takes"]:
                        voice.synthesize_variant_to_wav(
                            cell["text"],
                            Path(take["path"]),
                            settings_for(config, take["seed"]),
                        )
                        with PERFORMANCE_LOCK:
                            job["completed"] += 1
                with PERFORMANCE_LOCK:
                    job["status"] = "ready"
                self.save_performance_manifest(job)
        except Exception as exc:
            with PERFORMANCE_LOCK:
                job = PERFORMANCE_JOBS.get(job_id)
                if job:
                    job["status"] = "error"
                    job["error"] = str(exc)

    @staticmethod
    def save_performance_manifest(job: dict[str, Any]) -> None:
        job_dir = Path(job["cells"][0]["takes"][0]["path"]).parent
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "manifest.json").write_text(
            json.dumps(job, indent=2) + "\n", encoding="utf-8"
        )

    def get_performance_job(self, job_id: str) -> None:
        with PERFORMANCE_LOCK:
            job = PERFORMANCE_JOBS.get(job_id)
            if not job:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": "That audition round was not found."})
                return
            cells = {cell["id"]: cell for cell in job["cells"]}
            # Settings stay out of this payload to keep the audition blind. The
            # line text does not: the rater has to know what was meant to be
            # said before they can judge how it was said.
            payload = {
                "jobId": job_id,
                "status": job["status"],
                "mode": job["mode"],
                "text": job["text"],
                "completed": job["completed"],
                "total": job["total"],
                "error": job["error"],
                "rated": sum(cell["ratings"] is not None for cell in job["cells"]),
                "cells": [
                    {
                        "id": cell_id,
                        "text": cells[cell_id]["text"],
                        "takes": [
                            {
                                "index": take["index"],
                                "audioUrl": f"/performance-audio/{job_id}/{cell_id}-{take['index']}.wav",
                            }
                            for take in cells[cell_id]["takes"]
                        ],
                    }
                    for cell_id in job["order"]
                ] if job["status"] == "ready" else [],
            }
        self.send_json(HTTPStatus.OK, payload)

    def get_performance_audio(self, path: str) -> None:
        match = re.fullmatch(r"/performance-audio/([a-f0-9]{12})/([A-P])-([1-9])\.wav", path)
        if not match:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        job_id, cell_id, take_index = match.groups()
        with PERFORMANCE_LOCK:
            job = PERFORMANCE_JOBS.get(job_id)
            cell = next((item for item in job["cells"] if item["id"] == cell_id), None) if job else None
            take = next((item for item in cell["takes"] if item["index"] == int(take_index)), None) if cell else None
        if take is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_file(Path(take["path"]), "audio/wav")

    def rate_performance_variant(self, body: dict[str, Any]) -> None:
        job_id = str(body.get("jobId", ""))
        cell_id = str(body.get("cellId", ""))
        ratings = validate_ratings(body.get("ratings"))
        with PERFORMANCE_LOCK:
            job = PERFORMANCE_JOBS.get(job_id)
            if not job or job["status"] != "ready":
                raise ValueError("That audition round is not ready.")
            cell = next((item for item in job["cells"] if item["id"] == cell_id), None)
            if cell is None:
                raise ValueError("That audition clip was not found.")
            config = next(item for item in job["configs"] if item["config_id"] == cell["config_id"])
            cell["ratings"] = ratings
            rated = sum(item["ratings"] is not None for item in job["cells"])
            total_cells = len(job["cells"])
            complete = rated == total_cells
            log_record = {
                "time": time.time(), "job_id": job_id, "cell_id": cell_id,
                "line_id": cell["line_id"], "text": cell["text"], "mode": job["mode"],
                "seeds": [take["seed"] for take in cell["takes"]], "ratings": ratings,
                "settings": {
                    key: config[key]
                    for key in ("reference_id", "temperature", "top_p", "top_k", "repetition_penalty")
                },
            }
            self.save_performance_manifest(job)
        PERFORMANCE_ROOT.mkdir(parents=True, exist_ok=True)
        with PERFORMANCE_LOG.open("a", encoding="utf-8") as log:
            log.write(json.dumps(log_record) + "\n")
        self.send_json(HTTPStatus.OK, {"rated": rated, "total": total_cells, "complete": complete})

    def get_performance_results(self, job_id: str) -> None:
        with PERFORMANCE_LOCK:
            job = PERFORMANCE_JOBS.get(job_id)
            if not job:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": "That audition round was not found."})
                return
            if any(cell["ratings"] is None for cell in job["cells"]):
                self.send_json(HTTPStatus.CONFLICT, {"error": "Rate every clip before revealing the settings."})
                return
            results = summarize_round(job["configs"], job["lines"], job["cells"])
            seeds = list(job["seeds"])
        self.send_json(
            HTTPStatus.OK,
            {
                "jobId": job_id,
                "results": results,
                "winner": results[0]["configId"],
                "seeds": seeds,
            },
        )

    def apply_performance_variant(self, body: dict[str, Any]) -> None:
        job_id = str(body.get("jobId", ""))
        config_id = int(body.get("configId", 0))
        with PERFORMANCE_LOCK:
            job = PERFORMANCE_JOBS.get(job_id)
            if not job or any(cell["ratings"] is None for cell in job["cells"]):
                raise ValueError("Finish the blind ratings before applying a result.")
            config = next((item for item in job["configs"] if item["config_id"] == config_id), None)
            if config is None:
                raise ValueError("That configuration was not found.")
            voice = self.runtime.voice
            # The round judged this configuration across seeds on purpose, so
            # the live seed is a separate decision and is deliberately kept.
            settings = settings_for(config, voice.seed if voice else config.get("seed", 0))
        if not RUN_LOCK.acquire(blocking=False):
            self.send_json(HTTPStatus.CONFLICT, {"error": "The voice is busy. Try applying again in a moment."})
            return
        try:
            voice = self.runtime.voice
            if voice is None:
                raise RuntimeError("The voice model is unavailable.")
            voice.apply_settings(settings)
            reference = Path(settings["reference_path"])
            try:
                reference_value = str(reference.resolve().relative_to(MACHINE.voice_training.resolve())).replace("\\", "/")
            except ValueError:
                reference_value = str(reference.resolve())
            updates = {
                "chatterbox_reference": reference_value,
                "chatterbox_temperature": settings["temperature"],
                "chatterbox_top_p": settings["top_p"],
                "chatterbox_top_k": settings["top_k"],
                "chatterbox_repetition_penalty": settings["repetition_penalty"],
                "chatterbox_seed": settings["seed"],
            }
            self.runtime.config.update(updates)
            temporary = CONFIG_PATH.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(self.runtime.config, indent=2) + "\n", encoding="utf-8")
            temporary.replace(CONFIG_PATH)
        finally:
            RUN_LOCK.release()
        self.send_json(HTTPStatus.OK, {"applied": config_id, "voice": describe_voice(self.runtime.voice)})


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local Pinocchio workshop control panel.")
    parser.add_argument("--model", default="pinocchio-fast", help="Local Ollama model name.")
    parser.add_argument("--port", type=int, default=8787, help="Local browser port.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically.")
    args = parser.parse_args()

    if not UI_ROOT.is_dir():
        raise FileNotFoundError(f"UI files are missing: {UI_ROOT}")
    runtime = PipelineRuntime(args.model)
    print("Loading the local speech components...")
    runtime.load()
    ControlPanelHandler.runtime = runtime
    server = ThreadingHTTPServer(("127.0.0.1", args.port), ControlPanelHandler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"Pinocchio Workshop UI is ready at {url}")
    print("Press Ctrl+C in this window to close the UI.")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nClosing the control panel.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
