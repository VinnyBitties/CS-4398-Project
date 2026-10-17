import copy
import json
import unittest
from pathlib import Path
from report_parser import extract_features, analyze_report

class SandboxTests(unittest.TestCase):
    def setUp(self):
        self.report = json.loads(Path(__file__).with_name('sandbox_example.json').read_text())

    def test_documented_counts(self):
        self.assertEqual(extract_features(self.report), {
            'num_processes_created': 3, 'num_files_written': 4,
            'num_registry_keys_set': 12, 'num_network_connections': 1,
            'num_dns_requests': 2, 'num_signatures_matched': 0,
            'max_signature_severity': 0, 'has_persistence_signature': 0,
            'has_network_signature': 1})
        self.assertEqual(analyze_report(self.report).features, extract_features(self.report))

    def test_valid_zero_activity(self):
        for key in self.report['summary']:
            self.report['summary'][key] = 0
        for key in ('processes','network','dns','file_drops','registry','remote_threads'):
            self.report[key] = []
        self.assertTrue(all(v == 0 for v in extract_features(self.report).values()))

    def test_missing_counts(self):
        for key in self.report['summary']:
            with self.subTest(key=key):
                report = copy.deepcopy(self.report)
                del report['summary'][key]
                with self.assertRaisesRegex(ValueError, key):
                    extract_features(report)

    def test_invalid_counts(self):
        for value in (-1, True, '3', 3.5, None):
            with self.subTest(value=value):
                self.report['summary']['processes_created'] = value
                with self.assertRaises(ValueError):
                    extract_features(self.report)

    def test_invalid_event_arrays(self):
        for key in ('processes','network','dns','file_drops','registry','remote_threads'):
            for value in (None, {}, ['bad event']):
                with self.subTest(key=key,value=value):
                    report = copy.deepcopy(self.report)
                    report[key] = value
                    with self.assertRaisesRegex(ValueError, key):
                        extract_features(report)

    def test_missing_event_arrays(self):
        for key in ('processes','network','dns','file_drops','registry','remote_threads'):
            report = copy.deepcopy(self.report)
            del report[key]
            with self.assertRaisesRegex(ValueError, key):
                extract_features(report)

    def test_dns_is_not_a_connection(self):
        self.report['summary']['network_connections'] = 0
        self.report['network'] = []
        self.assertEqual(extract_features(self.report)['num_network_connections'],0)
        self.assertEqual(extract_features(self.report)['num_dns_requests'],2)

    def test_existing_format(self):
        report = {'behavior': {'summary': {'processes_created':3,'num_files_written':4,'num_registry_keys_set':12}},
                  'network': {'hosts':['host'], 'dns':[{},{}]},
                  'signatures':[{'name':'persistence','severity':3}]}
        features = extract_features(report)
        self.assertEqual(features['num_processes_created'],3)
        self.assertEqual(features['num_signatures_matched'],1)
        self.assertEqual(features['has_persistence_signature'],1)

    def test_invalid_root(self):
        for report in ({}, [], None, {'error':'sandbox unavailable'}):
            with self.assertRaises(ValueError):
                extract_features(report)

    def test_invalid_signatures(self):
        self.report['signatures'] = ['invalid']
        with self.assertRaisesRegex(ValueError,'signatures'):
            extract_features(self.report)

    def test_input_not_mutated(self):
        original = copy.deepcopy(self.report)
        extract_features(self.report)
        self.assertEqual(original,self.report)

if __name__ == '__main__':
    unittest.main()
