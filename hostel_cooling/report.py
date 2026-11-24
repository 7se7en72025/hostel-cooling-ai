import html
from pathlib import Path

SOURCES = [
    (
        "EnergyPlus Engineering Reference: zone heat balance",
        "https://energyplus.readthedocs.io/en/stable/guides/engineering-reference/2.1-basis-for-the-zone-and-air-system-integration.html",
    ),
    (
        "CBE Thermal Comfort Tool: adaptive and elevated-air-speed context",
        "https://cbe.berkeley.edu/research/cbe-thermal-comfort-tool/",
    ),
    (
        "pythermalcomfort: adaptive model and applicability",
        "https://pythermalcomfort.readthedocs.io/en/latest/documentation/models.html",
    ),
    (
        "Ollama: structured outputs",
        "https://docs.ollama.com/capabilities/structured-outputs",
    ),
]


def _write_legacy_report(summary, output):
    out = Path(output)
    rows = summary["rows"]
    plot_available = False
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        labels = [r["method"] for r in rows]
        colors = ["#167d64" if m == "ours" else "#a4b6c1" for m in labels]
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), layout="constrained")
        for ax, metric, title, ylabel in [
            (axes[0], "fan_wh_day", "Fan electricity", "Wh / day"),
            (
                axes[1],
                "comfort_violation_pct",
                "Occupied comfort violations",
                "% of occupied intervals",
            ),
        ]:
            ax.bar(
                labels,
                [r[metric] for r in rows],
                yerr=[r[metric + "_sd"] for r in rows],
                color=colors,
                capsize=3,
            )
            ax.set(title=title, ylabel=ylabel)
            ax.tick_params(axis="x", rotation=40)
            ax.spines[["top", "right"]].set_visible(False)
        fig.suptitle(
            "SYNTHETIC SIMULATION | error bars: SD across weather seeds", fontsize=11
        )
        fig.savefig(out / "comparison.png", dpi=170)
        fig.savefig(out / "comparison.svg")
        plt.close(fig)
        svg_path = out / "comparison.svg"
        svg_path.write_text(
            "\n".join(
                line.rstrip()
                for line in svg_path.read_text(encoding="utf-8").splitlines()
            )
            + "\n",
            encoding="utf-8",
        )
        plot_available = True
    except ImportError:
        pass
    escape = html.escape
    body_rows = "".join(
        f'<tr><td>{escape(r["method"])}</td><td>{r["fan_wh_day"]:.1f}</td><td>{r["fan_epi_period_kwh_m2"]:.4f}</td><td>{r["mean_abs_tsv_proxy"]:.2f}</td><td>{r["comfort_violation_pct"]:.1f}%</td><td>{r["acceptance_proxy_pct"]:.1f}%</td><td>{r["controller_latency_ms_median"]:.2f}</td></tr>'
        for r in rows
    )
    limitations = "".join(f"<li>{escape(s)}</li>" for s in summary["limitations"])
    methods = "".join(
        f'<li><b>{escape(r["method"])}</b>: {escape(r["label"])}.</li>' for r in rows
    )
    skipped = "".join(f"<li>{escape(str(s))}</li>" for s in summary["skipped"])
    sources = "".join(f'<li><a href="{u}">{escape(t)}</a></li>' for t, u in SOURCES)
    ours = next((r for r in rows if r["method"] == "ours"), None)
    fixed = next((r for r in rows if r["method"] == "fixed"), None)
    finding = (
        f'The preference controller used {ours["fan_wh_day"]:.1f} Wh/day, with {ours["comfort_violation_pct"]:.1f}% synthetic occupied comfort violations. Its fan electricity changed by {ours["fan_energy_change_vs_fixed_pct"]:+.1f}% relative to the fixed schedule. Comfort and energy must be assessed together; energy reduction alone does not establish success.'
        if ours and fixed
        else "The preference controller did not complete; review skipped methods before interpreting results."
    )
    if ours and not fixed:
        finding = f'The preference controller used {ours["fan_wh_day"]:.1f} Wh/day with {ours["comfort_violation_pct"]:.1f}% synthetic comfort violations. This subset has no fixed-schedule reference.'
    if ours and fixed:
        finding += f' Against fixed settings, occupied violations changed by {ours["comfort_violation_pct"]-fixed["comfort_violation_pct"]:+.2f} percentage points and mean absolute TSV changed from {fixed["mean_abs_tsv_proxy"]:.2f} to {ours["mean_abs_tsv_proxy"]:.2f}. This run does not establish the no-comfort-penalty hypothesis.'
    content = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Hostel cooling | Research report</title>
    <style>body{{font:16px/1.65 system-ui;color:#19332e;background:#f3f5f0;margin:0}}main{{max-width:1060px;margin:auto;padding:50px 30px}}h1{{font-size:46px;line-height:1.1;max-width:800px}}h2{{margin-top:40px}}.tag{{color:#a14824;font-weight:700;letter-spacing:1px}}table{{border-collapse:collapse;width:100%;font-size:13px;background:white}}td,th{{padding:10px;text-align:left;border-bottom:1px solid #dde4dc}}img{{width:100%}}code{{background:#e5eae2;padding:3px}}a{{color:#167d64}}.box{{background:#e1ece4;padding:22px;border-left:4px solid #167d64}}@media print{{body{{background:white}}main{{padding:0}}h2{{break-after:avoid}}tr,img{{break-inside:avoid}}}}</style><main>
    <div class="tag">CE F417 + CE F423 / SYNTHETIC COURSE PROTOTYPE</div><h1>Preference-aware cooling for student hostels</h1>
    <p>One project combining Applications of AI in Civil Engineering and Green Buildings and Energy Conservation. Controls: fan, window and curtain. Advisory software; no physical actuators.</p>
    <div class="box"><b>Evidence status</b><p>{escape(summary["provenance"])}. Preference backend: {escape(summary["preference_backend"])}. This work completes the computational prototype and reproducible simulated comparison; a consented human pilot remains future work.</p></div>
    <h2>Abstract</h2><p>The prototype tests whether activity-specific preference memory can inform low-energy room-control suggestions. A one-node resistance-capacitance room model predicts temperature; a moisture balance estimates relative humidity. A fuzzy comfort model and a discrete genetic algorithm trade comfort, fan electricity, noise and switching. Fixed, expert, adaptive, neural and physics-only baselines are compared on identical seeded weather. A one-time-survey ablation isolates memory updates. Human hypotheses remain untested.</p>
    <h2>Research questions</h2><p>F417: can conversation retain changing study/sleep preferences, and does that improve acceptance? F423: does adding room physics improve the comfort-energy trade-off? Conversation-versus-survey superiority, real energy savings and human acceptance require field data.</p>
    <h2>Methods</h2><p>Room: 12 m², 3 m height, west orientation, UA=45 W/K, effective C=2 MJ/K, 2 m² window, glazing gain factor 0.6. All are illustrative assumptions. The 15-minute analytical heat balance is C dT/dt = (UA + rho cp Vdot)(Tout-T) + Qsolar + Qinternal + Pfan. Fans add sensible heat; their perceived cooling is represented separately.</p>
    <p>A 60-minute constant-forcing rollout scores feasible actions. The GA uses population 10, eight generations, tournament selection, elitism, crossover and mutation. At most 24 actions allow an exhaustive audit; the returned GA action is retained even if the audit finds a better action. Sleep fan limits and closed-window constraints apply to all policies.</p>
    <ul>{methods}</ul><h3>Unavailable or failed runs</h3><ul>{skipped or '<li>None.</li>'}</ul>
    <h2>Experimental protocol</h2><p>{summary["days_per_seed"]} days per seed; seeds {escape(str(summary["seeds"]))}; 15-minute steps. Policies start from identical temperatures and share weather, initial explicit constraints and the hidden occupant scenario. Each policy evolves its own room state. All suggestions are automatically applied for comparison; acceptance is evaluated separately. Ours and survey receive the same initial survey, then a scripted mid-trial change is revealed only through conversation to ours. No raw human data is used.</p>
    <p>ANN holdout MAE: {summary["ann_validation"]["mae_tsv"]:.3f} TSV units on 400 synthetic IID samples; 2000 training samples. This is a synthetic fit check. Controller latency excludes preference extraction; extraction latency is separately logged in conversation_evidence.json.</p>
    <h2>Results</h2><p>{finding}</p>{'<img src="comparison.png" alt="Fan electricity and comfort violations by controller">' if plot_available else ''}
    <div style="overflow:auto"><table><thead><tr><th>Controller</th><th>Fan Wh/day</th><th>Period fan kWh/m²</th><th>Mean |TSV| proxy</th><th>Violations</th><th>Acceptance proxy</th><th>Median ms</th></tr></thead><tbody>{body_rows}</tbody></table></div>
    <p>EPI covers fan electricity during this trial only. No annual extrapolation or whole-building claim is made. Away intervals count toward electricity but are excluded from comfort/acceptance denominators. Per-seed data and SD are exported. A small number of weather seeds is not a human sample size.</p>
    <h2>Hypothesis status and discussion</h2><p>H1 (conversation vs survey) and H3 (human acceptance) are not established. The scripted preference shift checks memory behavior mechanically. H2 (activity awareness) is implemented with explicit activity inputs rather than inferred routines. H4 (lower energy without reduced comfort) must be evaluated from both columns, and remains a simulated observation, not a validated claim. An actual LLM baseline is omitted until a model is configured; the memoryless rule surrogate is clearly separate.</p>
    <h2>Limitations</h2><ul>{limitations}</ul>
    <h2>Pilot and ethics plan</h2><p>Collect at least seven consecutive days of 15-minute indoor/outdoor temperature, RH, facade solar/wind proxies, occupied activity, controls, fan power and optional TSV/accept-reject feedback. Obtain informed opt-in before storage, use pseudonymous IDs, allow export and deletion, and never infer sensitive traits. Calibrate UA and capacitance with chronological training data and report held-out one-step RMSE. Randomize controller periods in a later crossover study and analyze paired comfort and metered-energy outcomes. A 20-50 room deployment is outside the completed scope.</p>
    <h2>Reproduction</h2><p><code>python -m hostel_cooling experiment --days 7 --seeds 11 23 47</code></p><p>Raw exports: summary.json, comparison.csv, runs.csv, trajectories.csv and conversation_evidence.json. See README.md, docs/METHODS.md and docs/PILOT_PROTOCOL.md in the repository.</p>
    <h2>Sources and design context</h2><p>The supplied F417 and F423 proposal PDFs define the project scope. The simplified equations are this project's implementation, informed by the sources below; they do not reproduce a certified implementation.</p><ul>{sources}</ul><p>References checked 20 October 2026.</p></main></html>"""
    (out / "report.html").write_text(content, encoding="utf-8")


def write_report(summary, output):
    _write_legacy_report(summary, output)
    if "language_evaluation" not in summary:
        return
    out = Path(output)
    escape = html.escape
    rows = summary["rows"]
    language = summary["language_evaluation"]
    cal = summary["calibration"]
    from .conclusions import assess_hypotheses

    hypotheses = assess_hypotheses(out)
    hypothesis_rows = "".join(
        f'<tr><td>{escape(h["id"] + ": " + h["question"])}</td><td>{escape(h["verdict"])}</td><td>{escape(h["evidence"] + " " + h["limit"])}</td></tr>'
        for h in hypotheses["hypotheses"]
    )
    result_rows = "".join(
        f'<tr><td>{escape(r["label"])}</td><td>{r["fan_wh_day"]:.1f}</td><td>{r["mean_abs_tsv_proxy"]:.2f}</td><td>{r["comfort_violation_pct"]:.1f}%</td><td>{r["acceptance_proxy_pct"]:.1f}%</td></tr>'
        for r in rows
    )
    weather_note = (
        "Paired comparisons across weather scenarios give exploratory intervals."
        if len(summary["seeds"]) > 1
        else "The single weather scenario gives a matched comparison. More scenarios would let us estimate how results vary."
    )
    days = summary["days_per_seed"]
    day_label = "day" if days == 1 else "days"
    weather_count = len(summary["seeds"])
    weather_label = "scenario" if weather_count == 1 else "scenarios"
    files = (
        "summary.json",
        "runs.csv",
        "trajectories.csv",
        "llm_inference.jsonl",
        "language_evaluation.json",
        "calibration.json",
        "paired_comparisons.csv",
        "sensitivity.csv",
        "hypothesis_assessment.json",
        "preference_change_phases.csv",
        "PRESENTATION_NOTES.md",
        "reproducibility_verification.json",
    )
    links = " ".join(
        f'<a href="{name}">{name}</a>' for name in files if (out / name).is_file()
    )
    source_links = "".join(
        f'<li><a href="{url}">{escape(title)}</a></li>' for title, url in SOURCES
    )
    content = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Completed hostel cooling study</title>
    <style>body{{font:16px/1.65 system-ui;color:#213d31;background:#f4f6ef;margin:0}}main{{max-width:1080px;margin:auto;padding:48px 28px}}h1{{font:46px/1.1 Georgia;max-width:900px}}h2{{margin-top:38px}}a{{color:#27684f}}.evidence{{background:#e4eddf;padding:20px;border-left:4px solid #27684f}}table{{width:100%;border-collapse:collapse;font-size:13px;background:white}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #dce4d6}}img{{width:100%;height:auto}}.downloads a{{display:inline-block;margin:8px 15px 8px 0}}@media print{{body{{background:white}}main{{padding:0}}tr,img{{break-inside:avoid}}}}</style><main>
    <p>CE F417 + CE F423 / SIMULATED RESEARCH PROJECT</p><h1>Preference-aware cooling for student hostels</h1><p><a href="Hostel_Cooling_Project_Report.pdf">Download the study PDF</a></p>
    <div class="evidence"><b>Inference mode: {escape(summary['inference_mode'])}</b><p>The run covers activity preferences, trained neural and routine models, noisy-data calibration and course baseline comparisons. Room and occupant outcomes are simulated.</p></div>
    <h2>Research design</h2><p>The study covers {days} simulated {day_label} per weather scenario, with {weather_count} {weather_label} in total. Room physics advances every 15 minutes. All {len(rows)} controllers choose actions every {summary["control_interval_minutes"]} minutes under the same weather and constraints.</p>
    <h2>Language inference</h2><p>Model: {escape(summary["preference_backend"])}. The main comparison used {summary["llm_calls"]} model responses, including {summary["llm_cache_hits"]} retrieved from saved responses. Structured extractions require original-message evidence quotes and validated values.</p>
    <p>Held-out language benchmark: {language["n"]} phrases, {language["exact_match_accuracy"]*100:.1f}% exact-match accuracy and field F1 {language["field_f1"]:.3f}. All successes, misses and rejected invalid preferences remain available.</p>
    <p>The benchmark measures raw extraction without human correction. The application shows proposed preference changes for explicit confirmation or discard before saving. Preview leaves memory unchanged, and confirmation rechecks consent and the profile revision.</p>
    <h2>Calibrated room model</h2><p>Fourteen days of noisy synthetic observations fit the controller model. Training and test transitions are chronological and separate. Held-out RMSE: {cal["test_rmse_c"]:.3f} C, versus {cal["persistence_test_rmse_c"]:.3f} C for persistence. The fitted conductance differs from the known plant value, illustrating parameter identifiability and noise limitations.</p><img src="calibration.png" alt="Chronological calibration holdout error">
    <h2>Baseline comparisons</h2><img src="comparison.png" alt="Fan electricity and occupied comfort violations"><div style="overflow:auto"><table><thead><tr><th>Controller</th><th>Fan Wh/day</th><th>Mean |TSV| proxy</th><th>Violations</th><th>Acceptance proxy</th></tr></thead><tbody>{result_rows}</tbody></table></div>
    <p>F417 compares expert rules, adaptive comfort, ANN, generic LLM and the proposed method. F423 compares fixed passive settings, adaptive comfort, room physics, generic LLM and the proposed method. Survey and no-physics variants isolate retained context and forecast effects.</p>
    <h2>Closed-loop behavior</h2><img src="trajectories.png" alt="Matched fixed, generic LLM and proposed-controller room trajectories">
    <h2>Objective sensitivity</h2><img src="sensitivity.png" alt="Fan energy versus synthetic comfort under predeclared energy weights"><p>The sweep reports all six predeclared energy weights. It illustrates trade-offs and does not retrospectively select a winning test condition.</p>
    <h2>What the findings establish</h2><p>The study shows how the software behaved under the conditions tested. Comfort and acceptance were estimated by a simulated occupant model. A human study would be needed to measure savings and comfort in occupied rooms. {weather_note}</p>
    <p>EPI covers fan kWh per floor area during the simulated period. It excludes other building energy and makes no annual or certification claim. Physical actuators, measured field outcomes and multi-room human deployment are outside the approved simulated scope.</p>
    <h2>Answers to the original hypotheses</h2><div style="overflow:auto"><table><thead><tr><th>Hypothesis</th><th>Finding</th><th>Evidence and limits</th></tr></thead><tbody>{hypothesis_rows}</tbody></table></div>
    <p>Before the preference change, proposed and survey trajectories are exactly identical. After the recorded change, acceptance proxy differs by {hypotheses['post_change_acceptance_difference_pp']:+.2f} percentage points. Different phase durations and weather prevent interpreting an unpaired before/after difference as a human treatment effect.</p>
    <h2>Evidence downloads</h2><div class="downloads">{links}</div>
    <h2>Sources</h2><ul>{source_links}<li><a href="https://huggingface.co/Qwen/Qwen3-4B-GGUF">Official Qwen3-4B model</a></li><li><a href="https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md">llama.cpp schema-constrained server</a></li></ul>
    <p>Source code, model artifacts, interval data, tests, setup scripts and the full PDF accompany the study. The supplied course proposals define the combined question and in-course scope.</p></main></html>"""
    (out / "report.html").write_text(content, encoding="utf-8")
