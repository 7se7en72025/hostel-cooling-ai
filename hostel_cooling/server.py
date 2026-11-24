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
from .llm import LocalLLM, get_backend
from .physics import step
from .comfort import adaptive, fuzzy_vote
from .ann import ComfortANN
from .policies import METHODS, choose

from .paths import ROOT

WEB = Path(__file__).parent / "web"
STUDY = ROOT / "outputs" / "study"
STUDY_RUNS = ROOT / "build" / "study-runs"
EVIDENCE = {
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
    "hypothesis_assessment.json",
    "preference_change_phases.csv",
    "PRESENTATION_NOTES.md",
    "presentation_data.json",
    "reproducibility_verification.json",
    "submission_verification.json",
}
RUN_FILES = {
    "report.html": "text/html; charset=utf-8",
    "Hostel_Cooling_Project_Report.pdf": "application/pdf",
    **{
        name + ".png": "image/png"
        for name in ("calibration", "comparison", "trajectories", "sensitivity")
    },
}
FINAL_RUN_FILES = (
    "report.html",
    "Hostel_Cooling_Project_Report.pdf",
    "presentation_data.json",
)


def forecast(room, conditions, action):
    predicted, heat = step(room, conditions, action)
    future = predicted
    trajectory = []
    for minutes in (15, 30, 45, 60):
        if minutes > 15:
            future, _ = step(room, future, action)
        trajectory.append(
            {"minutes": minutes, "temperature_c": future.indoor_c, "rh": future.rh}
        )
    return predicted, heat, trajectory


def study_job(directory, summary):
    return {
        "state": "complete",
        "days": summary["days_per_seed"],
        "methods": len(summary["rows"]),
        "all_checks_passed": summary["complete"],
        "report_url": f"/study-runs/{directory.name}/report.html",
    }


def latest_study_job():
    latest = {"state": "idle"}
    latest_changed = -1
    for summary_path in STUDY_RUNS.glob("*/summary.json"):
        directory = summary_path.parent
        if not re.fullmatch(r"[a-f0-9]{16}", directory.name):
            continue
        try:
            report_changed = (directory / "report.html").stat().st_mtime_ns
            if report_changed <= latest_changed or not all(
                (directory / name).is_file() for name in FINAL_RUN_FILES
            ):
                continue
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            latest = study_job(directory, summary)
        except (OSError, ValueError, KeyError, TypeError):
            continue
        latest_changed = report_changed
    return latest


