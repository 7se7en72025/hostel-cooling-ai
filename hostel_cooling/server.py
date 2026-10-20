import json
import re
import threading
import tempfile
import secrets
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from datetime import datetime
from .domain import Action, Conditions, Preference, Room, number
from .preferences import Memory
from .llm import Offline, get_backend
from .optimizer import optimize
from .physics import step
from .comfort import adaptive, fuzzy_vote
from .ann import ComfortANN
from .policies import METHODS, choose

from .paths import ROOT

WEB = Path(__file__).parent / "web"
STUDY = ROOT / "outputs" / "study"


def serve(port=8765, backend=None):
    backend = backend or get_backend()
    memory = Memory(ROOT / "runtime" / "pilot.sqlite3")
    ann = (
        ComfortANN.load(ROOT / "models" / "comfort_ann.npz")
        if (ROOT / "models" / "comfort_ann.npz").exists()
        else ComfortANN()
    )
    job = {"state": "idle"}
    job_lock = threading.Lock()
    proposals = {}
    proposal_lock = threading.Lock()

    def selected_room(participant):
        personal = memory.room_model(participant)
        if personal:
            return personal
        fit = STUDY / "calibration.json"
        return json.loads(fit.read_text(encoding="utf-8")) if fit.exists() else None

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            # Do not log messages or request bodies containing participant text.
            pass

        def send(self, value, status=200, kind="application/json; charset=utf-8"):
            data = (
                value
                if isinstance(value, bytes)
                else json.dumps(value, allow_nan=False).encode()
            )
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'",
            )
            self.end_headers()
            self.wfile.write(data)

        def guard(self):
            self.participant = self.headers.get("X-Participant-ID", "local-pilot")
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", self.participant):
                raise ValueError(
                    "Participant alias must contain 1..40 letters, digits, underscores or hyphens"
                )
            if self.headers.get("Host") not in (
                f"127.0.0.1:{port}",
                f"localhost:{port}",
            ):
                raise PermissionError("Localhost access only")
            origin = self.headers.get("Origin")
            if origin and origin not in (
                f"http://127.0.0.1:{port}",
                f"http://localhost:{port}",
            ):
                raise PermissionError("Cross-origin requests are disabled")

        def do_GET(self):
            try:
                self.guard()
                path = urlsplit(self.path).path
                if path == "/api/status":
                    return self.send(
                        {
                            "version": "2.0.0",
                            "backend": backend.name,
                            "real_llm": backend.is_llm
                            and not getattr(backend, "replay_only", False),
                            "inference_mode": (
                                "recorded-response replay"
                                if getattr(backend, "replay_only", False)
                                else (
                                    "actual model"
                                    if backend.is_llm
                                    else "offline rules"
                                )
                            ),
                            "methods": METHODS,
                            "profile": memory.profile(self.participant),
                            "participant": self.participant,
                            "room_model": selected_room(self.participant),
                            "model_provenance": getattr(backend, "provenance", None),
                            "data_status": "Simulated research study with actual model inference",
                        }
                    )
                if path == "/api/profile/export":
                    return self.send(memory.export(self.participant))
                if path == "/api/routine":
                    from urllib.parse import parse_qs

                    query = parse_qs(urlsplit(self.path).query)
                    return self.send(
                        memory.routine(
                            self.participant,
                            float(query.get("hour", [16])[0]),
                            int(query.get("weekday", [0])[0]),
                            ROOT / "models" / "routine_model.json",
                        )
                    )
                if path == "/api/experiment/status":
                    with job_lock:
                        return self.send(dict(job))
                if path == "/api/results":
                    target = STUDY / "summary.json"
                    return self.send(
                        json.loads(target.read_text(encoding="utf-8"))
                        if target.exists()
                        else {"rows": [], "provenance": "No experiment yet."}
                    )
                if path.startswith("/evidence/"):
                    name = path.removeprefix("/evidence/")
                    allowed = {
                        "summary.json",
                        "comparison.csv",
                        "runs.csv",
                        "trajectories.csv",
                        "llm_inference.jsonl",
                        "conversation_evidence.json",
                        "language_evaluation.json",
                        "calibration.json",
                        "paired_comparisons.csv",
                        "sensitivity.csv",
                        "validation.json",
                    }
                    if name in {"calibration.png"} and (STUDY / name).is_file():
                        return self.send((STUDY / name).read_bytes(), kind="image/png")
                    if name in allowed and (STUDY / name).is_file():
                        kind = (
                            "application/json; charset=utf-8"
                            if name.endswith(".json")
                            else "text/plain; charset=utf-8"
                        )
                        return self.send((STUDY / name).read_bytes(), kind=kind)
                static = {
                    "/": (WEB / "index.html", "text/html; charset=utf-8"),
                    "/app.js": (
                        WEB / "app.js",
                        "application/javascript; charset=utf-8",
                    ),
                    "/style.css": (WEB / "style.css", "text/css; charset=utf-8"),
                    "/report": (STUDY / "report.html", "text/html; charset=utf-8"),
                    "/comparison.png": (STUDY / "comparison.png", "image/png"),
                    "/report.pdf": (
                        STUDY / "Hostel_Cooling_Project_Report.pdf",
                        "application/pdf",
                    ),
                    "/trajectories.png": (STUDY / "trajectories.png", "image/png"),
                    "/sensitivity.png": (STUDY / "sensitivity.png", "image/png"),
                }
                if path in static and static[path][0].exists():
                    return self.send(static[path][0].read_bytes(), kind=static[path][1])
                self.send({"error": "Not found"}, 404)
            except PermissionError as error:
                self.send({"error": str(error)}, 403)
            except (ValueError, TypeError) as error:
                self.send({"error": str(error)}, 400)
            except Exception:
                self.send({"error": "Could not read local data."}, 500)

        def do_POST(self):
            try:
                self.guard()
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 2_000_000:
                    raise ValueError("Request body must be 1 byte to 2 MB")
                if (
                    self.headers.get("Content-Type", "").split(";")[0]
                    != "application/json"
                ):
                    raise ValueError("Content-Type must be application/json")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("JSON object required")
                path = urlsplit(self.path).path
                if path == "/api/envelope":
                    from .envelope import estimate_envelope

                    return self.send(estimate_envelope(**data))
                if path == "/api/consent":
                    if type(data.get("consent")) is not bool:
                        raise ValueError("consent must be boolean")
                    memory.consent(self.participant, data["consent"])
                    if not data["consent"]:
                        with proposal_lock:
                            proposals.pop(self.participant, None)
                    return self.send(memory.profile(self.participant))
                if path == "/api/preferences":
                    text = data.get("message", "")
                    if not isinstance(text, str) or not 1 <= len(text.strip()) <= 2000:
                        raise ValueError("Message must be 1..2000 characters")
                    if data.get("activity") not in ("study", "sleep", "away"):
                        raise ValueError("activity must be study/sleep/away")
                    # Check consent before any external/local LLM request.
                    if not memory.profile(self.participant)["consent"]:
                        raise PermissionError(
                            "Enable consent before saving preferences."
                        )
                    result = memory.update(
                        self.participant, text, data["activity"], backend
                    )
                    return self.send(result)
                if path == "/api/preferences/preview":
                    profile = memory.profile(self.participant)
                    if not profile["consent"]:
                        raise PermissionError(
                            "Consent is required before interpreting and saving personal preferences."
                        )
                    text = data.get("message", "")
                    activity = data.get("activity")
                    if not isinstance(text, str) or not 1 <= len(text.strip()) <= 2000:
                        raise ValueError("Message must be 1..2000 characters")
                    if activity not in ("study", "sleep", "away"):
                        raise ValueError("Invalid activity")
                    preference = Preference().patched(profile["preference"])
                    patch = backend.extract(text, activity, preference)
                    proposed = preference.patched(patch)
                    if not patch:
                        return self.send(
                            {
                                "patch": {},
                                "proposal_id": None,
                                "message": "No supported preference changes found. Nothing was saved.",
                            }
                        )
                    token = secrets.token_urlsafe(24)
                    with proposal_lock:
                        proposals[self.participant] = {
                            "token": token,
                            "text": text,
                            "activity": activity,
                            "patch": patch,
                            "expected": profile["preference"],
                        }
                    return self.send(
                        {
                            "proposal_id": token,
                            "patch": patch,
                            "proposed_preference": proposed.dict(),
                            "message": "Review these model interpretations before saving. You can discard them and rephrase.",
                        }
                    )
                if path == "/api/preferences/confirm":
                    with proposal_lock:
                        proposal = proposals.get(self.participant)
                        if not proposal or not secrets.compare_digest(
                            str(data.get("proposal_id", "")), proposal["token"]
                        ):
                            raise ValueError("No matching preference proposal")
                        proposals.pop(self.participant)
                    if data.get("accept") is not True:
                        return self.send(
                            {
                                "saved": False,
                                "message": "Interpretation discarded; memory unchanged.",
                            }
                        )
                    result = memory.confirm_patch(
                        self.participant,
                        proposal["text"],
                        proposal["activity"],
                        proposal["patch"],
                        backend.name,
                        proposal["expected"],
                    )
                    return self.send(result)
                if path == "/api/recommend":
                    raw_conditions = dict(data.get("conditions", {}))
                    routine = memory.routine(
                        self.participant,
                        float(raw_conditions.get("hour", 16)) % 24,
                        datetime.now().weekday(),
                        ROOT / "models" / "routine_model.json",
                    )
                    inferred = raw_conditions.get("activity") == "auto"
                    if inferred:
                        raw_conditions["activity"] = routine["activity"]
                    saved_room = selected_room(self.participant)
                    defaults = saved_room["selected_room"] if saved_room else {}
                    c, room, current = (
                        Conditions(**raw_conditions),
                        Room(**{**defaults, **data.get("room", {})}),
                        Action(**data.get("current", {})),
                    )
                    if not inferred:
                        memory.observe_activity(
                            self.participant,
                            c.hour % 24,
                            datetime.now().weekday(),
                            c.activity,
                        )
                    p = Preference().patched(
                        memory.profile(self.participant)["preference"]
                    )
                    method = data.get("method", "ours")
                    action, info = choose(method, room, c, p, current, ann, backend)
                    predicted, heat = step(room, c, action)
                    trajectory = []
                    future = c
                    for i in range(4):
                        future, _ = step(room, future, action)
                        trajectory.append(
                            {
                                "minutes": (i + 1) * 15,
                                "temperature_c": future.indoor_c,
                                "rh": future.rh,
                            }
                        )
                    result = {
                        "action": action.dict(),
                        "method": method,
                        "method_label": METHODS[method],
                        "optimizer": info,
                        "predicted": asdict(predicted),
                        "heat": heat,
                        "comfort": fuzzy_vote(predicted, room, action, p),
                        "adaptive": adaptive(c, room.fan_speed_ms[action.fan]),
                        "trajectory": trajectory,
                        "preference": p.dict(),
                        "provenance": "Prediction from a simplified calibrated/specified RC model; input provenance selected by the researcher.",
                        "routine": routine,
                        "activity_inferred": inferred,
                        "constraints": [
                            s
                            for condition, s in [
                                (c.rain, "Rain: window closed"),
                                (c.poor_air, "Poor outdoor air: window closed"),
                                (not c.window_allowed, "Window unavailable: closed"),
                                (
                                    c.activity == "sleep",
                                    f"Sleep fan limit: {p.sleep_max_fan}",
                                ),
                                (c.activity == "away", "Away: fan off"),
                            ]
                            if condition
                        ],
                    }
                    result["suggestion_id"] = memory.save_suggestion(
                        self.participant, result
                    )
                    return self.send(result)
                if path == "/api/feedback":
                    if (
                        type(data.get("accepted")) is not bool
                        or type(data.get("suggestion_id")) is not int
                    ):
                        raise ValueError(
                            "accepted boolean and suggestion_id integer required"
                        )
                    vote = number(data.get("tsv"), -3, 3, "tsv")
                    memory.feedback(
                        self.participant, data["suggestion_id"], data["accepted"], vote
                    )
                    return self.send(
                        {
                            "saved": True,
                            "note": "Observed self-report stored separately from simulated comfort; no automatic preference change.",
                        }
                    )
                if path == "/api/experiment":
                    days = data.get("days", 7)
                    if type(days) is not int or not 1 <= days <= 14:
                        raise ValueError("days must be integer 1..14")
                    with job_lock:
                        if job["state"] == "running":
                            return self.send(
                                {"error": "Experiment already running"}, 409
                            )
                        job.clear()
                        job.update(state="running", days=days)

                    def work():
                        from .study import run_study

                        try:
                            kind = (
                                "local"
                                if backend.__class__.__name__ == "LocalLLM"
                                else "ollama" if backend.is_llm else "offline"
                            )
                            result = run_study(STUDY, days=days, backend_kind=kind)
                            with job_lock:
                                job.update(
                                    state="complete", methods=len(result["rows"])
                                )
                        except Exception as error:
                            with job_lock:
                                job.update(state="failed", error=str(error))

                    threading.Thread(target=work, daemon=True).start()
                    return self.send({"state": "running"}, 202)
                if path in ("/api/pilot/validate", "/api/pilot/calibrate"):
                    if not memory.profile(self.participant)["consent"]:
                        raise PermissionError(
                            "Enable consent to process pilot records."
                        )
                    content = data.get("csv")
                    if not isinstance(content, str) or len(content) > 1_800_000:
                        raise ValueError("CSV text must be below 1.8 MB")
                    from .pilot import load_pilot

                    temp_path = None
                    try:
                        with tempfile.NamedTemporaryFile(
                            mode="w", encoding="utf-8", suffix=".csv", delete=False
                        ) as f:
                            f.write(content)
                            temp_path = Path(f.name)
                        rows = load_pilot(temp_path)
                        if path.endswith("calibrate"):
                            from .pilot import calibrate

                            fit_path = temp_path.with_suffix(".json")
                            try:
                                result = calibrate(temp_path, fit_path)
                                memory.save_room_model(self.participant, result)
                                return self.send(result)
                            finally:
                                fit_path.unlink(missing_ok=True)
                        return self.send(
                            {
                                "valid": True,
                                "rows": len(rows),
                                "provenance": rows[0][3],
                                "note": "Schema validated; temporary CSV removed. Run CLI calibration to fit the room model.",
                            }
                        )
                    finally:
                        if temp_path:
                            temp_path.unlink(missing_ok=True)
                self.send({"error": "Not found"}, 404)
            except PermissionError as error:
                self.send({"error": str(error)}, 403)
            except (ValueError, TypeError, KeyError) as error:
                self.send({"error": str(error)}, 400)
            except RuntimeError as error:
                self.send({"error": str(error)}, 502)
            except Exception:
                self.send(
                    {"error": "Request failed; check local data and inputs."}, 500
                )

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Hostel Cooling Lab: http://127.0.0.1:{port} | {backend.name}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
