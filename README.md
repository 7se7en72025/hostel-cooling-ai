# Hostel Cooling Lab

One project for **CE F417: Applications of AI in Civil Engineering** and **CE F423: Green Buildings and Energy Conservation**. It combines preference memory, fuzzy comfort, a room heat/moisture model and a genetic optimizer to suggest fan, window and curtain settings.

**Evidence status: simulated course prototype.** The bundled data, comfort votes and acceptance rates are synthetic. Actual student feedback collected through the dashboard stays separate. The default natural-language component is an explicit-phrase parser, not an LLM. A real Ollama adapter is included but its live-model behavior has not been evaluated here. The generic LLM baseline is marked unavailable in the submitted benchmark.

## Run the demo

Requires Python 3.11+.

```powershell
cd C:\Users\RAIYYAN\Desktop\projects\hostel-cooling-ai
python -m pip install -r requirements.txt
python -m hostel_cooling serve
```

Open **http://127.0.0.1:8765**. On Windows, `start.bat` also starts the server after dependencies are installed. The app serves locally and loads no external fonts, scripts or assets.

1. Choose studying, sleeping or away and adjust the room conditions.
2. Generate a recommendation. Inspect its forecast, energy and GA optimality gap.
3. Optionally consent to local storage. Enter `I prefer 27 C. I want airflow.` while studying.
4. Switch to sleeping and enter `I prefer 29 C. I need quiet when sleeping.` Study preferences remain in memory.
5. Generate again. Simulate a 15-minute step, or record an actual optional accept/decline vote.
6. Open **Compare controllers** for the bundled experiment and report. **Pilot & data** supports CSV validation, export and erasure.

The dashboard represents one pseudonymous local participant. It is not a multi-user deployment or sensor acquisition service. Consent revocation erases that participant's profile, evidence, saved suggestions and self-reports. Synthetic benchmark results remain available.

## Reproduce the results

```powershell
python -m unittest discover -s tests -v
python -m hostel_cooling experiment --days 7 --seeds 11 23 47
python -m hostel_cooling sample-data
python -m hostel_cooling validate data/synthetic_pilot.csv
python -m hostel_cooling calibrate data/synthetic_pilot.csv
```

`outputs/demo/report.html` is the complete research report. `outputs/demo/Hostel_Cooling_Project_Report.pdf` is the six-page companion for submission. `summary.json`, `comparison.csv`, `runs.csv`, `trajectories.csv` and `conversation_evidence.json` preserve the data behind it. `comparison.png` and `.svg` are exportable figures. Energy and control trajectories reproduce for the same seeds. Runtime-dependent latency measurements vary.

The submitted 7-day, 3-seed run uses eight policy variants, including an explicitly labeled offline diagnostic and a survey ablation. The proposed controller consumes less fan electricity than the fixed schedule, with slightly higher simulated comfort violations. The study **does not establish energy savings without a comfort penalty**. See the exported data for exact values and variability.

`outputs/calibration.json` recovers the known UA and capacitance from the noiseless synthetic sample. Zero RMSE is expected when the generator and fitting equations match. It says nothing about field accuracy.

## Connect a real local LLM

Install Ollama separately and download a model appropriate for your machine. Set `OLLAMA_MODEL` to its actual installed name. No model or API key is bundled, and no paid API is called by default.

```powershell
$env:OLLAMA_MODEL = 'your-installed-model-name'
$env:OLLAMA_HOST = 'http://127.0.0.1:11434'
python -m hostel_cooling serve --llm
```

This sends consented conversation text to the configured endpoint. The adapter requests JSON-schema output, validates every change, and surfaces failures without silently replacing them with fake LLM output. A configured remote `OLLAMA_HOST` changes where messages go, so select the endpoint knowingly.

To evaluate an actual generic LLM policy and use real LLM preference extraction:

```powershell
python -m hostel_cooling experiment --llm --days 1 --seeds 11 --output outputs/llm_trial
```

This can make many model requests. Failed runs are discarded and reported, rather than included as completed comparisons. The dashboard's Run comparison button always runs the labeled offline benchmark. The generic LLM policy receives current conditions and feasible actions but no conversation memory or physics forecast.

## Project layout

| Path | Purpose |
| --- | --- |
| `hostel_cooling/domain.py` | Validated room, state, preferences and feasible actions |
| `physics.py`, `comfort.py` | Analytical 1R1C model, moisture balance, fuzzy and adaptive models |
| `preferences.py`, `llm.py` | Consent-gated SQLite memory, offline and Ollama backends |
| `optimizer.py`, `policies.py`, `ann.py` | GA, baselines and trained neural regressor |
| `experiment.py`, `pilot.py`, `report.py` | Simulation, CSV validation, calibration and reporting |
| `server.py`, `web/` | Local dashboard and JSON endpoints |
| `tests/` | Physical invariants, constraints, persistence, data and adapter checks |
| `docs/` | Methods, research context, pilot protocol and presentation walkthrough |
| `data/` | Clearly labeled synthetic pilot and data dictionary |
| `outputs/` | Reproducible synthetic evidence and report |

## Scope and limitations

The model uses assumed room properties, facade solar and ventilation proxies, and air temperature as an operative-temperature proxy. It omits surface radiation, spatial stratification, latent thermal coupling and condensation. Fan power heats the room; perceived fan cooling enters the comfort model separately. The adaptive reference is restricted to eligible awake/study conditions, with an explicitly labeled rule fallback elsewhere.

EPI is **fan electricity in kWh divided by floor area over the simulated period**. It is not annual whole-building EPI. GRIHA/LEED names in the proposal describe course context, not certification or implemented rating rules. No physical devices are actuated. A measured, consented pilot and a 20-50 room deployment remain future work.

Research sources and project-to-course mapping are in `docs/METHODS.md` and `docs/LITERATURE.md`.

## Presentation and optional development checks

`docs/DEMO_SCRIPT.md` provides a 7-10 minute presentation sequence, live-demo steps and viva answers. The screenshots and chart in `outputs/demo/` provide offline visual backups. The project contains no fabricated live LLM or field-study results.

Install optional development dependencies with `python -m pip install -r requirements-dev.txt`. Rebuild the companion PDF with `python tools/build_report.py` after generating experiment results. For the optional browser smoke test, install a Chromium browser using `python -m playwright install chromium`, run the server, then run `python tests/browser_smoke.py`.

The browser smoke script resets the dashboard's demo participant and erases its test feedback. Run it only against a disposable local demo, not a session containing real pilot records. The standard unit tests use temporary data and do not touch the dashboard profile.
