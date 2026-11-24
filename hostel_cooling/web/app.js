"use strict";
const $ = (id) => document.getElementById(id);
let activity = "study",
  current = { fan: 0, window: 0, curtain: 0 },
  last = null,
  busy = false,
  scenarioVersion = 0,
  profileVersion = 0,
  routineRequest = 0,
  studyAvailable = false,
  studyPollVersion = 0,
  studyPoll;
const numeric = [
  "indoor_c",
  "outdoor_c",
  "rh",
  "outdoor_rh",
  "solar_w_m2",
  "wind_ms",
  "hour",
  "running_mean_c",
];
const roomNumbers = ["area_m2", "ua_w_k", "capacity_mj"];
const materialNumbers = [
  "envelope-area", "envelope-thickness", "envelope-k",
  "envelope-density", "envelope-cp", "envelope-fraction",
];
for (const id of [...numeric, ...roomNumbers, ...materialNumbers]) $(id).required = true;
const WINDOW_POSITIONS = ["Closed", "Half open", "Open"];
let toastTimer;
let participant = localStorage.getItem("cooling-participant") || "local-pilot",
  inferredActivity = "study";
$("participant-id").value = participant;
function toast(message) {
  $("toast").textContent = message;
  $("toast").classList.add("visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $("toast").classList.remove("visible"), 5500);
}
async function api(path, data) {
  const response = await fetch(
    path,
    data === undefined
      ? { headers: { "X-Participant-ID": participant } }
      : {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Participant-ID": participant,
          },
          body: JSON.stringify(data),
        },
  );
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Request failed");
  return result;
}
function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function validNumbers(ids) {
  for (const id of ids) {
    const input = $(id);
    if (input.validity.valid) continue;
    for (let section = input.closest("details"); section; section = section.parentElement.closest("details")) {
      section.open = true;
    }
    input.reportValidity();
    return false;
  }
  return true;
}
function syncStats() {
  for (const [id, display, places] of [
    ["indoor_c", "display-temp", 1],
    ["rh", "display-rh", 0],
    ["outdoor_c", "display-outdoor", 1],
  ]) {
    const value = $(id).valueAsNumber;
    $(display).textContent = Number.isFinite(value) ? value.toFixed(places) : "–";
  }
}
function scenario() {
  const c = Object.fromEntries(numeric.map((id) => [id, Number($(id).value)]));
  c.activity = activity;
  for (const id of ["rain", "poor_air", "window_allowed"])
    c[id] = $(id).checked;
  return c;
}
function room() {
  return {
    area_m2: Number($("area_m2").value),
    ua_w_k: Number($("ua_w_k").value),
    capacity_j_k: Number($("capacity_mj").value) * 1e6,
    orientation: $("orientation").value,
  };
}
const initialRoom = room();
function setRoom(r) {
  $("ua_w_k").value = r.ua_w_k;
  $("capacity_mj").value = r.capacity_j_k / 1e6;
  $("area_m2").value = r.area_m2;
  $("orientation").value = r.orientation;
  invalidate();
}
function invalidate() {
  scenarioVersion += 1;
  last = null;
  $("recommend-result").hidden = true;
  $("recommend-empty").hidden = false;
  $("forecast-result").hidden = true;
  $("forecast-empty").hidden = false;
  $("feedback-card").hidden = true;
  $("feedback-status").textContent = "";
}
function showView(name) {
  document
    .querySelectorAll(".view")
    .forEach((n) => n.classList.toggle("active", n.id === `view-${name}`));
  document
    .querySelectorAll(".nav")
    .forEach((n) => {
      const selected = n.dataset.view === name;
      n.classList.toggle("active", selected);
      if (selected) n.setAttribute("aria-current", "page");
      else n.removeAttribute("aria-current");
    });
  $("view-label").textContent = {
    lab: "My room",
    evidence: "Study results",
    pilot: "Data & privacy",
  }[name];
  if (name === "evidence") {
    loadResults();
    pollExperiment();
  }
  window.scrollTo(0, 0);
}

function closeRainExample() {
  $("rain-example").hidden = true;
  $("show-rain-example").setAttribute("aria-expanded", "false");
  $("show-rain-example").focus();
}

