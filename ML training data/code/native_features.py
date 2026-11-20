"""Native-only 30-second contract shared by research and future inference.

The deployed v2 extractor remains unchanged. All of its identity, capture,
cleanup, timestamp and process-GUID checks run before this projection.
"""
import datetime as dt
import hashlib
import math
from pathlib import Path
import unified_features as legacy

SCHEMA_VERSION = 'cfd-native-window30-v3'
STATIC_COLUMNS = ['static_log_file_size', 'static_section_count',
    'static_weighted_entropy', 'static_max_entropy', 'static_log_imported_dll_count',
    'static_log_imported_api_count', 'static_log_string_density_per_kib']
DYNAMIC_COLUMNS = ['dynamic_log_child_process_count', 'dynamic_log_network_count',
    'dynamic_log_dns_count', 'dynamic_log_file_count', 'dynamic_log_registry_count']
FEATURE_COLUMNS = STATIC_COLUMNS + DYNAMIC_COLUMNS
EXTRACTOR_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
DEPENDENCY_SHA256 = legacy.EXTRACTOR_SHA256
InputError = legacy.InputError


def timestamp(value):
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00'))


def project(payload):
    old = legacy.extract(payload)
    static, dynamic = payload['static']['report'], payload['dynamic']['report']
    collection, telemetry = dynamic['collection'], dynamic['telemetry']
    root = next(p for p in telemetry['processes']
                if p['process_guid'] == collection['sample_process_guid'])
    launch = timestamp(root['timestamp'])
    end = launch + dt.timedelta(seconds=30)
    legacy.require(timestamp(collection['started_at']) <= launch and
                   timestamp(collection['finished_at']) >= end,
                   'INPUTS_INCOMPLETE', 'A complete measured 30-second post-launch window is required.')
    # Use guest UTC for both boundaries. No host/guest clock subtraction.
    clipped = {key: [event for event in telemetry[key] if timestamp(event['timestamp']) <= end]
               for key in legacy.LISTS}
    counts = legacy.attributed_counts(clipped, collection,
                                      timestamp(collection['started_at']), end)
    sections = static['sections']
    sizes = [legacy.number(x.get('raw_size'), 'section_raw_size', 25 * 1024**2) for x in sections]
    legacy.require(sum(sizes) > 0, 'MISSING_OR_INVALID_FEATURE', 'Nonempty PE section bytes are required.')
    imports = static.get('imports', {})
    legacy.require(isinstance(imports.get('apis'), list) and isinstance(imports.get('dlls'), list)
                   and len(imports['apis']) == old['static_imported_api_count']
                   and len(imports['dlls']) == old['static_imported_dll_count'],
                   'MISSING_OR_INVALID_FEATURE', 'Import arrays disagree with static summary.')
    values = [math.log1p(old['static_file_size']), old['static_section_count'],
        sum(s * section['entropy'] for s, section in zip(sizes, sections)) / sum(sizes),
        old['static_max_entropy'], math.log1p(old['static_imported_dll_count']),
        math.log1p(old['static_imported_api_count']),
        math.log1p(old['static_string_count'] * 1024 / max(1, old['static_file_size'])),
        math.log1p(counts[0] - 1), *[math.log1p(x) for x in counts[1:5]]]
    return {'features': dict(zip(FEATURE_COLUMNS, values)), 'quality': {
        'sha256': payload['sha256'], 'run_id': payload['run_id'], 'window_seconds': 30,
        'post_launch_coverage_seconds': old['dynamic_observation_seconds'],
        'root_guid': root['process_guid'], 'root_timestamp': root['timestamp'],
        'window_end': end.isoformat(), 'sample_tree_counts': dict(zip(legacy.LISTS, counts[:6])),
        'guest_event_counts': {k: len(telemetry[k]) for k in legacy.LISTS},
        'missing_data_policy': 'reject, never impute', 'clock_domain': 'guest UTC'}}


def extract(payload):
    return project(payload)['features']
