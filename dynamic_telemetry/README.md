# Dynamic Telemetry & Malware Detonation Engine

Automated nested KVM/QEMU dynamic analysis engine designed to execute untrusted binaries, record kernel-level Sysmon events, and extract structured behavioral telemetry.

## Architecture Overview
* **Hypervisor Layer:** KVM/QEMU nested virtualization inside an Azure host.
* **Guest Environment:** Hardened Windows 10 VM (`win10-sandbox`) monitored by Microsoft Sysmon.
* **Orchestration:** Out-of-band communication via QEMU Guest Agent Virtio serial channels (zero network sharing).
* **Rollback:** Sub-3s golden state snapshot reversion (`virsh snapshot-revert`) between runs.
* **Telemetry Parsing:** Binary Windows `.evtx` stream parsed into normalized JSON schemas using `python-evtx`.
* **API Service:** FastAPI daemonized with `systemd` (`sandbox-api.service`).

## API Endpoints
* **Swagger Documentation:** `http://9.160.32.135:8000/docs`
* **GET `/health`**: Checks hypervisor and QEMU guest agent readiness.
* **POST `/detonate`**: Uploads sample payload, stages headlessly, flushes Sysmon buffer, extracts event telemetry, and rolls back to baseline snapshot.

## Quickstart (Client Test)
```bash
pip install -r requirements.txt
python client_example.py <path_to_sample>