$("close-rain-example").addEventListener("click", closeRainExample);
$("show-rain-example").addEventListener("click", async () => {
  const panel = $("rain-example");
  const button = $("show-rain-example");
  if (!panel.hidden) {
    closeRainExample();
    return;
  }
  panel.hidden = false;
  button.setAttribute("aria-expanded", "true");
  $("rain-example-heading").focus();
  const results = $("rain-example-results");
  if (!results.hidden || panel.getAttribute("aria-busy") === "true") return;
  const status = $("rain-example-status");
  panel.setAttribute("aria-busy", "true");
  status.classList.remove("sr-only");
  status.textContent = "Calculating the two suggestions…";
  try {
    const example = await api("/api/rain-example");
    $("rain-example-context").textContent =
      `Both cases start with a student studying at ${example.indoor_c} °C indoors and ${example.outdoor_c} °C outdoors.`;
    results.replaceChildren(...example.cases.map(({ rain, action }) => {
      const item = el("article", undefined, rain ? "example-case rainy" : "example-case");
      item.append(
        el("h3", rain ? "Raining" : "Dry weather"),
        el("strong", `Window ${WINDOW_POSITIONS[action.window * 2].toLowerCase()}`),
        el("p", rain ? "The rain rule keeps the window closed." : "The window can let cooler outdoor air in."),
      );
      return item;
    }));
    results.hidden = false;
    status.classList.add("sr-only");
    status.textContent = "The dry weather and rain suggestions are ready.";
  } catch (error) {
    status.textContent = `${error.message}. Close the example and reopen it to try again.`;
  } finally {
    panel.removeAttribute("aria-busy");
  }
});
document
  .querySelectorAll(".nav")
  .forEach((n) => n.addEventListener("click", () => showView(n.dataset.view)));
document.querySelectorAll("[data-activity]").forEach((n) =>
  n.addEventListener("click", () => {
    activity = n.dataset.activity;
    document
      .querySelectorAll("[data-activity]")
      .forEach((x) => {
        x.classList.toggle("selected", x === n);
        x.setAttribute("aria-pressed", String(x === n));
      });
    $("activity-badge").textContent = {
      study: "Studying",
      sleep: "Sleeping",
      away: "Away",
      auto: "Learning routine",
    }[activity];
    $("routine-status").hidden = activity !== "auto";
    invalidate();
    refreshRoutine();
  }),
);
for (const id of [
  ...numeric,
  "rain",
  "poor_air",
  "window_allowed",
  ...roomNumbers,
  "orientation",
  "method",
])
  $(id).addEventListener("input", () => {
    syncStats();
    invalidate();
    if (id === "hour") refreshRoutine();
  });