def serve(port=8765, backend=None):
    backend = backend or get_backend()
    replay = getattr(backend, "replay_only", False)
    live_model = backend.is_llm and not replay
    study_available = isinstance(backend, LocalLLM) and live_model
    memory = Memory(ROOT / "runtime" / "pilot.sqlite3")
    ann = (
        ComfortANN.load(ROOT / "models" / "comfort_ann.npz")
        if (ROOT / "models" / "comfort_ann.npz").exists()
        else ComfortANN()
    )
    job = latest_study_job()
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

        def send_file(self, directory, name, kinds):
            kind = kinds.get(name)
            if name in EVIDENCE:
                kind = (
                    "application/json; charset=utf-8"
                    if name.endswith(".json")
                    else "text/plain; charset=utf-8"
                )
            target = directory / name
            if kind and target.is_file():
                return self.send(target.read_bytes(), kind=kind)
            return self.send({"error": "Not found"}, 404)

        def guard(self):
            self.participant = self.headers.get("X-Participant-ID", "local-pilot")
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", self.participant):
                raise ValueError(
                    "Participant alias must contain 1..40 letters, digits, underscores or hyphens"
                )
            hosts = (
                f"127.0.0.1:{self.server.server_port}",
                f"localhost:{self.server.server_port}",
            )
            if self.headers.get("Host") not in hosts:
                raise PermissionError("Localhost access only")
            origin = self.headers.get("Origin")
            if origin and origin not in tuple(f"http://{host}" for host in hosts):
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
                            "real_llm": live_model,
                            "study_available": study_available,
                            "inference_mode": (
                                "recorded-response replay"
                                if replay
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
                            "data_status": "Submitted simulated research study",
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
                if path == "/api/rain-example":
                    defaults = Conditions()
                    room, preference, current = Room(), Preference(), Action()
                    cases = []
                    for rain in (False, True):
                        conditions = Conditions(rain=rain)
                        action, _ = choose(
                            "ours", room, conditions, preference, current
                        )
                        cases.append({"rain": rain, "action": action.dict()})
                    return self.send(
                        {
                            "indoor_c": defaults.indoor_c,
                            "outdoor_c": defaults.outdoor_c,
                            "cases": cases,
                        }
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
                    return self.send_file(STUDY, name, {"calibration.png": "image/png"})
                match = re.fullmatch(r"/study-runs/([a-f0-9]{16})/([^/]+)", path)
                if match:
                    run_id, name = match.groups()
                    directory = STUDY_RUNS / run_id
                    if all(
                        (directory / artifact).is_file() for artifact in FINAL_RUN_FILES
                    ):
                        return self.send_file(directory, name, RUN_FILES)
                static = {
                    "/": (WEB / "index.html", "text/html; charset=utf-8"),
                    "/project-overview.pdf": (
                        WEB.parent / "resources" / "Hostel_Cooling_Overview.pdf",
                        "application/pdf",
                    ),
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
                    "/presentation.pptx": (
                        STUDY / "Hostel_Cooling_Final_Presentation.pptx",
                        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    ),
                    "/presentation.pdf": (
                        STUDY / "Hostel_Cooling_Final_Presentation.pdf",
                        "application/pdf",
                    ),
                    "/viva.pdf": (
                        STUDY / "Hostel_Cooling_Viva_Guide.pdf",
                        "application/pdf",
                    ),
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
                    with proposal_lock:
                        memory.consent(self.participant, data["consent"])
                        if not data["consent"]:
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
                    text = data.get("message", "")
                    activity = data.get("activity")
                    if not isinstance(text, str) or not 1 <= len(text.strip()) <= 2000:
                        raise ValueError("Message must be 1..2000 characters")
                    if activity not in ("study", "sleep", "away"):
                        raise ValueError("Invalid activity")
                    with proposal_lock:
                        profile = memory.profile(self.participant)
                        if not profile["consent"]:
                            raise PermissionError(
                                "Consent is required before interpreting and saving personal preferences."
                            )
                        proposal = {
                            "token": secrets.token_urlsafe(24),
                            "expected": profile["preference"],
                        }
                        proposals[self.participant] = proposal
                    preference = Preference().patched(proposal["expected"])
                    try:
                        patch = backend.extract(text, activity, preference)
                        proposed = preference.patched(patch)
                    except Exception:
                        with proposal_lock:
                            if proposals.get(self.participant) is proposal:
                                proposals.pop(self.participant)
                        raise
                    with proposal_lock:
                        if proposals.get(self.participant) is not proposal:
                            return self.send(
                                {
                                    "error": "This review expired. Interpret your preference again."
                                },
                                409,
                            )
                        if patch:
                            proposal.update(text=text, activity=activity, patch=patch)
                        else:
                            proposals.pop(self.participant)
                    if not patch:
                        return self.send(
                            {
                                "patch": {},
                                "proposal_id": None,
                                "message": "No supported preference changes found. Nothing was saved.",
                            }
                        )
                    return self.send(
                        {
                            "proposal_id": proposal["token"],
                            "patch": patch,
                            "proposed_preference": proposed.dict(),
                            "message": "Review these model interpretations before saving. You can discard them and rephrase.",
                        }
                    )
                if path == "/api/preferences/confirm":
                    accept = data.get("accept")
                    if type(accept) is not bool:
                        raise ValueError("accept must be boolean")
                    with proposal_lock:
                        proposal = proposals.get(self.participant)
                        if (
                            not proposal
                            or "patch" not in proposal
                            or not secrets.compare_digest(
                                str(data.get("proposal_id", "")), proposal["token"]
                            )
                        ):
                            raise ValueError("No matching preference proposal")
                        proposals.pop(self.participant)
                        if accept:
                            result = memory.confirm_patch(
                                self.participant,
                                proposal["text"],
                                proposal["activity"],
                                proposal["patch"],
                                backend.name,
                                proposal["expected"],
                            )
                    if not accept:
                        return self.send(
                            {
                                "saved": False,
                                "message": "Interpretation discarded; memory unchanged.",
                            }
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
                    predicted, heat, trajectory = forecast(room, c, action)
                    fixed_action, _ = choose("fixed", room, c, p, current)
                    try:
                        _, fixed_heat, fixed_trajectory = forecast(
                            room, c, fixed_action
                        )
                    except ValueError:
                        fixed = None
                    else:
                        fixed = {
                            "action": fixed_action.dict(),
                            "trajectory": fixed_trajectory,
                            "one_hour_fan_wh": 4 * fixed_heat["fan_wh"],
                        }
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
                        "one_hour_fan_wh": 4 * heat["fan_wh"],
                        "fixed_schedule": fixed,
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
                    if not study_available:
                        raise PermissionError(
                            "Running a new study requires the pinned local model."
                        )
                    days = data.get("days", 7)
                    if type(days) is not int or not 1 <= days <= 14:
                        raise ValueError("days must be integer 1..14")
                    with job_lock:
                        if job["state"] == "running":
                            return self.send(
                                {"error": "Experiment already running"}, 409
                            )
                        previous_report = job.get("report_url")
                        job.clear()
                        job.update(
                            state="running", days=days, report_url=previous_report
                        )

                    def work():
                        from .study import run_study

                        try:
                            run_id = secrets.token_hex(8)
                            output = STUDY_RUNS / run_id
                            output.mkdir(parents=True)
                            result = run_study(output, days=days)
                            with job_lock:
                                job.update(study_job(output, result))
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
    print(
        f"Hostel Cooling Lab: http://127.0.0.1:{server.server_port} | {backend.name}",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
