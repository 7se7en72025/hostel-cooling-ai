# Literature context

Checked 20 October 2026. This is a focused reference screen, not a systematic review. Journal items below were screened at the indexed primary-abstract level because full-text access was unavailable. Do not present their detailed experimental findings as independently reproduced here.

| Primary source | Relevant contribution | Relationship to this prototype |
| --- | --- | --- |
| [Tekler et al., 2023, Enhancing personalised thermal comfort models with Active Learning for improved HVAC controls](https://arxiv.org/abs/2309.09073) | Uses active preference annotation to reduce feedback burden in occupant-centered control | Motivates targeted feedback. Our prototype does not implement active sampling. |
| [Yang, Siew and Joe-Wong, 2024, An LLM-Based Digital Twin for Optimizing Human-in-the Loop Systems](https://arxiv.org/abs/2403.16809) | Uses LLM agents as simulated occupants within control optimization | Shows why LLM-based simulation is prior work, and why synthetic occupants are not human validation. |
| [Liu, Zhou and Li, 2026, Conversational preference learning for personalized thermal comfort control with a lightweight large language model](https://doi.org/10.1016/j.enbuild.2026.117181) | Studies preferences learned from longitudinal conversation | Closely overlaps the general idea. Avoid a first-of-its-kind claim. The hostel passive-control setting needs its own empirical test. |
| [Li et al., 2026, Personalized thermal comfort elicitation for human-centric building environments with low-cognitive-load conversational AI](https://doi.org/10.1016/j.buildenv.2026.114586) | Frames conversational elicitation using uncertainty and cognitive constraints | Supports an explicit comparison of conversation with surveys and feedback burden in later work. |

The scope distinction is an inexpensive hostel control set (fan, window and curtain), explicit study/sleep/away context, retained preference evidence, and physics/optimizer ablations. This is a project framing, not proof of a novel research gap or a literature-wide absence. Existing work already covers conversation, preference trajectories, occupant simulation and physical building control in various combinations.

Technical foundations:

- [EnergyPlus zone heat-balance engineering reference](https://energyplus.readthedocs.io/en/stable/guides/engineering-reference/2.1-basis-for-the-zone-and-air-system-integration.html): supports heat-balance structure. This implementation is a much simpler grey-box approximation.
- [CBE Thermal Comfort Tool](https://cbe.berkeley.edu/research/cbe-thermal-comfort-tool/): provides context for adaptive and elevated-air-speed models.
- [pythermalcomfort adaptive-model documentation](https://pythermalcomfort.readthedocs.io/en/latest/documentation/models.html): documents applicability and reference calculations. Our simplified function is not a certification tool.
- [Ollama structured-output documentation](https://docs.ollama.com/capabilities/structured-outputs): defines the optional schema-constrained local-model integration.

The final question remains empirical: does activity-specific retained preference feedback plus a calibrated room model improve metered energy and occupied comfort relative to matched baselines? The current dataset cannot establish that. It supports reproducibility, software validation and preparation for a measured pilot.


Actual model resources in the completed project:

- [Official Qwen3-4B GGUF model card](https://huggingface.co/Qwen/Qwen3-4B-GGUF): actual pinned transformer used for extraction and the generic LLM baseline.
- [llama.cpp server documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md): local, schema-constrained inference interface.
- [EnergyPlus concrete material example](https://raw.githubusercontent.com/NatLabRockies/EnergyPlus/develop/testfiles/1ZoneUncontrolled.idf): source for the optional envelope calculator's initial concrete properties. Surface films, effective mass participation and other envelope properties remain explicit user assumptions.
