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