# Dynamic Sandbox Integration

## Purpose and status

The planned dynamic-analysis component should execute unknown Windows binaries inside an isolated, revertible VM, collect runtime telemetry, and return it for behavioral scoring and evidence. Its current status in this branch is **Stubbed/configurable**.

The repository contains the backend client, validation, telemetry adapter, pipeline gate, and mock-service tests. It does **not** contain the referenced `dynamic_telemetry/` service, hypervisor configuration, guest image, snapshot/reset automation, sample-transfer logic, Sysmon configuration, log exporter, or real isolation test.

## Code that is present

| Path | Responsibility |
| --- | --- |
| `backend/src/stages/sandboxClient.js` | Multipart `/detonate` client, timeout/error mapping, one-at-a-time lock |
| `backend/src/adapters/sandboxToMl.js` | Response validation, known field translation, ML report construction |
| `backend/src/pipeline/stages.js` | Configuration gate, stage ordering, dependency on usable telemetry |
| `backend/test/sandboxStages.test.js` | Mock client, timeout, serialization, adapter, and pipeline tests |

## Enablement and expected service

The backend adds `sandbox` and `behavioral_ml` stages only when `SANDBOX_URL` is nonempty.

```dotenv
SANDBOX_URL=http://127.0.0.1:9000
SANDBOX_DETONATION_SECONDS=15
SANDBOX_TIMEOUT_MS=120000
BEHAVIORAL_ML_URL=http://127.0.0.1:8000/
BEHAVIORAL_ML_TIMEOUT_MS=15000
```

The client appends `/detonate` to the base URL and sends multipart data containing the stored file and requested execution timeout. It expects JSON and maps connection failure, request timeout, non-2xx status, and invalid JSON to stable stage errors.

Only file submissions apply. URL rendering/detonation is not implemented.

## Concurrency and lifecycle assumption

The backend serializes detonation requests because the documented design assumes one VM. That lock prevents overlapping client calls in one Node process; it does not provide VM isolation, snapshot restoration, distributed locking, or cleanup.

A safe external service would need to demonstrate at least:

1. Reject unauthorized/oversized inputs and store them outside shared host paths.
2. Revert or recreate a known guest state before each run.
3. Transfer the sample without exposing host mounts or credentials.
4. Enforce execution time/resource limits.
5. Isolate or simulate network access according to an approved policy.
6. Collect process, file, registry, network, DNS, and injection telemetry.
7. Export logs without allowing the guest to write arbitrary host paths.
8. Restore the known state and prove cleanup before the next job.

None of these behaviors is evidenced by the code in this branch.

## Telemetry expectations

The adapter recognizes a sandbox response containing a summary and event arrays. Expected behavioral counts include processes created, files created, registry modifications, network connections, DNS queries, and remote threads injected. The current adapter also maps known producer names such as `process_count`, `files_written`, and `query` into the ML consumer's names.

If the response reports a parse error, lacks telemetry, or has no required event arrays/counts, the sandbox stage fails. It is not converted into a zero-activity report. If remote-thread data is unavailable, the adapter records a zero with a note; that value represents a blind spot, not observed absence.

## Test inventory and observed result

The Node mock tests cover:

- Field-name translation and pass-through of an already compatible report.
- Rejection of parse-error and no-telemetry responses.
- Multipart upload and timeout field.
- HTTP error, unreachable service, and timeout handling.
- Non-overlapping detonation calls.
- Pipeline translation and behavioral scoring against mock services.
- Ensuring failed/empty sandbox output is not scored.
- Independent behavioral-ML failure and link-stage exclusion.

On 2026-11-03, these tests did not start because the available npm shim reported unsupported WSL 1. No real sandbox or VM test was attempted.

## Safety validation record

| Control | Current evidence | Result |
| --- | --- | --- |
| Host isolation | No sandbox implementation | Not verified |
| Network isolation | No environment configuration | Not verified |
| Snapshot/reset | No lifecycle implementation | Not verified |
| Sample transfer | Referenced service absent | Not verified |
| Resource/time limits | Client requests a timeout only | Partial client control, not verified in guest |
| Log export integrity | Adapter rejects parse/no telemetry | Consumer validation only |
| One run at a time | In-process client lock and mock test | Implemented at client boundary; not VM proof |

## Security rules

- Do not run real malware from this branch.
- Do not treat `SANDBOX_URL` configuration as containment evidence.
- Keep the service on a dedicated isolated network with no host/shared credentials.
- Preserve raw telemetry and environment/version metadata for reproducibility, but apply access and retention controls.
- Record guest OS version, patches, hypervisor, snapshot ID, tools, network mode, timeout, and resource limits for every evaluated run.

## Known limitations

- No runnable service or VM artifacts.
- No verified schema shared directly by producer and ML consumer.
- No injected-thread capture evidence.
- No URL detonation.
- No safety, reproducibility, or performance results.
- No malware sample-handling procedure.

## Next work

1. Add the service/environment implementation or merge its source with a versioned contract.
2. Write and review a malware-handling and containment procedure before testing.
3. Prove network isolation and snapshot restoration with inert canary tests.
4. Agree one telemetry schema and remove translation ambiguity.
5. Run the sandbox and behavioral-ML integration with inert fixtures and record evidence.
6. Add observability, artifact retention, cleanup, and failure-recovery procedures.

## Related documentation

- [Machine-learning component](machine-learning.md)
- [Backend component](backend.md)
- [Architecture](../architecture.md)
- [Setup and Operations](../setup-and-operations.md)
- [Prototype Status](../prototype-status.md)
