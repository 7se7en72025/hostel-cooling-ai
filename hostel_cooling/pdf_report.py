"""Submission report generated entirely from recorded study evidence."""

import json
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Image,
)

INK = colors.HexColor("#233d33")
GREEN = colors.HexColor("#27684f")
MUTED = colors.HexColor("#667a6d")
STYLES = {
    "body": ParagraphStyle(
        "body",
        fontName="Helvetica",
        fontSize=10,
        leading=15,
        textColor=INK,
        spaceAfter=10,
    ),
    "small": ParagraphStyle(
        "small",
        fontName="Helvetica",
        fontSize=8,
        leading=11.8,
        textColor=MUTED,
        spaceAfter=7,
    ),
    "title": ParagraphStyle(
        "title",
        fontName="Helvetica",
        fontSize=31,
        leading=36,
        textColor=INK,
        spaceAfter=20,
    ),
    "heading": ParagraphStyle(
        "heading",
        fontName="Helvetica-Bold",
        fontSize=21,
        leading=27,
        textColor=INK,
        spaceAfter=18,
    ),
    "subheading": ParagraphStyle(
        "subheading",
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=18,
        textColor=GREEN,
        spaceBefore=10,
        spaceAfter=8,
    ),
    "label": ParagraphStyle(
        "label",
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=14,
        textColor=GREEN,
        spaceAfter=14,
    ),
    "cell": ParagraphStyle(
        "cell", fontName="Helvetica", fontSize=8, leading=11, textColor=INK
    ),
}


def p(text, style="body"):
    return Paragraph(text, STYLES[style])


def table(rows, widths):
    cells = [[p(escape(str(c)), "cell") for c in row] for row in rows]
    result = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
    result.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8efe4")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#dce4d6")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return result


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#dce4d6"))
    canvas.line(44, 43, A4[0] - 44, 43)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(
        44, 29, "HOSTEL COOLING / CE F417 + CE F423 / COMPLETE SIMULATED STUDY"
    )
    canvas.drawRightString(A4[0] - 44, 29, str(doc.page))
    canvas.restoreState()


