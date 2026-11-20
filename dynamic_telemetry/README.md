# Dynamic Telemetry Service Prototype

`dynamic_telemetry/api.py` is an environment-specific FastAPI prototype for KVM/QEMU snapshot control and Sysmon EVTX parsing. It is intended to back Sentinel's optional `sandbox` stage.

> **Safety:** Do not execute real malware. The committed source does not yet demonstrate working sample transfer into the guest, EVTX export back to the host, network isolation, failure-safe reset, cleanup, or containment.

## Included files

| File | Purpose |
| --- | --- |
| `dynamic_telemetry/api.py` | `/health`, `/detonate`, virsh/QEMU Guest Agent commands, snapshot revert, EVTX parsing |
| `dynamic_telemetry/client_example.py` | Simple environment-specific API client |
| `dynamic_telemetry/requirements.txt` | FastAPI, Uvicorn, multipart, `python-evtx`, requests |
| `dynamic_telemetry/sandbox-api.service` | Example systemd service definition |

## Intended endpoints

- `GET /health` checks QEMU Guest Agent reachability.
- `POST /detonate` accepts multipart field `file` and form field `timeout`, then intends to return summary counts plus process, network, DNS, file, and registry telemetry.

The backend appends `/detonate` to `SANDBOX_URL` and serializes calls for a single-VM design.

## Environment-specific constants

The source currently hard-codes the libvirt domain, snapshot, staging directory, service account, working directory, and example client address. These values describe one development environment; they are not portable defaults or deployment instructions.

Before starting a service, replace hard-coded values with reviewed configuration and validate:

1. Dedicated host/guest boundary and guest hardening.
2. Working bounded sample transfer to the guest.
3. Working EVTX export to the exact host path the parser reads.
4. Network isolation/simulation and egress tests.
5. Authentication, upload/resource limits, and service exposure.
6. Reset and cleanup under normal, timeout, crash, and parser-failure paths.
7. Retention, logging, access, and incident procedures.

## Current source gaps

Source inspection on 2026-11-19 found no host-to-guest sample copy and no guest-to-host EVTX copy. The guest command references `C:\Tools\<filename>`, while the upload remains in a host staging directory; the parser reads a generated host EVTX path that no code populates. Therefore live detonation and telemetry collection are not verified.

The snapshot-revert calls and QEMU Guest Agent channel express the intended control plane, but they do not prove network isolation or host containment.

## Dependency installation for inert development

Use an isolated environment on the reviewed virtualization host:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r dynamic_telemetry/requirements.txt
```

Do not run `uvicorn` against an unreviewed VM/network or expose it publicly. After the transfer/export path is implemented, start with inert canary files and prove every lifecycle/cleanup step before considering broader testing.

## Backend configuration after validation

```dotenv
SANDBOX_URL=http://sandbox-host.example:8000
SANDBOX_DETONATION_SECONDS=15
SANDBOX_TIMEOUT_MS=120000
```

See [the dynamic-analysis component record](../docs/components/dynamic-analysis.md) for the full contract, test boundary, and safety checklist.
