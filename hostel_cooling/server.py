import json
import re
import threading
import tempfile
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from .domain import Action, Conditions, Preference, Room, number
from .preferences import Memory
from .llm import Offline
from .optimizer import optimize
from .physics import step
from .comfort import adaptive, fuzzy_vote
from .ann import ComfortANN
from .policies import METHODS, choose

ROOT = Path(__file__).resolve().parents[1]
WEB = Path(__file__).parent / "web"


def serve(port=8765, backend=None):
    backend = backend or Offline()
    memory = Memory(ROOT/"runtime"/"pilot.sqlite3")
    ann = ComfortANN()
    job = {"state": "idle"}
    job_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            # Do not log messages or request bodies containing participant text.
            pass

        def send(self, value, status=200, kind="application/json; charset=utf-8"):
            data = value if isinstance(value, bytes) else json.dumps(value, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type",kind)
            self.send_header("Content-Length",str(len(data)))
            self.send_header("Cache-Control","no-store")
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
            self.end_headers(); self.wfile.write(data)

        def guard(self):
            if self.headers.get("Host") not in (f"127.0.0.1:{port}",f"localhost:{port}"):
                raise PermissionError("Localhost access only")
            origin = self.headers.get("Origin")
            if origin and origin not in (f"http://127.0.0.1:{port}",f"http://localhost:{port}"):
                raise PermissionError("Cross-origin requests are disabled")

        def do_GET(self):
            try:
                self.guard()
                path = urlsplit(self.path).path
                if path == "/api/status":
                    return self.send({"version":"1.0.0","backend":backend.name,"real_llm":backend.is_llm,"methods":METHODS,
                        "profile":memory.profile("local-pilot"),"data_status":"Synthetic demo / uncalibrated room"})
                if path == "/api/profile/export":
                    return self.send(memory.export("local-pilot"))
                if path == "/api/experiment/status":
                    with job_lock:
                        return self.send(dict(job))
                if path == "/api/results":
                    target = ROOT/"outputs"/"demo"/"summary.json"
                    return self.send(json.loads(target.read_text(encoding="utf-8")) if target.exists() else {"rows":[],"provenance":"No experiment yet."})
                static = {"/":(WEB/"index.html","text/html; charset=utf-8"),"/app.js":(WEB/"app.js","application/javascript; charset=utf-8"),"/style.css":(WEB/"style.css","text/css; charset=utf-8"),
                    "/report":(ROOT/"outputs"/"demo"/"report.html","text/html; charset=utf-8"),"/comparison.png":(ROOT/"outputs"/"demo"/"comparison.png","image/png")}
                if path in static and static[path][0].exists():
                    return self.send(static[path][0].read_bytes(),kind=static[path][1])
                self.send({"error":"Not found"},404)
            except PermissionError as error:
                self.send({"error":str(error)},403)
            except Exception:
                self.send({"error":"Could not read local data."},500)

        def do_POST(self):
            try:
                self.guard()
                length = int(self.headers.get("Content-Length","0"))
                if not 0 < length <= 2_000_000:
                    raise ValueError("Request body must be 1 byte to 2 MB")
                if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    raise ValueError("Content-Type must be application/json")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data,dict):
                    raise ValueError("JSON object required")
                path = urlsplit(self.path).path
                if path == "/api/consent":
                    if type(data.get("consent")) is not bool:
                        raise ValueError("consent must be boolean")
                    memory.consent("local-pilot",data["consent"])
                    return self.send(memory.profile("local-pilot"))
                if path == "/api/preferences":
                    text = data.get("message","")
                    if not isinstance(text,str) or not 1 <= len(text.strip()) <= 2000:
                        raise ValueError("Message must be 1..2000 characters")
                    if data.get("activity") not in ("study","sleep","away"):
                        raise ValueError("activity must be study/sleep/away")
                    # Check consent before any external/local LLM request.
                    if not memory.profile("local-pilot")["consent"]:
                        raise PermissionError("Enable consent before saving preferences.")
                    result = memory.update("local-pilot",text,data["activity"],backend)
                    return self.send(result)
                if path == "/api/recommend":
                    c, room, current = Conditions(**data.get("conditions",{})), Room(**data.get("room",{})), Action(**data.get("current",{}))
                    p = Preference().patched(memory.profile("local-pilot")["preference"])
                    method = data.get("method","ours")
                    action, info = choose(method,room,c,p,current,ann,backend)
                    predicted, heat = step(room,c,action)
                    trajectory = []; future=c
                    for i in range(4):
                        future,_ = step(room,future,action)
                        trajectory.append({"minutes":(i+1)*15,"temperature_c":future.indoor_c,"rh":future.rh})
                    result = {"action":action.dict(),"method":method,"method_label":METHODS[method],"optimizer":info,
                        "predicted":asdict(predicted),"heat":heat,"comfort":fuzzy_vote(predicted,room,action,p),
                        "adaptive":adaptive(c,room.fan_speed_ms[action.fan]),"trajectory":trajectory,
                        "preference":p.dict(),"provenance":"Simulated recommendation from uncalibrated model; not sensor feedback.",
                        "constraints":[s for condition,s in [(c.rain,"Rain: window closed"),(c.poor_air,"Poor outdoor air: window closed"),(not c.window_allowed,"Window unavailable: closed"),(c.activity=="sleep",f"Sleep fan limit: {p.sleep_max_fan}"),(c.activity=="away","Away: fan off")] if condition]}
                    result["suggestion_id"] = memory.save_suggestion("local-pilot",result)
                    return self.send(result)
                if path == "/api/feedback":
                    if type(data.get("accepted")) is not bool or type(data.get("suggestion_id")) is not int:
                        raise ValueError("accepted boolean and suggestion_id integer required")
                    vote = number(data.get("tsv"),-3,3,"tsv")
                    memory.feedback("local-pilot",data["suggestion_id"],data["accepted"],vote)
                    return self.send({"saved":True,"note":"Observed self-report stored separately from simulated comfort; no automatic preference change."})
                if path == "/api/experiment":
                    days = data.get("days",7)
                    if type(days) is not int or not 1 <= days <= 14:
                        raise ValueError("days must be integer 1..14")
                    with job_lock:
                        if job["state"]=="running":
                            return self.send({"error":"Experiment already running"},409)
                        job.clear();job.update(state="running",days=days)
                    def work():
                        from .experiment import run_experiment
                        try:
                            # Dashboard benchmark is always offline, clearly labeled.
                            result=run_experiment(ROOT/"outputs"/"demo",days=days)
                            with job_lock:
                                job.update(state="complete",methods=len(result["rows"]))
                        except Exception as error:
                            with job_lock:
                                job.update(state="failed",error=str(error))
                    threading.Thread(target=work,daemon=True).start()
                    return self.send({"state":"running"},202)
                if path == "/api/pilot/validate":
                    if not memory.profile("local-pilot")["consent"]:
                        raise PermissionError("Enable consent to process pilot records.")
                    content = data.get("csv")
                    if not isinstance(content,str) or len(content)>1_800_000:
                        raise ValueError("CSV text must be below 1.8 MB")
                    from .pilot import load_pilot
                    temp_path = None
                    try:
                        with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",suffix=".csv",delete=False) as f:
                            f.write(content);temp_path=Path(f.name)
                        rows=load_pilot(temp_path)
                        return self.send({"valid":True,"rows":len(rows),"provenance":rows[0][3],"note":"Schema validated; temporary CSV removed. Run CLI calibration to fit the room model."})
                    finally:
                        if temp_path:
                            temp_path.unlink(missing_ok=True)
                self.send({"error":"Not found"},404)
            except PermissionError as error:
                self.send({"error":str(error)},403)
            except (ValueError,TypeError,KeyError) as error:
                self.send({"error":str(error)},400)
            except RuntimeError as error:
                self.send({"error":str(error)},502)
            except Exception:
                self.send({"error":"Request failed; check local data and inputs."},500)

    server = ThreadingHTTPServer(("127.0.0.1",port),Handler)
    print(f"Hostel Cooling Lab: http://127.0.0.1:{port} | {backend.name}",flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
