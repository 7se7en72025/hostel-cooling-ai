"""Consent-gated, evidence-backed preference memory; local SQLite storage."""

import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from .domain import Preference


def offline_patch(text, activity, preference):
    """Limited explicit phrase parser. Never presented as an LLM."""
    t = text.lower().strip()
    patch = {}
    target = re.search(
        r"(?:prefer|target|comfortable at|temperature)\s*(?:is\s*)?(\d{2}(?:\.\d)?)\s*(?:°?c|degrees)?\b",
        t,
    )
    negated_target = re.search(
        r"\b(?:don't|do not|never|not)\s+(?:really\s+)?(?:prefer|want|comfortable|target)",
        t,
    )
    if target and not negated_target:
        patch["activity_targets"] = {activity: float(target.group(1))}
    elif re.search(r"\b(too hot|feeling hot|garmi|garam)\b", t) and not re.search(
        r"\b(not|no|never)\s+(?:too\s+)?hot\b", t
    ):
        patch["activity_targets"] = {
            activity: max(20, preference.target(activity) - 0.5)
        }
    elif re.search(r"\b(too cold|feeling cold|thand)\b", t) and not re.search(
        r"\b(not|no|never)\s+(?:too\s+)?cold\b", t
    ):
        patch["activity_targets"] = {
            activity: min(34, preference.target(activity) + 0.5)
        }
    if re.search(r"\b(quiet|noisy|noise|slow fan|low fan)\b", t) and not re.search(
        r"\b(don't|do not|not)\s+(?:need|want|mind|prefer)?\s*(?:a\s+)?(?:quiet|noise)",
        t,
    ):
        if activity == "sleep" or "sleep" in t:
            patch.update(sleep_max_fan=1, noise_weight=1.2)
    if re.search(r"\b(fan off|no fan|without fan)\b", t) and (
        activity == "sleep" or "sleep" in t
    ):
        patch["sleep_max_fan"] = 0
    if "airflow" in t or "breeze" in t:
        if activity == "study" or "study" in t or "studying" in t:
            patch["study_airflow"] = not bool(
                re.search(r"\b(no|not|avoid|don't|do not)\b", t)
            )
    if "save energy" in t or "less electricity" in t:
        patch["energy_weight"] = 0.7
    return patch


