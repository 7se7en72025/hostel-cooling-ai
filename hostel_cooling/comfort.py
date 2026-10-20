"""Heuristic fuzzy comfort and a separately scoped adaptive reference."""

import math


def fuzzy_vote(c, room, action, preference):
    speed = min(1.8, room.fan_speed_ms[action.fan] + 0.12 * action.window * c.wind_ms)
    relief = 1.6 * max(0, speed - 0.1) ** 0.6 if c.indoor_c > 25 else 0
    humidity_penalty = max(0, c.rh - 60) * 0.018
    error = c.indoor_c - relief + humidity_penalty - preference.target(c.activity)
    # Five overlapping triangular sets; zero-order Sugeno weighted consequent.
    centers = (-4, -2, 0, 2, 4)
    clipped = max(-4, min(4, error))
    memberships = [max(0, 1 - abs(clipped - center) / 2) for center in centers]
    vote = sum(m * v for m, v in zip(memberships, (-3, -1.5, 0, 1.5, 3))) / sum(
        memberships
    )
    return {
        "tsv_proxy": vote,
        "effective_c": c.indoor_c - relief + humidity_penalty,
        "comfort_score": max(0, 100 * (1 - abs(vote) / 3)),
        "violation": abs(error) > preference.tolerance_c,
        "memberships": dict(
            zip(("cold", "cool", "neutral", "warm", "hot"), memberships)
        ),
    }


def adaptive(c, speed=0.1):
    # Simplified ASHRAE adaptive equation; sleep is outside documented metabolic scope.
    valid = (
        10 < c.running_mean_c < 33.5 and c.activity == "study" and 10 < c.indoor_c < 40
    )
    if not valid:
        return {
            "applicable": False,
            "reason": "Requires study/awake activity, 10<T_running<33.5 C, and 10<T_indoor<40 C.",
        }
    neutral = 0.31 * c.running_mean_c + 17.8
    extension = (
        (2.2 if speed >= 1.2 else 1.8 if speed >= 0.9 else 1.2 if speed >= 0.6 else 0)
        if c.indoor_c >= 25
        else 0
    )
    lo, hi = neutral - 3.5, neutral + 3.5 + extension
    return {
        "applicable": True,
        "neutral_c": neutral,
        "lower_80_c": lo,
        "upper_80_c": hi,
        "within_80": lo <= c.indoor_c <= hi,
        "operative_proxy_c": c.indoor_c,
        "note": "Air temperature approximates operative temperature; not a compliance determination.",
    }


def simulated_response(c, room, action, hidden):
    """Synthetic occupant oracle differs from the controller's fuzzy model; still circular simulation."""
    speed = room.fan_speed_ms[action.fan] + 0.1 * action.window * c.wind_ms
    relief = 1.8 * math.sqrt(max(0, speed - 0.1)) if c.indoor_c > 25 else 0
    sensation = max(
        -3,
        min(
            3,
            (
                c.indoor_c
                - relief
                + 0.025 * max(0, c.rh - 55)
                - hidden.target(c.activity)
            )
            / 1.8,
        ),
    )
    noisy = c.activity == "sleep" and action.fan > hidden.sleep_max_fan
    airflow_missing = c.activity == "study" and hidden.study_airflow and action.fan == 0
    accepted = abs(sensation) <= 1.2 and not noisy and not airflow_missing
    return sensation, accepted
