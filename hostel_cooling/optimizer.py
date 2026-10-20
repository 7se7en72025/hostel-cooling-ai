import random
from dataclasses import asdict
from .domain import Action, legal_actions
from .physics import step
from .comfort import fuzzy_vote


def objective(room, c, p, action, current=Action(), horizon=4):
    cost = 0
    for _ in range(horizon):
        c, heat = step(room, c, action)
        comfort = fuzzy_vote(c, room, action, p)
        if c.activity != "away":
            cost += abs(comfort["tsv_proxy"]) + 0.5 * comfort["violation"]
            cost += (
                p.noise_weight
                * (action.fan / 3) ** 2
                * (1 if c.activity == "sleep" else 0.15)
            )
            cost += 0.25 * (
                p.study_airflow and c.activity == "study" and action.fan == 0
            )
        cost += p.energy_weight * heat["fan_wh"] / 16.25
    cost /= horizon
    cost += 0.035 * (
        abs(action.fan - current.fan)
        + abs(action.window - current.window)
        + abs(action.curtain - current.curtain)
    )
    return cost


def optimize(
    room, c, p, current=Action(), seed=7, population=10, generations=8, audit=True
):
    """Actual discrete GA with elitism, tournament selection, crossover, mutation.

    A 24-action problem also permits an exhaustive audit; GA result is not replaced.
    """
    rng = random.Random(seed)
    actions = legal_actions(c, p)
    cache = {}

    def score(a):
        if a not in cache:
            cache[a] = objective(room, c, p, a, current)
        return cache[a]

    pop = [rng.choice(actions) for _ in range(population)]
    if current in actions:
        pop[0] = current
    history = []
    for _ in range(generations):
        pop.sort(key=score)
        history.append(score(pop[0]))
        children = pop[:2]
        while len(children) < population:
            parents = [
                min(rng.sample(pop, min(3, len(pop))), key=score) for _ in range(2)
            ]
            genes = [
                rng.choice(pair)
                for pair in zip(
                    asdict(parents[0]).values(), asdict(parents[1]).values()
                )
            ]
            if rng.random() < 0.35:
                index = rng.randrange(3)
                genes[index] = list(asdict(rng.choice(actions)).values())[index]
            child = Action(*genes)
            children.append(child if child in actions else rng.choice(actions))
        pop = children
    best = min(pop, key=score)
    evaluated_ga = len(cache)
    optimum = min(actions, key=score) if audit else None
    return {
        "action": best.dict(),
        "objective": score(best),
        "ga_history": history,
        "ga_evaluations": evaluated_ga,
        "feasible_actions": len(actions),
        "exact_gap": max(0, score(best) - score(optimum)) if audit else None,
        "exact_action": optimum.dict() if audit else None,
        "forecast_minutes": 60,
        "forecast_assumption": "Current outdoor conditions and activity held constant for one hour.",
    }
