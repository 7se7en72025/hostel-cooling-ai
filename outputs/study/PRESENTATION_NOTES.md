# Final presentation and viva notes

Use the recorded study results below. The project contains actual local transformer inference and explicitly synthetic room/occupant outcomes.

## 1. Cooling for student hostels

- Preference memory, building physics and constrained room control
- Completed simulated research project

All room and occupant outcomes are simulated. The local transformer, training and exported computations actually ran. Course instructor: Prof. Rajiv Gupta.

## 2. Research question

- Can retained student preferences guide fan, window and curtain decisions?
- F417: language, memory and AI comparisons
- F423: airflow, solar gains and energy
- Study, sleep and away can require different settings

Source proposals define the combined scope. Conversation-based comfort learning already exists: https://doi.org/10.1016/j.enbuild.2026.117181

## 3. Implemented system

- 1. Consented feedback updates an activity-specific profile
- 2. Heat and moisture balances estimate room conditions
- 3. Fuzzy comfort and a GA score legal controls
- 4. Suggestions, evidence and self-reports persist locally
- Learned activity inference and CSV calibration are available in the application

Source: implemented modules preferences.py, physics.py, optimizer.py, server.py and routines.py. Self-reports remain separate from simulation labels.

## 4. Room model and calibration

- C dT/dt = G (Tout - T) + solar + internal gains + fan power
- Fan electrical heat and perceived airflow relief remain separate

| Parameter | Synthetic plant | Fitted controller |
| --- | --- | --- |
| UA / W K-1 | 58 | 72 |
| C / MJ K-1 | 2.5 | 2.75 |
| Area / m2 | 12 | 12 |

The fitted parameters use separate noisy observations and can be biased. Model structure context: https://energyplus.readthedocs.io/en/stable/guides/engineering-reference/2.1-basis-for-the-zone-and-air-system-integration.html

## 5. Actual local preference learning

- Qwen3-4B-Q4_K_M
- Pinned model revision and SHA256; local inference, no API key
- Structured values require exact-message evidence quotes
- Separate study and sleep targets survive activity changes
- Invalid values and unsupported evidence cannot silently change memory

Model source: https://huggingface.co/Qwen/Qwen3-4B-GGUF. Inference API: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md. Actual prompts and outputs: llm_inference.jsonl.

## 6. Saved learning models

- Comfort ANN: 0.148 TSV holdout MAE
- 2,000 training and 400 independent synthetic holdout points
- Routine model: 93.5% chronological test accuracy
- Majority routine baseline: 36.6%
- Saved weights, counts, datasets and validation metadata accompany the project

All model validation labels are synthetic. Routine split: 14 train days and seven later test days. Source: models/ann_validation.json and routine_validation.json.

## 7. Matched experimental design

- 7 days per seed; seeds [11, 23, 47]
- 15-minute physics, hourly control decisions for every policy
- 9 methods, separate closed-loop room trajectories
- Same forcing, initial state and explicit constraints
- Survey and no-physics ablations isolate memory and lookahead

All actions apply, including proxy-declined suggestions. Comfort excludes away intervals. The generic LLM receives no personal history or numerical room forecast.

## 8. F417 comparison

- Synthetic comfort outcomes; actual generic LLM inference

| Controller | Wh/day | Mean |TSV| | Violation % |
| --- | --- | --- | --- |
| expert | 497.4 | 1.07 | 50.9 |
| adaptive | 485.1 | 1.06 | 50.6 |
| ann | 491.3 | 1.03 | 49.0 |
| generic_llm | 141.4 | 1.77 | 76.5 |
| ours | 290.7 | 1.40 | 54.7 |

Source: CE_F417_comparison.csv. Adaptive reference uses a documented fallback outside awake/study applicability. https://pythermalcomfort.readthedocs.io/en/latest/documentation/models.html

## 9. F423 fan electricity

- Energy must be interpreted alongside occupied discomfort
- Proposed period fan EPI: 0.1696 kWh/m2

Source: CE_F423_comparison.csv. EPI covers only fan electricity during this trial, not annual whole-building EPI.

## 10. Comfort and energy trade-off

- Ours: 290.7 Wh/day; 54.7% violations
- Fixed: 448.0 Wh/day; 52.3% violations
- Fan energy change: -35.1%
- Comfort violation change: +2.38 percentage points
- Synthetic results establish a scenario trade-off, not a human benefit

Source: summary.json and paired_comparisons.csv. Paired weather-seed intervals are exploratory with n=3; no participant inference.

## 11. Memory and physics ablations

- The survey starts with the same initial profile
- A scripted target change reaches only memory-enabled policies

| Method | Wh/day | Violation % | Accept proxy % |
| --- | --- | --- | --- |
| ours | 290.7 | 54.7 | 44.6 |
| survey | 328.5 | 55.9 | 39.8 |
| no_physics | 145.0 | 71.1 | 28.6 |
| physics | 236.6 | 54.8 | 40.6 |

Source: comparison.csv and conversation_evidence.json. The small scripted experiment tests retention mechanically; it is not an actual conversation-versus-survey trial.

## 12. Language evaluation

- 24 fixed held-out synthetic phrases
- Exact-match accuracy: 70.8%
- Field precision / recall: 0.667 / 0.800
- Cross-activity persistence: True
- All failures and safe rejections remain in the evidence
- The app requires review and confirmation before saving preferences

Source: language_evaluation.json. This is real local model inference, not parser output. Phrases include negation, unrelated observations, invalid values and mixed contexts.

## 13. Held-out room prediction

- 14 days of noisy synthetic observations
- Chronological 80/20 transition split
- Low prediction error does not prove parameter identifiability

Source: calibration.json and noisy_pilot_metadata.json. Parameter selection never uses test transitions.

## 14. Objective-weight sensitivity

- All six predeclared energy weights are reported
- Same three seeds, three days per weight
- Comfort outcomes accompany the energy curve in sensitivity.csv

This sweep illustrates objective dependence. It does not select a winning weight after observing the test outcomes.

## 15. Completed deliverables

- Working local application with actual transformer requests
- Saved ANN and routine models, plus material and calibration tools
- Both course baseline sets, ablations and sensitivity analysis
- Raw interval data, inference journals and automated checks
- Reproducible setup, complete report and source repository

The approved scope is a completed simulated course project. Physical sensors, metered human outcomes and a 20-50 room field study are separate empirical work.

## 16. Limits and interpretation

- One-node room physics omits radiant and spatial effects
- Comfort labels and acceptance derive from assumed synthetic occupants
- LLM extraction can miss or misinterpret phrases
- No human effectiveness or building-certification claim
- A measured, consented field study would test external validity

Preserve the distinction between completed software and unmeasured real-world benefit. The project reports unfavorable outcomes instead of manufacturing positive hypotheses.
