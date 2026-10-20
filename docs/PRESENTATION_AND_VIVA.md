# Final project presentation and viva

The current presentation content is generated from the completed results in **outputs/study/PRESENTATION_NOTES.md** and **presentation_data.json**. The complete submission report is **Hostel_Cooling_Project_Report.pdf** in the same directory. Use those actual values, not historical v1 screenshots or offline results.

## Application walkthrough

1. Run start.bat and open http://127.0.0.1:8765. Confirm the backend names Qwen3-4B and the participant alias is the intended profile.
2. Choose studying, consent to memory if desired, and enter: `I prefer 27 C. I want airflow.` Review the interpretation, then confirm to save it. Preview alone leaves memory unchanged.
3. Choose sleeping and enter: `I prefer 29 C. Please keep the fan low when I sleep.` Review and confirm. Both activity targets remain available after reload.
4. Generate a recommendation, inspect the fan/window/curtain values, fuzzy sensation and GA audit, then advance 15 simulated minutes and recommend again.
5. Enable raining and show the closed-window constraint. Choose learned routine mode and explain its predicted activity, confidence and source.
6. In Pilot & data, select data/noisy_pilot.csv, validate it and calibrate/apply the fitted parameters. Explain the chronological train/test split and why fitted parameters can differ from the known generator.
7. Compare controllers shows both course baselines, with an actual generic LLM policy. Open the full report and raw inference journal. Read energy and comfort together.
8. Export the selected profile, then withdraw consent to erase its logical records. Do not erase another participant's records during a presentation.

## Direct answers to the proposal hypotheses

The final report and application contain all eight F417/F423 hypotheses, findings, evidence and limits. F417 H1 has a successful mechanical target-retention test, not evidence of general survey superiority. Routine inference is evaluated separately on synthetic schedules. Acceptance proxy improves relative to the unchanged survey after the scripted preference update. The energy-without-comfort-loss claim is not supported in this configuration. Physics improves modeled discomfort at an energy cost, and period fan EPI falls relative to fixed settings. These are completed computational findings, including the negative result.

## Viva answers

**Where is the LLM?** Qwen3-4B-Q4_K_M runs locally through a pinned llama.cpp binary. The application and study issue actual schema-constrained requests. The model revision, file SHA256, prompts, responses and timings are recorded. No paid API or fake LLM score is required.

**Why does a fan add heat?** Its electrical power becomes sensible heat in the room model. Perceived cooling from air movement enters the comfort calculation separately. The fan does not remove room heat as an air conditioner would.

**Why a GA for 24 actions?** It implements the course's GA method and permits direct quality auditing. Exhaustive search is simpler for this particular action set. The exact audit does not replace the returned GA result.

**What did the ANN and routine model learn?** The ANN approximates synthetic comfort labels with a saved one-hidden-layer regressor. The routine model learns time/weekday activity counts with a separate chronological holdout. Their training datasets and validation evidence are saved, and synthetic results do not establish human generalization.

**What does the EPI mean?** Fan kWh divided by room floor area for the simulated trial period. It excludes other building electricity and makes no annual whole-building claim.

**Why is calibration error nonzero now?** The current study uses an independent noisy observation dataset and a separate known plant. The held-out error is evaluated without selecting parameters on test transitions. The older noiseless exact-recovery sample is only a software check.

**Does the project prove improved human comfort?** No. It completes the approved simulated computational project and reports actual model behavior plus synthetic room outcomes. The report includes trade-offs and every held-out language failure. A measured human trial would test external validity separately.

**What can be reproduced without new model inference?** Recorded-response replay can reproduce requests whose hashes match the actual response journal. It is explicitly labeled replay and cannot invent an answer to a new request. Default application and study execution use the actual local model.
