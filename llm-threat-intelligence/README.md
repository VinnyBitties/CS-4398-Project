# LLM and Threat-Intelligence Prototype

This directory provides two prototype functions for Sentinel:

- Validate hash/IP/domain/URL indicators and check a small in-code demo intelligence map.
- Build an evidence prompt and optionally ask Groq model `openai/gpt-oss-20b` for a plain-language explanation.

MITRE ATT&CK mapping, evidence citations, a production intelligence feed, and a versioned output schema are not implemented.

## Files

| File | Purpose |
| --- | --- |
| `threat_intel.py` | Indicator validation and demonstration-only lookup |
| `llm_analyzer.py` | JSON report loading, evidence prompt, optional Groq explanation |
| `sample_report.json` | Inert sample input for local prompt/demo lookup |
| `STATUS.md` | Current capability and gaps |

The production integration entry point is `backend/scripts/llm_bridge.py`, not the module's `__main__` demo.

## Install and configure

Use an isolated environment:

```bash
python3 -m venv .venv-llm
source .venv-llm/bin/activate
python -m pip install -r requirements.txt
```

Backend configuration:

```dotenv
PYTHON_PATH=../.venv-llm/bin/python
LLM_DIR=../llm-threat-intelligence
LLM_BRIDGE_PATH=./scripts/llm_bridge.py
LLM_TIMEOUT_MS=30000
# GROQ_API_KEY=...  # optional; never commit
```

Without `GROQ_API_KEY`, the bridge returns demo intelligence and the prompt with `explanation_status: "skipped"`. With a key, it calls Groq. Provider failure returns `explanation_status: "error"` without discarding the prompt/intelligence. A component without the generator reports `not_generated`; a successful call reports `generated`.

## Demo lookup behavior

`threat_intel.py` validates indicator syntax. The built-in map contains reserved demonstration indicators only. `not_found` means only that the indicator is absent from that map; it is not a safety result.

## Security and privacy

- Never commit `GROQ_API_KEY`.
- Reports can contain sensitive URLs, telemetry, paths, commands, hashes, and indicators.
- Approve provider retention/training terms before external transmission.
- Treat extracted strings and model output as untrusted text; prompt injection remains a risk.
- Generated prose is not a verdict and has no sentence-level evidence citations.

See [the full component record](../docs/components/llm-threat-intelligence.md) for the bridge contract, fallback states, privacy gaps, and next work.