class Memory:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript(
                """
            CREATE TABLE IF NOT EXISTS profiles (id TEXT PRIMARY KEY, consent INTEGER, preference TEXT);
            CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, participant TEXT, created TEXT,
                activity TEXT, message TEXT, patch TEXT, backend TEXT);
            CREATE TABLE IF NOT EXISTS suggestions (id INTEGER PRIMARY KEY, participant TEXT,
                created TEXT, payload TEXT);
            CREATE TABLE IF NOT EXISTS feedback (id INTEGER PRIMARY KEY, participant TEXT,
                suggestion_id INTEGER UNIQUE, created TEXT, accepted INTEGER, tsv REAL);
            CREATE TABLE IF NOT EXISTS activity_observations (id INTEGER PRIMARY KEY, participant TEXT,
                created TEXT, hour REAL, weekday INTEGER, activity TEXT);
            CREATE TABLE IF NOT EXISTS room_models (participant TEXT PRIMARY KEY, payload TEXT);
            """
            )

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def profile(self, participant):
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM profiles WHERE id=?", (participant,)
            ).fetchone()
            events = db.execute(
                "SELECT created,activity,message,patch,backend FROM events WHERE participant=? ORDER BY id DESC LIMIT 20",
                (participant,),
            ).fetchall()
        return {
            "consent": bool(row and row["consent"]),
            "preference": json.loads(row["preference"]) if row else Preference().dict(),
            "events": [dict(e, patch=json.loads(e["patch"])) for e in events],
        }

    def consent(self, participant, value):
        if not value:
            self.erase(participant)
            return
        with self.connect() as db:
            db.execute(
                "INSERT INTO profiles VALUES (?,1,?) ON CONFLICT(id) DO UPDATE SET consent=1",
                (participant, json.dumps(Preference().dict())),
            )

    def update(self, participant, text, activity, backend):
        # Extract and commit under the same lock to prevent lost concurrent revisions.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM profiles WHERE id=?", (participant,)
            ).fetchone()
            if not row or not row["consent"]:
                raise PermissionError(
                    "Consent is required before saving feedback or preferences."
                )
            p = Preference().patched(json.loads(row["preference"]))
            patch = backend.extract(text, activity, p)
            p = p.patched(patch)
            db.execute(
                "UPDATE profiles SET preference=? WHERE id=?",
                (json.dumps(p.dict()), participant),
            )
            db.execute(
                "INSERT INTO events VALUES(NULL,?,?,?,?,?,?)",
                (participant, now(), activity, text, json.dumps(patch), backend.name),
            )
        return {
            "patch": patch,
            "preference": p.dict(),
            "backend": backend.name,
            "message": (
                "Preference updated."
                if patch
                else "No supported explicit preference found; memory unchanged. Try: 'I prefer 27 C' or 'I need quiet when sleeping'."
            ),
        }

    def save_suggestion(self, participant, payload):
        with self.connect() as db:
            row = db.execute(
                "SELECT consent FROM profiles WHERE id=?", (participant,)
            ).fetchone()
            if not row or not row[0]:
                return None
            return db.execute(
                "INSERT INTO suggestions VALUES(NULL,?,?,?)",
                (participant, now(), json.dumps(payload)),
            ).lastrowid

    def confirm_patch(
        self, participant, text, activity, patch, backend_name, expected_preference
    ):
        """Commit a reviewed interpretation only if consent/context still match."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM profiles WHERE id=?", (participant,)
            ).fetchone()
            if not row or not row["consent"]:
                raise PermissionError(
                    "Consent was withdrawn; this proposal cannot be saved."
                )
            before = json.loads(row["preference"])
            if before != expected_preference:
                raise ValueError(
                    "Preferences changed since this proposal. Generate a new interpretation."
                )
            updated = Preference().patched(before).patched(patch)
            db.execute(
                "UPDATE profiles SET preference=? WHERE id=?",
                (json.dumps(updated.dict()), participant),
            )
            db.execute(
                "INSERT INTO events VALUES(NULL,?,?,?,?,?,?)",
                (
                    participant,
                    now(),
                    activity,
                    text,
                    json.dumps(patch),
                    backend_name + " / user confirmed",
                ),
            )
        return {
            "patch": patch,
            "preference": updated.dict(),
            "backend": backend_name,
            "message": "Reviewed preference changes saved.",
        }

    def feedback(self, participant, suggestion_id, accepted, tsv):
        with self.connect() as db:
            if not db.execute(
                "SELECT id FROM suggestions WHERE id=? AND participant=?",
                (suggestion_id, participant),
            ).fetchone():
                raise ValueError("No saved suggestion belongs to this participant.")
            db.execute(
                "INSERT INTO feedback VALUES(NULL,?,?,?,?,?) ON CONFLICT(suggestion_id) DO UPDATE SET accepted=excluded.accepted,tsv=excluded.tsv,created=excluded.created",
                (participant, suggestion_id, now(), int(accepted), tsv),
            )

    def export(self, participant):
        result = self.profile(participant)
        with self.connect() as db:
            result["suggestions"] = [
                dict(r, payload=json.loads(r["payload"]))
                for r in db.execute(
                    "SELECT id,created,payload FROM suggestions WHERE participant=?",
                    (participant,),
                )
            ]
            result["feedback"] = [
                dict(r)
                for r in db.execute(
                    "SELECT suggestion_id,created,accepted,tsv FROM feedback WHERE participant=?",
                    (participant,),
                )
            ]
            # Export all evidence; profile display is intentionally capped at 20.
            result["events"] = [
                dict(r, patch=json.loads(r["patch"]))
                for r in db.execute(
                    "SELECT created,activity,message,patch,backend FROM events WHERE participant=?",
                    (participant,),
                )
            ]
            result["activity_observations"] = [
                dict(r)
                for r in db.execute(
                    "SELECT created,hour,weekday,activity FROM activity_observations WHERE participant=?",
                    (participant,),
                )
            ]
            result["room_model"] = self.room_model(participant)
        return result

    def observe_activity(self, participant, hour, weekday, activity):
        from .routines import RoutineModel

        check = RoutineModel()
        check.observe(hour, weekday, activity)
        with self.connect() as db:
            row = db.execute(
                "SELECT consent FROM profiles WHERE id=?", (participant,)
            ).fetchone()
            if row and row[0]:
                db.execute(
                    "INSERT INTO activity_observations VALUES(NULL,?,?,?,?,?)",
                    (participant, now(), hour, weekday, activity),
                )

    def routine(self, participant, hour, weekday=0, prior_path=None):
        from .routines import RoutineModel

        prior = (
            RoutineModel.load(prior_path)
            if prior_path and Path(prior_path).exists()
            else RoutineModel()
        )
        with self.connect() as db:
            rows = db.execute(
                "SELECT hour,weekday,activity FROM activity_observations WHERE participant=?",
                (participant,),
            ).fetchall()
        if len(rows) >= 8:
            personal = RoutineModel(prior.counts * 0.15)
            for row in rows:
                personal.observe(row["hour"], row["weekday"], row["activity"])
            result = personal.predict(hour, weekday)
            result["source"] = "personal observations with a weak synthetic prior"
        else:
            result = prior.predict(hour, weekday)
            result["source"] = (
                "synthetic pretrained prior; insufficient personal history"
            )
        result["personal_observations"] = len(rows)
        return result

    def room_model(self, participant):
        with self.connect() as db:
            row = db.execute(
                "SELECT payload FROM room_models WHERE participant=?", (participant,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def save_room_model(self, participant, result):
        with self.connect() as db:
            row = db.execute(
                "SELECT consent FROM profiles WHERE id=?", (participant,)
            ).fetchone()
            if not row or not row[0]:
                raise PermissionError(
                    "Consent required to save a calibrated room model"
                )
            db.execute(
                "INSERT INTO room_models VALUES(?,?) ON CONFLICT(participant) DO UPDATE SET payload=excluded.payload",
                (participant, json.dumps(result)),
            )

    def erase(self, participant):
        with self.connect() as db:
            for table in (
                "profiles",
                "events",
                "suggestions",
                "feedback",
                "activity_observations",
                "room_models",
            ):
                db.execute(
                    f"DELETE FROM {table} WHERE {'id' if table == 'profiles' else 'participant'}=?",
                    (participant,),
                )


def now():
    return datetime.now(timezone.utc).isoformat()
