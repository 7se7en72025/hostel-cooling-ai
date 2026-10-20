"""Layer-based engineering estimates for material/geometry inputs.

The concrete preset comes from the cited EnergyPlus example. Film resistances,
mass participation and roof/window properties remain explicit project assumptions.
Calibration can replace these estimates; this is not an envelope certification.
"""

from .domain import Room, number

CONCRETE_SOURCE = "https://raw.githubusercontent.com/NatLabRockies/EnergyPlus/develop/testfiles/1ZoneUncontrolled.idf"


def estimate_envelope(
    layers=None,
    opaque_wall_m2=18,
    window_m2=2,
    window_u_w_m2k=5.8,
    roof_m2=0,
    roof_u_w_m2k=1.5,
    floor_m2=12,
    height_m=3,
    mass_participation=0.25,
    furniture_capacity_j_k=300_000,
    orientation="west",
):
    layers = layers or [
        {
            "name": "EnergyPlus example concrete",
            "thickness_m": 0.2,
            "conductivity_w_mk": 1.729577,
            "density_kg_m3": 2242.585,
            "specific_heat_j_kgk": 836.8,
        }
    ]
    if not isinstance(layers, list) or not 1 <= len(layers) <= 12:
        raise ValueError("Provide 1..12 material layers")
    for name, value, lo, hi in [
        ("opaque_wall_m2", opaque_wall_m2, 1, 200),
        ("window_m2", window_m2, 0.1, 15),
        ("window_u_w_m2k", window_u_w_m2k, 0.1, 10),
        ("roof_m2", roof_m2, 0, 100),
        ("roof_u_w_m2k", roof_u_w_m2k, 0.05, 10),
        ("mass_participation", mass_participation, 0.01, 1),
        ("furniture_capacity_j_k", furniture_capacity_j_k, 0, 10_000_000),
    ]:
        number(value, lo, hi, name)
    resistance = 0.13 + 0.04
    areal_capacity = 0
    for layer in layers:
        thickness = number(layer.get("thickness_m"), 0.001, 2, "layer thickness")
        conductivity = number(layer.get("conductivity_w_mk"), 0.01, 20, "conductivity")
        density = number(layer.get("density_kg_m3"), 1, 10_000, "density")
        capacity = number(layer.get("specific_heat_j_kgk"), 100, 5000, "specific heat")
        resistance += thickness / conductivity
        areal_capacity += density * capacity * thickness
    wall_u = 1 / resistance
    ua = wall_u * opaque_wall_m2 + window_u_w_m2k * window_m2 + roof_u_w_m2k * roof_m2
    c = (
        1.2 * 1006 * floor_m2 * height_m
        + mass_participation * areal_capacity * opaque_wall_m2
        + furniture_capacity_j_k
    )
    room = Room(
        area_m2=floor_m2,
        height_m=height_m,
        ua_w_k=ua,
        capacity_j_k=c,
        window_m2=window_m2,
        orientation=orientation,
    )
    return {
        "room": room.__dict__,
        "wall_u_w_m2k": wall_u,
        "wall_r_m2k_w": resistance,
        "wall_areal_capacity_j_m2k": areal_capacity,
        "layers": layers,
        "material_source": CONCRETE_SOURCE,
        "assumptions": "Surface films 0.13+0.04 m2 K/W; supplied effective mass participation. Window/roof values are user assumptions. Use calibration for the final room model.",
    }
