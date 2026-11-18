# LLM and Threat-Intelligence Integration

## Purpose and status

The planned component should convert analysis evidence into a plain-language explanation, map supported behaviors to MITRE ATT&CK, and provide recommendations with traceable evidence. Its current status is **Stubbed/configurable**.

This branch contains a bounded input adapter, pipeline stage, and Python bridge for an external `llm-threat-intelligence/` directory. That external component is absent. No provider, model, prompt artifact, LLM call, explanation, citation scheme, or ATT&CK mapper is implemented here.

## Code that is present

| Path | Responsibility |
| --- | --- |
| `backend/src/adapters/llmInput.js` | Assemble prior stage reports, extract/filter indicators, bound event/indicator lists |
| `backend/scripts/llm_bridge.py` | Import the external component and exchange JSON through stdin/stdout |
| `backend/src/pipeline/stages.js` | Add the final `llm` stage when `LLM_DIR` is configured |
| `backend/src/stages/pythonStage.js` | Bounded Python subprocess execution and error handling |
| `backend/test/llmStage.test.js` | Adapter, bridge, ordering, link, and failure tests |

## Enablement and execution

```dotenv
LLM_DIR=../llm-threat-intelligence
LLM_BRIDGE_PATH=./scripts/llm_bridge.py
LLM_TIMEOUT_MS=30000
PYTHON_PATH=python3
```

When enabled, the stage runs last for files and URLs. It receives any stored signature, static-analysis, sandbox, and behavioral-ML reports; failed or unavailable stages are represented as empty/missing evidence rather than invented results. The bridge receives a report plus indicators as JSON on stdin and must return JSON on stdout.

If the directory is missing, import fails, execution times out, the process exits nonzero, output exceeds bounds, or JSON is invalid, only the `llm` stage fails.

## Evidence and indicator preparation

The adapter preserves earlier reports while bounding high-volume event lists. It records truncation so downstream prose should not imply that a shortened list is complete.

Candidate indicators include:

- File SHA-256 for file submissions.
- Submitted URL and host for link submissions.
- Public domains and selected standalone IP addresses observed in sandbox telemetry.

The adapter filters selected standalone private, loopback, link-local, and other nonpublic IP indicators. That filter does not redact the complete submitted URL: a URL such as `http://127.0.0.1/` remains a URL indicator. Earlier-stage reports also retain raw telemetry fields for the bridge. Indicator count and event-list length are capped, but submitted URLs and raw telemetry are not otherwise redacted. These bounds reduce volume; they are not a complete privacy review or sensitive-data policy.

## Output currently available

The bridge is expected to return threat-intelligence results for indicators and a prompt built from evidence. The backend can store indicator results and the stage report. The backend README explicitly records that the component does not yet call an LLM, so generated `explanation` is absent/null in the represented integration.

No committed schema requires:

- Evidence citations from sentences to stage/report fields.
- MITRE tactic/technique identifiers and versions.
- Confidence or uncertainty.
- Recommendations or severity.
- Refusal/fallback behavior when evidence is insufficient.
- Prompt/model/provider metadata.

Those contracts must be defined before the dashboard treats output as an analyst report.

## Configuration record

| Field | Current value |
| --- | --- |
| Provider/model | Not recorded; external component absent |
| API/SDK version | Not recorded |
| Temperature/token limits | Not recorded |
| Prompt version | Not recorded |
| Timeout | Backend default 30 seconds |
| Retry behavior | No retry in current bridge stage |
| Cost controls | Not recorded |
| Data sent externally | No provider call in branch; candidate evidence/indicators prepared by adapter |
| Redaction/minimization | Selected standalone IP filter and list bounds only; submitted URLs and raw telemetry remain unredacted |

## Test inventory and observed result

The Node tests cover file and URL indicators, private-address exclusion, telemetry truncation, bridge success/failure, missing directory, component exception, stage ordering, link participation, and independent pipeline failure. They use fixtures or a temporary external-component shape, not a real provider.

On 2026-11-03, `npm test` did not start because the available npm shim reported unsupported WSL 1. No real model, enrichment provider, prompt, or MITRE mapping was tested.

## Grounding and mapping requirements

Before this component can be considered implemented, each report claim should identify the source stage and evidence field, distinguish observed facts from model/heuristic inferences, state missing/failed stages, and avoid converting “no evidence” into “benign.” MITRE mappings should include tactic/technique identifiers, evidence, confidence, ATT&CK version/date, and human review outcome.

Fallback output should remain useful when no provider is available: structured evidence, stage statuses, explicit uncertainty, and no fabricated narrative.

## Security and privacy notes

- Telemetry, strings, domains, IPs, URLs, filenames, and hashes can be sensitive even without file content.
- Define provider retention/training terms and approved data classes before external calls.
- Store credentials outside source and reports; use least-privilege secrets.
- Treat model output as untrusted text and render safely.
- Prompt injection can exist in extracted strings, URLs, or telemetry; delimit evidence and prevent it from changing system instructions.
- ATT&CK mappings and remediation advice require human review until measured.

## Known limitations

- External implementation absent.
- No LLM provider/model invocation.
- No versioned prompt or output schema.
- No citations, hallucination controls, ATT&CK validation, cost limits, or redaction policy.
- No accuracy, mapping precision, or analyst usability evaluation.

## Next work

1. Define the versioned input/output schema and evidence-citation format.
2. Select provider/model under an approved privacy and cost policy.
3. Add prompt/version metadata, deterministic fallbacks, timeouts/retries, and secret handling.
4. Implement ATT&CK mapping with versioned technique identifiers and reviewer workflow.
5. Build adversarial tests for prompt injection, missing evidence, false mappings, and unsupported claims.
6. Connect a safe detailed report renderer in the dashboard.

## Related documentation

- [Architecture](../architecture.md)
- [Backend component](backend.md)
- [Frontend component](frontend.md)
- [Prototype Status](../prototype-status.md)
- [Setup and Operations](../setup-and-operations.md)
