# LLM and Threat-Intelligence Integration

## Purpose and status

This component builds bounded analysis evidence, validates/enriches indicators against a demonstration map, and can optionally ask Groq for a plain-language explanation. Its status is **Partial**.

The external-component source is now committed in `llm-threat-intelligence/`, and the bridge can call Groq model `openai/gpt-oss-20b`. MITRE ATT&CK mapping, evidence citations, a production intelligence feed, a versioned output schema, and provider evaluation are not implemented.

## Source layout

| Path | Responsibility |
| --- | --- |
| `backend/src/adapters/llmInput.js` | Builds bounded prior-stage report and extracts indicators |
| `backend/scripts/llm_bridge.py` | JSON stdin/stdout bridge, demo lookup, prompt, optional explanation/fallback |
| `backend/src/pipeline/stages.js` | Adds final `llm` stage when `LLM_DIR` is configured |
| `backend/src/stages/pythonStage.js` | Bounded subprocess execution/error mapping |
| `llm-threat-intelligence/threat_intel.py` | Indicator validation and small demo indicator map |
| `llm-threat-intelligence/llm_analyzer.py` | Evidence prompt and optional Groq call |
| `backend/test/llmStage.test.js` | Adapter, bridge, fallback, ordering, and pipeline tests |

## Enablement

Install the root Python requirements in the interpreter named by `PYTHON_PATH`, then configure:

```dotenv
LLM_DIR=../llm-threat-intelligence
LLM_BRIDGE_PATH=./scripts/llm_bridge.py
LLM_TIMEOUT_MS=30000
# GROQ_API_KEY=...  # optional; never commit
```

The stage runs last for files and links. Failed/missing earlier stages remain absent evidence rather than being invented.

## Input preparation

The adapter includes the sample identity and available signature, static, sandbox, and behavioral-ML reports. High-volume event/indicator lists are bounded and truncation is recorded.

Candidate indicators include:

- File SHA-256.
- Submitted URL and domain.
- Public domains and selected standalone public IPs found in telemetry.

Selected standalone private, loopback, link-local, and nonpublic IP indicators are filtered. Submitted URLs and raw report fields are not comprehensively redacted, so a private address can still appear inside a URL or telemetry. Bounding is not a privacy policy.

## Threat intelligence

`threat_intel.py` validates hash/IP/domain/URL syntax and checks a small in-code demonstration map. Results can be `unsupported`, `invalid`, `suspicious`, or `not_found`. `not_found` explicitly does not mean safe.

This is not a live commercial/community feed. There is no feed version, coverage statement, update process, SLA, or accuracy evaluation.

## Optional Groq explanation

`llm_analyzer.py` builds a prompt from supplied evidence and, when `GROQ_API_KEY` exists, calls Groq with:

- Model: `openai/gpt-oss-20b`
- `max_tokens`: 500
- System instruction: remain grounded in supplied evidence and admit insufficiency

The bridge treats explanation generation as optional:

| `explanation_status` | Meaning |
| --- | --- |
| `generated` | Groq returned explanation text |
| `skipped` | `GROQ_API_KEY` was not set |
| `error` | Provider/import/network/key/rate-limit call failed |
| `not_generated` | Loaded component has no generator function |

For `skipped`, `error`, and `not_generated`, the stage can still return demo threat intelligence and the prompt. Prompt/intelligence construction failures still fail the stage.

## Output and missing contract

The backend stores:

- `threat_intel[]`
- `prompt`
- `explanation` or `null`
- `explanation_status` and optional `explanation_error`
- Extracted `indicators[]`
- `stages_used[]`

There is no versioned schema for cited claims, severity/confidence, recommendations, ATT&CK tactic/technique IDs, ATT&CK version, or reviewer disposition. The dashboard also lacks a dedicated safe explanation/mapping viewer.

## Tests

`backend/test/llmStage.test.js` covers indicator validation/filtering, event/indicator bounds, missing component, bridge exception, all explanation fallback states using temporary modules, ordering, file/link participation, and independent stage failure.

These tests do not call Groq or validate ATT&CK mappings. Fresh Node results are in [Prototype Status](../prototype-status.md#verification-record).

## Security, privacy, and grounding

- Telemetry, strings, URLs, domains, IPs, paths, filenames, and hashes can be sensitive.
- Approve provider retention/training terms and allowed data before setting a real key.
- Extracted content can contain prompt injection; current prompt formatting is not a complete delimiter/policy defense.
- Render output as untrusted text.
- Store secrets outside source/reports and use least privilege.
- A generated explanation is analyst assistance, not an independent verdict.
- Claims and future ATT&CK mappings require source-field citations and human review.

## Known limitations

- Demo-only threat-intelligence coverage.
- No MITRE ATT&CK mapping implementation.
- No sentence-level evidence citations or versioned output schema.
- No prompt version, temperature setting, retry/backoff, cost budget, or provider/model evaluation.
- No complete redaction/data-class policy.
- No dashboard report renderer for the explanation/mappings.

## Next work

1. Define a versioned, cited structured output contract.
2. Add reviewed ATT&CK technique mapping with evidence and ATT&CK version.
3. Establish provider/privacy/retention/cost policy and secret handling.
4. Add prompt-injection, missing-evidence, false-mapping, and unsupported-claim evaluations.
5. Replace/augment demo intelligence with an approved versioned feed.
6. Add a safe dashboard renderer and reviewer workflow.

## Related documentation

- [Component README](../../llm-threat-intelligence/README.md)
- [Component status](../../llm-threat-intelligence/STATUS.md)
- [Architecture](../architecture.md)
- [Backend](backend.md)
- [Frontend](frontend.md)
- [Prototype Status](../prototype-status.md)
