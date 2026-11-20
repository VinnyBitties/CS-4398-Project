"""Prospective research contracts; same functions for saved and live evidence.

No active model selects these contracts until the research release gates pass.
"""
import hashlib
import math
import ntpath
from pathlib import Path
import native_features_semantic as semantic
import managed_metadata

SCHEMA_VERSION = 'cfd-native-release-candidates-v2'
MANAGED_COLUMNS = ['static_cli_present', 'static_log_cli_declared_type_refs', 'static_log_cli_declared_methods', 'static_cli_measurement_unavailable']
CATEGORY_COLUMNS = ['dynamic_executable_named_create_observed', 'dynamic_autorun_location_observed']
CONTRACTS = {
    'targets': (semantic.previous.STATIC_COLUMNS, semantic.DYNAMIC_COLUMNS),
    'entropy': (semantic.STATIC_COLUMNS, semantic.DYNAMIC_COLUMNS),
    'managed': (semantic.STATIC_COLUMNS + MANAGED_COLUMNS, semantic.DYNAMIC_COLUMNS),
    'categories': (semantic.STATIC_COLUMNS + MANAGED_COLUMNS, semantic.DYNAMIC_COLUMNS + CATEGORY_COLUMNS),
}
EXTRACTOR_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
DEPENDENCIES = {'native_features_semantic.py': semantic.EXTRACTOR_SHA256,
                **semantic.DEPENDENCIES, 'managed_metadata.py': managed_metadata.EXTRACTOR_SHA256}
InputError = semantic.InputError


def columns(view):
    return list(CONTRACTS[view][0]) + list(CONTRACTS[view][1])


def target_features(payload):
    # Keep the historical semantic extractor immutable. Its mandatory entropy
    # measurement is not a dependency of these seven static/six runtime inputs.
    checked = semantic.previous.project(payload)
    events = semantic.attributed_events(payload, checked)
    dns = semantic.targets(events['dns'], 'query', dns=True)
    files = semantic.targets(events['file_drops'], 'target_filename')
    registry = semantic.targets(events['registry'], 'target_object')
    values = {k: checked['features'][k] for k in semantic.previous.STATIC_COLUMNS}
    values.update(dict(zip(semantic.DYNAMIC_COLUMNS, [
        checked['features']['dynamic_log_child_process_count'],
        checked['features']['dynamic_log_network_count'], math.log1p(len(dns)),
        math.log1p(len(files)), math.log1p(len(registry)),
        float(any(ntpath.splitext(p)[1] in semantic.ARCHIVE_SUFFIXES for p in files))])))
    return values


def extract(payload, view='targets'):
    require = semantic.previous.legacy.require
    require(view in CONTRACTS, 'INPUT_SCHEMA_MISMATCH', 'Unknown release feature view.')
    values = target_features(payload)
    if view != 'targets':
        sections = [s for s in payload['static']['report']['sections']
                    if s['executable'] and s['raw_size'] > 0]
        total = sum(s['raw_size'] for s in sections)
        require(total > 0, 'UNDEFINED_EXECUTABLE_ENTROPY',
                'No measured executable-section bytes; this feature view is unsupported.')
        values['static_executable_section_weighted_entropy'] = sum(
            s['entropy'] * s['raw_size'] for s in sections) / total
    if view in ('managed','categories'):
        record = payload['static']['report'].get('managed_metadata') or {}
        require(record.get('schema_version') == managed_metadata.SCHEMA and record.get('status') in ('complete','unavailable')
            and record.get('extractor_sha256') == managed_metadata.EXTRACTOR_SHA256
            and record.get('sha256') == payload['sha256'],
            'MANAGED_METADATA_UNAVAILABLE', 'Managed metadata is missing, incompatible or not hash-bound.')
        counts = [record.get('type_ref_rows'), record.get('method_def_rows')]
        if record['status']=='unavailable':
            require(record.get('present') is None and counts==[None,None] and
                    isinstance(record.get('reason'),str) and 0<len(record['reason'])<=128,
                    'MANAGED_METADATA_UNAVAILABLE', 'Unrecognized supplemental measurement failure.')
            # These remain null in evidence. Only a training-fold-fitted median
            # imputer may transform them; the explicit unknown flag stays one.
            values.update(zip(MANAGED_COLUMNS,[None,None,None,1.0]))
        else:
            require(type(record.get('present')) is bool and all(type(x) is int and 0 <= x <= 25*1024**2 for x in counts),
                    'MANAGED_METADATA_UNAVAILABLE', 'Invalid declared metadata counts.')
            require(record['present'] or counts == [0,0], 'MANAGED_METADATA_UNAVAILABLE', 'Inconsistent absent CLI metadata.')
            values.update(zip(MANAGED_COLUMNS,[float(record['present']), *[math.log1p(x) for x in counts],0.0]))
    if view == 'categories':
        events = semantic.attributed_events(payload)
        files = semantic.targets(events['file_drops'],'target_filename')
        registry = semantic.targets(events['registry'],'target_object')
        values[CATEGORY_COLUMNS[0]] = float(any(ntpath.splitext(p)[1] in {'.exe','.dll','.sys','.scr'} for p in files))
        locations = ('\\software\\microsoft\\windows\\currentversion\\run',
                     '\\software\\microsoft\\windows\\currentversion\\runonce')
        values[CATEGORY_COLUMNS[1]] = float(any(p.endswith(k) or k+'\\' in p for p in registry for k in locations))
    return {key: values[key] for key in columns(view)}
