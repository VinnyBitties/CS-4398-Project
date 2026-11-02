import copy
import json
import threading
import unittest
from urllib.request import Request, urlopen
from pathlib import Path
from report_parser import extract_features, analyze_report
from predict import create_server, predict_report

# Verifies report parsing, feature extraction, validation, and input immutability.

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

    def test_run_and_runonce_registry_paths_without_signatures(self):
        report = copy.deepcopy(self.report)
        report["signatures"] = []
        report["registry"] = [
            {"path": r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run"},
            {"key_path": r"HKCU\Software\Microsoft\Windows\CurrentVersion\RunOnce"},
        ]
        analysis = analyze_report(report)
        self.assertEqual(analysis.features["has_persistence_signature"], 1)
        self.assertTrue(any("registry persistence path" in item for item in analysis.evidence))
        self.assertTrue(any("RunOnce" in item for item in analysis.evidence))

    def test_scheduled_task_command_is_persistence_but_ordinary_process_is_not(self):
        scheduled = copy.deepcopy(self.report)
        scheduled["signatures"] = []
        scheduled["processes"] = [{"command_line": "schtasks.exe /Create /SC ONLOGON /TN updater"}]
        ordinary = copy.deepcopy(self.report)
        ordinary["signatures"] = []
        ordinary["processes"] = [{"command_line": "example.exe --scan"}]

        scheduled_analysis = analyze_report(scheduled)
        ordinary_analysis = analyze_report(ordinary)
        self.assertEqual(scheduled_analysis.features["has_persistence_signature"], 1)
        self.assertTrue(any("scheduled-task command" in item for item in scheduled_analysis.evidence))
        self.assertEqual(ordinary_analysis.features["has_persistence_signature"], 0)

    def test_missing_telemetry_is_an_error(self):
        report = copy.deepcopy(self.report)
        del report["registry"]
        with self.assertRaisesRegex(ValueError, "registry"):
            analyze_report(report)

    def test_cli_and_http_predictions_match_for_same_model(self):
        class FakeClassifier:
            classes_ = [0, 1]

            def predict(self, features):
                return [1]

            def predict_proba(self, features):
                return [[0.1, 0.9]]

        model = FakeClassifier()
        expected = predict_report(self.report, threshold=0.8, classifier=model)
        server = create_server("127.0.0.1", 0, threshold=0.8, classifier=model)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = Request(
                f"http://127.0.0.1:{server.server_port}/analyze",
                data=json.dumps(self.report).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request) as response:
                actual = json.loads(response.read())
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

        self.assertEqual(actual, expected)

if __name__ == '__main__':
    unittest.main()
