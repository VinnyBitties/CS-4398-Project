"""Exercise the public CLI workflow and a real prediction server process."""
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from config import FEATURE_SCHEMA_VERSION


class EndToEndTests(unittest.TestCase):
    def test_generated_reports_to_saved_models_to_http(self):
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(prefix='sentinel-e2e-') as directory:
            root = Path(directory)

            def run(script, *args):
                result = subprocess.run(
                    [sys.executable, '-B', str(scripts / script), *map(str, args)],
                    cwd=root, capture_output=True, text=True, timeout=60,
                )
                self.assertEqual(result.returncode, 0, f'{script}\n{result.stdout}\n{result.stderr}')
                return result.stdout

            run('synthetic_reports.py', '--count', '300', '--seed', '42')
            run('build_dataset.py', '--out', 'data/records.json')
            run('split_dataset.py', '--data', 'data/records.json', '--seed', '42')
            classifier = root / 'models' / 'classifier.joblib'
            anomaly = root / 'models' / 'anomaly.joblib'
            run('train_classifier.py', '--data', 'data/splits/train.json',
                '--model-out', classifier, '--trees', '10')
            run('train_anomaly.py', '--data', 'data/splits/train_benign.json', '--model-out', anomaly)
            run('tune_threshold.py', '--validation-data', 'data/splits/validation.json',
                '--model', classifier, '--out', 'models/threshold.json')
            threshold = json.loads((root / 'models/threshold.json').read_text())['threshold']
            metrics = json.loads(run('evaluate.py', '--data', 'data/splits/test.json',
                                     '--model', classifier, '--model-type', 'classifier',
                                     '--threshold', threshold))
            self.assertEqual(metrics['threshold'], threshold)
            self.assertEqual(sum(sum(row) for row in metrics['confusion_matrix']), 60)
            anomaly_metrics = json.loads(run('evaluate.py', '--data', 'data/splits/test.json',
                                             '--model', anomaly, '--model-type', 'anomaly'))
            self.assertEqual(anomaly_metrics['anomaly_count'] + anomaly_metrics['known_count'], 60)
            records = json.loads((root / 'data/splits/test.json').read_text())
            report = records[0]['report']
            report_path = root / 'held_out_report.json'
            report_path.write_text(json.dumps(report))
            model_args = ['--classifier-model', str(classifier), '--anomaly-model', str(anomaly),
                          '--threshold', str(threshold)]
            expected = json.loads(run('predict.py', '--file', report_path, *model_args))

            # Let the OS choose the port; read the flushed startup message rather
            # than reserving/releasing a port that another process could claim.
            log_path = root / 'server.log'
            with log_path.open('w', encoding='utf-8') as log:
                process = subprocess.Popen(
                    [sys.executable, '-B', str(scripts / 'predict.py'), '--serve',
                     '--host', '127.0.0.1', '--port', '0', *model_args],
                    cwd=root, stdout=log, stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                )
                try:
                    deadline = time.monotonic() + 30
                    base_url = None
                    while time.monotonic() < deadline:
                        contents = log_path.read_text(encoding='utf-8')
                        match = re.search(r'Listening on (http://127\.0\.0\.1:\d+)', contents)
                        if match:
                            base_url = match.group(1)
                            break
                        if process.poll() is not None:
                            self.fail(f'Server exited before startup:\n{contents}')
                        time.sleep(.1)
                    self.assertIsNotNone(base_url, log_path.read_text(encoding='utf-8'))
                    with urlopen(base_url + '/health', timeout=5) as response:
                        health = json.loads(response.read())
                    self.assertEqual(health['status'], 'ok')
                    self.assertEqual(health['threshold'], threshold)
                    self.assertEqual(health['feature_schema_version'], FEATURE_SCHEMA_VERSION)
                    for name, artifact in (('classifier', classifier), ('anomaly', anomaly)):
                        info = health['models'][name]
                        self.assertTrue(info['loaded'])
                        self.assertTrue(info['schema_verified'])
                        self.assertEqual(info['version'], 'sha256:' + hashlib.sha256(artifact.read_bytes()).hexdigest())
                    request = Request(base_url + '/analyze', data=json.dumps(report).encode(),
                                      headers={'Content-Type': 'application/json'})
                    with urlopen(request, timeout=5) as response:
                        actual = json.loads(response.read())
                    self.assertEqual(actual, expected)
                    self.assertEqual(actual['prediction_source'], 'trained_model')
                    self.assertEqual(actual['anomaly_source'], 'trained_model')
                    self.assertEqual(actual['malicious'], actual['classifier_probability'] >= threshold)
                    self.assertIn('anomaly_score', actual)

                    # A running trained service must still reject missing evidence.
                    for count in report['summary']:
                        report['summary'][count] = 0
                    for events in ('processes', 'network', 'dns', 'file_drops', 'registry', 'remote_threads'):
                        report[events] = []
                    request = Request(base_url + '/analyze', data=json.dumps(report).encode(),
                                      headers={'Content-Type': 'application/json'})
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(request, timeout=5)
                    with caught.exception as response:
                        self.assertEqual(response.code, 400)
                        error = json.loads(response.read())
                    self.assertIn('NO_TELEMETRY', error['error'])
                    self.assertNotIn('risk_score', error)
                finally:
                    if process.poll() is None:
                        process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