function renderProfile(profile) {
  $("consent").checked = profile.consent;
  const p = profile.preference;
  $("memory-profile").replaceChildren(
    ...[
      `Study target ${p.activity_targets.study ?? p.target_c} °C`,
      `Sleep target ${p.activity_targets.sleep ?? p.target_c} °C`,
      `Sleep fan ≤ ${p.sleep_max_fan}`,
      `Study airflow: ${p.study_airflow ? "preferred" : "unspecified"}`,
    ].map((t) => el("span", t)),
  );
  $("memory-events").replaceChildren(
    ...profile.events.slice(0, 4).map((e) => {
      const n = el("div", e.message, "memory-event");
      n.append(
        el(
          "small",
          `${e.activity} · ${e.backend} · ${new Date(e.created).toLocaleString()}`,
        ),
      );
      return n;
    }),
  );
}
async function refresh({ resetRoom = false } = {}) {
  const version = profileVersion;
  const status = await api("/api/status");
  if (version !== profileVersion) return;
  studyAvailable = status.study_available;
  $("backend").textContent = status.backend;
  renderProfile(status.profile);
  const methods = $("method");
  methods.querySelector("[value=generic_llm]").disabled = !status.real_llm;
  if (!status.real_llm && methods.value === "generic_llm") methods.value = "ours";
  if (resetRoom) {
    setRoom(status.room_model?.selected_room || initialRoom);
  }
  $("profile-status").textContent =
    `Profile: ${status.participant} / ${status.inference_mode}`;
  refreshRoutine();
  if ($("view-evidence").classList.contains("active")) pollExperiment();
}
function svgElement(tag, attributes, content) {
  const ns = "http://www.w3.org/2000/svg";
  const node = document.createElementNS(ns, tag);
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, value);
  if (content !== undefined) node.textContent = content;
  return node;
}
function forecastChart(result, initial) {
  const start = { minutes: 0, temperature_c: initial.indoor_c, rh: initial.rh };
  const readings = [start, ...result.trajectory];
  const fixed = result.fixed_schedule;
  const reference = fixed ? [start, ...fixed.trajectory] : [];
  const readingsEnd = readings.at(-1).temperature_c.toFixed(1);
  const referenceEnd = reference.at(-1)?.temperature_c.toFixed(1);
  $("forecast-temperature").textContent = `${readingsEnd} °C`;
  const fanElectricity = (value) => `${Number(value.toFixed(2))} Wh fan electricity`;
  $("forecast-electricity").textContent = fanElectricity(result.one_hour_fan_wh);
  $("fixed-forecast").hidden = !fixed;
  $("fixed-unavailable").hidden = Boolean(fixed);
  $("fixed-temperature-heading").hidden = !fixed;
  if (fixed) {
    $("fixed-temperature").textContent = `${referenceEnd} °C`;
    $("fixed-electricity").textContent = fanElectricity(fixed.one_hour_fan_wh);
  }
  const temperatures = [...readings, ...reference].map((p) => p.temperature_c);
  const low = Math.floor(Math.min(...temperatures));
  const high = Math.max(low + 1, Math.ceil(Math.max(...temperatures)));
  const x = (minutes) => 49 + (minutes / readings.at(-1).minutes) * 264;
  const y = (temp) => 105 - ((temp - low) / (high - low)) * 86;
  const svg = svgElement("svg", {
    viewBox: "0 0 340 130", role: "img",
    "aria-label": `Indoor temperature starts at ${initial.indoor_c.toFixed(1)} °C and ends at ${readingsEnd} °C with the suggestion` +
      (fixed ? ` and ${referenceEnd} °C on a fixed schedule.` : "."),
  });
  for (const tick of [high, (high + low) / 2, low]) {
    svg.append(
      svgElement("line", { x1: 49, x2: 313, y1: y(tick), y2: y(tick), class: "forecast-gridline" }),
      svgElement("text", { x: 42, y: y(tick) + 3, "text-anchor": "end" }, `${tick.toFixed(1)}°C`),
    );
  }
  for (const [series, className] of [[reference, "forecast-line fixed"], [readings, "forecast-line"]]) {
    if (!series.length) continue;
    svg.append(svgElement("polyline", {
      points: series.map((point) => `${x(point.minutes)},${y(point.temperature_c)}`).join(" "),
      class: className,
    }));
  }
  for (const point of readings) {
    svg.append(
      svgElement("circle", { cx: x(point.minutes), cy: y(point.temperature_c), r: 3, class: "forecast-point" }),
      svgElement("text", { x: x(point.minutes), y: 123, "text-anchor": "middle" }, point.minutes ? `+${point.minutes}m` : "Now"),
    );
  }
  $("forecast-readings").replaceChildren(...readings.map((point, index) => {
    const row = el("tr");
    const time = el("th", point.minutes ? `+${point.minutes} min` : "Now");
    time.scope = "row";
    row.append(time, el("td", `${point.temperature_c.toFixed(1)} °C`));
    if (fixed) row.append(el("td", `${reference[index].temperature_c.toFixed(1)} °C`));
    row.append(el("td", `${point.rh.toFixed(1)}%`));
    return row;
  }));
  $("forecast-chart").replaceChildren(svg);
}
async function recommend() {
  if (busy) return;
  busy = true;
  const buttons = [$("recommend"), $("recommend-top")];
  buttons.forEach((b) => (b.disabled = true));
  $("recommend-top").textContent = "Finding settings…";
  const version = scenarioVersion;
  try {
    if (!validNumbers([...numeric, ...roomNumbers])) return;
    const c = scenario();
    const result = await api("/api/recommend", {
      conditions: c,
      room: room(),
      current,
      method: $("method").value,
    });
    if (version !== scenarioVersion) return;
    last = result;
    $("recommend-empty").hidden = true;
    $("recommend-result").hidden = false;
    $("forecast-empty").hidden = true;
    $("forecast-result").hidden = false;
    const a = result.action;
    if (result.activity_inferred) {
      inferredActivity = result.predicted.activity;
      $("activity-badge").textContent = `Inferred: ${inferredActivity}`;
    }
    $("routine-status").textContent =
      `Routine model: ${result.routine.activity}, ${(100 * result.routine.confidence).toFixed(0)}% confidence / ${result.routine.source}`;
    $("fan-action").textContent = ["Off", "Low · 1", "Medium · 2", "High · 3"][
      a.fan
    ];
    $("fan-detail").textContent = a.fan ? `${result.heat.fan_w} W while running` : "No fan electricity";
    $("window-action").textContent = WINDOW_POSITIONS[a.window * 2];
    $("curtain-action").textContent = a.curtain ? "Closed" : "Open";
    $("explanation").textContent = [
      a.fan ? "Air from the fan can make the room feel cooler." : "Keeping the fan off saves electricity.",
      a.window ? "An open window lets outdoor air in." : "The closed window limits airflow from outside.",
      a.curtain ? "Closed curtains reduce heat from sunlight." : "Open curtains let in daylight.",
    ].join(" ");
    $("constraints").textContent = result.constraints.join(" · ");
    $("energy").textContent = `${result.heat.fan_wh.toFixed(2)} Wh`;
    const vote = result.comfort.tsv_proxy;
    $("comfort").textContent = ["Cold", "Cool", "Slightly cool", "Neutral", "Slightly warm", "Warm", "Hot"][Math.round(vote) + 3];
    const gap = result.optimizer.exact_gap;
    $("recommend-technical").textContent =
      `${result.method_label}. Solar gain ${result.heat.solar_w.toFixed(0)} W, air changes per hour ${result.heat.ventilation_ach.toFixed(1)}, modeled comfort score ${vote.toFixed(2)} on a −3 to +3 scale.` +
      (gap == null ? "" : ` Difference from the best possible score ${gap.toFixed(4)}.`);
    forecastChart(result, c);
    $("scene-curtain").setAttribute("opacity", a.curtain ? "1" : ".3");
    $("fan-blades").classList.toggle("fan-running", a.fan > 0);
    $("feedback-card").hidden = !result.suggestion_id;
    if (matchMedia("(max-width: 900px)").matches && $("view-lab").classList.contains("active")) {
      $("recommend-result").focus({ preventScroll: true });
      $("recommend-result").scrollIntoView({ block: "nearest" });
    }
    toast("Your suggested settings are ready.");
  } catch (e) {
    if (version === scenarioVersion) toast(e.message);
  } finally {
    busy = false;
    buttons.forEach((b) => (b.disabled = false));
    $("recommend-top").textContent = "Get a suggestion ↗";
  }
}
$("recommend").addEventListener("click", recommend);
$("recommend-top").addEventListener("click", recommend);
$("step").addEventListener("click", () => {
  if (!last) return;
  current = last.action;
  for (const id of ["indoor_c", "rh"])
    $(id).value = last.predicted[id].toFixed(2);
  $("hour").value = Number(last.predicted.hour.toFixed(4)) % 24;
  syncStats();
  invalidate();
  refreshRoutine();
  toast("15 minutes have passed in the simulation. Get a new suggestion to continue.");
});
$("consent").addEventListener("change", async () => {
  const version = profileVersion;
  const toggle = $("consent");
  toggle.disabled = true;
  closePreferenceReview();
  try {
    const result = await api("/api/consent", { consent: toggle.checked });
    if (version !== profileVersion) return;
    invalidate();
    if (result.consent) renderProfile(result);
    else await refresh({ resetRoom: true });
    toast(
      result.consent
        ? "Consent saved locally."
        : "Consent withdrawn. Local profile and feedback erased.",
    );
  } catch (e) {
    if (version === profileVersion) {
      toast(e.message);
      await refresh();
    }
  } finally {
    toggle.disabled = false;
  }
});
let pendingPreferenceProposal = null;
function closePreferenceReview() {
  pendingPreferenceProposal = null;
  $("preference-review").hidden = true;
}
function renderPreferenceReview(result) {
  closePreferenceReview();
  $("chat-status").textContent = result.message;
  if (!result.proposal_id) return;
  pendingPreferenceProposal = result.proposal_id;
  const patch = result.patch,
    items = [];
  for (const [context, target] of Object.entries(patch.activity_targets || {}))
    items.push(`${context}: comfortable target ${target} C`);
  if (patch.sleep_max_fan !== undefined)
    items.push(
      `Maximum fan during sleep: ${["off", "low", "medium", "high"][patch.sleep_max_fan]}`,
    );
  if (patch.study_airflow !== undefined)
    items.push(
      `Airflow while studying: ${patch.study_airflow ? "preferred" : "avoid"}`,
    );
  if (patch.noise_weight !== undefined)
    items.push("Prioritize quiet during sleep");
  $("interpreted-changes").replaceChildren(...items.map((t) => el("li", t)));
  $("preference-review").hidden = false;
}
$("chat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("save-preference").disabled = true;
  closePreferenceReview();
  const version = profileVersion;
  try {
    const result = await api("/api/preferences/preview", {
      message: $("message").value,
      activity: activity === "auto" ? inferredActivity : activity,
    });
    if (version === profileVersion && $("consent").checked)
      renderPreferenceReview(result);
  } catch (error) {
    if (version !== profileVersion) return;
    $("chat-status").textContent = error.message;
    toast(error.message);
  } finally {
    $("save-preference").disabled = false;
  }
});
async function confirmPreference(accept) {
  if (!pendingPreferenceProposal) return;
  const version = profileVersion;
  const proposal = pendingPreferenceProposal;
  closePreferenceReview();
  try {
    const result = await api("/api/preferences/confirm", {
      proposal_id: proposal,
      accept,
    });
    if (version !== profileVersion) return;
    $("chat-status").textContent = result.message;
    if (accept) {
      $("message").value = "";
      invalidate();
      await refresh();
    }
    if (version === profileVersion) toast(result.message);
  } catch (error) {
    if (version === profileVersion) toast(error.message);
  }
}
$("confirm-preference").addEventListener("click", () =>
  confirmPreference(true),
);
$("discard-preference").addEventListener("click", () =>
  confirmPreference(false),
);
async function feedback(accepted) {
  const version = scenarioVersion;
  try {
    if (!last?.suggestion_id)
      throw new Error("Enable consent and generate a saved suggestion first.");
    const result = await api("/api/feedback", {
      suggestion_id: last.suggestion_id,
      accepted,
      tsv: Number($("tsv").value),
    });
    if (version !== scenarioVersion) return;
    $("feedback-status").textContent = result.note;
    toast("Self-report saved locally.");
  } catch (e) {
    if (version === scenarioVersion) toast(e.message);
  }
}
$("accept").addEventListener("click", () => feedback(true));
$("reject").addEventListener("click", () => feedback(false));
async function loadResults() {
  try {
    const summary = await api("/api/results");
    const fixed = summary.rows.find((r) => r.method === "fixed");
    const project = summary.rows.find((r) => r.method === "ours");
    $("study-takeaways").hidden = !fixed || !project;
    if (fixed && project) {
      const change = 100 * (project.fan_wh_day / fixed.fan_wh_day - 1);
      const discomfort = project.comfort_violation_pct - fixed.comfort_violation_pct;
      $("study-energy").textContent = `${Math.abs(change).toFixed(0)}% ${change < 0 ? "less" : "more"}`;
      $("study-energy-detail").textContent = `${project.fan_wh_day.toFixed(1)} vs ${fixed.fan_wh_day.toFixed(1)} Wh/day on a fixed schedule.`;
      $("study-comfort").textContent = `${Math.abs(discomfort).toFixed(1)} points ${discomfort < 0 ? "lower" : "higher"}`;
      $("study-comfort-detail").textContent = `${project.comfort_violation_pct.toFixed(1)}% vs ${fixed.comfort_violation_pct.toFixed(1)}% of occupied time on a fixed schedule.`;
    }
    $("results-meta").textContent = summary.rows.length
      ? `${summary.days_per_seed} simulated days for each of ${summary.seeds.length} weather scenarios. Settings reviewed every ${summary.control_interval_minutes || 15} minutes.`
      : "No results yet. Run a comparison.";
    $("results").replaceChildren(
      ...summary.rows.map((r) => {
        const tr = el("tr", undefined, r.method === "ours" ? "highlight" : "");
        for (const t of [
          r.label,
          r.fan_wh_day.toFixed(1),
          r.mean_abs_tsv_proxy.toFixed(2),
          `${r.comfort_violation_pct.toFixed(1)}%`,
          `${r.acceptance_proxy_pct.toFixed(1)}%`,
          r.controller_latency_ms_median.toFixed(2),
        ])
          tr.append(el("td", t));
        return tr;
      }),
    );
    $("skipped").replaceChildren(
      ...(summary.skipped || []).map((s) =>
        el("p", `${s.method}: ${s.reason}`, "notice"),
      ),
    );
    const hypotheses = await api("/evidence/hypothesis_assessment.json");
    $("hypothesis-results").replaceChildren(
      ...hypotheses.hypotheses.map((h) => {
        const row = el("tr");
        for (const text of [
          h.id + ": " + h.question,
          h.verdict,
          h.evidence + " " + h.limit,
        ])
          row.append(el("td", text));
        return row;
      }),
    );
  } catch (e) {
    toast(e.message);
  }
}
$("run-experiment").addEventListener("click", async () => {
  const button = $("run-experiment");
  button.disabled = true;
  try {
    await api("/api/experiment", { days: 7 });
  } catch (e) {
    toast(e.message);
  }
  pollExperiment();
});
async function pollExperiment() {
  clearTimeout(studyPoll);
  const version = ++studyPollVersion;
  const button = $("run-experiment");
  const report = $("experiment-report");
  try {
    const job = await api("/api/experiment/status");
    if (version !== studyPollVersion) return;
    const running = job.state === "running";
    button.disabled = running || !studyAvailable;
    report.hidden = !job.report_url;
    if (job.report_url) report.href = job.report_url;
    const messages = {
      running: "Running the seeded simulations locally. This may take several minutes.",
      complete: job.all_checks_passed
        ? "Latest comparison report is ready."
        : "The run finished with incomplete checks. See the report for details.",
      failed: job.error,
      idle: "",
    };
    $("experiment-status").textContent = [
      messages[job.state],
      !studyAvailable && "A new study requires the pinned local model.",
    ].filter(Boolean).join(" ");
    if (running && $("view-evidence").classList.contains("active")) {
      studyPoll = setTimeout(pollExperiment, 1500);
    }
  } catch (e) {
    if (version !== studyPollVersion) return;
    button.disabled = !studyAvailable;
    toast(e.message);
  }
}
$("validate-pilot").addEventListener("click", async () => {
  const button = $("validate-pilot");
  button.disabled = true;
  const version = profileVersion;
  try {
    const file = $("pilot-file").files[0];
    if (!file) throw new Error("Select a CSV file first.");
    if (file.size > 1800000)
      throw new Error(
        "CSV must be below 1.8 MB. Use the CLI for larger datasets.",
      );
    const csv = await file.text();
    if (version !== profileVersion) return;
    const result = await api("/api/pilot/validate", { csv });
    if (version !== profileVersion) return;
    $("pilot-status").textContent =
      `Valid: ${result.rows} rows · ${result.provenance}. ${result.note}`;
  } catch (e) {
    if (version !== profileVersion) return;
    $("pilot-status").textContent = e.message;
    toast(e.message);
  } finally {
    button.disabled = false;
  }
});
$("export").addEventListener("click", async () => {
  try {
    const result = await api("/api/profile/export");
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(result, null, 2)], { type: "application/json" }),
    );
    const a = el("a");
    a.href = url;
    a.download = "hostel-cooling-my-data.json";
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    $("privacy-status").textContent = "Export downloaded.";
  } catch (e) {
    toast(e.message);
  }
});
$("erase").addEventListener("click", async () => {
  const version = profileVersion;
  closePreferenceReview();
  try {
    await api("/api/consent", { consent: false });
    if (version !== profileVersion) return;
    invalidate();
    await refresh({ resetRoom: true });
    if (version !== profileVersion) return;
    $("privacy-status").textContent =
      "Local memory erased and consent withdrawn.";
    toast("Local profile, evidence and feedback erased.");
  } catch (e) {
    if (version === profileVersion) toast(e.message);
  }
});
refresh({ resetRoom: true }).catch((e) => toast(e.message));
syncStats();

