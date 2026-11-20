# Dynamic Sandbox Integration

## Purpose and status

The dynamic-analysis component is intended to execute authorized Windows samples inside an isolated, revertible VM, collect runtime telemetry, and return it for behavioral scoring and reporting. Its current status is **Partial** and **not safety-verified**.

This branch now contains both the backend client/adapter and `dynamic_telemetry/api.py`, a FastAPI service with KVM/QEMU snapshot commands and Sysmon EVTX parsing. Source presence supersedes the old “service absent” description, but it does not prove working sample transfer, EVTX export, network isolation, live detonation, cleanup, or containment.

> **Safety:** Do not execute real malware. Use inert canary files only until the gaps below are fixed and an independent containment review passes.

## Source layout

| Path | Responsibility |
| --- | --- |
| `dynamic_telemetry/api.py` | FastAPI health/detonation endpoints, virsh/QEMU Guest Agent calls, snapshot revert, EVTX parser |
| `dynamic_telemetry/client_example.py` | Environment-specific health/detonation example |
| `dynamic_telemetry/requirements.txt` | FastAPI/Uvicorn/multipart/EVTX/request dependencies |
| `dynamic_telemetry/sandbox-api.service` | Example systemd unit |
| `backend/src/stages/sandboxClient.js` | Multipart client, timeouts/errors, one-at-a-time lock |
| `backend/src/adapters/sandboxToMl.js` | Response validation and behavioral-ML normalization |
| `backend/src/pipeline/stages.js` | Optional sandbox/behavioral-ML gates |
| `backend/test/sandboxStages.test.js` | Mock service/client/adapter/pipeline tests |

## Intended service flow

1. `POST /detonate` stores the uploaded file under a generated host name.
2. The service reverts a named libvirt domain to a named snapshot.
3. QEMU Guest Agent commands start the configured guest path and export the Sysmon operational log.
4. `python-evtx` parses process, network, DNS, file, and registry event IDs.
5. The service returns summary counts and event arrays.
6. A `finally` block attempts another snapshot revert and removes host staging files.

`GET /health` sends QEMU Guest Agent `guest-ping` and returns ready/degraded state.

## Source-inspection gaps

The committed implementation does not currently demonstrate the complete intended flow:

- No code copies the uploaded host sample into `C:\Tools\...` inside the guest.
- No code exports/copies the guest `sysmon_dump.evtx` into the generated host EVTX path before parsing.
- The `certutil -decode` guest command has no source/destination arguments and is not a sample-transfer mechanism.
- Network configuration, authentication, upload limits, resource controls, guest hardening, and host/guest credential boundaries are not defined in the repository.
- Snapshot revert in `finally` is an intent, not proof of failure-safe recovery; an exception during cleanup can still leave uncertainty.
- Deployment constants (domain, snapshot, service user, paths, address) are environment-specific.

Until sample transfer and EVTX export are implemented and exercised, a live detonation/telemetry claim is unsupported.

## Backend contract

When `SANDBOX_URL` is nonempty, the backend appends `/detonate` and sends:

- Multipart field `file` containing the stored upload.
- Form field `timeout` from `SANDBOX_DETONATION_SECONDS`.

Expected output contains `summary` plus `telemetry` arrays for processes, network, DNS, file drops, and registry changes. The adapter accepts known raw/normalized variants and creates the behavioral-ML report.

Empty, malformed, or parse-failed telemetry causes the sandbox stage to fail. It is not scored as zero activity. Remote-thread data can remain uncaptured and is recorded with adapter notes.

## Configuration

Backend example after an environment is independently reviewed:

```dotenv
SANDBOX_URL=http://sandbox-host.example:8000
SANDBOX_DETONATION_SECONDS=15
SANDBOX_TIMEOUT_MS=120000
BEHAVIORAL_ML_URL=http://127.0.0.1:8000/analyze
BEHAVIORAL_ML_TIMEOUT_MS=15000
```

Do not copy the committed fixed address or service paths as portable defaults.

## Concurrency and isolation

The Node client serializes requests within one process because the design assumes one VM. It does not provide distributed locking, authorization, host isolation, network isolation, snapshot correctness, or cleanup proof.

A safe development environment needs at minimum:

1. Dedicated host/guest boundary with no shared credentials or writable host mounts.
2. Reviewed egress isolation/simulation and prohibited-destination tests.
3. Verified sample transfer and EVTX export that cannot escape staging paths.
4. Resource/time limits and service authentication.
5. Known-state reset checks before and after every inert run, including forced failures.
6. Patch/tool/snapshot version records and immutable run metadata.
7. Retention, access, cleanup, and incident procedures.

## Tests and verification boundary

Backend mock tests cover multipart serialization, timeout/error mapping, non-overlap, adapter normalization, dependency failures, and pipeline behavior. They do not run KVM/QEMU, transfer a sample, collect EVTX, or prove containment.

No live VM test is recorded for 2026-11-19. The verification table in [Prototype Status](../prototype-status.md#verification-record) reports only commands actually run.

## Safety validation record

| Control | Current evidence | Result |
| --- | --- | --- |
| Service source | FastAPI/KVM/QEMU/Sysmon code committed | Present |
| Sample transfer | No working host-to-guest copy in source | Not verified |
| EVTX export | No guest-to-host copy into parsed path | Not verified |
| Network isolation | No committed network policy/test | Not verified |
| Snapshot/reset | Revert commands in normal/finally paths | Source present; behavior not verified |
| Host containment | No independent review or canary evidence | Not verified |
| One request at a time | In-process Node lock and mock test | Client boundary only |
| Live telemetry | No recorded inert end-to-end run | Not verified |

## Next work

1. Implement explicit, bounded sample transfer and EVTX export.
2. Replace deployment constants with validated configuration and startup checks.
3. Add authentication, size/resource limits, structured logs, and cleanup evidence.
4. Prove network isolation and reset with inert canaries and forced failures.
5. Version the producer/consumer telemetry schema.
6. Run the full sandbox → adapter → ML path with inert fixtures and preserve evidence.
7. Obtain independent containment approval before any real malware.

## Related documentation

- [Dynamic service README](../../dynamic_telemetry/README.md)
- [Machine learning](machine-learning.md)
- [Backend](backend.md)
- [Architecture](../architecture.md)
- [Setup and Operations](../setup-and-operations.md)
- [Prototype Status](../prototype-status.md)
