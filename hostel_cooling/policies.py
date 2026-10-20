from dataclasses import replace
from .domain import Action, Preference, legal_actions
from .comfort import adaptive
from .optimizer import optimize, objective
from .physics import step

METHODS = {
    "fixed": "Fixed schedule (F423 B1; illustrative, not GRIHA/LEED certification)",
    "expert": "Expert rules (F417 B1)",
    "adaptive": "Adaptive reference + rules outside scope (B2)",
    "ann": "Synthetic-trained ANN (F417 B3)",
    "physics": "Room model only (F423 B3)",
    "generic_llm": "Generic LLM, no memory or room physics (B4)",
    "memoryless": "Memoryless rule surrogate (offline diagnostic, NOT B4)",
    "ours": "Preference memory + fuzzy comfort + RC + GA",
    "survey": "One-time preference survey + RC + GA (ablation)",
    "no_physics": "LLM preference memory without RC forecast (ablation)",
}


def choose(method, room, c, p, current, ann=None, llm=None, seed=7):
    # All methods receive identical explicit sleep/safety constraints, not hidden preferences.
    feasible = legal_actions(c, p)
    if method == "no_physics":
        from .comfort import fuzzy_vote

        def instant_score(a):
            comfort = (
                0
                if c.activity == "away"
                else abs(fuzzy_vote(c, room, a, p)["tsv_proxy"])
            )
            energy = p.energy_weight * room.fan_w[a.fan] / 65
            noise = (
                p.noise_weight
                * (a.fan / 3) ** 2
                * (1 if c.activity == "sleep" else 0.15)
            )
            return comfort + energy + noise

        return min(feasible, key=instant_score), {}
    if method in ("ours", "survey"):
        result = optimize(room, c, p, current, seed=seed)
        return Action(**result["action"]), result
    if method == "generic_llm":
        if llm is None or not llm.is_llm:
            raise RuntimeError(
                "Generic LLM baseline unavailable; configure a real LLM."
            )
        return llm.generic_action(c, feasible), {}
    shade = int(c.solar_w_m2 > 100)
    window = int(c.outdoor_c < c.indoor_c and c.outdoor_rh < 80)
    if method == "fixed":
        action = Action(
            0 if c.activity == "away" else 2,
            int(c.hour < 8 or c.hour >= 20),
            int(8 <= c.hour < 19),
        )
    elif method in ("expert", "memoryless"):
        fan = (
            0
            if c.activity == "away"
            else (
                3
                if c.indoor_c > 32
                else 2 if c.indoor_c > 29 else 1 if c.indoor_c > 27 else 0
            )
        )
        action = Action(fan, window, shade)
    elif method == "adaptive":
        eligible = [a for a in feasible if a.window == window and a.curtain == shade]
        if not eligible:
            eligible = feasible
        scored = []
        for a in eligible:
            ref = adaptive(c, room.fan_speed_ms[a.fan])
            if ref["applicable"]:
                penalty = max(
                    0, c.indoor_c - ref["upper_80_c"], ref["lower_80_c"] - c.indoor_c
                )
                scored.append((penalty + 0.1 * room.fan_w[a.fan] / 65, a))
        if scored:
            return min(scored, key=lambda x: x[0])[1], {"adaptive_applicable": True}
        fallback, _ = choose("expert", room, c, p, current)
        return fallback, {"adaptive_applicable": False}
    elif method == "physics":
        generic = Preference(sleep_max_fan=p.sleep_max_fan)
        return min(feasible, key=lambda a: objective(room, c, generic, a, current)), {}
    elif method == "ann":

        def score(a):
            # ANN baseline has current conditions, no RC lookahead.
            comfort = 0 if c.activity == "away" else abs(ann.predict(c, room, a))
            return (
                comfort
                + 0.2 * room.fan_w[a.fan] / 65
                + 0.1 * (a.window != window)
                + 0.1 * (a.curtain != shade)
            )

        return min(feasible, key=score), {}
    else:
        raise ValueError("Unknown policy")
    # Project rules onto common feasible space; never bypass rain/security constraints.
    if action not in feasible:
        action = min(
            feasible,
            key=lambda a: abs(a.fan - action.fan)
            + abs(a.window - action.window)
            + abs(a.curtain - action.curtain),
        )
    return action, {}
