# Hostel Cooling Project

Complete simulated research project for **CE F417: Applications of AI in Civil Engineering** and **CE F423: Green Buildings and Energy Conservation**.

The system uses an **actual locally running Qwen3-4B transformer**, persistent activity-specific preferences, a calibrated RC room model, fuzzy comfort and a genetic optimizer to recommend fan, window and curtain settings. It includes saved trained models and both courses' complete baseline sets, including the actual generic LLM baseline.

The approved study uses simulated room and occupant data. Model inference, training, calibration, application behavior and exported computations are real. Synthetic comfort/acceptance outcomes are not presented as measured student results.

## Start the complete application

On this prepared machine, run **start.bat** or:

```powershell
python -m hostel_cooling serve
```

Open **http://127.0.0.1:8765**. The server starts or reuses the pinned local transformer automatically. No API key or paid service is required.

For a fresh Windows checkout with Python 3.11+, run **setup.bat** once. It creates a virtual environment, installs the recorded dependencies, downloads and verifies the portable inference runtime and approximately 2.5 GB model, and trains the smaller models. The default Vulkan build can use compatible GPUs. A CPU setup is also available:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1 -Acceleration cpu
```

Model weights, binaries and private participant records stay in the ignored runtime directory. No system-wide model installation is required. Other operating systems can run llama.cpp externally and set COOLING_LLM_URL, or use the supported Ollama adapter.

## What is implemented

- Actual local transformer requests with constrained JSON, exact-message evidence quotes and validated preference updates.
- Separate participant aliases, consent, persistent activity targets, evidence history, suggestions, self-reports, export and erasure.
- A saved activity routine learner with confidence and explicit synthetic-prior/personal-history provenance.
- Exact constant-forcing 1R1C heat integration, moisture balance, ventilation/solar proxies and separate perceived fan cooling.
- Chronological noisy-data calibration, held-out prediction error and an actual persistence comparison.
- Fuzzy comfort scoring, GA selection/crossover/mutation, legal-action constraints and exhaustive optimality auditing.
- A trained and serialized neural comfort model, its source dataset and independent synthetic holdout.
- Both course comparison sets, survey/no-physics ablations, paired weather-seed contrasts and a predeclared objective-weight sweep.
- Complete request/response journals, reproducible data, submission report and executable verification scripts.

Physical sensors and actuators are outside the chosen simulated scope. The application never pretends to control a real room.

## Use the application

Choose a pseudonymous profile alias and consent if you want memory or data processing. Different profiles keep separate preferences and observations. Recommendations with generic preferences remain available without consent.

Select study, sleep, away or learned routine mode. Enter current room conditions. Ask for a recommendation, inspect its controls and forecast, and optionally simulate the next 15 minutes. The actual local model interprets natural-language preferences, then the app shows its proposed changes for review. Confirm to save or discard and rephrase. Nothing is saved during preview. Unsupported or invalid extractions leave the profile unchanged.

Pilot & data can validate a CSV, calibrate its room parameters and apply them to the current profile. It also exports and erases that profile's stored records. Actual optional accept/decline votes stay separate from synthetic benchmark outcomes.

Compare controllers displays the completed study and links to its submission PDF and raw evidence. The Run complete study button starts the full actual-model pipeline asynchronously; it is not an offline-rule substitute.

## Reproduce the full project

```powershell
python -m hostel_cooling setup-model
python -m hostel_cooling study --days 7 --seeds 11 23 47
python -m unittest discover -s tests -v
python tools/verify_submission.py
```

**run-study.bat** also runs the complete study. Model inference is the main runtime cost. Matching requests can reuse explicitly labeled cached actual model responses. Controller latency is recorded separately from preference extraction. The response journal distinguishes generated results from cache hits.

The pipeline trains/saves models, generates a separate 14-day noisy pilot, calibrates the controller on chronological training data, compares nine methods over seven days and three weather seeds at a common hourly control cadence, evaluates 24 held-out language phrases, runs six predeclared energy weights, and produces the report.

To reproduce the frozen submitted results quickly without downloading the large transformer, use its recorded actual responses:

```powershell
python -m hostel_cooling study --backend replay --output build/replay-study
python tools/verify_replay.py
```

Replay is explicitly labeled and refuses requests absent from the recorded journal. The separately executed replay reproduced trajectories and sensitivity files byte for byte, all nine methods' scientific metrics and every language outcome. Timings and backend labels are excluded from that equality check.

## Submission and evidence

The final handoff includes a **14-page report**, **18-slide editable PowerPoint with native charts/tables and speaker notes**, a rendered slide PDF, and an **8-page viva guide with 34 questions and answers**. All four files are in outputs/study/. The application also links to the report, presentation and guide from Compare controllers.

To rebuild the editable presentation and viva guide:

```powershell
python -m pip install -r requirements-submission.txt
python tools/build_presentation.py
python tools/build_viva.py
```

Export the PPTX to PDF using PowerPoint or LibreOffice after changing slides. Then run python tools/build_submission.py to package the final deliverables, complete source and SHA256 manifest into ../Hostel_Cooling_Final_Submission.zip. The package excludes historical offline outputs and private runtime data.

The current final outputs are in **outputs/study/**. Earlier v1 offline results under outputs/demo are historical artifacts and are not the completed submission.

| Output | Content |
| --- | --- |
| Hostel_Cooling_Project_Report.pdf | Complete submission report |
| Hostel_Cooling_Final_Presentation.pptx | Editable final presentation with native charts/tables and speaker notes |
| Hostel_Cooling_Final_Presentation.pdf | Rendered final slides |
| Hostel_Cooling_Viva_Guide.pdf / VIVA_GUIDE.md | Thirty-four viva questions, answers, key results and run commands |
| report.html | Browser report with figures and evidence links |
| summary.json / comparison.csv | Aggregate results and study metadata |
| runs.csv / trajectories.csv | Per-seed outcomes and every closed-loop control interval |
| llm_inference.jsonl | Actual transformer prompts, responses, model hashes, usage and timings |
| conversation_evidence.json | Scripted preference changes and actual extraction results |
| language_evaluation.json | All 24 held-out phrase outcomes, including failures |
| calibration.json | Estimated room parameters and untouched chronological holdout error |
| paired_comparisons.csv | Matched-seed differences and exploratory intervals |
| sensitivity.csv | All six declared objective-weight conditions |
| submission_verification.json | Required-baseline, raw-energy and constraint checks |
| reproducibility_verification.json | Independent frozen-response reproduction checks |
| presentation_data.json / PRESENTATION_NOTES.md | Eighteen-slide presentation content and viva notes |
| hypothesis_assessment.json | Findings, evidence and limits for all eight original proposal hypotheses |
| preference_change_phases.csv | Matched per-seed outcomes before and after the preference update |

**models/** contains saved ANN weights, activity counts, training data, validation results and the training curve. **data/** contains the synthetic observation data, its known generator/noise metadata and the fixed language benchmark. The source proposals define the combined course scope; docs/METHODS.md maps each requirement to implementation.

## Course baselines

| Course | Baseline set |
| --- | --- |
| CE F417 | Expert rules, scoped adaptive reference, trained ANN, actual generic LLM, proposed preference + physics + GA |
| CE F423 | Fixed schedule, scoped adaptive reference, room physics only, actual generic LLM, proposed preference + physics + GA |

The survey ablation holds the initial profile fixed. The no-physics ablation retains language memory while omitting room lookahead. The generic LLM receives current measurements and feasible control values, without personal history or a numerical RC forecast. All methods share explicit safety/availability constraints and a common decision cadence.

## Interpretation

The frozen 24-phrase benchmark achieved 17/24 exact matches (70.8%) without user correction. Every failure is retained. Automated research uses the raw extraction endpoint to measure this behavior. The application adds explicit review and confirmation before committing an interpretation, because quote grounding alone did not prevent all mistaken inferences.

The study reports energy and comfort together, including unfavorable outcomes. Fan EPI means fan kWh divided by floor area during the simulated period; it is not annual whole-building EPI. GRIHA/LEED course context does not imply a rating implementation or certification. The adaptive reference has a documented awake/study eligibility scope and a fallback elsewhere.

The fitted RC model and ANN remain simplified synthetic models. Low prediction error does not prove accurate physical parameters. Comfort and acceptance derive from an assumed numerical occupant, so neither establishes human benefit. Routine and language evaluation measure software behavior on declared synthetic datasets. A measured human study would answer a different empirical question.

## Optional modes and development

Use --backend offline only when explicitly testing the rule parser. The default local backend does not silently replace missing inference with offline rules. The Ollama adapter remains available through --backend ollama with OLLAMA_MODEL set to a real installed model.

```powershell
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python tests/browser_smoke.py
```

Browser validation uses and erases a dedicated test alias rather than a participant's records. Unit tests use temporary files. GitHub CI runs the non-GPU software/model checks on Windows and Linux. Setup scripts and requirements-lock.txt preserve the tested software versions. Large model resources are pinned separately by revision, release and SHA256.
