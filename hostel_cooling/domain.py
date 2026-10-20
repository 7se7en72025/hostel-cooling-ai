from dataclasses import asdict, dataclass, field, replace
import math


def number(value, low, high, name):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not low <= value <= high
    ):
        raise ValueError(f"{name} must be a finite number between {low} and {high}")
    return float(value)


@dataclass(frozen=True)
class Action:
    fan: int = 0
    window: float = 0
    curtain: int = 0  # 1 = closed

    def __post_init__(self):
        if type(self.fan) is not int or self.fan not in range(4):
            raise ValueError("fan must be an integer 0..3")
        if self.window not in (0, 0.5, 1) or isinstance(self.window, bool):
            raise ValueError("window must be 0, 0.5, or 1")
        if type(self.curtain) is not int or self.curtain not in (0, 1):
            raise ValueError("curtain must be 0 or 1")

    def dict(self):
        return asdict(self)


@dataclass(frozen=True)
class Room:
    area_m2: float = 12
    height_m: float = 3
    ua_w_k: float = 45
    capacity_j_k: float = 2_000_000  # air + effective fabric/furniture capacitance
    window_m2: float = 2
    glazing_g: float = 0.6
    orientation: str = "west"
    fan_w: tuple = (0, 18, 38, 65)
    fan_speed_ms: tuple = (0.1, 0.4, 0.8, 1.2)

    def __post_init__(self):
        for name, lo, hi in [
            ("area_m2", 4, 100),
            ("height_m", 2, 5),
            ("ua_w_k", 1, 500),
            ("capacity_j_k", 100_000, 50_000_000),
            ("window_m2", 0.1, 15),
            ("glazing_g", 0.05, 1),
        ]:
            number(getattr(self, name), lo, hi, name)
        if self.orientation not in ("north", "south", "east", "west"):
            raise ValueError("orientation must be north/south/east/west")
        if len(self.fan_w) != 4 or len(self.fan_speed_ms) != 4:
            raise ValueError("four calibrated fan levels are required")
        for value in self.fan_w:
            number(value, 0, 300, "fan power")
        for value in self.fan_speed_ms:
            number(value, 0, 2, "fan air speed")


@dataclass(frozen=True)
class Conditions:
    indoor_c: float = 31
    outdoor_c: float = 29
    rh: float = 55
    outdoor_rh: float = 50
    solar_w_m2: float = 400  # facade incident irradiance before orientation proxy
    wind_ms: float = 1.5
    hour: float = 16
    activity: str = "study"
    running_mean_c: float = 29
    rain: bool = False
    poor_air: bool = False
    window_allowed: bool = True

    def __post_init__(self):
        for name, lo, hi in [
            ("indoor_c", 5, 50),
            ("outdoor_c", -10, 55),
            ("rh", 1, 100),
            ("outdoor_rh", 1, 100),
            ("solar_w_m2", 0, 1400),
            ("wind_ms", 0, 15),
            ("hour", 0, 24),
            ("running_mean_c", -10, 45),
        ]:
            number(getattr(self, name), lo, hi, name)
        if self.activity not in ("study", "sleep", "away"):
            raise ValueError("activity must be study, sleep, or away")
        for name in ("rain", "poor_air", "window_allowed"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be boolean")


@dataclass
class Preference:
    target_c: float = 28
    tolerance_c: float = 2
    sleep_max_fan: int = 1
    noise_weight: float = 0.6
    energy_weight: float = 0.25
    study_airflow: bool = False
    activity_targets: dict = field(default_factory=dict)

    def target(self, activity):
        return self.activity_targets.get(activity, self.target_c)

    def dict(self):
        return asdict(self)

    def patched(self, patch):
        allowed = {
            "target_c",
            "tolerance_c",
            "sleep_max_fan",
            "noise_weight",
            "energy_weight",
            "study_airflow",
            "activity_targets",
        }
        if not isinstance(patch, dict) or set(patch) - allowed:
            raise ValueError("unsupported preference fields")
        p = replace(self, activity_targets=dict(self.activity_targets))
        for key, value in patch.items():
            if key == "activity_targets":
                if not isinstance(value, dict) or set(value) - {
                    "study",
                    "sleep",
                    "away",
                }:
                    raise ValueError("invalid activity targets")
                for a, t in value.items():
                    p.activity_targets[a] = number(t, 20, 34, "target")
            elif key == "study_airflow":
                if type(value) is not bool:
                    raise ValueError("study_airflow must be boolean")
                p.study_airflow = value
            elif key == "sleep_max_fan":
                if type(value) is not int or value not in range(4):
                    raise ValueError("sleep_max_fan must be 0..3")
                p.sleep_max_fan = value
            else:
                lo, hi = {
                    "target_c": (20, 34),
                    "tolerance_c": (0.5, 4),
                    "noise_weight": (0, 3),
                    "energy_weight": (0, 3),
                }[key]
                setattr(p, key, number(value, lo, hi, key))
        return p


def legal_actions(c, p):
    windows = (0,) if c.rain or c.poor_air or not c.window_allowed else (0, 0.5, 1)
    fans = (
        (0,)
        if c.activity == "away"
        else range(1 + (p.sleep_max_fan if c.activity == "sleep" else 3))
    )
    return [Action(f, w, s) for f in fans for w in windows for s in (0, 1)]
