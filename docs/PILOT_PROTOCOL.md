# Pilot protocol and data dictionary

The included dataset is synthetic. This protocol describes the future measured pilot, not completed participant recruitment.

Collect one room at 15-minute intervals for at least seven days, preferably covering changes in outdoor weather and control states. Obtain informed opt-in before logging conversation or votes. Explain withdrawal, local storage, export, endpoint use for optional LLMs and retention dates. Use random room/participant labels in separate files, with identity mappings outside this repository. Avoid collecting names, age, gender or other sensitive attributes.

The current CSV loader accepts one room per file with uninterrupted consecutive timestamps and one provenance type. Split gaps into separate files. Do not fabricate missing measurements. An actual study must define timezone and daylight-saving handling; the bundled sample uses a consistent local naive timeline.

| Column | Type / unit | Requirement |
| --- | --- | --- |
| timestamp | ISO datetime | Consecutive 900-second intervals |
| indoor_c, outdoor_c | °C | Indoor 5..50, outdoor -10..55 |
| rh, outdoor_rh | % | 1..100 |
| solar_w_m2 | W/m² | Facade solar proxy, 0..1400 |
| wind_ms | m/s | 0..15 |
| activity | categorical | study / sleep / away |
| fan | integer | 0 / 1 / 2 / 3 |
| window | fraction | 0 / 0.5 / 1 |
| curtain | integer | 1 closed, 0 open |
| tsv | optional float | -3..3, blank if unavailable |
| accepted | optional integer | 0 / 1, blank if unavailable |
| consent | text | true in every row |
| provenance | text | synthetic / measured; no mixing |

Each row's measured indoor state starts a 15-minute interval. Its controls and outdoor forcing describe that interval; the next row's indoor temperature is the prediction target. Do not reverse this alignment during calibration.

Meter fan electrical power for each speed. Record floor area, material/envelope assumptions, facade orientation, glazing and observed shade behavior. Measure or justify airspeed and mean radiant temperature rather than assuming them. Calibrate sensor offsets together before deployment and retain quality flags outside the simple prototype schema.

`python -m hostel_cooling validate PATH.csv` checks schema, ranges, consent, provenance and spacing. It does not validate sensor reliability. `calibrate` grid-searches UA and effective capacitance on the first 80% of transitions and reports held-out one-step RMSE on the last 20%. It holds all other assumptions fixed and may identify biased parameters to compensate for missing physics. Use fitted values explicitly in Room construction or dashboard physics controls. Calibration output is not automatically applied to experiments.

For later field comparisons, randomize controller periods with washout or account for thermal carryover. Predefine comfort margins, primary outcomes, missing-data exclusions and withdrawal handling. Compare paired measured fan Wh and occupied discomfort, and report accepted suggestions separately from applied controls. A small pilot should estimate feasibility and variance before any powered effectiveness study.

The dashboard separates pseudonymous local profiles in `runtime/pilot.sqlite3`. Consent is optional for generic recommendations but required for persistence and imported pilot processing. Erasure removes the local logical records; backups, exports and low-level SQLite page recovery are outside this application's deletion guarantee. Do not share the runtime directory or real pilot files through Git.


The completed software can calibrate and apply a room model from the Pilot & data screen. A fitted model is saved only with consent, scoped to the selected participant alias and included in that profile's export/erasure. The study's default calibrated synthetic room remains a separate shared research artifact. Startup uses the actual pinned local transformer; offline rules require explicit backend selection.