def build_report(output_dir):
    out = Path(output_dir)
    s = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    rows = {r["method"]: r for r in s["rows"]}
    ours, fixed = rows["ours"], rows["fixed"]
    cal = s["calibration"]
    ann = s["ann_validation"]
    routine = s["trained_models"]["routine"]
    lang = s.get("language_evaluation", {})
    target = out / "Hostel_Cooling_Project_Report.pdf"
    story = [
        p("FINAL COURSE PROJECT / 20 OCTOBER 2026", "label"),
        Spacer(1, 24),
        p("Preference-aware cooling<br/>for student hostels", "title"),
        p(
            "CE F417: Applications of AI in Civil Engineering<br/>CE F423: Green Buildings and Energy Conservation"
        ),
        p("Course instructor: Prof. Rajiv Gupta"),
        Spacer(1, 18),
        p("Completed scope", "subheading"),
        p(
            "A functioning local research application, actual transformer inference, saved comfort and activity models, noisy-data room calibration, complete baseline comparisons, ablations and reproducible evidence. The approved experimental setting uses simulated rooms and occupants."
        ),
        p("Abstract", "subheading"),
        p(
            "This project integrates language-based preference memory with building heat and moisture balances to recommend fan, window and curtain settings. A quantized local Qwen3-4B model extracts activity-specific preferences with quote validation. A fuzzy comfort model and discrete genetic algorithm evaluate legal actions. The study compares fixed, expert, adaptive, neural, room-model and generic-LLM controllers under matched closed-loop conditions, with survey and physics ablations."
        ),
        p(
            f"The comparison covers {s['days_per_seed']} days per weather seed, seeds {s['seeds']}, and {len(rows)} methods. The proposed controller uses {ours['fan_wh_day']:.1f} Wh/day of fan electricity with {ours['comfort_violation_pct']:.1f}% occupied comfort violations. Fixed settings use {fixed['fan_wh_day']:.1f} Wh/day with {fixed['comfort_violation_pct']:.1f}% violations. Results describe simulated performance, not measured energy savings or human acceptance."
        ),
        p("Evidence distinction", "subheading"),
        p(
            "The language model inference, executable software, stored model parameters, calibration procedure and tests are actual computations. Weather, room observations, occupant targets, sensation labels and benchmark acceptance outcomes are synthetic. No human field study is claimed.",
            "small",
        ),
        PageBreak(),
    ]

    story += [
        p("1. Problem and research context", "heading"),
        p(
            "Hostel room controls support different needs during study, sleep and absence. A fixed setting cannot represent every preference or account for changes in outdoor conditions. Fans provide perceived cooling through airflow, windows exchange outdoor air and curtains influence solar heat gains."
        ),
        p("Research questions", "subheading"),
        p(
            "F417 asks whether conversation can retain changing preferences and influence decisions beyond a fixed survey. F423 asks whether a room model improves the comfort-energy trade-off for passive controls. The implementation also tests activity prediction, feedback persistence and the quality of a genetic search."
        ),
        p("Relevant prior work", "subheading"),
        p(
            "Tekler et al. (2023) study active learning for personalized comfort controls. Yang, Siew and Joe-Wong (2024) use LLM-based occupant simulation in a digital twin. Liu, Zhou and Li (2026) study conversational preference trajectories, while Li et al. (2026) consider conversational elicitation under cognitive constraints. The general idea of conversational comfort learning is therefore established prior work."
        ),
        p("Project contribution", "subheading"),
        p(
            "The contribution is an implemented, auditable hostel-control study that joins retained activity preferences with transparent physics and matched baselines. Its scope includes a local model runtime, trained artifacts, held-out language checks, routine inference and a reproducible experimental pipeline. It does not claim to invent conversational preference learning or establish a literature-wide research gap."
        ),
        p("Course mapping", "subheading"),
        table(
            [
                ["CE F417", "CE F423"],
                [
                    "Actual LLM extraction and preference memory",
                    "Room resistance-capacitance heat model",
                ],
                [
                    "Fuzzy memberships and genetic optimization",
                    "Natural ventilation and solar shading proxies",
                ],
                [
                    "ANN, expert and adaptive comparisons",
                    "Fan electricity and period EPI",
                ],
                [
                    "Language evaluation and activity learning",
                    "Noisy observation calibration and validation",
                ],
            ],
            [252, 253],
        ),
        p(
            "Journal references were screened at the primary indexed-abstract level where full text was unavailable. Technical documentation supports implementation details. Source links appear in Section 11.",
            "small",
        ),
        PageBreak(),
    ]

    story += [
        p("2. Implemented system", "heading"),
        p(
            "A participant selects or confirms activity and supplies current room conditions. Consented natural-language feedback enters the local transformer. The extractor proposes structured preference changes and evidence quotes. Validation rejects unknown fields, invalid types, ungrounded quotes and values outside domain limits. The memory store preserves separate activity targets and the evidence for each revision."
        ),
        p("Actual language model", "subheading"),
        table(
            [
                ["Property", "Recorded configuration"],
                ["Model", s["model_provenance"]["model"]],
                ["Quantization", "Q4_K_M"],
                ["Runtime", s["model_provenance"]["runtime"]],
                ["Sampling", "Temperature 0, seed 7, thinking disabled"],
                ["Model SHA256", s["model_provenance"]["sha256"]],
                ["Inference scope", "Local HTTP server, no paid API"],
                ["Decision interval", str(s["control_interval_minutes"]) + " minutes"],
            ],
            [148, 357],
        ),
        p("Grounded preference updates", "subheading"),
        p(
            "The extraction schema covers a desired temperature and its activity, a sleep fan limit and study airflow. Every non-null value requires a quote contained in the original message. A model-based verification request can repair an invalid quote. Unsupported preferences remain unchanged. Numeric and Boolean domain checks apply before commit. No offline parser silently substitutes for an unavailable model."
        ),
        p("Persistent context and privacy", "subheading"),
        p(
            "SQLite stores consent, profiles, preference evidence, suggestions, actual optional self-reported feedback, activity observations and calibrated room models. Participant aliases separate local profiles. Export and erasure cover those logical records. The service binds to localhost and rejects unrelated origins. Simulation benchmark feedback remains separate from actual user self-reports."
        ),
        p("Recorded inference", "subheading"),
        p(
            "Each study request records its prompt, input, structured output, pinned model identity, usage and elapsed time. Matching requests may reuse explicitly labeled cache records. Frozen response replay supports reproduction without inventing new model answers. Model weights and inference binaries remain outside Git and are downloaded from pinned sources with checksums."
        ),
        PageBreak(),
    ]

    story += [
        p("3. Building physics and calibration", "heading"),
        p(
            "A one-node thermal resistance-capacitance model represents a well-mixed room with effective fabric and furniture capacitance. For constant forcing during one step:"
        ),
        p(
            "G = UA + rho cp Vdot<br/>Q = Qsolar + Qinternal + Pfan<br/>C dT/dt = G (Tout - T) + Q<br/>Teq = Tout + Q/G<br/>Tnext = Teq + (T - Teq) exp(-G dt/C)"
        ),
        table(
            [
                ["Parameter", "Synthetic plant", "Fitted controller"],
                ["Area / height", "12 m2 / 3 m", "12 m2 / 3 m"],
                ["UA / W K-1", s["plant_room"]["ua_w_k"], s["room"]["ua_w_k"]],
                [
                    "Effective C / MJ K-1",
                    s["plant_room"]["capacity_j_k"] / 1e6,
                    s["room"]["capacity_j_k"] / 1e6,
                ],
                ["Window / gain factor", "2 m2 / 0.6", "2 m2 / 0.6"],
                ["Fan power / W", "0, 18, 38, 65", "0, 18, 38, 65"],
            ],
            [205, 150, 150],
        ),
        p("Ventilation and moisture", "subheading"),
        p(
            "Air changes use a wind/opening proxy. Open windows can warm the room when outdoor air is hotter. Curtains reduce assumed transmitted solar gains. Fan electrical power enters the sensible heat balance, while airflow relief enters the comfort model separately. A humidity-ratio balance includes outdoor air exchange and an assumed occupant moisture source."
        ),
        p("Chronological calibration", "subheading"),
        p(
            f"A separate 14-day synthetic observation dataset contains 1,344 records with independent sensor noise. The first {cal['train_transitions']} transitions select parameters. The final {cal['test_transitions']} transitions remain held out. Test RMSE is {cal['test_rmse_c']:.3f} C, MAE {cal['test_mae_c']:.3f} C and mean bias {cal['test_bias_c']:.3f} C. Persistence RMSE is {cal['persistence_test_rmse_c']:.3f} C."
        ),
        p(
            "The fitted conductance differs from the known generator value. Noise, errors in predictors and weak parameter identifiability can bias a one-step fit. Low prediction error is not proof of correct physical parameters. The study intentionally keeps the calibrated controller distinct from the known simulated plant.",
            "small",
        ),
        PageBreak(),
    ]

    story += [
        p("4. Comfort and optimization", "heading"),
        p(
            "The comfort controller uses an effective-temperature proxy that combines indoor air temperature, a heuristic airspeed relief and a humidity penalty. Its error relative to the current activity target drives five overlapping triangular fuzzy sets. Centers at -4, -2, 0, 2 and 4 C have sensation consequents -3, -1.5, 0, 1.5 and 3. Weighted defuzzification gives a TSV proxy."
        ),
        p("Optimization objective", "subheading"),
        p(
            "The one-hour rollout averages absolute fuzzy sensation, a comfort-violation penalty, requested airflow, activity-specific fan noise and normalized fan electricity. A switching term discourages unnecessary changes. Weather and activity remain constant through each candidate forecast. The objective weights are assumptions whose sensitivity is reported separately."
        ),
        p("Genetic search and audit", "subheading"),
        p(
            "A candidate contains fan speed, window opening and curtain state. The GA uses population 10, eight generations, tournament selection, elitism, crossover and mutation. At most 24 feasible actions make exhaustive auditing possible. The reported action remains the GA solution; the audit reports a nonnegative objective gap rather than replacing it with the exact optimum."
        ),
        p("Constraints", "subheading"),
        table(
            [
                ["Condition", "Constraint"],
                ["Away", "Fan off"],
                ["Sleeping", "Learned or initial sleep fan maximum"],
                ["Rain / poor outdoor air", "Window closed"],
                ["Window unavailable", "Window closed"],
                ["All conditions", "Discrete validated control values"],
            ],
            [252, 253],
        ),
        p("Adaptive reference", "subheading"),
        p(
            "The adaptive neutral temperature uses 0.31 Trunning + 17.8 C, with the 80% band and airspeed extensions. Its scoped reference calculation requires awake/study activity and valid thermal inputs. Sleeping and away periods use an explicitly identified expert fallback. Air temperature approximates operative temperature, so this project makes no standards-compliance claim."
        ),
        PageBreak(),
    ]

    method_rows = [["Method", "Role"]] + [
        [key, value["label"]] for key, value in rows.items()
    ]
    story += [
        p("5. Experimental design", "heading"),
        p(
            f"The main trial uses {s['days_per_seed']} days for each of {len(s['seeds'])} distinct weather seeds. Physics advances every 15 minutes; every controller chooses settings on the same {s['control_interval_minutes']}-minute cadence. Identical forcing, initial conditions, common explicit constraints and hidden occupant scenarios support paired comparisons. Each policy evolves its own room trajectory."
        ),
        table(method_rows, [93, 412]),
        p("Preference ablations", "subheading"),
        p(
            "Ours and the one-time survey begin with identical explicit profiles. A scripted mid-trial change shifts the synthetic occupant's study target. Only a conversation exposes that change to memory-enabled methods. The no-physics method retains language-based memory but scores current comfort without an RC forecast. The generic LLM sees current conditions and legal control values without personal history or room simulation."
        ),
        p("Outcome definitions", "subheading"),
        p(
            "Fan Wh/day includes all intervals. Mean absolute sensation and comfort violations exclude away periods. Acceptance is an independent numerical occupant-oracle proxy and includes airflow/noise criteria. Every suggested action still applies in the simulation, even if the proxy declines it. Controller timings exclude preference extraction, which is logged separately."
        ),
        PageBreak(),
    ]

    result_rows = [
        ["Controller", "Fan Wh/day", "Mean |TSV|", "Violation %", "Accept %"]
    ]
    for key, r in rows.items():
        result_rows.append(
            [
                key,
                f"{r['fan_wh_day']:.1f}",
                f"{r['mean_abs_tsv_proxy']:.2f}",
                f"{r['comfort_violation_pct']:.1f}",
                f"{r['acceptance_proxy_pct']:.1f}",
            ]
        )
    story += [
        p("6. Main comparison results", "heading"),
        table(result_rows, [101, 101, 101, 101, 101]),
        Spacer(1, 13),
        Image(str(out / "comparison.png"), width=505, height=177),
        p(
            f"Relative to fixed settings, the proposed controller's fan electricity changes by {ours['fan_energy_change_vs_fixed_pct']:+.1f}%. Occupied violation rate changes by {ours['comfort_violation_pct']-fixed['comfort_violation_pct']:+.2f} percentage points. Both outcomes matter: lower fan use alone cannot establish improved performance."
        ),
        p(
            f"Its period fan EPI is {ours['fan_epi_period_kwh_m2']:.4f} kWh/m2 over this {s['days_per_seed']}-day trial. This excludes other electrical loads and makes no annual whole-building EPI claim."
        ),
        p(
            "Error bars describe SD across weather seeds. Three weather seeds are not three participants. A synthetic sensation oracle related to the controller assumptions cannot independently validate human comfort. Full per-seed tables, paired contrasts and raw trajectories accompany the report.",
            "small",
        ),
        PageBreak(),
    ]

    story += [
        p("7. Ablations and weight sensitivity", "heading"),
        p("Memory and physics comparisons", "subheading"),
    ]
    for key in ("survey", "no_physics", "physics", "generic_llm"):
        r = rows[key]
        story.append(
            p(
                f"Against {key}, ours changes fan use by {ours['fan_wh_day']-r['fan_wh_day']:+.1f} Wh/day, violations by {ours['comfort_violation_pct']-r['comfort_violation_pct']:+.2f} percentage points and acceptance proxy by {ours['acceptance_proxy_pct']-r['acceptance_proxy_pct']:+.2f} percentage points."
            )
        )
    if (out / "sensitivity.png").exists():
        story += [Image(str(out / "sensitivity.png"), width=470, height=268)]
    story += [
        p(
            "The predeclared energy-weight sweep uses 0, 0.1, 0.25, 0.5, 1 and 2 under the same three weather seeds for three days per condition. It illustrates the objective's trade-off, rather than selecting a winning weight using the test outcomes."
        ),
        p("Paired uncertainty", "subheading"),
        p(
            "For each contrast, per-seed differences yield a mean, sample SD and exploratory 95% Student-t interval. With only three weather seeds these intervals are descriptive and underpowered. They are not participant-effect confidence intervals. No human causal effect or statistical superiority follows."
        ),
        PageBreak(),
    ]

    story += [
        p("8. Model validation and retained context", "heading"),
        table(
            [
                ["Model / task", "Evaluation result"],
                [
                    "Comfort ANN",
                    f"2,000 synthetic training points, 400 IID holdout points; MAE {ann['mae_tsv']:.3f} TSV",
                ],
                [
                    "Activity routine learner",
                    f"14 train days / 7 chronological test days; accuracy {routine['accuracy']*100:.1f}%, macro-F1 {routine['macro_f1']:.3f}",
                ],
                [
                    "Majority activity baseline",
                    f"Accuracy {routine['majority_baseline_accuracy']*100:.1f}%",
                ],
                [
                    "LLM held-out phrases",
                    f"{lang.get('n',0)} cases; exact-match accuracy {lang.get('exact_match_accuracy',0)*100:.1f}%, field F1 {lang.get('field_f1',0):.3f}",
                ],
                [
                    "Persistent cross-activity memory",
                    str(lang.get("memory_context_persistent", False)),
                ],
                [
                    "Consent withdrawal / erasure",
                    str(lang.get("consent_erasure_passed", False)),
                ],
            ],
            [175, 330],
        ),
        p("Actual inference evaluation", "subheading"),
        p(
            "The fixed language benchmark covers desired temperatures, airflow, sleep noise, mixed activities, unrelated messages, negation and invalid values. Every case and error remains in language_evaluation.json. Development prompt examples are separate from the held-out phrases. Missing fields, extra fields and incorrect activities reduce the reported accuracy. A safe refusal of an invalid preference does not create a memory update."
        ),
        p("Review before saving", "subheading"),
        p(
            "The benchmark evaluates raw automatic extraction without human correction. Because the observed failures include extra inferred preferences, the application presents every proposed interpretation for explicit confirmation or discard before saving. Preview does not change memory. Confirmation rechecks consent and the profile revision. This review step is a software safeguard, not an improvement to the reported raw benchmark score."
        ),
        p("Activity learning", "subheading"),
        p(
            "The saved routine model learns time and weekday distributions from explicit activity observations. A synthetic pretrained prior supports cold starts; the application names that source. With sufficient personal observations, it combines those observations with a weaker prior. Auto mode shows predicted activity and confidence. Automatically inferred activities do not label their own training data."
        ),
        p("Interpretation", "subheading"),
        p(
            "ANN accuracy describes a synthetic fit, routine accuracy describes a synthetic schedule holdout, and language accuracy describes controlled phrases. These tests establish executable behavior and reveal model weaknesses. None constitutes human comfort validation."
        ),
        PageBreak(),
    ]

    story += [
        p("9. Application and reproducibility", "heading"),
        p(
            "The local application supports participant aliases, opt-in preference storage, activity-specific conversation memory, actual local transformer requests, learned routine selection, control forecasts, explicit constraints, saved suggestions, self-reported feedback, CSV validation, room calibration, profile export and withdrawal. Model and study runs use the same Python modules as the application."
        ),
        p("One-command study", "subheading"),
        p(
            "python -m hostel_cooling setup-model<br/>python -m hostel_cooling study<br/>python -m hostel_cooling serve"
        ),
        p("Pinned resources", "subheading"),
        p(
            "The portable inference runtime and model weights use pinned release/revision URLs and SHA256 checks. The ANN weights, routine counts, synthetic training datasets and validation metadata are saved. Requirements and setup scripts recreate the software environment. Large runtime binaries, weights and private profile data remain outside Git."
        ),
        p("Evidence files", "subheading"),
        table(
            [
                ["File", "Purpose"],
                ["summary.json / runs.csv", "Aggregate and per-seed metrics"],
                ["trajectories.csv", "Every policy action and room state"],
                ["llm_inference.jsonl", "Actual model request/response journal"],
                ["language_evaluation.json", "All held-out phrase outcomes"],
                ["calibration.json", "Parameters and chronological holdout error"],
                ["paired_comparisons.csv", "Paired weather-seed contrasts"],
                ["sensitivity.csv", "Predeclared objective-weight sweep"],
                ["models/", "Saved neural and routine artifacts"],
            ],
            [200, 305],
        ),
        p("Software checks", "subheading"),
        p(
            "Tests cover physical directionality and analytical integration, feasible actions, GA auditing, malformed inputs, consent-gated persistence, transactional rollback, profile isolation, erasure, model serialization, routine inference, noisy calibration and cache-only replay. Browser checks exercise actual model memory, constraints, calibration, activity inference and responsive layouts."
        ),
        PageBreak(),
    ]

    story += [
        p("10. Conclusions and limits", "heading"),
        p(
            "The project completes the simulated computational scope for both courses. It connects actual local language inference to persistent preferences, calibrated synthetic room physics and constrained recommendations. Both baseline sets now include a real generic LLM policy. Saved models, source data, held-out checks, raw inference records and repeatable scripts make the results reviewable."
        ),
        p("Hypothesis interpretation", "subheading"),
        p(
            "The experiment directly tests synthetic memory, physics and energy trade-offs. A scripted preference change supports a mechanical retention test. Routine prediction is evaluated on a chronological synthetic holdout. Actual preference-extraction quality is measured on controlled phrases. Claims about student satisfaction, survey burden or human acceptance require a separately consented field study."
        ),
        p("Model limitations", "subheading"),
        p(
            "The 1R1C model omits surface radiation, spatial stratification, condensation and latent thermal coupling. Its ventilation and facade solar factors are proxies. One-step parameter estimation can remain biased despite low error. Air temperature stands in for operative temperature. The fuzzy sensation equation and acceptance oracle are related assumptions, and the synthetic ANN learns a generic occupant."
        ),
        p("Control limitations", "subheading"),
        p(
            "Constant-forcing forecasts, fixed objective weights and a small discrete control set limit long-horizon optimality. All simulated actions apply regardless of acceptance. GA auditing reports residual suboptimality; a larger study should assess forecast uncertainty and controller calibration. The local language model can miss paraphrases or propose invalid fields, which the validation layer must handle."
        ),
        p("Scope distinction", "subheading"),
        p(
            "Physical sensors, motorized actuators, whole-building metering and a multi-room human trial are outside the approved simulated project. No ASHRAE, GRIHA or LEED certification is claimed. The software and simulation study are completed deliverables; field validation remains a separate empirical task."
        ),
        PageBreak(),
    ]

    refs = [
        (
            "EnergyPlus zone heat-balance reference",
            "https://energyplus.readthedocs.io/en/stable/guides/engineering-reference/2.1-basis-for-the-zone-and-air-system-integration.html",
        ),
        (
            "CBE Thermal Comfort Tool",
            "https://cbe.berkeley.edu/research/cbe-thermal-comfort-tool/",
        ),
        (
            "pythermalcomfort adaptive-model applicability",
            "https://pythermalcomfort.readthedocs.io/en/latest/documentation/models.html",
        ),
        (
            "Tekler et al. (2023), active comfort preference learning",
            "https://arxiv.org/abs/2309.09073",
        ),
        (
            "Yang, Siew and Joe-Wong (2024), LLM digital twin",
            "https://arxiv.org/abs/2403.16809",
        ),
        (
            "Liu, Zhou and Li (2026), conversational preference learning",
            "https://doi.org/10.1016/j.enbuild.2026.117181",
        ),
        (
            "Li et al. (2026), conversational preference elicitation",
            "https://doi.org/10.1016/j.buildenv.2026.114586",
        ),
        (
            "Qwen3-4B official GGUF model and Apache-2.0 license",
            "https://huggingface.co/Qwen/Qwen3-4B-GGUF",
        ),
        (
            "llama.cpp local server and schema-constrained responses",
            "https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md",
        ),
    ]
    from .conclusions import assess_hypotheses

    assessment = assess_hypotheses(out)
    for index, course in enumerate(("F417", "F423"), 11):
        story += [
            p(f"{index}. {course} hypothesis assessment", "heading"),
            p(
                "Each original proposal hypothesis is assessed against the recorded study. Support below is limited to the stated synthetic setting. A negative finding is a completed result."
            ),
            table(
                [["Hypothesis", "Finding", "Evidence and interpretation"]]
                + [
                    [
                        h["id"] + ": " + h["question"],
                        h["verdict"],
                        h["evidence"] + " " + h["limit"],
                    ]
                    for h in assessment["hypotheses"]
                    if h["id"].startswith(course)
                ],
                [115, 125, 265],
            ),
            Spacer(1, 18),
            p("Preference-change comparison", "subheading"),
            p(
                f"After the scripted target update, the conversation method has {assessment['post_change_acceptance_difference_pp']:+.2f} percentage points higher acceptance proxy than the unchanged survey. The pre-change trajectories are identical under the matched optimizer. The phase split and each seed's raw metrics are exported in preference_change_phases.csv."
            ),
            p(assessment["phase_comparison_note"], "small"),
            PageBreak(),
        ]
    story += [p("13. References", "heading")]
    for title, url in refs:
        story.append(p(f'<link href="{url}" color="#27684f">{escape(title)}</link>'))
    story += [
        Spacer(1, 20),
        p(
            "The supplied CE F417 and CE F423 proposal PDFs define the research question, control set, baseline families and in-course scope. This report integrates them into one completed simulated study. References checked 20 October 2026.",
            "small",
        ),
    ]
    SimpleDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=44,
        rightMargin=44,
        topMargin=43,
        bottomMargin=58,
        title="Preference-aware cooling for student hostels",
        author="Hostel Cooling Project",
    ).build(story, onFirstPage=footer, onLaterPages=footer)
    return target
