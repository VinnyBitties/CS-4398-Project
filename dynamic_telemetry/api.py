import os
import time
import uuid
import shutil
import subprocess
from typing import List, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import Evtx.Evtx as evtx
import xml.etree.ElementTree as ET

app = FastAPI(
    title="Malware Sandbox Detonation Engine",
    description="Automated nested KVM/QEMU dynamic detonation and behavioral telemetry engine.",
    version="1.0.0"
)

DOMAIN = "win10-sandbox"
SNAPSHOT = "clean-hardened-sysmon"
UPLOAD_DIR = "/home/Coinflippers/sandbox_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def run_cmd(cmd: List[str]) -> str:
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\nError: {res.stderr.strip()}")
    return res.stdout.strip()

def guest_exec(command_str: str) -> None:
    run_cmd(["virsh", "qemu-agent-command", DOMAIN,
             f'{{"execute":"guest-exec", "arguments":{{"path":"cmd.exe", "arg":["/c", "{command_str}"]}}}}'])

def revert_snapshot() -> None:
    run_cmd(["virsh", "snapshot-revert", DOMAIN, SNAPSHOT])

def parse_sysmon_evtx(filepath: str) -> Dict[str, Any]:
    events = {"processes": [], "network": [], "dns": [], "file_drops": [], "registry": []}
    if not os.path.exists(filepath):
        return events
    try:
        with evtx.Evtx(filepath) as log:
            for record in log.records():
                root = ET.fromstring(record.xml())
                ns = {"ns": "http://schemas.microsoft.com/win/2004/08/events/event"}
                eid_elem = root.find(".//ns:System/ns:EventID", ns)
                if eid_elem is None or not eid_elem.text:
                    continue
                eid = eid_elem.text
                data = {d.get("Name"): d.text for d in root.findall(".//ns:EventData/ns:Data", ns)}
                
                if eid == "1":
                    events["processes"].append({
                        "image": data.get("Image"),
                        "command_line": data.get("CommandLine"),
                        "parent": data.get("ParentImage"),
                        "pid": data.get("ProcessId")
                    })
                elif eid == "3":
                    events["network"].append({
                        "image": data.get("Image"),
                        "dest_ip": data.get("DestinationIp"),
                        "dest_port": data.get("DestinationPort")
                    })
                elif eid == "22":
                    events["dns"].append({
                        "query": data.get("QueryName"),
                        "results": data.get("QueryResults")
                    })
                elif eid == "11":
                    events["file_drops"].append({
                        "target_filename": data.get("TargetFilename"),
                        "image": data.get("Image")
                    })
                elif eid in ["12", "13"]:
                    events["registry"].append({
                        "target_object": data.get("TargetObject"),
                        "details": data.get("Details")
                    })
    except Exception as e:
        events["parse_error"] = str(e)
    return events

@app.get("/health")
def health_check():
    try:
        run_cmd(["virsh", "qemu-agent-command", DOMAIN, '{"execute":"guest-ping"}'])
        return {"status": "ready", "vm": DOMAIN, "snapshot_target": SNAPSHOT}
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "degraded", "error": str(e)})

@app.post("/detonate")
async def detonate_sample(file: UploadFile = File(...), timeout: int = Form(15)):
    job_id = str(uuid.uuid4())
    safe_filename = "".join(c for c in file.filename if c.isalnum() or c in "._-")
    host_sample_path = os.path.join(UPLOAD_DIR, f"{job_id}_{safe_filename}")
    host_evtx_path = os.path.join(UPLOAD_DIR, f"{job_id}_sysmon.evtx")
    guest_sample_path = f"C:\\Tools\\{safe_filename}"

    with open(host_sample_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        revert_snapshot()
        time.sleep(1)

        run_cmd(["virsh", "qemu-agent-command", DOMAIN,
                 f'{{"execute":"guest-exec", "arguments":{{"path":"cmd.exe", "arg":["/c", "certutil -decode"]}}}}'])

        guest_exec(f'cmd.exe /c start "" "{guest_sample_path}"')
        time.sleep(timeout)

        guest_exec('wevtutil epl "Microsoft-Windows-Sysmon/Operational" C:\\Tools\\sysmon_dump.evtx /ow:true')
        time.sleep(2)

        telemetry = parse_sysmon_evtx(host_evtx_path)

        return {
            "job_id": job_id,
            "filename": safe_filename,
            "timeout_seconds": timeout,
            "summary": {
                "process_count": len(telemetry["processes"]),
                "network_count": len(telemetry["network"]),
                "dns_count": len(telemetry["dns"]),
                "file_drops_count": len(telemetry["file_drops"]),
                "registry_count": len(telemetry["registry"])
            },
            "telemetry": telemetry
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        revert_snapshot()
        for p in [host_sample_path, host_evtx_path]:
            if os.path.exists(p):
                os.remove(p)
