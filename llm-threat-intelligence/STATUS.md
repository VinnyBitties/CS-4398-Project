# LLM and Threat-Intelligence Status

Status on 2026-11-19: **Partial**.

## Present

- Indicator validation for hash, IP, domain, and URL values.
- Small demonstration-only threat-intelligence map.
- Evidence-grounded prompt construction from Sentinel report fields.
- Optional Groq explanation using model `openai/gpt-oss-20b` when `GROQ_API_KEY` is set.
- Backend JSON bridge and final pipeline-stage integration.
- Nonfatal explanation states: `generated`, `skipped`, `error`, and `not_generated`.
- Node tests for filtering/bounds, bridge errors/fallbacks, ordering, and file/link behavior.

## Not implemented or verified

- MITRE ATT&CK tactic/technique mapping.
- Sentence-level evidence citations and versioned structured report schema.
- Production threat-intelligence feeds or feed-update process.
- Prompt/provider/model quality, hallucination, cost, latency, and mapping evaluation.
- Complete sensitive-data redaction and provider-retention policy.
- Prompt-injection defense beyond a grounding instruction.
- Dedicated frontend explanation/mapping viewer.
- Live Groq execution in the current documentation verification record.

## Next priorities

1. Define cited/versioned output and ATT&CK mapping contracts.
2. Approve provider privacy, retention, key, and cost controls.
3. Add adversarial grounding/mapping tests and human review.
4. Replace or supplement demo intelligence with an approved versioned source.
5. Add a safe dashboard renderer.
