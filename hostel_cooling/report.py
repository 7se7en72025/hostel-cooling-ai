import html
from pathlib import Path

SOURCES = [
    ("EnergyPlus Engineering Reference: zone heat balance", "https://energyplus.readthedocs.io/en/stable/guides/engineering-reference/2.1-basis-for-the-zone-and-air-system-integration.html"),
    ("CBE Thermal Comfort Tool: adaptive and elevated-air-speed context", "https://cbe.berkeley.edu/research/cbe-thermal-comfort-tool/"),
    ("pythermalcomfort: adaptive model and applicability", "https://pythermalcomfort.readthedocs.io/en/latest/documentation/models.html"),
    ("Ollama: structured outputs", "https://docs.ollama.com/capabilities/structured-outputs"),
]


def write_report(summary, output):
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
        for ax, metric, title, ylabel in [(axes[0],"fan_wh_day","Fan electricity","Wh / day"),(axes[1],"comfort_violation_pct","Occupied comfort violations","% of occupied intervals")]:
            ax.bar(labels, [r[metric] for r in rows], yerr=[r[metric+"_sd"] for r in rows], color=colors, capsize=3)
            ax.set(title=title, ylabel=ylabel); ax.tick_params(axis="x",rotation=40); ax.spines[["top","right"]].set_visible(False)
        fig.suptitle("SYNTHETIC SIMULATION | error bars: SD across weather seeds",fontsize=11)
        fig.savefig(out/"comparison.png",dpi=170); fig.savefig(out/"comparison.svg");plt.close(fig)
        svg_path = out/"comparison.svg"
        svg_path.write_text("\n".join(line.rstrip() for line in svg_path.read_text(encoding="utf-8").splitlines())+"\n",encoding="utf-8")
        plot_available = True
    except ImportError:
        pass
    escape = html.escape
    body_rows = "".join(f'<tr><td>{escape(r["method"])}</td><td>{r["fan_wh_day"]:.1f}</td><td>{r["fan_epi_period_kwh_m2"]:.4f}</td><td>{r["mean_abs_tsv_proxy"]:.2f}</td><td>{r["comfort_violation_pct"]:.1f}%</td><td>{r["acceptance_proxy_pct"]:.1f}%</td><td>{r["controller_latency_ms_median"]:.2f}</td></tr>' for r in rows)
    limitations = "".join(f"<li>{escape(s)}</li>" for s in summary["limitations"])
    methods = "".join(f'<li><b>{escape(r["method"])}</b>: {escape(r["label"])}.</li>' for r in rows)
    skipped = "".join(f'<li>{escape(str(s))}</li>' for s in summary["skipped"])
    sources = "".join(f'<li><a href="{u}">{escape(t)}</a></li>' for t,u in SOURCES)
    ours = next((r for r in rows if r["method"] == "ours"), None)
    fixed = next((r for r in rows if r["method"] == "fixed"), None)
    finding = f'The preference controller used {ours["fan_wh_day"]:.1f} Wh/day, with {ours["comfort_violation_pct"]:.1f}% synthetic occupied comfort violations. Its fan electricity changed by {ours["fan_energy_change_vs_fixed_pct"]:+.1f}% relative to the fixed schedule. Comfort and energy must be assessed together; energy reduction alone does not establish success.' if ours else "The preference controller did not complete; review skipped methods before interpreting results."
    if ours and fixed:
        finding += f' Against fixed settings, occupied violations changed by {ours["comfort_violation_pct"]-fixed["comfort_violation_pct"]:+.2f} percentage points and mean absolute TSV changed from {fixed["mean_abs_tsv_proxy"]:.2f} to {ours["mean_abs_tsv_proxy"]:.2f}. This run does not establish the no-comfort-penalty hypothesis.'
    content = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Hostel cooling | Research report</title>
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
    <h2>Sources and design context</h2><p>The supplied F417 and F423 proposal PDFs define the project scope. The simplified equations are this project's implementation, informed by the sources below; they do not reproduce a certified implementation.</p><ul>{sources}</ul><p>References checked 20 October 2026.</p></main></html>'''
    (out/"report.html").write_text(content, encoding="utf-8")
