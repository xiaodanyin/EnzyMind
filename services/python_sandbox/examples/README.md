# ADH1 analysis validation

The [autonomous research prompt](adh1_autonomous_prompt_zh.txt) specifies only a research goal and experimental conditions; the Agent chooses tools, analysis methods and code. The recorded 2026-11-12 run used the documented `EnzyMindN8NClient`, existing Workspace v2 and a personal DeepSeek key. The personal-key pathway worked, but the complete autonomous analysis **did not pass acceptance**: the first Python call read incorrect fields and exhausted the tool budget without attachments; a natural follow-up failed during memory compression. See the [validation record](../VALIDATION.md). The scripted regression below does not establish autonomous analysis success. The linked prompts are preserved in their original Chinese for reproducibility.

## Scripted tool-chain regression

Create a **new conversation** in the frontend Agent and copy the entire [adh1_prompt_zh.txt](adh1_prompt_zh.txt), including the Python block. It contains neither workspace credentials nor fixed prediction values. The Agent obtains the four prediction-result UUIDs during the run.

Query Enzyme Info retrieves yeast ADH1 (P00330). The same complete sequence is used to predict kcat and Km for ethanol and 1-propanol. Python Analysis then reads the four actual records and calculates descriptors, initial-rate curves, an analytical crossing point and sensitivity across 81 parameter combinations. This uses six tool calls, including one Python execution.

The prompt embeds a fixed [analysis script](adh1_analysis.py) for reproducibility. It depends on the injected `data`, `results` and `output_dir` variables and is not a standalone CLI script. The `ek/em/pk/pm` fields in `data` hold the actual UUIDs for ethanol kcat/Km and 1-propanol kcat/Km, respectively. All four must also appear in `inputs.result_ids`.

Outputs are `substrates.png`, `analysis.png`, `comparison.csv` (2 rows), `rates.csv` (401 rows), `sensitivity.csv` (324 rows) and `summary.json`. These are model predictions and code calculations. Sensitivity combinations are neither probabilities nor confidence intervals and do not constitute experimental validation.

The recorded scripted Agent run on 2026-11-12 took 27.72 seconds, with 0.84 seconds of Python execution. Independent checks covered all six files, numeric rows, source digests, code AST, crossing point and both figures. The Agent included six valid result citations rather than following the requested single-link presentation; calculations and attachments were correct. See the [validation record](../VALIDATION.md) for evidence.

SHA-256 of the validated scripted prompt: `667dad974c7b5cb78b68b18d6083a12c76546957484e72461350fc5259a9b9c0`.
