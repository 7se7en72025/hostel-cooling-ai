"""Create the final viva guide with answers tied to recorded results."""

import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hostel_cooling.pdf_report import p, table, footer
from reportlab.platypus import SimpleDocTemplate, Spacer, PageBreak, KeepTogether
from reportlab.lib.pagesizes import A4


def build(out=ROOT / "outputs/study"):
    out = Path(out)
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    rows = {r["method"]: r for r in summary["rows"]}
    ours, fixed, generic = [rows[m] for m in ("ours", "fixed", "generic_llm")]
    lang = summary["language_evaluation"]
    cal = summary["calibration"]
    groups = [
        (
            "Project and contribution",
            [
                (
                    "What problem does the project solve?",
                    "A hostel occupant can prefer different conditions during study, sleep and time away. The project retains explicit activity-specific preferences and combines them with current conditions to recommend fan, window and curtain settings.",
                ),
                (
                    "How do F417 and F423 form one project?",
                    "F417 supplies language-based preference extraction, fuzzy comfort, genetic optimization and ANN/expert comparisons. F423 supplies room heat and moisture balances, solar and ventilation effects, calibration and fan electricity/EPI evaluation. The same software and pilot evidence serve both courses.",
                ),
                (
                    "What is actually completed?",
                    "The local application, actual transformer integration, consented persistent profiles, saved ANN and routine models, calibration, nine-policy comparison, ablations, sensitivity sweep and raw evidence are implemented and executed. The final report and editable presentation summarize those computations.",
                ),
                (
                    "Which data are real and which are simulated?",
                    "Model inference, training computations, calibration, application interactions and timing measurements are actual executions. Weather, indoor observations, occupant targets, sensation labels and benchmark acceptance are synthetic. No recruited students, metered building savings or physical device operation are claimed.",
                ),
                (
                    "What is the research contribution?",
                    "An auditable combination of retained activity preferences, a calibrated low-order room model and constrained passive controls, evaluated against both courses' baseline sets. Conversation-based comfort learning already exists in prior literature, so this project does not claim the general idea is new.",
                ),
            ],
        ),
        (
            "Language, memory and learning",
            [
                (
                    "Where is the LLM?",
                    "Qwen3-4B-Q4_K_M runs locally through a pinned llama.cpp server. Requests use structured JSON, temperature zero, a fixed inference seed and an exact-message evidence requirement. The model revision, SHA256, prompts, responses, usage and timings are preserved in the inference journal.",
                ),
                (
                    "Did you train or fine-tune Qwen?",
                    "No. Qwen is a pretrained transformer. The project uses prompting and structured extraction, then updates a local preference profile. Here preference learning means updating retained user context, not changing the transformer's weights. The smaller ANN and activity model are trained within this project.",
                ),
                (
                    "How does memory survive a context change?",
                    "SQLite stores separate study and sleep temperature targets plus explicit airflow/noise settings and their evidence history. Returning to an activity retrieves that activity's target. Reloading the app does not erase a consented profile. Tests verify persistence and separate participant aliases.",
                ),
                (
                    "Does a quote guarantee the interpretation is correct?",
                    f"No. The frozen phrase test obtained {lang['exact_match_accuracy']*100:.1f}% exact matches. A phrase can occur in the message but still be interpreted incorrectly. The application therefore previews every proposed patch and requires confirmation or discard before saving. The raw benchmark score remains unchanged.",
                ),
                (
                    "What language fields are supported?",
                    "The actual local extraction schema covers desired temperature with activity, sleep fan limit and study airflow. It does not learn arbitrary room preferences or schedules from unrestricted prose. Curtain settings are currently driven by the solar/comfort objective rather than an explicit learned shade-preference field.",
                ),
                (
                    "How are routines learned?",
                    f"A saved time-of-day and weekday activity-count model trains on 14 synthetic days and tests on the next seven. Accuracy is {summary['trained_models']['routine']['accuracy']*100:.1f}% against a 36.6% majority baseline. Auto mode shows confidence and whether the source is the synthetic prior or sufficient personal observations. Inferred activities do not label their own training data.",
                ),
                (
                    "What did the ANN learn?",
                    f"A NumPy network with three inputs, 12 tanh hidden units and one output approximates synthetic sensation labels. It trains by gradient descent on 2,000 points and has a separate 400-point IID synthetic holdout with MAE {summary['ann_validation']['mae_tsv']:.3f} TSV. This checks surrogate fitting, not human comfort prediction.",
                ),
                (
                    "What happens without consent or after withdrawal?",
                    "Generic recommendations remain possible without persistence. Memory changes and imported pilot processing require consent. Withdrawal erases that alias's local logical profile, events, suggestions, feedback, activity observations and fitted room model. Previously exported files and external backups are outside that erasure guarantee.",
                ),
            ],
        ),
        (
            "Physics, comfort and optimization",
            [
                (
                    "What is the RC heat equation?",
                    "C dT/dt = G(Tout - T) + Q, with G = UA + rho cp Vdot and Q = solar + internal + fan power. For constant forcing, Teq = Tout + Q/G and Tnext = Teq + (T - Teq) exp(-G dt/C). The exact step avoids explicit-Euler instability for the assumed constant interval.",
                ),
                (
                    "Why use a one-node RC model?",
                    "It is transparent and inexpensive enough to evaluate many candidate controls. Effective capacitance represents air, fabric and furniture together. It omits spatial gradients and detailed radiant surfaces. A good fit in this synthetic setting is not proof of validity for a real hostel room.",
                ),
                (
                    "Why does the fan heat the room?",
                    "Its electrical power becomes sensible heat. Perceived cooling arises from the airspeed term in the comfort model and is treated separately. A fan does not remove room heat like an air conditioner.",
                ),
                (
                    "Can opening a window make the room hotter?",
                    "Yes. Ventilation exchanges air with outdoors. If outside is warmer, opening increases sensible heat input. If outside is cooler, it can help remove heat. Rain, poor-air and availability constraints can force the window closed.",
                ),
                (
                    "How are sunlight and curtains modeled?",
                    "A time/orientation multiplier converts incident facade solar into a window-gain proxy, multiplied by glazing area and solar factor. Closing the curtain reduces the assumed gain to 25% of the unshaded value. This factor is a declared model assumption, not a measured blind performance curve.",
                ),
                (
                    "How are materials used?",
                    "The optional envelope calculator sums layer thermal resistances and surface films, then converts envelope area and U-values to UA. Density, specific heat and an explicit effective-mass participation factor inform capacitance. The final study uses separately fitted aggregate UA and capacitance from noisy synthetic observations.",
                ),
                (
                    "How was the room calibrated?",
                    f"Fourteen days produce 1,344 noisy observation rows. The first 80% of transitions select UA and effective capacitance, and the last 20% are an untouched chronological test. Test RMSE is {cal['test_rmse_c']:.3f} C, compared with {cal['persistence_test_rmse_c']:.3f} C for persistence. Fitted UA/C differ from the known synthetic plant, illustrating parameter uncertainty.",
                ),
                (
                    "Is the fuzzy score the same as PMV or measured TSV?",
                    "No. Five overlapping triangular sets use effective-temperature error relative to a personal target. Zero-order Sugeno consequents give a sensation proxy from -3 to +3. Humidity penalty and fan relief are heuristic. The score is neither a physiological PMV implementation nor a human comfort vote.",
                ),
                (
                    "What does the GA optimize?",
                    "A one-hour forecast averages absolute fuzzy sensation, a comfort-violation penalty, noise, missing requested airflow and normalized fan electricity, then adds a switching cost. Population 10 and eight generations use elitism, tournament selection, crossover and mutation. Objective weights are assumptions and are tested in a six-weight sweep.",
                ),
                (
                    "Why use a GA for such a small action set?",
                    "At most 24 discrete actions make exhaustive search practical. GA is included to implement and assess the course method. Enumeration audits its quality, and the reported gap can be positive. The exact solution does not silently replace the returned GA result.",
                ),
                (
                    "How is adaptive comfort used?",
                    "The simplified reference uses neutral temperature 0.31 times running-mean outdoor temperature plus 17.8 C, an 80% band and documented elevated-air-speed extensions. It applies only within the declared awake/study and temperature scope. Other periods use a rule fallback. Air temperature substitutes for operative temperature, so this is not a compliance assessment.",
                ),
            ],
        ),
        (
            "Experimental design and conclusions",
            [
                (
                    "Why are the comparisons matched?",
                    "All nine methods share each seed's weather, activity, initial state, available actions and explicit constraints. Each evolves its own closed-loop room trajectory. Physics advances every 15 minutes, while every controller chooses hourly. There are three seeds, seven days per seed, 27 controller runs and 18,144 raw intervals.",
                ),
                (
                    "What separates the survey and conversation methods?",
                    "They begin with the same exact profile and optimizer. At step 356 a scripted study target changes by -1 C in the hidden occupant. An explicit message exposes the change to conversation methods, while the initial survey stays unchanged. Before that change the matched trajectories are identical. This isolates a mechanical retention effect, not general conversational superiority.",
                ),
                (
                    "What is the main energy-comfort result?",
                    f"Proposed: {ours['fan_wh_day']:.1f} fan Wh/day and {ours['comfort_violation_pct']:.2f}% occupied violations. Fixed: {fixed['fan_wh_day']:.1f} Wh/day and {fixed['comfort_violation_pct']:.2f}% violations. Electricity decreases by about 35.1%, but violations increase by 2.38 percentage points. The no-comfort-loss hypothesis is not supported.",
                ),
                (
                    "Why is the generic LLM low energy not a win?",
                    f"It uses {generic['fan_wh_day']:.1f} Wh/day but has {generic['comfort_violation_pct']:.1f}% occupied violations. Turning controls down can save energy while worsening comfort. Energy and comfort must be assessed together. The generic LLM receives current conditions without retained personal history or an RC forecast.",
                ),
                (
                    "What do the ablations establish?",
                    "The unchanged-survey method tests the value of updating the target after the scripted change. Removing physics retains language memory but omits RC lookahead. Physics reduces modeled violations relative to that ablation at higher fan electricity. These are scenario-specific mechanisms rather than proof that the proposed method wins every outcome.",
                ),
                (
                    "How is acceptance measured?",
                    "The benchmark's numerical occupant accepts when assumed sensation is within 1.2 and airflow/noise conditions are satisfied. This is a proxy, separate from actual optional dashboard self-reports. All simulated actions apply even when the proxy declines, so the experiment assumes control compliance.",
                ),
                (
                    "What does EPI mean here?",
                    f"Period fan electricity in kWh divided by room floor area. Proposed seven-day fan EPI is {ours['fan_epi_period_kwh_m2']:.4f} kWh/m2. It excludes other building energy and is neither annual building EPI nor a GRIHA/LEED rating.",
                ),
                (
                    "Are three seeds enough for significance?",
                    "They show variation across three synthetic weather scenarios. Exploratory paired t intervals are not participant confidence intervals, and three scenarios give limited precision. They do not establish human effectiveness or a statistically powered non-inferiority claim.",
                ),
                (
                    "How can the results be reproduced?",
                    "The full study can rerun actual inference using pinned resources. Frozen-response replay instead accepts only exact previously recorded request hashes and labels itself as replay. A separate replay matched the trajectory and sensitivity files byte for byte, all scientific comparison metrics and every language outcome. Machine timings and backend names are excluded from equality.",
                ),
                (
                    "What remains outside the submitted scope?",
                    "Real sensors and motorized controls, measured human comfort, metered whole-building savings and the proposed 20-50 room deployment. The original course proposals place the larger trial after the semester. The approved simulated computational project does not replace that empirical validation.",
                ),
            ],
        ),
    ]
    pitch = f"This project combines both course proposals into one hostel cooling system. An actual local Qwen3 model extracts explicit activity-specific preferences, which are reviewed before saving. A calibrated RC model predicts room conditions, fuzzy comfort scores candidate controls, and a genetic algorithm recommends fan, window and curtain settings. Nine methods were compared over seven days and three weather seeds. The proposed controller used {ours['fan_wh_day']:.1f} fan Wh/day, about 35.1% below fixed scheduling, with a 2.38-point increase in occupied discomfort violations. Thus it demonstrates an energy-comfort trade-off rather than unchanged comfort. Raw data, model outputs, trained artifacts and reproducibility checks accompany the submission. Room and occupant outcomes are simulated; the model inference and software executions are real."
    story = [
        p("FINAL PROJECT / VIVA GUIDE", "label"),
        p("Hostel cooling: defense guide", "title"),
        p(pitch),
        Spacer(1, 10),
        p("Numbers to remember", "subheading"),
        table(
            [
                ["Evidence", "Recorded value"],
                ["Main experiment", "9 methods / 3 seeds / 7 days / 18,144 intervals"],
                ["Proposed vs fixed", "290.7 vs 448.0 Wh/day; +2.38 points discomfort"],
                [
                    "Local language extraction",
                    "17/24 exact matches (70.8%) before user review",
                ],
                ["ANN / routine", "0.148 TSV MAE / 93.5% synthetic routine accuracy"],
                [
                    "Calibrated room forecast",
                    "0.180 C test RMSE vs 0.233 C persistence",
                ],
                [
                    "After preference update",
                    "+9.70 points acceptance proxy versus unchanged survey",
                ],
            ],
            [185, 320],
        ),
        PageBreak(),
    ]
    md = [
        "# Final project viva guide",
        "",
        pitch,
        "",
        "## Numbers to remember",
        "",
        "- Nine methods, three seeds, seven days and 18,144 intervals.",
        "- Fan energy falls 35.1%; occupied discomfort rises 2.38 percentage points.",
        "- Actual raw language accuracy: 70.8%; app review is required before saving.",
        "",
    ]
    for title, questions in groups:
        story.append(p(title, "heading"))
        md += ["## " + title, ""]
        for question, answer in questions:
            story += [
                KeepTogether([p(escape(question), "subheading"), p(escape(answer))])
            ]
            md += ["### " + question, "", answer, ""]
        story.append(PageBreak())
    story += [
        p("Before the presentation", "heading"),
        p(
            "Open the final PPTX and use its speaker notes. Keep the final report and this guide available. Start the local application before presenting and verify the backend is Qwen3-4B. Use a new presentation alias so personal records are not exposed. Demonstrate preview, confirmation, study/sleep persistence, rain constraints and the final comparison table."
        ),
        p("Reproduction commands", "subheading"),
        p(
            "start.bat<br/>python -m unittest discover -s tests -v<br/>python tools/verify_submission.py<br/>python -m hostel_cooling study --backend replay --output build/replay-study<br/>python tools/verify_replay.py"
        ),
        p("Evidence navigation", "subheading"),
        p(
            "The final report explains methods and all eight hypothesis findings. outputs/study/ contains raw intervals, per-seed results, language cases and model journals. models/ contains training datasets and serialized weights. docs/METHODS.md maps the implementation to the supplied proposals."
        ),
        p("Final answer if challenged", "subheading"),
        p(
            "The completed contribution is executable, reproducible computational evidence under stated synthetic assumptions. A negative hypothesis result is still a completed scientific finding. Human benefit and real-room deployment would require measured validation."
        ),
    ]
    md += [
        "## Before presenting",
        "",
        "Use the final PPTX speaker notes, open the local app before starting, and keep the report and raw evidence ready. Demonstrate a dedicated presentation alias, reviewed memory update, activity persistence, rain constraint and final results.",
        "",
        "## Reproduction commands",
        "",
        "```powershell",
        "start.bat",
        "python -m unittest discover -s tests -v",
        "python tools/verify_submission.py",
        "python -m hostel_cooling study --backend replay --output build/replay-study",
        "python tools/verify_replay.py",
        "```",
        "",
    ]
    (out / "VIVA_GUIDE.md").write_text("\n".join(md), encoding="utf-8")
    target = out / "Hostel_Cooling_Viva_Guide.pdf"
    SimpleDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=44,
        rightMargin=44,
        topMargin=43,
        bottomMargin=58,
        title="Hostel cooling viva guide",
    ).build(story, onFirstPage=footer, onLaterPages=footer)
    print(
        json.dumps(
            {
                "path": str(target.resolve()),
                "questions": sum(len(q) for _, q in groups),
            },
            indent=2,
        )
    )
    return target


if __name__ == "__main__":
    build()