async function refreshRoutine() {
  const request = ++routineRequest;
  try {
    const hour = Number($("hour").value) % 24;
    const weekday = (new Date().getDay() + 6) % 7;
    const r = await api(`/api/routine?hour=${hour}&weekday=${weekday}`);
    if (request !== routineRequest) return;
    inferredActivity = r.activity;
    $("routine-status").textContent =
      `Learned routine: ${r.activity}, ${(100 * r.confidence).toFixed(0)}% confidence / ${r.source}`;
    if (activity === "auto")
      $("activity-badge").textContent = `Inferred: ${r.activity}`;
  } catch (e) {
    if (request === routineRequest) $("routine-status").textContent = e.message;
  }
}
$("switch-participant").addEventListener("click", async () => {
  const alias = $("participant-id").value.trim();
  if (!/^[A-Za-z0-9_-]{1,40}$/.test(alias)) {
    toast("Use 1 to 40 letters, digits, underscores or hyphens.");
    return;
  }
  if (alias === participant) return;
  const version = ++profileVersion;
  routineRequest += 1;
  closePreferenceReview();
  participant = alias;
  localStorage.setItem("cooling-participant", alias);
  inferredActivity = "study";
  $("consent").checked = false;
  for (const id of ["memory-profile", "memory-events", "routine-status", "chat-status", "pilot-status", "privacy-status"])
    $(id).textContent = "";
  $("message").value = "";
  $("pilot-file").value = "";
  $("profile-status").textContent = `Opening profile ${alias}…`;
  setRoom(initialRoom);
  try {
    await refresh({ resetRoom: true });
    if (version === profileVersion) toast(`Opened profile ${alias}`);
  } catch (e) {
    if (version === profileVersion) toast(e.message);
  }
});
$("calibrate-pilot").addEventListener("click", async () => {
  const button = $("calibrate-pilot");
  button.disabled = true;
  const version = profileVersion;
  try {
    const file = $("pilot-file").files[0];
    if (!file) throw new Error("Select a CSV first.");
    if (file.size > 1800000)
      throw new Error("Use the CLI for CSVs above 1.8 MB.");
    $("pilot-status").textContent = "Fitting the room on training data...";
    const csv = await file.text();
    if (version !== profileVersion) return;
    const result = await api("/api/pilot/calibrate", { csv });
    if (version !== profileVersion) return;
    invalidate();
    await refresh({ resetRoom: true });
    if (version !== profileVersion) return;
    $("pilot-status").textContent =
      `Applied fitted room: UA=${result.selected_room.ua_w_k} W/K, C=${(result.selected_room.capacity_j_k / 1e6).toFixed(2)} MJ/K. Held-out RMSE ${result.test_rmse_c.toFixed(3)} C; persistence ${result.persistence_test_rmse_c.toFixed(3)} C.`;
  } catch (e) {
    if (version !== profileVersion) return;
    $("pilot-status").textContent = e.message;
    toast(e.message);
  } finally {
    button.disabled = false;
  }
});

