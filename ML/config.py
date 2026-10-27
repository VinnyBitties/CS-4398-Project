FEATURE_COLUMNS = [
    "num_processes_created",
    "num_files_written",
    "num_registry_keys_set",
    "num_network_connections",
    "num_dns_requests",
    "num_signatures_matched",
    "max_signature_severity",
    "has_persistence_signature",   # binary flag from signatures list
    "has_network_signature",
]

DEFAULT_MALICIOUS_THRESHOLD = 0.5

PERSISTENCE_KEYWORDS = [
    "persistence",
    "autorun",
    "auto-run",
    "startup",
    "run key",
    "scheduled task",
    "task scheduler",
    "service install",
    "registry run",
]

NETWORK_KEYWORDS = [
    "network",
    "dns",
    "http",
    "https",
    "beacon",
    "c2",
    "command and control",
    "exfil",
    "exfiltration",
    "callback",
    "communication",
]

# --- Dataset / synthetic data paths -----------------------------------------
# Centralized here so synthetic_reports.py, build_dataset.py, and the eventual
# train_classifier.py / train_anomaly.py all agree on where things live.
# Swap SYNTHETIC_REPORTS_DIR for a real sandbox output directory once one exists
# -- nothing downstream needs to change.
 
from pathlib import Path
 
DATA_DIR = Path("data")
SYNTHETIC_REPORTS_DIR = DATA_DIR / "synthetic_reports"
MANIFEST_PATH = DATA_DIR / "manifest.csv"          # columns: report_path,label
FEATURES_CSV_PATH = DATA_DIR / "features.csv"      # columns: FEATURE_COLUMNS + label
 
# label convention used across the dataset: 1 = malicious, 0 = benign
LABEL_MALICIOUS = 1
LABEL_BENIGN = 0