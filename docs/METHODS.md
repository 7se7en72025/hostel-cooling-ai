# Methods and course mapping

## Combined scope

The two supplied five-slide proposal PDFs describe complementary views of the same project. F417 emphasizes memory from conversation, fuzzy sets, genetic algorithms and ANN/expert comparisons. F423 emphasizes airflow, solar gains, an RC room model, energy and EPI. This repository implements one computational pilot and a reproducible synthetic comparison. It does not claim to complete a human study.

| Proposal requirement | Implementation | Evidence limit |
| --- | --- | --- |
| Fan/window/curtain control | Four fan speeds, three window openings, two shade states | Advisory sandbox only |
| Conversation preference memory | Activity targets, noise limit, airflow and energy weights, evidence log | Offline parser in submitted benchmark; optional Ollama |
| Activity context | Explicit study/sleep/away input and simulated daily schedule | No automatic routine inference |
| Fuzzy comfort | Five triangular sets and Sugeno consequences | Heuristic TSV proxy, not a validated physiological model |
| RC model | Exact constant-forcing 1R1C heat equation and air moisture balance | Uncalibrated synthetic room |
| Genetic algorithm | Population 10, eight generations, tournament selection, elitism, crossover, mutation | Exact enumeration audits a small action space |
| F417 B1/B2/B3/B4 | Expert rules, adaptive+fallback, ANN, actual generic LLM adapter | B4 unavailable in submitted run |
| F423 B1/B2/B3/B4 | Fixed schedule, adaptive+fallback, physics only, same generic LLM | Fixed settings are illustrative, not rating-system prescriptions |
| Preference improvement | Initial-survey ablation with scripted mid-trial preference change | Mechanical memory test only |
| Comfort, energy, acceptance, latency | Exported per-seed and aggregate metrics | Human outcomes remain unmeasured |
| Data/pilot model | 672-row synthetic sample, validator and chronological calibration | Software recovery test, not field validation |

## Room and moisture equations

For a timestep with fixed weather and controls:

`G = UA + rho_air * cp_air * Vdot` in W/K.

`Q = Qsolar + Qinternal + Pfan` in W.

`C dT/dt = G (Tout - T) + Q`.

`Teq = Tout + Q/G`; `Tnext = Teq + (T - Teq) exp(-G dt/C)`.

Default values: area 12 m², height 3 m, UA 45 W/K, effective capacitance 2 MJ/K, window 2 m², glazing factor 0.6, west orientation. Air constants are 1.2 kg/m³ and 1006 J/(kg K). These are model assumptions, not measured material properties.

`ACH = 0.4 + opening * (1 + 2 * wind_ms)`. This is a tunable proxy rather than an airflow-network solution. Window flow can heat the room when outside is hotter. Curtains reduce solar gain to 25% of unshaded glazing gains. Orientation uses a time-of-day multiplier. Neither is calibrated.

Fan levels consume 0, 18, 38, 65 W. The heat balance includes all electrical fan power as sensible room heat. Airspeed assumptions are 0.1, 0.4, 0.8, 1.2 m/s, plus a small window-airflow proxy. Perceived cooling does not subtract energy from the room heat balance.

Humidity uses humidity ratio, outdoor exchange and a 40 g/hour occupant moisture source. Relative humidity saturates at 100%. Condensation, solar absorption by room surfaces, radiant asymmetry and latent thermal feedback are outside scope.

## Comfort and optimizer

The controller forms effective temperature from indoor temperature, a heuristic airspeed relief and a humidity penalty. The personal activity target defines its error. Triangular memberships centered on -4, -2, 0, 2, 4 C have consequents -3, -1.5, 0, 1.5, 3. The weighted result is a TSV proxy. This is not PMV or measured TSV.

The one-hour objective averages absolute fuzzy TSV, a comfort violation penalty, context-specific noise, requested airflow and normalized fan energy, then adds switching cost. Outdoor inputs and activity stay fixed through the forecast. Preferences select the target and weights. The returned action is the GA result. The exhaustive result is an audit only, and reported `exact_gap` can be nonzero. A tiny action space would normally justify exhaustive search; GA is included to meet the course method and compare its quality explicitly.

The adaptive reference uses `Tneutral = 0.31 Trunning + 17.8` and the 80% band of ±3.5 C, with documented elevated-air-speed extensions. Applicability requires 10 < Trunning < 33.5 C, awake/study context and 10 < Tair < 40 C. Air temperature approximates operative temperature. Sleeping and away use a rule fallback and cannot be interpreted as ASHRAE compliance.

## ANN

A real NumPy neural regressor has three input features, 12 tanh hidden units and one output. It trains by gradient descent on 2000 synthetic points with an independent 400-point synthetic IID holdout. The training seed is 1701. Generic training targets come from an assumed sensation function, not human responses. The ANN controller evaluates current sensations without RC lookahead. The holdout MAE only checks the surrogate fit.

## Evaluation protocol

Each seed supplies identical weather, occupied schedule, initial room state and synthetic hidden-occupant scenario to all policies. Each policy evolves its own closed-loop room state. Both survey and proposed methods begin with the same initial explicit profile. Halfway through the trial, the hidden study target shifts by -1 C. Only a scripted conversation reveals the changed preference to the proposed method. The controller never directly reads the hidden profile.

The acceptance oracle differs numerically from the fuzzy controller but remains related to its assumptions. A proposal is accepted in the oracle when its absolute sensation is <=1.2 and noise/airflow requirements are met. Every action still gets applied, including proxy-declined actions. This evaluates policy effects under full compliance and does not model actual acceptance-mediated energy consumption.

Comfort violations use absolute oracle TSV >1 during occupied intervals. Fan energy includes all intervals. Mean absolute TSV avoids hot/cold cancellation. Acceptance is an oracle proxy; real dashboard self-reports are separate SQLite records and do not enter this synthetic benchmark. Latency times the controller, including GA audit. Preference extraction latency is logged separately.

Per-method means and sample SD across weather seeds describe scenario variation. These are not participant confidence intervals. Energy change is relative to the fixed-schedule mean. EPI is period fan kWh/m². No claims of annualized building performance, causal human benefit or statistical significance follow.

Scientific outputs are deterministic for fixed seeds. Latency is machine-dependent. Failed LLM runs are discarded in full and disclosed. Comparisons involving an incomplete seed set need separate scrutiny before interpretation.
