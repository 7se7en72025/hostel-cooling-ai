# Final presentation and viva walkthrough

Aim for a 7-10 minute presentation with a 2-minute dashboard demonstration. Use the PDF report and exported chart as evidence. Keep `outputs/demo/dashboard.png` and `comparison-dashboard.png` as offline visual backups.

## Suggested presentation sequence

1. **Problem and scope (45 seconds):** Hostel students may want airflow while studying and quiet while sleeping. One project combines AI preference memory (F417) with room heat, airflow and solar effects (F423). This is a completed simulated computational pilot.
2. **Research context (45 seconds):** Conversation-based thermal preference learning already exists. The local question concerns hostel fan/window/curtain decisions across activities. Avoid claiming the first conversational comfort system. Use the primary references in LITERATURE.md.
3. **System (60 seconds):** Explicit student feedback updates an activity profile. Room physics estimates future conditions. Fuzzy comfort and a GA choose feasible controls. Evidence stays attached to each preference revision.
4. **Building physics (60 seconds):** Explain C dT/dt = G(Tout-T)+Q. Fans add heat to the air but improve perceived comfort through airflow. Opening a window can heat a room if outside air is hotter. A curtain reduces modeled solar gain.
5. **AI methods (60 seconds):** Show triangular fuzzy sets conceptually, the actual trained ANN baseline, and GA selection/crossover/mutation. Explain that exact enumeration audits the small action set. The default language parser is not an LLM; an optional Ollama backend accepts real local models.
6. **Experimental design (45 seconds):** Seven days, three weather seeds, matched forcing and separate policy trajectories. The survey and proposed controller start with the same initial profile. A scripted preference change tests retained context. Describe all synthetic outcomes as proxies.
7. **Results (60 seconds):** Open comparison.png or the table. Ours uses about 323.3 versus 448.0 Wh/day for the fixed schedule, a 27.8% fan-energy reduction. Comfort violations rise from about 53.7% to 53.9%, and mean absolute TSV also rises. This is a trade-off, so the no-comfort-penalty hypothesis is not established. Actual values and variability are in summary.json.
8. **Live demonstration (2 minutes):** Follow the sequence below.
9. **Limits and next step (45 seconds):** Synthetic oracle, assumed room properties, missing radiant/latent effects, untested live LLM and no actual acceptance trial. The next step is a consented, calibrated measured pilot.

## Reliable live demonstration

Start with `python -m hostel_cooling serve`, then open http://127.0.0.1:8765.

1. Leave the initial 31 C room in study mode and generate a recommendation. Explain the control values and one-hour constant-weather forecast.
2. Enable consent, then enter **I prefer 27 C. I want airflow.** while studying. The memory chips should show study target 27 C and airflow preferred.
3. Switch to sleeping and enter **I prefer 29 C. I need quiet when sleeping.** Generate again and show the fan limit. Both activity targets remain in memory.
4. Check Raining and generate again. The window must close regardless of comfort objective.
5. Open Compare controllers and the research report. Explain the energy and comfort columns together. Use bundled results rather than waiting for a new benchmark during the presentation.
6. In Pilot & data, select `data/synthetic_pilot.csv` and validate it. Explain provenance, sensor assumptions and the chronological calibration split.
7. Export the demo memory, then erase and withdraw consent. The synthetic benchmark remains available.

Avoid calling benchmark acceptance an actual student acceptance rate. An Accept button records a separate self-report; it does not actuate a physical device or retrospectively change benchmark outcomes.

## Likely viva questions

**Why a GA for only 24 actions?** It meets the course's GA requirement and allows direct audit. Exhaustive search is a simpler production choice here. A larger control horizon could motivate population search.

**Where is the LLM?** `llm.py` contains a real Ollama HTTP adapter with schema output and validation. The submitted offline run uses an explicit phrase parser for reproducibility. A real model was not configured or benchmarked, so B4 has no fabricated score. Enabling it is documented in README.md.

**What did the ANN learn?** It approximates a generic synthetic sensation function from temperature, humidity and airspeed. An independent synthetic holdout checks fit. It has no evidence of human generalization.

**Why not claim improved comfort?** The fixed schedule has slightly fewer simulated violations in this run. The correct finding is an energy-comfort trade-off. The survey ablation shows the mechanical effect of memory updates under its scripted scenario.

**Is this ASHRAE compliant?** No. The adaptive equation is a scoped reference with awake/study eligibility and air-temperature approximation. Sleep uses a documented fallback.

**What does the EPI mean?** Fan kWh divided by 12 m2 for the simulated seven-day period. It excludes the rest of building electricity and makes no annual claim.

**Why is calibration RMSE zero?** The noiseless synthetic sample uses the same equations as the fitting model, and its true parameters are in the search grid. This checks software recovery, not sensor or physical accuracy.

**What remains?** Actual local-model evaluation, a measured sensor pilot, activity inference, independent comfort validation, uncertainty and weather forecasting, and eventually a larger randomized field study.
