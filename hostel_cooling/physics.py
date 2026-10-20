"""Transparent 1R1C grey-box model, not an EnergyPlus or CFD replacement."""

import math
from dataclasses import replace


def saturation_pa(temp):
    return 610.94 * math.exp(17.625 * temp / (temp + 243.04))


def humidity_ratio(temp, rh):
    vapour = rh / 100 * saturation_pa(temp)
    return 0.62198 * vapour / (101325 - vapour)


def step(room, c, action, minutes=15):
    if not 0 < minutes <= 1440:
        raise ValueError("minutes must be in (0, 1440]")
    seconds = minutes * 60
    volume = room.area_m2 * room.height_m
    ach = 0.4 + action.window * (1 + 2 * c.wind_ms)
    flow = ach * volume / 3600
    conductance = room.ua_w_k + 1.2 * 1006 * flow
    orientation = {
        "north": 0.4,
        "south": 0.75,
        "east": 1 if c.hour < 12 else 0.35,
        "west": 1 if c.hour >= 12 else 0.35,
    }[room.orientation]
    solar = (
        room.window_m2
        * room.glazing_g
        * c.solar_w_m2
        * orientation
        * (0.25 if action.curtain else 1)
    )
    internal = 8 if c.activity == "away" else (75 if c.activity == "sleep" else 120)
    fan_w = room.fan_w[action.fan]
    gains = solar + internal + fan_w
    equilibrium = c.outdoor_c + gains / conductance
    temperature = equilibrium + (c.indoor_c - equilibrium) * math.exp(
        -conductance * seconds / room.capacity_j_k
    )
    # Moisture balance on air mass; constant outdoor forcing over the timestep.
    outdoor_w = humidity_ratio(c.outdoor_c, c.outdoor_rh)
    initial_w = humidity_ratio(c.indoor_c, c.rh)
    moisture_kg_s = 0 if c.activity == "away" else 0.04 / 3600
    moisture_eq = outdoor_w + moisture_kg_s / (1.2 * flow)
    w = moisture_eq + (initial_w - moisture_eq) * math.exp(-flow * seconds / volume)
    vapour = 101325 * w / (0.62198 + w)
    rh = max(1, min(100, 100 * vapour / saturation_pa(temperature)))
    # RH saturation is capped; condensation and latent thermal coupling are omitted.
    state = replace(c, indoor_c=temperature, rh=rh, hour=(c.hour + minutes / 60) % 24)
    return state, {
        "fan_wh": fan_w * minutes / 60,
        "solar_w": solar,
        "internal_w": internal,
        "fan_w": fan_w,
        "ventilation_ach": ach,
        "conductance_w_k": conductance,
        "air_speed_ms": min(
            1.8, room.fan_speed_ms[action.fan] + 0.12 * action.window * c.wind_ms
        ),
    }


def operative_temperature(c, room, action):
    # No surface temperature sensors: use air temperature. Explicit limitation in report.
    return c.indoor_c
