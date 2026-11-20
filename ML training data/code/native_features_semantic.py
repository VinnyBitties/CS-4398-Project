"""Offline native feature revision; does not change the active inference contract.

All v2 identity, completeness, cleanup and GUID checks run first. Targets are
used for cardinality or generic suffix categories, never as literal predictors.
An observed event without its required target is unavailable, not a zero.
"""
import datetime as dt
import hashlib
import math
import ntpath
from pathlib import Path
import native_features as previous

SCHEMA_VERSION = 'cfd-native-window30-semantic-v4'
STATIC_COLUMNS = previous.STATIC_COLUMNS + ['static_executable_section_weighted_entropy']
DYNAMIC_COLUMNS = ['dynamic_log_child_process_count', 'dynamic_log_network_count',
    'dynamic_log_unique_dns_targets', 'dynamic_log_unique_file_targets',
    'dynamic_log_unique_registry_targets', 'dynamic_archive_named_create_observed']
FEATURE_COLUMNS = STATIC_COLUMNS + DYNAMIC_COLUMNS
EXTRACTOR_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
DEPENDENCIES = {'native_features.py': previous.EXTRACTOR_SHA256,
                'unified_features.py': previous.DEPENDENCY_SHA256}
InputError = previous.InputError
ARCHIVE_SUFFIXES = frozenset(('.zip', '.7z', '.rar', '.tar', '.gz', '.bz2', '.xz'))


def attributed_events(payload, checked=None):
    """Return validated sample-tree events in [verified launch, launch+30s]."""
    checked = checked or previous.project(payload)
    dynamic = payload['dynamic']['report']
    start = previous.timestamp(checked['quality']['root_timestamp'])
    end = start + dt.timedelta(seconds=30)
    telemetry = dynamic['telemetry']
    processes = [e for e in telemetry['processes'] if start <= previous.timestamp(e['timestamp']) <= end]
    scope = {checked['quality']['root_guid']}
    children = {}
    for e in processes:
        children.setdefault(e['parent_process_guid'], []).append(e['process_guid'])
    pending = list(scope)
    while pending:
        for child in children.get(pending.pop(), []):
            previous.legacy.require(child not in scope, 'ATTRIBUTION_UNAVAILABLE', 'Invalid process graph.')
            scope.add(child); pending.append(child)
    selected = {'processes': [e for e in processes if e['process_guid'] in scope]}
    for name in previous.legacy.LISTS[1:]:
        actor = 'source_process_guid' if name == 'remote_threads' else 'process_guid'
        selected[name] = [e for e in telemetry[name] if e[actor] in scope
                         and start <= previous.timestamp(e['timestamp']) <= end]
    previous.legacy.require(all(len(selected[k]) == checked['quality']['sample_tree_counts'][k]
                               for k in previous.legacy.LISTS),
                            'ATTRIBUTION_UNAVAILABLE', 'Semantic and count projections disagree.')
    return selected


def targets(events, key, dns=False):
    values = set()
    for event in events:
        value = event.get(key)
        previous.legacy.require(isinstance(value, str) and 0 < len(value.strip()) <= 32768,
            'MISSING_OR_INVALID_FEATURE', 'Observed event lacks a bounded target: ' + key)
        value = value.strip().casefold()
        values.add(value.rstrip('.') if dns else value.replace('/', '\\'))
    previous.legacy.require(all(values), 'MISSING_OR_INVALID_FEATURE', 'Empty normalized target.')
    return values


def project(payload):
    checked = previous.project(payload)
    events = attributed_events(payload, checked)
    sections = [s for s in payload['static']['report']['sections'] if s['executable'] and s['raw_size'] > 0]
    total = sum(s['raw_size'] for s in sections)
    previous.legacy.require(total > 0, 'MISSING_OR_INVALID_FEATURE', 'No measured executable-section bytes.')
    dns = targets(events['dns'], 'query', dns=True)
    files = targets(events['file_drops'], 'target_filename')
    registry = targets(events['registry'], 'target_object')
    features = {k: checked['features'][k] for k in previous.STATIC_COLUMNS}
    features['static_executable_section_weighted_entropy'] = sum(s['entropy'] * s['raw_size'] for s in sections) / total
    features.update(dict(zip(DYNAMIC_COLUMNS, [
        checked['features']['dynamic_log_child_process_count'], checked['features']['dynamic_log_network_count'],
        math.log1p(len(dns)), math.log1p(len(files)), math.log1p(len(registry)),
        float(any(ntpath.splitext(p)[1] in ARCHIVE_SUFFIXES for p in files))])))
    previous.legacy.require(list(features) == FEATURE_COLUMNS and all(math.isfinite(v) for v in features.values()),
                            'MISSING_OR_INVALID_FEATURE', 'Nonfinite or unordered feature vector.')
    return {'features': features, 'quality': {**checked['quality'],
        'unique_targets': {'dns': len(dns), 'file_drops': len(files), 'registry': len(registry)},
        'archive_semantics': 'Sysmon FileCreate target name has an archive suffix; contents and intent unverified.',
        'activation_status': 'Process creation verified; application initialization and exit status unmeasured.'}}


def extract(payload):
    return project(payload)['features']
