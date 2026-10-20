# Data provenance

`synthetic_pilot.csv` contains 672 simulated 15-minute observations, generated with seed 101 over seven days starting at an arbitrary illustrative date of 1 April 2026. No participant or sensor observations are included. All `consent=true` fields are synthetic schema examples, not evidence of human consent.

Generate again with `python -m hostel_cooling sample-data`. Full schema and interval alignment are in `docs/PILOT_PROTOCOL.md`.


The completed study uses noisy_pilot.csv: 1,344 observations across 14 days, generated with seed 301 from a plant with UA=58 W/K and C=2.5 MJ/K. Independent sensor noise affects indoor/outdoor temperatures, RH and facade solar readings. noisy_pilot_metadata.json records the known generator and noise scales. Calibration uses the first 80% of transitions and reports the untouched final 20%.

preference_benchmark.json contains 24 fixed synthetic language cases. No real student messages appear in these files. Actual transformer outputs and all evaluation failures are preserved separately under outputs/study/.