$("apply-envelope").addEventListener("click", async () => {
  try {
    if (!validNumbers([...materialNumbers, "area_m2"])) return;
    const result = await api("/api/envelope", {
      layers: [
        {
          name: "User-specified wall",
          thickness_m: Number($("envelope-thickness").value),
          conductivity_w_mk: Number($("envelope-k").value),
          density_kg_m3: Number($("envelope-density").value),
          specific_heat_j_kgk: Number($("envelope-cp").value),
        },
      ],
      opaque_wall_m2: Number($("envelope-area").value),
      mass_participation: Number($("envelope-fraction").value),
      floor_m2: Number($("area_m2").value),
      orientation: $("orientation").value,
    });
    $("ua_w_k").value = result.room.ua_w_k.toFixed(3);
    $("capacity_mj").value = (result.room.capacity_j_k / 1e6).toFixed(3);
    $("envelope-status").textContent =
      `Wall U=${result.wall_u_w_m2k.toFixed(3)} W/m2K. Applied UA=${result.room.ua_w_k.toFixed(2)} W/K, C=${(result.room.capacity_j_k / 1e6).toFixed(2)} MJ/K. ${result.assumptions}`;
    invalidate();
    toast("Material-based room parameters applied to this scenario.");
  } catch (e) {
    toast(e.message);
  }
});
